"""Track 9. The gap is not one thing. What produces each part of it.

MEASURED, EIA-861 utility files 2016 to 2018, with balancing-authority codes
from 2017 and 2018 carried back to 2016 by utility, which is valid because a
utility's balancing authority does not change year to year.

Track 1 showed the zero mass rotates between years, which reads as capacity
available and not called. That covers 10% to 18% of enrolled capacity. It says
nothing about the largest piece of the gap, utilities that delivered some of
their potential but not all, and nothing about why zeros arise. This track tests
two candidate mechanisms and reports what each test can and cannot see.

1. WHOLESALE ACCOUNTING. If zero or missing actuals reflected reductions booked
   in an RTO's wholesale settlement rather than the retail filing, they would
   concentrate inside RTO footprints. Test: compare the share of capacity at
   zero or unreported inside and outside the seven RTO and ISO footprints.

2. SYSTEM-DRIVEN DISPATCH. If partial delivery reflected how hard each year's
   system conditions pushed utilities to call their programs, utilization would
   move together across utilities in the same footprint in the same year. Test:
   share of within-utility year-to-year variance explained by footprint-by-year
   common shocks, against a permutation null, with an explicit power check so a
   null result is not mistaken for evidence of absence.
"""

from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from ..shared.dr_program import Provenance
from . import t1_utilization as t1

RTO_FOOTPRINTS = frozenset({"MISO", "SWPP", "PJM", "ERCO", "NYIS", "ISNE", "CISO"})
MIN_UTILITIES_PER_FOOTPRINT = 5
PERMUTATIONS = 2_000
POWER_TRIALS = 200
POWER_SHOCKS = (0.01, 0.02, 0.03, 0.05)
SEED = 20260920


def panel() -> pd.DataFrame:
    df = t1.utility_panel()
    df = df[df.potential_peak_mw > 0].copy()
    ba = (
        df[df.ba_code.notna()]
        .groupby("key")
        .ba_code.agg(lambda s: s.mode().iloc[0])
    )
    df["ba"] = df.key.map(ba)
    df["in_rto"] = df.ba.isin(RTO_FOOTPRINTS)
    df["utilization"] = df.actual_peak_mw / df.potential_peak_mw
    return df


# --- mechanism 1: wholesale accounting --------------------------------------
def footprint_split() -> pd.DataFrame:
    df = panel().dropna(subset=["ba"])
    out = df.pivot_table(
        index="in_rto", columns="status", values="potential_peak_mw", aggfunc="sum"
    )
    out = out.div(out.sum(axis=1), axis=0)
    out.index = out.index.map({True: "inside RTO", False: "outside RTO"})
    out["zero_or_unreported"] = out.get("exact_zero", 0) + out.get("not_reported", 0)
    return out.assign(provenance=Provenance.MEASURED.value)


def wholesale_accounting_test() -> dict:
    df = panel().dropna(subset=["ba"])
    rto_share_all = df[df.in_rto].potential_peak_mw.sum() / df.potential_peak_mw.sum()
    by_status = {
        status: float(
            g[g.in_rto].potential_peak_mw.sum() / g.potential_peak_mw.sum()
        )
        for status, g in df.groupby("status")
    }
    split = footprint_split()
    inside = float(split.loc["inside RTO", "zero_or_unreported"])
    outside = float(split.loc["outside RTO", "zero_or_unreported"])
    return {
        "ba_coverage": float(panel().ba.notna().mean()),
        "rto_share_of_all_potential": float(rto_share_all),
        "rto_share_of_exact_zero": by_status.get("exact_zero"),
        "rto_share_of_not_reported": by_status.get("not_reported"),
        "zero_or_unreported_inside_rto": inside,
        "zero_or_unreported_outside_rto": outside,
        "outside_over_inside": outside / inside,
        "hypothesis_predicts": "concentration inside RTO footprints",
        "observed": "concentration outside RTO footprints",
        "wholesale_accounting_refuted_as_general_explanation": bool(
            by_status.get("exact_zero", 1) < rto_share_all
            and by_status.get("not_reported", 1) < rto_share_all
        ),
        "consistent_with": (
            "utilities outside organised markets deciding for themselves whether "
            "to call, and not calling when long on capacity, the mechanism Nadel "
            "proposed in 2017. Consistent with, not shown: reserve margins by "
            "utility would be needed to test it"
        ),
    }


