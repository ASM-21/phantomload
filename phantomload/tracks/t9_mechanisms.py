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
            "no detectable common shock, with power to see one of SD 0.05 or more. "
            "Partial delivery is sticky within a utility and does not move with "
            "its footprint, which reads as a stable property of each program, "
            "whether definition, protocol or consistent partial performance, "
            "rather than as system conditions deciding how much gets called"
            if not t["common_shocks_detected"] and detectable
            else "inconclusive"
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
    }


def run() -> dict:
    return {
        "footprint_split": footprint_split().reset_index(names="footprint"),
        "decomposition": decomposition(),
        "size_gradient": size_gradient().reset_index(),
        "power_check": power_check(),
        "summary": summary(),
    }
