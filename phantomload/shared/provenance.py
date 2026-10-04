"""Provenance records for every quoted claim.

A digest of a file on disk says the file has not changed. It does not say which
rows a claim was computed from, and two claims reading the same file through
different filters rest on different evidence. So each claim here is tied to a
NAMED SLICE, a function returning the exact subset the claim uses after
filtering, and the digest is taken of that subset in a canonical form.

Canonical form: columns sorted by name, rows sorted by every column, written as
CSV with a fixed float format. Two slices with the same values digest the same
regardless of the order they were read in, and any change to a value that a
claim rests on changes the digest.
"""

from __future__ import annotations

import hashlib
import io
import platform
import subprocess
import sys
from collections.abc import Callable

import pandas as pd

from . import ferc
from .calibration import cone_table, lmp_table
from .dr_program import load_eia_panel


def slice_digest(df: pd.DataFrame) -> str:
    """sha256 of a canonical serialisation of a data slice.

    A NAMED index carries data (the EIA panel is indexed by year and sector)
    and is folded in as columns. An unnamed index is only row position, an
    artifact of how the slice was filtered out of its source file, and is
    dropped: otherwise two identical slices taken by different filters would
    digest differently, and the digest would track file layout rather than the
    values a claim rests on. A test pins exactly that.
    """
    named = any(n is not None for n in df.index.names)
    frame = df.reset_index() if named else df.reset_index(drop=True)
    frame = frame[sorted(frame.columns, key=str)]
    frame = frame.sort_values(list(frame.columns)).reset_index(drop=True)
    buf = io.StringIO()
    frame.to_csv(buf, index=False, float_format="%.10g", lineterminator="\n")
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def environment() -> dict:
    import numpy

    return {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": numpy.__version__,
        "platform": platform.system(),
    }


def git_state(root) -> dict:
    """Commit and dirty flag. Degrades to 'unversioned' outside a checkout
    rather than failing, because a tarball is a legitimate way to receive this."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": "unversioned", "dirty": None}


# --- named slices -----------------------------------------------------------
# Each is the exact subset a family of claims is computed from. Adding a claim
# that reads data through a filter not listed here is a gap in the ledger.

def _national_total() -> pd.DataFrame:
    p = load_eia_panel().reset_index()
    return p[p.sector == "total"][["year", "potential_peak_mw", "actual_peak_mw"]]


def _national_by_sector() -> pd.DataFrame:
    p = load_eia_panel().reset_index()
    return p[p.sector != "total"]


def _cost_years() -> pd.DataFrame:
    p = load_eia_panel().reset_index()
    return p.dropna(subset=["customer_incentives_kusd", "other_costs_kusd"])


def _utility_panel_positive() -> pd.DataFrame:
    from ..tracks import t1_utilization as t1

    up = t1.utility_panel()
    return up[up.potential_peak_mw > 0][
        ["year", "key", "potential_peak_mw", "actual_peak_mw"]
    ]


def _utility_class() -> pd.DataFrame:
    from ..tracks import t9_mechanisms as t9

    return pd.read_csv(t9.CLASS_PANEL, dtype={"utility_number": str})


def _aceee_2015() -> pd.DataFrame:
    from ..tracks import t1_utilization as t1

    return t1.utility_table()[["utility", "state", "potential_peak_mw", "actual_peak_mw"]]


def _pjm_cone_latest() -> pd.DataFrame:
    t = cone_table()
    return t[t.delivery_year == "2027/2028"]


def _pjm_lmp() -> pd.DataFrame:
    return lmp_table()


def _ferc_regional() -> pd.DataFrame:
    return ferc.regional()


def _rto() -> pd.DataFrame:
    return ferc.rto()


def _carboncast_hours() -> pd.DataFrame:
    from ..tracks import t4_curtailment as t4

    return pd.concat(
        [t4.load_region(r)[["region", "utc", "total_gen", "renewable_gen"]] for r in t4.REGIONS]
    ).assign(utc=lambda d: d.utc.astype(str))


SLICES: dict[str, Callable[[], pd.DataFrame]] = {
    "eia_national_total": _national_total,
    "eia_national_by_sector": _national_by_sector,
    "eia_cost_years": _cost_years,
    "eia_utility_2016_2018_positive": _utility_panel_positive,
    "eia_utility_class_2016_2018": _utility_class,
    "aceee_2015_28_utilities": _aceee_2015,
    "pjm_cone_2027_28": _pjm_cone_latest,
    "pjm_lmp_annual": _pjm_lmp,
    "ferc_regional": _ferc_regional,
    "ferc_rto_wholesale": _rto,
    "carboncast_hourly": _carboncast_hours,
}


def slice_records() -> dict[str, dict]:
    out = {}
    for name, fn in SLICES.items():
        df = fn()
        out[name] = {"rows": int(len(df)), "digest": slice_digest(df)}
    return out