# --- mechanism 2: system-driven dispatch ------------------------------------
def partial_delivery_panel_unfiltered() -> pd.DataFrame:
    """Positive in every year, known footprint; no footprint-size filter yet."""
    df = panel().dropna(subset=["ba"])
    df = df[df.actual_peak_mw > 0]
    years = df.groupby("key").year.nunique()
    df = df[df.key.isin(years[years == df.year.nunique()].index)].copy()
    df["utilization"] = df.utilization.clip(upper=1.5)
    return df


def partial_delivery_panel() -> pd.DataFrame:
    df = panel().dropna(subset=["ba"])
    df = df[df.actual_peak_mw > 0]
    years = df.groupby("key").year.nunique()
    df = df[df.key.isin(years[years == df.year.nunique()].index)]
    sizes = df.groupby("ba").key.nunique()
    df = df[df.ba.isin(sizes[sizes >= MIN_UTILITIES_PER_FOOTPRINT].index)].copy()
    # a handful of utilities report actual above potential; cap so one filing
    # quirk cannot dominate a variance decomposition
    df["utilization"] = df.utilization.clip(upper=1.5)
    return df


class _Encoded:
    """Integer-coded panel for fast permutation tests.

    The within-utility deviation does not depend on footprint labels, so it is
    computed once. A permutation only reassigns which footprint each utility
    belongs to, which changes the grouping of a fixed vector, and grouped means
    of a fixed vector are a pair of bincounts. That turns each permutation from a
    pandas groupby into a few microseconds of numpy, which matters because the
    power check runs tens of thousands of them and the claims guard runs it in
    every sandbox test.
    """

    def __init__(self, df: pd.DataFrame):
        self.key = pd.factorize(df.key)[0]
        self.year = pd.factorize(df.year)[0]
        self.n_years = int(self.year.max()) + 1
        per_key_ba = df.drop_duplicates("key").set_index("key").ba
        key_codes = pd.factorize(df.key)[1]
        self.ba_of_key = pd.factorize(per_key_ba.reindex(key_codes))[0]
        self.n_ba = int(self.ba_of_key.max()) + 1
        self.u = df.utilization.to_numpy(dtype=float)

    def share(self, u: np.ndarray, ba_of_key: np.ndarray) -> float:
        n_k = np.bincount(self.key)
        dev = u - (np.bincount(self.key, u) / n_k)[self.key]
        group = ba_of_key[self.key] * self.n_years + self.year
        n_g = np.bincount(group)
        common = (np.bincount(group, dev) / np.where(n_g == 0, 1, n_g))[group]
        return float(1 - ((dev - common) ** 2).sum() / (dev**2).sum())


def _common_shock_share(df: pd.DataFrame) -> float:
    enc = _Encoded(df)
    return enc.share(enc.u, enc.ba_of_key)


def _permutation_p(
    enc: _Encoded, u: np.ndarray, rng: np.random.Generator, n: int
) -> tuple[float, np.ndarray]:
    real = enc.share(u, enc.ba_of_key)
    null = np.array([enc.share(u, rng.permutation(enc.ba_of_key)) for _ in range(n)])
    return float((null >= real).mean()), null


@functools.lru_cache(maxsize=1)
def common_shock_test() -> dict:
    df = partial_delivery_panel()
    rng = np.random.default_rng(SEED)
    enc = _Encoded(df)
    p, null = _permutation_p(enc, enc.u, rng, PERMUTATIONS)
    return {
        "utilities": int(df.key.nunique()),
        "footprints": int(df.ba.nunique()),
        "years": int(df.year.nunique()),
        "share_explained_by_common_shocks": _common_shock_share(df),
        "permutation_null_mean": float(null.mean()),
        "permutation_null_p95": float(np.percentile(null, 95)),
        "p_value": p,
        "within_utility_sd": float(df.groupby("key").utilization.std().mean()),
        "common_shocks_detected": bool(p < 0.05),
    }


@functools.lru_cache(maxsize=1)
def power_check() -> pd.DataFrame:
    """Inject a known footprint-by-year shock and count how often the test sees
    it. Without this, a null result says nothing: a test that cannot detect the
    effect returns null whether or not the effect is there."""
    df = partial_delivery_panel()
    rng = np.random.default_rng(SEED + 1)
    enc = _Encoded(df)
    true_group = enc.ba_of_key[enc.key] * enc.n_years + enc.year
    n_groups = enc.n_ba * enc.n_years
    rows = []
    for sd in POWER_SHOCKS:
        hits = 0
        for _ in range(POWER_TRIALS):
            shock = rng.normal(0, sd, n_groups)
            injected = enc.u + shock[true_group]
            p, _ = _permutation_p(enc, injected, rng, 200)
            hits += p < 0.05
        rows.append(
            {
                "injected_shock_sd": sd,
                "detection_rate": hits / POWER_TRIALS,
                "provenance": Provenance.SIMULATED.value,
            }
        )
    return pd.DataFrame(rows)


