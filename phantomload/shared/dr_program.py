"""Shared program registry. Every track reads through this module.

The registry has one row per (entity, year, program_type). Real DR data at that
granularity is not public: EIA-861's published aggregates are by sector, not by
program type, and per-program dispatch logs live in utility evaluation reports
behind PUC portals. So the schema supports the program-level record the analysis
wants, and the loader fills it at the granularity the data actually has, with
`granularity` and `provenance` on every row saying which.

Rule enforced here rather than in prose: a record cannot claim MEASURED
provenance unless it came from a vendored source file. Simulated records are
constructed through `synthetic_program` and are stamped SIMULATED at birth, so
no downstream table can quietly present them as measurement.
"""

from __future__ import annotations

import dataclasses
import enum
import functools
import pathlib

import pandas as pd

DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data"
EIA_PANEL = DATA_DIR / "eia861_dr_national.csv"

SECTORS = ("residential", "commercial", "industrial", "transportation")


class Provenance(str, enum.Enum):
    """Where a number came from. Carried on every record and every result row."""

    MEASURED = "measured"          # transcribed from a published data source
    LITERATURE = "literature"      # a published parameter, cited
    ASSUMPTION = "assumption"      # a stated assumption, range-swept, not cited
    SIMULATED = "simulated"        # produced by a model in this repo
    IDENTITY = "identity"          # true by definition, not an empirical finding


class ProgramType(str, enum.Enum):
    DIRECT_LOAD_CONTROL = "direct_load_control"
    PRICE_BASED = "price_based"
    CAPACITY_MARKET = "capacity_market"
    UNKNOWN = "unknown"            # EIA aggregates do not split by program type


@dataclasses.dataclass(frozen=True)
class ProgramYear:
    """One program, one year.

    enrolled_mw   EIA calls this "potential peak demand savings": the peak
                  reduction the program is reported as being able to deliver.
    verified_mw   EIA calls this "actual peak demand savings": the reduction
                  actually realised in that year.
    dispatch_events / event_hours are None wherever the source does not report
    them, which for every real row in this repo is everywhere. They are not
    imputed. Track 1 explains why that gap is the whole problem.
    """

    entity: str
    year: int
    sector: str
    program_type: ProgramType
    enrolled_mw: float | None
    verified_mw: float | None
    energy_savings_mwh: float | None
    customers: float | None
    incentive_cost_kusd: float | None
    other_cost_kusd: float | None
    dispatch_events: int | None
    event_hours: float | None
    provenance: Provenance
    granularity: str
    note: str = ""

    @property
    def total_cost_kusd(self) -> float | None:
        if self.incentive_cost_kusd is None or self.other_cost_kusd is None:
            return None
        return self.incentive_cost_kusd + self.other_cost_kusd

    @property
    def utilization(self) -> float | None:
        """verified / enrolled. See track 1 for what this ratio does and does
        not identify. It is NOT "fraction of capacity that works"."""
        if not self.enrolled_mw or self.verified_mw is None:
            return None
        return self.verified_mw / self.enrolled_mw


@functools.lru_cache(maxsize=1)
def load_eia_panel() -> pd.DataFrame:
    """Wide panel: index (year, sector), one column per published metric."""
    if not EIA_PANEL.exists():
        raise FileNotFoundError(
            f"{EIA_PANEL} missing. Run tools/build_eia861_panel.py to regenerate it."
        )
    long = pd.read_csv(EIA_PANEL)
    wide = long.pivot_table(index=["year", "sector"], columns="metric", values="value")
    wide.columns.name = None
    # pivot_table drops groups that are entirely blank, e.g. transportation in
    # years where EIA prints "--" for every metric. Reindexing over the full
    # grid keeps them as NaN rows so downstream code sees a missing value
    # rather than a missing key.
    full = pd.MultiIndex.from_product(
        [sorted(long.year.unique()), list(SECTORS) + ["total"]],
        names=["year", "sector"],
    )
    return wide.reindex(full).sort_index()


def registry(include_total: bool = False) -> list[ProgramYear]:
    """Every EIA row as a ProgramYear. Sector rows only unless include_total."""
    wide = load_eia_panel()
    out: list[ProgramYear] = []
    for (year, sector), row in wide.iterrows():
        if sector == "total" and not include_total:
            continue

        def get(col: str) -> float | None:
            v = row.get(col)
            return None if pd.isna(v) else float(v)

        out.append(
            ProgramYear(
                entity="US",
                year=int(year),
                sector=str(sector),
                program_type=ProgramType.UNKNOWN,
                enrolled_mw=get("potential_peak_mw"),
                verified_mw=get("actual_peak_mw"),
                energy_savings_mwh=get("energy_savings_mwh"),
                customers=get("customers_enrolled"),
                incentive_cost_kusd=get("customer_incentives_kusd"),
                other_cost_kusd=get("other_costs_kusd"),
                dispatch_events=None,
                event_hours=None,
                provenance=Provenance.MEASURED,
                granularity="national_by_sector",
                note="EIA-861 via Electric Power Annual tables 10.3/10.4/10.8",
            )
        )
    return out


def to_frame(programs: list[ProgramYear]) -> pd.DataFrame:
    df = pd.DataFrame([dataclasses.asdict(p) for p in programs])
    if df.empty:
        return df
    df["program_type"] = df["program_type"].map(lambda v: getattr(v, "value", v))
    df["provenance"] = df["provenance"].map(lambda v: getattr(v, "value", v))
    df["total_cost_kusd"] = df["incentive_cost_kusd"] + df["other_cost_kusd"]
    df["utilization"] = df["verified_mw"] / df["enrolled_mw"]
    return df


def synthetic_program(**kwargs) -> ProgramYear:
    """Build a modelled program. Provenance is forced to SIMULATED.

    Tracks 3 and 5 have no real per-program data and construct their populations
    here, so a simulated row can never be mistaken for a measured one downstream.
    """
    kwargs.pop("provenance", None)
    kwargs.setdefault("entity", "synthetic")
    kwargs.setdefault("granularity", "program")
    kwargs.setdefault("energy_savings_mwh", None)
    kwargs.setdefault("customers", None)
    kwargs.setdefault("incentive_cost_kusd", None)
    kwargs.setdefault("other_cost_kusd", None)
    kwargs.setdefault("dispatch_events", None)
    kwargs.setdefault("event_hours", None)
    return ProgramYear(provenance=Provenance.SIMULATED, **kwargs)