# --- reports that carry no measurement ---------------------------------------
# Nearly a third of positive reports set actual exactly equal to potential, and
# many utilities do it every year. A program whose delivered figure is its
# enrolled figure, three years running, is recording a contract or copying a
# field, not measuring a response. Those reports matter twice over. They
# manufacture the small-program end of the size gradient, because small
# programs do it far more often. And they bias the common-shock test toward a
# null, because an observation fixed at 1.0 every year adds no variance and
# pulls every regional average toward zero.


def exact_equality() -> dict:
    df = panel()
    pos = df[df.status == "positive"].copy()
    pos["exact_full"] = np.isclose(pos.actual_peak_mw, pos.potential_peak_mw)
    pos["size_band"] = pd.qcut(
        pos.potential_peak_mw.rank(method="first"), 4,
        labels=["smallest", "second", "third", "largest"],
    )
    by_band = pos.groupby("size_band", observed=True).exact_full.mean()
    habit = pos.groupby("key").exact_full.agg(["sum", "count"])
    habit = habit[habit["count"] == pos.year.nunique()]
    return {
        "share_of_positive_reports": float(pos.exact_full.mean()),
        "share_of_positive_capacity": float(
            pos[pos.exact_full].potential_peak_mw.sum() / pos.potential_peak_mw.sum()
        ),
        "smallest_quarter_share": float(by_band.iloc[0]),
        "largest_quarter_share": float(by_band.iloc[-1]),
        "utilities_positive_every_year": int(len(habit)),
        "exact_every_year": int((habit["sum"] == habit["count"]).sum()),
        "never_exact": int((habit["sum"] == 0).sum()),
    }


def size_gradient_measured_only() -> dict:
    """The size gradient on reports that carry a measurement."""
    from scipy import stats

    df = panel()
    pos = df[(df.status == "positive")].copy()
    pos = pos[~np.isclose(pos.actual_peak_mw, pos.potential_peak_mw)]
    per = pos.groupby("key").agg(size=("potential_peak_mw", "mean"), u=("utilization", "mean"))
    rho, pval = stats.spearmanr(per["size"], per.u)
    med = pos.groupby(
        pd.qcut(pos.potential_peak_mw.rank(method="first"), 4, labels=[1, 2, 3, 4]),
        observed=True,
    ).utilization.median()
    reported = df[df.status != "not_reported"]
    measured = reported[
        ~(np.isclose(reported.actual_peak_mw, reported.potential_peak_mw)
          & (reported.actual_peak_mw > 0))
    ]
    return {
        "utilities": int(len(per)),
        "median_utility_measured": float(measured.utilization.median()),
        "median_utility_raw": float(reported.utilization.median()),
        "rho": float(rho),
        "p": float(pval),
        "smallest_quarter_median": float(med.iloc[0]),
        "largest_quarter_median": float(med.iloc[-1]),
    }


CLASS_PANEL = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "data"
    / "eia861_dr_utility_class_2016_2018.csv"
)


def class_gradient() -> pd.DataFrame:
    """The size gradient within each customer class, raw and on measured reports.

    If large programs realised less because they are disproportionately
    industrial interruptible contracts, the gradient would vanish within class.
    It does not vanish within class on raw reports. It vanishes on measured
    reports, in every class, which places the gradient on the copied-report
    convention rather than on class mix or on program size.
    """
    from scipy import stats

    raw = pd.read_csv(CLASS_PANEL, dtype={"utility_number": str})
    raw["key"] = raw.utility_number + "_" + raw.state
    g = (
        raw.groupby(["year", "key", "customer_class"])[["potential_peak_mw", "actual_peak_mw"]]
        .sum(min_count=1)
        .reset_index()
    )
    g = g[(g.potential_peak_mw > 0) & g.actual_peak_mw.notna()].copy()
    g["u"] = g.actual_peak_mw / g.potential_peak_mw
    g["copied"] = np.isclose(g.actual_peak_mw, g.potential_peak_mw) & (g.actual_peak_mw > 0)
    rows = []
    for cls, x in g.groupby("customer_class"):
        if x.key.nunique() < 40:
            continue
        for basis, sub in (("raw", x), ("measured", x[~x.copied])):
            per = sub.groupby("key").agg(size=("potential_peak_mw", "mean"), u=("u", "mean"))
            rho, pval = stats.spearmanr(per["size"], per.u)
            rows.append(
                {
                    "customer_class": cls,
                    "basis": basis,
                    "utilities": int(len(per)),
                    "rho": float(rho),
                    "p_value": float(pval),
                    "copied_share": float(x.copied.mean()),
                    "provenance": Provenance.MEASURED.value,
                }
            )
    return pd.DataFrame(rows)


def class_gradient_summary() -> dict:
    cg = class_gradient()
    raw = cg[cg.basis == "raw"]
    meas = cg[cg.basis == "measured"]
    return {
        "classes": int(raw.customer_class.nunique()),
        "raw_significant_in_every_class": bool((raw.p_value < 0.05).all()),
        "measured_significant_in_any_class": bool((meas.p_value < 0.05).any()),
        "measured_rho_max_abs": float(meas.rho.abs().max()),
        "raw_rho_min_abs": float(raw.rho.abs().min()),
    }


SPEC_FILTERS = ("all", "drop_always_exact", "drop_ever_exact")
SPEC_MIN_FOOTPRINT = (3, 5, 8)


@functools.lru_cache(maxsize=1)
def specification_grid() -> pd.DataFrame:
    """The common-shock test under every combination of the two choices it rests
    on: which reports to include, and how many utilities a footprint needs."""
    base = partial_delivery_panel_unfiltered()
    base["exact_full"] = np.isclose(base.actual_peak_mw, base.potential_peak_mw)
    ever = base.groupby("key").exact_full.any()
    always = base.groupby("key").exact_full.all()
    subsets = {
        "all": base,
        "drop_always_exact": base[~base.key.map(always)],
        "drop_ever_exact": base[~base.key.map(ever)],
    }
    rows = []
    for name in SPEC_FILTERS:
        for min_fp in SPEC_MIN_FOOTPRINT:
            sub = subsets[name]
            sizes = sub.groupby("ba").key.nunique()
            sub = sub[sub.ba.isin(sizes[sizes >= min_fp].index)]
            enc = _Encoded(sub)
            rng = np.random.default_rng(SEED)
            pval, null = _permutation_p(enc, enc.u, rng, PERMUTATIONS)
            rows.append(
                {
                    "filter": name,
                    "min_utilities_per_footprint": min_fp,
                    "utilities": int(sub.key.nunique()),
                    "footprints": int(sub.ba.nunique()),
                    "share_explained": enc.share(enc.u, enc.ba_of_key),
                    "null_mean": float(null.mean()),
                    "p_value": pval,
                    "provenance": Provenance.MEASURED.value,
                }
            )
    return pd.DataFrame(rows)


def specification_summary() -> dict:
    g = specification_grid()
    return {
        "specifications": int(len(g)),
        "significant": int((g.p_value < 0.05).sum()),
        "p_min": float(g.p_value.min()),
        "p_max": float(g.p_value.max()),
        "share_above_null_everywhere": bool((g.share_explained > g.null_mean).all()),
        "published_spec_p": float(
            g[(g["filter"] == "all") & (g.min_utilities_per_footprint == 5)].p_value.iloc[0]
        ),
        "verdict": "specification-dependent",
    }


def dispatch_summary() -> dict:
    t = common_shock_test()
    pw = power_check().set_index("injected_shock_sd").detection_rate
    detectable = [sd for sd, rate in pw.items() if rate >= 0.8]
    return {
        **t,
        "power_at_largest_shock": float(pw.iloc[-1]),
        "smallest_reliably_detected_sd": float(min(detectable)) if detectable else None,
        "test_is_vacuous": bool(not detectable),
        "verdict": (
            "specification-dependent. In the published specification no common "
            "shock is detectable, but the result depends on two choices made "
            "once: whether to include reports where actual simply equals "
            "potential, and how many utilities a footprint needs. Across the "
            "grid of both, the common share exceeds its null every time and is "
            "significant in some specifications and not others"
        ),
    }


# --- size --------------------------------------------------------------------
# The national ratio is capacity-weighted, so it is dominated by whatever the
# largest programs do. If utilization varied little with size that would not
# matter. It varies a great deal, so a single program's number cannot be read
# against the national figure without knowing its size.


def size_gradient() -> pd.DataFrame:
    df = panel()
    reported = df[df.status != "not_reported"].copy()
    reported["size_band"] = pd.qcut(
        reported.potential_peak_mw, 4,
        labels=["smallest quarter", "second quarter", "third quarter", "largest quarter"],
    )
    total = reported.potential_peak_mw.sum()
    out = reported.groupby("size_band", observed=True).agg(
        utility_years=("key", "size"),
        potential_mw=("potential_peak_mw", "sum"),
        median_utilization=("utilization", "median"),
        realised_mw=("actual_peak_mw", "sum"),
    )
    out["capacity_weighted_utilization"] = out.realised_mw / out.potential_mw
    out["share_of_enrolled_capacity"] = out.potential_mw / total
    out["provenance"] = Provenance.MEASURED.value
    return out.drop(columns="realised_mw")


def size_summary() -> dict:
    from scipy import stats

    df = panel()
    reported = df[df.status != "not_reported"]
    # One row per utility: averaging over years avoids counting the same
    # program three times, which would overstate the evidence threefold.
    per_utility = reported.groupby("key").agg(
        size=("potential_peak_mw", "mean"), utilization=("utilization", "mean")
    )
    rho, pval = stats.spearmanr(per_utility["size"], per_utility.utilization)
    g = size_gradient()
    by_year = reported.groupby("year").apply(
        lambda x: (x.utilization.median(), x.actual_peak_mw.sum() / x.potential_peak_mw.sum()),
        include_groups=False,
    )
    return {
        "utilities": int(len(per_utility)),
        "spearman_size_vs_utilization": float(rho),
        "spearman_p": float(pval),
        "smallest_quarter_median": float(g.median_utilization.iloc[0]),
        "largest_quarter_median": float(g.median_utilization.iloc[-1]),
        "largest_quarter_share_of_capacity": float(g.share_of_enrolled_capacity.iloc[-1]),
        "monotone_across_size": bool(g.median_utilization.is_monotonic_decreasing),
        "median_utility_utilization": float(reported.utilization.median()),
        "median_exceeds_weighted_every_year": bool(
            all(med > w for med, w in by_year)
        ),
    }


def decomposition() -> pd.DataFrame:
    """The unrealised gap, split by component, with what each is consistent with."""
    df = panel()
    rows = []
    for year, g in df.groupby("year"):
        potential = g.potential_peak_mw.sum()
        zero = g[g.status == "exact_zero"].potential_peak_mw.sum()
        unreported = g[g.status == "not_reported"].potential_peak_mw.sum()
        pos = g[g.status == "positive"]
        partial_gap = (pos.potential_peak_mw - pos.actual_peak_mw).clip(lower=0).sum()
        realised = g.actual_peak_mw.sum()
        rows.append(
            {
                "year": int(year),
                "realised": realised / potential,
                "gap_zero_mass": zero / potential,
                "gap_unreported": unreported / potential,
                "gap_partial_delivery": partial_gap / potential,
                "provenance": Provenance.MEASURED.value,
            }
        )
    return pd.DataFrame(rows)


def summary() -> dict:
    dec = decomposition()
    w = wholesale_accounting_test()
    s = dispatch_summary()
    gap = dec[["gap_zero_mass", "gap_unreported", "gap_partial_delivery"]].sum(axis=1)
    return {
        **{f"ws_{k}": v for k, v in w.items()},
        **{f"cs_{k}": v for k, v in s.items()},
        "partial_share_of_gap_min": float((dec.gap_partial_delivery / gap).min()),
        "partial_share_of_gap_max": float((dec.gap_partial_delivery / gap).max()),
        "zero_share_of_gap_min": float((dec.gap_zero_mass / gap).min()),
        "zero_share_of_gap_max": float((dec.gap_zero_mass / gap).max()),
        **{f"size_{k}": v for k, v in size_summary().items()},
        **{f"exact_{k}": v for k, v in exact_equality().items()},
        **{f"sizem_{k}": v for k, v in size_gradient_measured_only().items()},
        **{f"spec_{k}": v for k, v in specification_summary().items()},
        **{f"cls_{k}": v for k, v in class_gradient_summary().items()},
    }


def run() -> dict:
    return {
        "footprint_split": footprint_split().reset_index(names="footprint"),
        "decomposition": decomposition(),
        "size_gradient": size_gradient().reset_index(),
        "specification_grid": specification_grid(),
        "class_gradient": class_gradient(),
        "power_check": power_check(),
        "summary": summary(),
    }
