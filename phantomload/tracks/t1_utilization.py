"""Track 1. What fraction of enrolled DR capacity actually shows up.

MEASURED. The ratio itself comes straight from EIA-861 national aggregates,
2013-2024, four sectors. No modelling.

The important part of this track is not the ratio. It is that the ratio is not
identified. EIA reports "potential peak demand savings" (what the program is
said to be able to deliver) and "actual peak demand savings" (what was realised
that year). A program that sat idle in a mild year and a program whose enrolled
capacity would evaporate under a real call both report the same thing: a low
ratio. The published aggregates contain no dispatch-event count, so nothing in
this data separates them.

So this track computes the ratio, then computes how long a panel would have to
be before a low ratio could be read as evidence of phantom capacity rather than
of an insurance resource that was correctly not called. The answer is longer
than the panel. That is the finding.
"""

from __future__ import annotations

import functools
import itertools
import math
import pathlib

import numpy as np
import pandas as pd

from ..shared.calibration import RESERVE_RETURN_PERIOD
from ..shared import ferc
from ..shared.dr_program import SECTORS, Provenance, load_eia_panel

PANEL_YEARS = 12  # 2013-2024 inclusive
MATERIAL_WEIGHT = 0.01  # sectors below this share of enrolled MW are not ranged


def utilization_table() -> pd.DataFrame:
    """verified / enrolled by year and sector, plus the national total."""
    wide = load_eia_panel().reset_index()
    df = wide[["year", "sector", "potential_peak_mw", "actual_peak_mw"]].copy()
    df = df.rename(
        columns={"potential_peak_mw": "enrolled_mw", "actual_peak_mw": "verified_mw"}
    )
    df["utilization"] = df["verified_mw"] / df["enrolled_mw"]
    df["shortfall_mw"] = df["enrolled_mw"] - df["verified_mw"]
    df["provenance"] = Provenance.MEASURED.value
    return df.dropna(subset=["utilization"]).sort_values(["sector", "year"])


def national_summary() -> dict:
    df = utilization_table()
    nat = df[df.sector == "total"].sort_values("year")
    u = nat["utilization"].to_numpy()
    years = nat["year"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(years, u, 1)
    resid = u - (slope * years + intercept)
    ss_tot = ((u - u.mean()) ** 2).sum()
    return {
        "n_years": int(len(u)),
        "first_year": int(years.min()),
        "last_year": int(years.max()),
        "mean_utilization": float(u.mean()),
        "sd_utilization": float(u.std(ddof=1)),
        "min_utilization": float(u.min()),
        "min_year": int(years[u.argmin()]),
        "max_utilization": float(u.max()),
        "max_year": int(years[u.argmax()]),
        "shortfall_share_mean": float(1 - u.mean()),
        "trend_per_decade": float(slope * 10),
        "trend_r2": float(1 - (resid**2).sum() / ss_tot),
        "mean_shortfall_mw": float(nat["shortfall_mw"].mean()),
    }


def sector_summary() -> pd.DataFrame:
    df = utilization_table()
    df = df[df.sector.isin(SECTORS)]
    out = (
        df.groupby("sector")["utilization"]
        .agg(["mean", "std", "min", "max", "count"])
        .rename(columns={"mean": "mean_utilization"})
    )
    latest = df[df.year == df.year.max()].set_index("sector")["utilization"]
    out["utilization_latest"] = latest
    out["provenance"] = Provenance.MEASURED.value
    return out.sort_values("mean_utilization", ascending=False)


# --- identifiability --------------------------------------------------------
# A reserve-style resource designed for a 1-in-T year condition is genuinely not
# called in any given year with probability (1 - 1/T). Observing W consecutive
# quiet years is therefore unsurprising under the reserve hypothesis until
# (1 - 1/T)^W falls below the significance level.


def p_quiet(return_period: float, window_years: int) -> float:
    """P(zero genuine calls in `window_years`) for a 1-in-T resource."""
    if return_period <= 1:
        return 0.0
    return (1.0 - 1.0 / return_period) ** window_years


# This is the rule of three, and it was not derived here. Hanley and
# Lippman-Hand set it out in JAMA in 1983: observing zero events in n trials
# puts the 95% upper bound on the event rate at about 3/n. Solving
# (1 - p)^n = alpha for n is the exact form, and 3/p is the small-p
# approximation to it, so the window this function returns is about 3T years
# for a one-in-T-year resource. Tuyl 2009 reviews the variants; Eypasch and
# colleagues 1995 give the clinical version. See PRIOR_WORK.md.
RULE_OF_THREE_CITATION = (
    "Hanley and Lippman-Hand, 'If nothing goes wrong, is everything all right? "
    "Interpreting zero numerators', JAMA 249(13), 1983; Eypasch et al., BMJ "
    "311, 1995; Tuyl, 'The Rule of Three, its Variants and Extensions', "
    "International Statistical Review, 2009"
)


def rule_of_three_window(return_period: float) -> float:
    """The textbook approximation, 3T years, for comparison with the exact form."""
    return 3.0 * return_period


def min_window(return_period: float, alpha: float = 0.05) -> int:
    """Years of quiet needed to reject the reserve hypothesis at `alpha`.

    Exact form of the rule of three. See RULE_OF_THREE_CITATION: this is a
    standard result, applied here rather than discovered here.
    """
    if return_period <= 1:
        return 1
    return math.ceil(math.log(alpha) / math.log(1.0 - 1.0 / return_period))


def max_identifiable_return_period(window_years: int, alpha: float = 0.05) -> float:
    """Largest T a window of this length can rule out. Inverse of min_window."""
    q = alpha ** (1.0 / window_years)
    return 1.0 / (1.0 - q)


def identifiability_table(alpha: float = 0.05) -> pd.DataFrame:
    rows = []
    for t in [2, 3, 5, 10, 15, 20, 30, 50]:
        rows.append(
            {
                "return_period_years": t,
                "p_quiet_over_panel": p_quiet(t, PANEL_YEARS),
                "min_window_years": min_window(t, alpha),
                "identifiable_in_panel": min_window(t, alpha) <= PANEL_YEARS,
                "alpha": alpha,
                "provenance": Provenance.IDENTITY.value,
            }
        )
    return pd.DataFrame(rows)


# --- the closed form is optimistic ------------------------------------------
# p_quiet assumes years are independent draws. Extreme system conditions are not
# independent: heat domes persist, droughts run multi-year, ENSO phases last
# seasons. Persistence reduces the number of effective independent trials in a
# panel, so a persistent process produces longer quiet runs than an independent
# one with the same long-run frequency, and the window needed to reject the
# reserve hypothesis grows.
#
# Model the occurrence of a call-worthy year as a two-state Markov chain with
# stationary probability p = 1/T and persistence q = P(extreme | extreme prior
# year). The off-state transition rate follows from the stationary condition:
#
#     r = P(extreme | normal) = p (1 - q) / (1 - p)
#     P(no extreme year in W) = (1 - p) (1 - r)^(W - 1)
#
# At q = p the chain is memoryless and this collapses to the independent case,
# which a test asserts. At q > p, the physically plausible direction, the
# required window is strictly longer, so the closed-form answer elsewhere in
# this track is a LOWER bound on what identification actually needs.


# The persistence correction below has a name in survey statistics that this
# repo reached without knowing: it is an effective-sample-size adjustment. Kish
# (Survey Sampling, 1965) writes the design effect for clustered observations as
# Deff = 1 + (m - 1) * ICC, and any binomial interval, including the zero-event
# bound the rule of three comes from, is corrected by replacing n with n / Deff.
# For an AR(1) process the effective size is n * (1 - rho) / (1 + rho). So the
# dependence-corrected rule of three is 3 * Deff / n, and the Markov chain below
# is one way of generating Deff for a two-state weather process.
#
# No published source states that correction for the zero-event case, and the
# power-system literature on short records arrives at the same problem from the
# other side: Wilson and Zachary (arXiv:1907.13050) estimate loss-of-load
# expectation from seven winter seasons with within-season autocorrelation and
# block-bootstrap whole seasons rather than treat hours as independent, reporting
# a 95% interval of 1.92 to 9.37 hours per season around a mean of 5.08. Dent and
# Zachary (arXiv:1412.1786) find two thirds of calculated loss-of-load arising
# from six days. Short records plus dependence is a known hard problem; the
# closed form here is a small piece of it.
EFFECTIVE_SAMPLE_CITATION = (
    "Kish, Survey Sampling, Wiley 1965 (design effect); Wilson and Zachary, "
    "'Using extreme value theory for the estimation of risk metrics for capacity "
    "adequacy assessment', arXiv:1907.13050, 2019; Dent and Zachary, "
    "arXiv:1412.1786, 2014"
)


def design_effect(persistence: float, return_period: float) -> float:
    """Ratio of the nominal window to the effective one, from the chain itself.

    Defined as the window a persistent process needs divided by the window an
    independent process with the same long-run frequency needs, which is the
    design effect in the sense used above.
    """
    return min_window_markov(return_period, persistence) / min_window(return_period)


def ar1_effective_size(n: int, rho: float) -> float:
    """Textbook AR(1) effective sample size, for comparison with design_effect."""
    return n * (1.0 - rho) / (1.0 + rho)


def p_quiet_markov(return_period: float, window_years: int, persistence: float) -> float:
    """P(zero calls in `window_years`) for a persistent 1-in-T process."""
    if return_period <= 1:
        return 0.0
    p = 1.0 / return_period
    if not 0.0 <= persistence < 1.0:
        raise ValueError("persistence must be in [0, 1)")
    r = p * (1.0 - persistence) / (1.0 - p)
    if r <= 0:
        return 1.0
    return (1.0 - p) * (1.0 - r) ** (window_years - 1)


def min_window_markov(
    return_period: float, persistence: float, alpha: float = 0.05, cap: int = 5_000
) -> int:
    w = 1
    while w < cap and p_quiet_markov(return_period, w, persistence) > alpha:
        w += 1
    return w


def persistence_sweep(return_period: float = 10.0, alpha: float = 0.05) -> pd.DataFrame:
    p = 1.0 / return_period
    rows = []
    for q in [p, 0.2, 0.3, 0.4, 0.5, 0.6]:
        if q < p:
            continue
        need = min_window_markov(return_period, q, alpha)
        rows.append(
            {
                "return_period_years": return_period,
                "persistence": round(q, 4),
                "memoryless": abs(q - p) < 1e-12,
                "min_window_years": need,
                "vs_independent": need / min_window(return_period, alpha),
                "design_effect": need / min_window(return_period, alpha),
                "p_quiet_over_panel": p_quiet_markov(return_period, PANEL_YEARS, q),
                "provenance": Provenance.IDENTITY.value,
            }
        )
    return pd.DataFrame(rows)


def simulate_quiet_runs(
    return_period: float, window_years: int, persistence: float, n: int = 200_000, seed: int = 7
) -> float:
    """Monte Carlo check on the closed form above. Simulated, and only used to
    verify the algebra, never to produce a headline."""
    rng = np.random.default_rng(seed)
    p = 1.0 / return_period
    r = p * (1.0 - persistence) / (1.0 - p)
    state = rng.random(n) < p           # stationary start
    quiet = ~state
    for _ in range(window_years - 1):
        move = np.where(state, rng.random(n) < persistence, rng.random(n) < r)
        state = move
        quiet &= ~state
    return float(quiet.mean())


def persistence_summary(alpha: float = 0.05) -> dict:
    sweep = persistence_sweep(alpha=alpha)
    worst = sweep.iloc[-1]
    return {
        "return_period": 10.0,
        "independent_min_window": min_window(10.0, alpha),
        "persistence_max_tested": float(worst.persistence),
        "min_window_at_max_persistence": int(worst.min_window_years),
        "window_multiplier_at_max_persistence": float(worst.vs_independent),
        "closed_form_is_a_lower_bound_under_persistence": bool(
            (sweep[~sweep.memoryless].vs_independent >= 1).all()
        ),
        "collapses_to_independent_when_memoryless": bool(
            sweep[sweep.memoryless].min_window_years.iloc[0] == min_window(10.0, alpha)
        ),
        "design_effect_at_max_persistence": design_effect(float(worst.persistence), 10.0),
        "is_an_effective_sample_size_correction": True,
        "citation": EFFECTIVE_SAMPLE_CITATION,
    }


def classify(
    utilizations: list[float],
    return_period: float,
    phantom_threshold: float = 0.05,
    alpha: float = 0.05,
) -> str:
    """PHANTOM / RESERVE / UNIDENTIFIED for a run of yearly utilizations.

    A near-zero run is only called PHANTOM once the run is long enough to reject
    the reserve hypothesis for the stated return period. Short runs return
    UNIDENTIFIED rather than guessing, which is the entire point: the naive
    version of this classifier, thresholding a single year, is what produces the
    phantom-capacity headline this repo is testing.
    """
    quiet = [u for u in utilizations if u <= phantom_threshold]
    if len(quiet) < len(utilizations):
        return "WORKING"
    if len(utilizations) >= min_window(return_period, alpha):
        return "PHANTOM"
    return "UNIDENTIFIED"


def misclassification_demo(alpha: float = 0.05) -> pd.DataFrame:
    """A genuine 1-in-T reserve program, observed over windows of each length.

    SIMULATED, and only to show the shape of the error: the same program is
    called UNIDENTIFIED or PHANTOM purely as a function of how long you watched.
    """
    rows = []
    for t in RESERVE_RETURN_PERIOD.sweep(5):
        need = min_window(t, alpha)
        for w in [1, 3, 5, PANEL_YEARS, need]:
            rows.append(
                {
                    "return_period_years": round(t, 2),
                    "window_years": w,
                    "p_program_looks_dead": p_quiet(t, w),
                    "verdict_if_quiet": classify([0.0] * w, t, alpha=alpha),
                    "provenance": Provenance.SIMULATED.value,
                }
            )
    return pd.DataFrame(rows).drop_duplicates()




# --- composition ------------------------------------------------------------
# National utilization is the enrolled-weighted mean of sector utilizations,
# U = sum_s w_s u_s. So a flat national ratio can mean every sector is flat, or
# that a sector getting worse is being offset by the mix shifting toward a
# better one. Those have different implications and the aggregate hides which.


def weights_and_rates() -> pd.DataFrame:
    df = utilization_table()
    sec = df[df.sector.isin(SECTORS)].copy()
    totals = sec.groupby("year").enrolled_mw.transform("sum")
    sec["weight"] = sec.enrolled_mw / totals
    return sec[["year", "sector", "weight", "utilization", "enrolled_mw"]]


def shift_share(start: int | None = None, end: int | None = None) -> pd.DataFrame:
    """Split the change in national utilization into within, mix and interaction.

        dU = sum_s w_s0 (u_s1 - u_s0)      within-sector
           + sum_s u_s0 (w_s1 - w_s0)      mix
           + sum_s (w_s1 - w_s0)(u_s1 - u_s0)   interaction

    A sector present in one year and absent in the other carries weight zero in
    the missing year, so an exiting sector shows up in the mix term rather than
    being dropped.
    """
    ws = weights_and_rates()
    start = int(ws.year.min()) if start is None else start
    end = int(ws.year.max()) if end is None else end
    a = ws[ws.year == start].set_index("sector")
    b = ws[ws.year == end].set_index("sector")
    rows = []
    for sector in SECTORS:
        w0 = float(a.weight.get(sector, 0.0) or 0.0)
        w1 = float(b.weight.get(sector, 0.0) or 0.0)
        u0 = float(a.utilization.get(sector, 0.0) or 0.0)
        u1 = float(b.utilization.get(sector, 0.0) or 0.0)
        rows.append(
            {
                "sector": sector,
                "weight_start": w0,
                "weight_end": w1,
                "utilization_start": u0,
                "utilization_end": u1,
                "within": w0 * (u1 - u0),
                "mix": u0 * (w1 - w0),
                "interaction": (w1 - w0) * (u1 - u0),
                "provenance": Provenance.MEASURED.value,
            }
        )
    out = pd.DataFrame(rows)
    out.attrs["start"] = start
    out.attrs["end"] = end
    return out


def frozen_mix_series(base_year: int | None = None) -> pd.DataFrame:
    """National utilization each year if the sector mix never moved."""
    ws = weights_and_rates()
    base_year = int(ws.year.min()) if base_year is None else base_year
    base = ws[ws.year == base_year].set_index("sector").weight
    rows = []
    for year, grp in ws.groupby("year"):
        g = grp.set_index("sector")
        w = base.reindex(g.index).fillna(0.0)
        if w.sum() == 0:
            continue
        rows.append(
            {
                "year": int(year),
                "actual": float((g.weight * g.utilization).sum()),
                "frozen_mix": float((w * g.utilization).sum() / w.sum()),
                "provenance": Provenance.MEASURED.value,
            }
        )
    return pd.DataFrame(rows)


def dispersion_floor() -> pd.DataFrame:
    """Enrolled-weighted spread of sector utilizations, by year.

    This is a floor on the true dispersion across programs, not a measure of it.
    Total variance across utilities decomposes into a between-sector part, which
    is what this shows, plus a within-sector part that national aggregates
    cannot see. A national ratio of 0.39 is consistent with every utility near
    0.39 or with half the fleet at zero, and nothing in this dataset separates
    those. See ROADMAP item 1.
    """
    ws = weights_and_rates()
    rows = []
    for year, g in ws.groupby("year"):
        mean = float((g.weight * g.utilization).sum())
        var = float((g.weight * (g.utilization - mean) ** 2).sum())
        # min and max are taken over material sectors only. Transportation
        # carries well under 1% of enrolled MW and swings between 0.3% and 93%
        # utilization on a couple of hundred MW, so an unfiltered range is a
        # statement about a rounding error rather than about the fleet. The
        # weighted sd above already handles it correctly and is left unfiltered.
        material = g[g.weight >= MATERIAL_WEIGHT]
        rows.append(
            {
                "year": int(year),
                "weighted_mean": mean,
                "between_sector_sd": var**0.5,
                "min_sector": float(material.utilization.min()),
                "max_sector": float(material.utilization.max()),
                "spread": float(material.utilization.max() - material.utilization.min()),
                "sectors_counted": int(len(material)),
                "provenance": Provenance.MEASURED.value,
            }
        )
    return pd.DataFrame(rows)


# --- regional ---------------------------------------------------------------
# The sector dispersion above is a floor on the real spread. FERC publishes the
# same EIA series cut by census division, which lets that floor be raised, but
# only partway: the regional cut carries potential peak savings, not actual, so
# regional utilization itself is still not observable. What can be computed is
# the spread that regional differences in CLASS MIX alone would produce, holding
# each class at its national utilization. That is a second floor, strictly above
# nothing and strictly below the truth, and it is labelled as such everywhere.


def regional_mix_floor(year: int = 2023) -> pd.DataFrame:
    classes = ["residential", "commercial", "industrial"]
    panel = load_eia_panel()
    national_u = {
        c: float(panel.loc[(year, c), "actual_peak_mw"])
        / float(panel.loc[(year, c), "potential_peak_mw"])
        for c in classes
    }
    by_class = {c: ferc.regional_metric("potential_peak_mw", year, c) for c in classes}
    frame = pd.DataFrame(by_class)
    weights = frame.div(frame.sum(axis=1), axis=0)
    out = weights.copy()
    out.columns = [f"weight_{c}" for c in classes]
    out["enrolled_mw"] = frame.sum(axis=1)
    out["mix_implied_utilization"] = sum(
        weights[c] * national_u[c] for c in classes
    )
    out["national_utilization"] = sum(
        frame[c].sum() / frame.sum().sum() * national_u[c] for c in classes
    )
    out["provenance"] = "measured_mix_national_rates"
    return out.sort_values("mix_implied_utilization")


def regional_summary(year: int = 2023) -> dict:
    mix = regional_mix_floor(year)
    enrolled = ferc.regional_metric("potential_peak_mw", year)
    share = (enrolled / enrolled.sum()).sort_values(ascending=False)
    hhi = float((share**2).sum())
    return {
        "year": year,
        "divisions": int(len(mix)),
        "mix_floor_min": float(mix.mix_implied_utilization.min()),
        "mix_floor_min_division": str(mix.mix_implied_utilization.idxmin()),
        "mix_floor_max": float(mix.mix_implied_utilization.max()),
        "mix_floor_max_division": str(mix.mix_implied_utilization.idxmax()),
        "mix_floor_spread": float(
            mix.mix_implied_utilization.max() - mix.mix_implied_utilization.min()
        ),
        "largest_division_share": float(share.iloc[0]),
        "largest_division": str(share.index[0]),
        "top3_share": float(share.iloc[:3].sum()),
        "enrolled_hhi": hhi,
        "regional_utilization_observable": False,
        "note": (
            "mix-only floor: holds each class at its national utilization, so it "
            "measures the dispersion that class composition alone would produce "
            "and nothing of the within-class regional variation"
        ),
    }


# --- utility level ----------------------------------------------------------
# Everything above is an aggregate, and an aggregate cannot say whether a
# national dispatch utilization near 40% means every utility lands near 40% or
# whether a large part of the fleet delivers nothing while the rest delivers
# most of what it promised. ACEEE published the utility cut for 2015, which
# settles the shape question for the largest programs in one year.
#
# It also permits a test the aggregates cannot support. The two competing
# explanations predict different distributions:
#
#   ABSENT     capacity that would fail if called produces PARTIAL delivery.
#              Some customers respond, some do not, and the reported number
#              lands somewhere in the middle.
#   UNCALLED   capacity that was never dispatched produces EXACTLY ZERO. Not
#              calling an event is an administrative fact, not a performance
#              one, and it has no partial version.
#
# So a point mass at exactly zero is evidence for the uncalled mechanism, and a
# continuous spread above zero is evidence for neither, since partial calling
# and partial performance are indistinguishable there.

ACEEE_UTILITIES = (
    pathlib.Path(__file__).resolve().parents[2] / "data" / "aceee_dr_utilities_2015.csv"
)
ACEEE_NATIONAL_2015 = {"utilities": 421, "potential_mw": 32_875, "actual_mw": 13_036}
NEAR_ZERO = 0.05
NEAR_FULL = 0.80


def utility_table() -> pd.DataFrame:
    df = pd.read_csv(ACEEE_UTILITIES)
    df["utilization"] = df.actual_peak_mw / df.potential_peak_mw
    df["potential_share_of_own_peak"] = df.potential_peak_mw / df.system_peak_mw
    df["provenance"] = Provenance.MEASURED.value
    return df.sort_values("utilization", na_position="last")


def utility_dispersion() -> dict:
    df = utility_table()
    reported = df[df.reported_actual]
    total_potential = float(df.potential_peak_mw.sum())
    bands = {
        "near_zero": reported[reported.utilization <= NEAR_ZERO],
        "middle": reported[
            (reported.utilization > NEAR_ZERO) & (reported.utilization < NEAR_FULL)
        ],
        "near_full": reported[reported.utilization >= NEAR_FULL],
    }
    national = ACEEE_NATIONAL_2015["potential_mw"]
    exact_zero = reported[reported.actual_peak_mw == 0]
    no_data = df[~df.reported_actual]
    return {
        "year": 2015,
        "utilities": int(len(df)),
        "utilities_with_actual": int(len(reported)),
        "coverage_share_of_national_potential": total_potential / national,
        "median_utilization": float(reported.utilization.median()),
        "mean_utilization": float(reported.utilization.mean()),
        "mw_weighted_utilization": float(
            reported.actual_peak_mw.sum() / reported.potential_peak_mw.sum()
        ),
        "min_utilization": float(reported.utilization.min()),
        "max_utilization": float(reported.utilization.max()),
        **{
            f"{name}_n": int(len(g)) for name, g in bands.items()
        },
        **{
            f"{name}_share_of_potential": float(g.potential_peak_mw.sum() / total_potential)
            for name, g in bands.items()
        },
        "exact_zero_n": int(len(exact_zero)),
        "exact_zero_mw": float(exact_zero.potential_peak_mw.sum()),
        "no_data_n": int(len(no_data)),
        "no_data_mw": float(no_data.potential_peak_mw.sum()),
        "zero_or_missing_share_of_national": float(
            (exact_zero.potential_peak_mw.sum() + no_data.potential_peak_mw.sum())
            / national
        ),
        "largest_zero_utility": str(
            exact_zero.loc[exact_zero.potential_peak_mw.idxmax(), "utility"]
        ),
        "largest_zero_mw": float(exact_zero.potential_peak_mw.max()),
    }


def zero_mass_test() -> dict:
    """Does the shape favour uncalled capacity or absent capacity.

    Reported as a split verdict, because it is one. The point mass at exactly
    zero is hard to produce by partial non-performance and easy to produce by
    not calling an event. The continuous spread above zero discriminates
    nothing: partial calling and partial performance look identical there.
    """
    df = utility_table()
    reported = df[df.reported_actual]
    zeros = reported[reported.actual_peak_mw == 0]
    above = reported[reported.actual_peak_mw > 0]
    gaps = above.utilization.sort_values().diff().dropna()
    return {
        "zero_mass_utilities": int(len(zeros)),
        "zero_mass_share_of_utilities": float(len(zeros) / len(reported)),
        "zero_mass_share_of_sample_potential": float(
            zeros.potential_peak_mw.sum() / reported.potential_peak_mw.sum()
        ),
        "spread_above_zero_min": float(above.utilization.min()),
        "spread_above_zero_max": float(above.utilization.max()),
        "largest_gap_above_zero": float(gaps.max()),
        "spread_is_continuous": bool(gaps.max() < 0.20),
        "favours_uncalled_for_the_zero_mass": True,
        "discriminates_above_zero": False,
        "verdict": (
            "split: a point mass at exactly zero is what not calling an event "
            "looks like and is not what partial non-performance looks like, so "
            "that part of the shortfall reads as uncalled rather than as failed "
            "delivery. Whether uncalled capacity would have delivered is a "
            "separate question the shape cannot answer. Above zero the "
            "distribution is continuous and separates nothing"
        ),
    }


# --- the full population, three years ---------------------------------------
# ACEEE's table is one year and the 28 largest programs. The EIA-861 detailed
# files for 2016 to 2018 cover every reporting utility, and they turn the
# zero-mass result from a single-year observation into something testable in
# the way ROADMAP item 1 said would be decisive: does the same utility report
# zero every year, or does the zero mass move around?
#
# A structurally dead program reports zero every year. A reserve program that
# was not needed reports zero in a mild year and something in a hard one. That
# asymmetry is real but weaker than it first looked, for two reasons recorded
# below rotation_grid(). Over three years a reserve called once a decade also
# reports zero every year, so persistence does not identify a dead program.
# And rotation only shows the zero-year capacity was available when the other
# year carries a measured delivery, which most of the rotation here does not.

UTILITY_PANEL = (
    pathlib.Path(__file__).resolve().parents[2]
    / "data"
    / "eia861_dr_utility_2016_2018.csv"
)
MIN_UTILITIES = 50  # below this the population statistics are not meaningful


class InsufficientData(RuntimeError):
    """Raised instead of returning a degenerate answer."""


# Wabash Valley Power reports in Indiana under two balancing authorities, PJM
# and MISO, in every year, and in 2016, before EIA added the column, as two rows
# with nothing to tell them apart. A key of utility plus state is therefore not
# unique, and an earlier version of this module let three downstream functions
# resolve that three different ways: persistence kept the first row, the size
# test averaged two different programs, and the footprint test put both in one
# footprint. Totals were never affected, which is why reconciliation passed.
#
# The entity here is one utility within one state, summed across balancing
# authorities, assigned to the authority that holds most of its capacity. A test
# asserts the key is unique, and another reconciles the raw row counts against
# PUDL's expected counts, which differ in 2016 by exactly this pair.
NUMERIC = [
    "customers_enrolled",
    "potential_peak_mw",
    "actual_peak_mw",
    "energy_savings_mwh",
    "customer_incentives_kusd",
    "other_costs_kusd",
]


def utility_panel_raw() -> pd.DataFrame:
    return pd.read_csv(UTILITY_PANEL, dtype={"utility_number": str})


def utility_panel() -> pd.DataFrame:
    # built once per process and copied out, because the specification grids
    # below call it hundreds of times and callers are free to mutate the copy
    return _utility_panel_cached().copy()


@functools.lru_cache(maxsize=1)
def _utility_panel_cached() -> pd.DataFrame:
    raw = utility_panel_raw()
    raw["key"] = raw.utility_number + "_" + raw.state
    dominant = (
        raw.sort_values("potential_peak_mw", ascending=False)
        .drop_duplicates(["year", "key"])
        .set_index(["year", "key"])[["utility", "utility_number", "state", "ba_code"]]
    )
    # min_count=1 keeps an all-blank group blank: a utility whose every row
    # reported no actual stays "not reported", never becomes a zero
    sums = raw.groupby(["year", "key"])[NUMERIC].sum(min_count=1)
    df = dominant.join(sums).reset_index()
    df["reported_actual"] = df.actual_peak_mw.notna()
    df["status"] = "positive"
    df.loc[df.actual_peak_mw == 0, "status"] = "exact_zero"
    df.loc[~df.reported_actual, "status"] = "not_reported"
    df["provenance"] = Provenance.MEASURED.value
    return df


def zero_mass_by_year() -> pd.DataFrame:
    df = utility_panel()
    df = df[df.potential_peak_mw > 0]
    rows = []
    for year, g in df.groupby("year"):
        if g.key.nunique() < MIN_UTILITIES:
            raise InsufficientData(f"{year}: {g.key.nunique()} utilities")
        total = g.potential_peak_mw.sum()
        for status in ("exact_zero", "not_reported", "positive"):
            s = g[g.status == status]
            rows.append(
                {
                    "year": int(year),
                    "status": status,
                    "utilities": int(len(s)),
                    "potential_mw": float(s.potential_peak_mw.sum()),
                    "share_of_potential": float(s.potential_peak_mw.sum() / total),
                    "provenance": Provenance.MEASURED.value,
                }
            )
    return pd.DataFrame(rows)


def zero_persistence() -> dict:
    """Among utilities reporting an actual value in every year, how persistent
    is a zero. This is the statistic as first published. Rotation into a
    measured delivery favours uncalled capacity, but this statistic counts any
    positive report as rotation; rotation_composition() separates the two. Over
    three years persistence is ambiguous: a rarely called reserve and a program
    that does not operate both stay at zero."""
    df = utility_panel()
    df = df[df.potential_peak_mw > 0]
    years = sorted(df.year.unique())
    rep = df.pivot_table(index="key", columns="year", values="reported_actual", aggfunc="first")
    zero = df.assign(z=df.status == "exact_zero").pivot_table(
        index="key", columns="year", values="z", aggfunc="first"
    )
    complete = rep.dropna()
    complete = complete[(complete == True).all(axis=1)].index  # noqa: E712
    if len(complete) < MIN_UTILITIES:
        raise InsufficientData(f"{len(complete)} utilities reporting every year")
    zeros = zero.loc[complete].astype(bool).sum(axis=1)
    mean_mw = df.groupby("key").potential_peak_mw.mean()
    ever = zeros[zeros >= 1].index
    always = zeros[zeros == len(years)].index
    largest_always = mean_mw.loc[always].sort_values(ascending=False)
    return {
        "years": [int(y) for y in years],
        "utilities_reporting_every_year": int(len(complete)),
        "never_zero": int((zeros == 0).sum()),
        "zero_every_year": int(len(always)),
        "ever_zero": int(len(ever)),
        "rotating_share_of_ever_zero_mw": float(
            1 - mean_mw.loc[always].sum() / mean_mw.loc[ever].sum()
        ),
        "persistent_share_of_ever_zero_mw": float(
            mean_mw.loc[always].sum() / mean_mw.loc[ever].sum()
        ),
        "largest_persistent_key": str(largest_always.index[0]),
        "largest_persistent_mw": float(largest_always.iloc[0]),
        "majority_of_zero_capacity_rotates": bool(
            1 - mean_mw.loc[always].sum() / mean_mw.loc[ever].sum() > 0.5
        ),
    }


# --- does the rotation result survive its own choices -----------------------
# zero_persistence() rests on six choices made once: what counts as zero, what
# to do with reports where actual simply equals potential, which utilities form
# the panel, how to weight them, what the unit of analysis is, and whether a
# program whose enrolled figure changed several-fold is still the same program.
# rotation_grid() varies all six. That answers whether the number is fragile.
#
# It cannot answer whether the number measures what the prose said it measures,
# and that turned out to be the real problem. The statistic counts a utility as
# rotating if it reported anything above the zero rule in any other year.
# Reading the utilities behind it showed that most of the rotating capacity
# rotates into reports that say nothing about whether the zero-year capacity
# was available: a program whose enrolled figure fell twentyfold, a report
# within 0.02% of enrolled capacity, and positive years under 4% of potential.
# rotation_composition() classifies every case, and zero_followup() asks the
# question the rotation statistic only gestures at: when capacity reports zero
# in one year, how much of it delivers in the next.

ROTATION_ZERO_RULES = (0.0, 0.01, NEAR_ZERO)
ROTATION_COPY_RULES = ("count_as_delivery", "exact_is_missing", "within_1pct_is_missing")
ROTATION_PANELS = ("complete", "two_or_more")
ROTATION_WEIGHTS = ("mean", "median", "max", "count")
ROTATION_ENTITIES = ("utility_state", "utility")
ROTATION_RESIZED = ("keep", "drop")
COPY_TOLERANCE = 0.01   # a report within 1% of enrolled capacity
RESIZE_FACTOR = 3.0     # enrolled capacity moving more than threefold in three years
PUBLISHED_ROTATION_SPEC = {
    "zero_rule": 0.0,
    "copies": "count_as_delivery",
    "panel": "complete",
    "weight": "mean",
    "entity": "utility_state",
    "resized": "keep",
}
ROTATION_CLASSES = (
    "zero_every_year",  # persistent: zero in every reported year
    "measured",         # some other year delivered at least 5% and was not a copy
    "resized",          # enrolled capacity moved more than threefold
    "copied",           # every positive year equals enrolled capacity exactly
    "near_copy",        # every positive year within 1% of enrolled capacity
    "near_zero",        # every positive year below 5% of enrolled capacity
    "mixed",            # positive years that are copies and near zeros together
)


@functools.lru_cache(maxsize=2)
def _entity_panel_cached(entity: str) -> pd.DataFrame:
    df = utility_panel()
    cols = ["year", "key", "potential_peak_mw", "actual_peak_mw"]
    if entity == "utility_state":
        out = df[cols].copy()
    elif entity == "utility":
        # one row per utility, summed across states; the actual is kept only
        # when every state filed one, so a blank state is not turned into a
        # partial delivery
        out = (
            df.groupby(["year", "utility_number"])
            .agg(
                potential_peak_mw=("potential_peak_mw", "sum"),
                actual_peak_mw=("actual_peak_mw", "sum"),
                rows=("actual_peak_mw", "size"),
                filed=("actual_peak_mw", "count"),
            )
            .reset_index()
            .rename(columns={"utility_number": "key"})
        )
        out.loc[out.filed < out.rows, "actual_peak_mw"] = np.nan
        out = out[cols]
    else:
        raise ValueError(f"unknown entity {entity!r}")
    return out[out.potential_peak_mw > 0].reset_index(drop=True)


def _entity_panel(entity: str) -> pd.DataFrame:
    return _entity_panel_cached(entity).copy()


def _is_copy(actual: pd.Series, potential: pd.Series, tolerance: float = 0.0) -> pd.Series:
    """A positive report equal to enrolled capacity, exactly or within tolerance."""
    if tolerance == 0.0:
        same = pd.Series(np.isclose(actual, potential), index=actual.index)
    else:
        same = (actual / potential - 1.0).abs() <= tolerance
    return (actual > 0) & same


def rotation_share(
    zero_rule: float = 0.0,
    copies: str = "count_as_delivery",
    panel: str = "complete",
    weight: str = "mean",
    entity: str = "utility_state",
    resized: str = "keep",
) -> dict:
    """The rotation statistic under one specification.

    Defaults reproduce zero_persistence(), which a test asserts.
    """
    if weight not in ROTATION_WEIGHTS:
        raise ValueError(f"unknown weight {weight!r}")
    out = _rotation_all_weights(zero_rule, copies, panel, entity, resized)
    return {
        "entities": out["entities"],
        "ever_zero": out["ever_zero"],
        "zero_every_reported_year": out["zero_every_reported_year"],
        "rotating_share": out[f"rotating_share_{weight}"],
        "zero_mw_coverage": out["zero_mw_coverage"],
    }


@functools.lru_cache(maxsize=128)
def _rotation_all_weights(
    zero_rule: float, copies: str, panel: str, entity: str, resized: str
) -> dict:
    df = _entity_panel(entity)
    n_years = df.year.nunique()
    if copies != "count_as_delivery":
        tol = {"exact_is_missing": 0.0, "within_1pct_is_missing": COPY_TOLERANCE}[copies]
        df.loc[_is_copy(df.actual_peak_mw, df.potential_peak_mw, tol), "actual_peak_mw"] = np.nan
    by_key = df.groupby("key").potential_peak_mw
    spread = by_key.max() / by_key.min()
    rep = df[df.actual_peak_mw.notna()].copy()
    rep["zero"] = rep.actual_peak_mw / rep.potential_peak_mw <= zero_rule
    zero_mw = rep.loc[rep.zero, "potential_peak_mw"].sum()
    filed = rep.groupby("key").year.nunique()
    keep = filed[filed >= (n_years if panel == "complete" else 2)].index
    if resized == "drop":
        keep = keep.intersection(spread[spread <= RESIZE_FACTOR].index)
    rep = rep[rep.key.isin(keep)]
    if rep.key.nunique() < MIN_UTILITIES:
        raise InsufficientData(f"{rep.key.nunique()} entities in the rotation panel")
    g = rep.groupby("key")
    per = pd.DataFrame(
        {
            "zero_years": g.zero.sum(),
            "years": g.zero.size(),
            "mean": g.potential_peak_mw.mean(),
            "median": g.potential_peak_mw.median(),
            "max": g.potential_peak_mw.max(),
        }
    )
    per["count"] = 1.0
    ever = per[per.zero_years >= 1]
    always = ever[ever.zero_years == ever.years]
    return {
        "entities": int(len(per)),
        "ever_zero": int(len(ever)),
        "zero_every_reported_year": int(len(always)),
        **{
            f"rotating_share_{w}": float(1.0 - always[w].sum() / ever[w].sum())
            for w in ROTATION_WEIGHTS
        },
        # how much of the zero-reported capacity the panel can see at all
        "zero_mw_coverage": float(rep.loc[rep.zero, "potential_peak_mw"].sum() / zero_mw),
    }


@functools.lru_cache(maxsize=1)
def rotation_grid() -> pd.DataFrame:
    rows = []
    for zr, cp, pn, en, rs in itertools.product(
        ROTATION_ZERO_RULES,
        ROTATION_COPY_RULES,
        ROTATION_PANELS,
        ROTATION_ENTITIES,
        ROTATION_RESIZED,
    ):
        for wt in ROTATION_WEIGHTS:
            spec = {"zero_rule": zr, "copies": cp, "panel": pn, "weight": wt,
                    "entity": en, "resized": rs}
            rows.append({**spec, **rotation_share(**spec),
                         "provenance": Provenance.MEASURED.value})
    return pd.DataFrame(rows)


def rotation_grid_summary() -> dict:
    g = rotation_grid()
    cap = g[g.weight != "count"]
    cnt = g[g.weight == "count"]
    published = g[
        (g[list(PUBLISHED_ROTATION_SPEC)] == pd.Series(PUBLISHED_ROTATION_SPEC)).all(axis=1)
    ]
    pub_cov = published.zero_mw_coverage.iloc[0]
    return {
        "specifications": int(len(g)),
        "published": float(published.rotating_share.iloc[0]),
        "capacity_specifications": int(len(cap)),
        "capacity_min": float(cap.rotating_share.min()),
        "capacity_median": float(cap.rotating_share.median()),
        "capacity_max": float(cap.rotating_share.max()),
        "capacity_above_half": int((cap.rotating_share > 0.5).sum()),
        "count_specifications": int(len(cnt)),
        "count_min": float(cnt.rotating_share.min()),
        "count_max": float(cnt.rotating_share.max()),
        "count_above_half": int((cnt.rotating_share > 0.5).sum()),
        "published_zero_mw_coverage": float(pub_cov),
        "coverage_min": float(g.zero_mw_coverage.min()),
        "coverage_max": float(g.zero_mw_coverage.max()),
    }


def classify_zero_capacity(frame: pd.DataFrame, zero_rule: float = 0.0) -> pd.DataFrame:
    """Classify every entity that ever reported zero by what its other years say.

    Generic: `frame` needs key, year, potential_peak_mw and actual_peak_mw, with
    actual blank where nothing was reported. Only entities that reported an
    actual figure in every year are classified, as in the published statistic.
    The command line tool runs this same function on other people's data.

    Rotation is only evidence that zero-year capacity was available when the
    other year carries a measurement of a real delivery. So the classes, in
    order of precedence, are: zero in every year; resized, where enrolled
    capacity moved more than RESIZE_FACTOR, so the capacity at zero is not the
    capacity that later delivered; measured, where some other year delivered
    at least NEAR_ZERO of potential and was not within COPY_TOLERANCE of it;
    and the rotations that show nothing about availability, which are copies,
    near-copies and near-zero deliveries.
    """
    df = frame[frame.potential_peak_mw > 0].copy()
    n_years = df.year.nunique()
    df["u"] = df.actual_peak_mw / df.potential_peak_mw
    rep = df[df.actual_peak_mw.notna()]
    filed = rep.groupby("key").year.nunique()
    rep = rep[rep.key.isin(filed[filed == n_years].index)].copy()
    rep["zero"] = rep.u <= zero_rule
    rep = rep[rep.key.map(rep.groupby("key").zero.any())]
    rows = []
    for key, g in rep.groupby("key"):
        pos = g[~g.zero]
        spread = float(g.potential_peak_mw.max() / g.potential_peak_mw.min())
        exact = _is_copy(pos.actual_peak_mw, pos.potential_peak_mw, 0.0)
        near = _is_copy(pos.actual_peak_mw, pos.potential_peak_mw, COPY_TOLERANCE)
        measured = (pos.u >= NEAR_ZERO) & ~near
        if pos.empty:
            cls = "zero_every_year"
        elif spread > RESIZE_FACTOR:
            cls = "resized"
        elif measured.any():
            cls = "measured"
        elif exact.all():
            cls = "copied"
        elif near.all():
            cls = "near_copy"
        elif (pos.u < NEAR_ZERO).all():
            cls = "near_zero"
        else:
            cls = "mixed"
        rows.append(
            {
                "key": key,
                "class": cls,
                "mean_potential_mw": float(g.potential_peak_mw.mean()),
                "potential_spread": spread,
                "zero_years": int(g.zero.sum()),
                "max_nonzero_utilization": float(pos.u.max()) if len(pos) else float("nan"),
            }
        )
    out = pd.DataFrame(
        rows,
        columns=["key", "class", "mean_potential_mw", "potential_spread", "zero_years",
                 "max_nonzero_utilization"],
    )
    out["share_of_ever_zero_mw"] = out.mean_potential_mw / out.mean_potential_mw.sum()
    out.attrs["zero_rule"] = zero_rule
    return out.sort_values("mean_potential_mw", ascending=False).reset_index(drop=True)


def rotation_composition(zero_rule: float = 0.0) -> pd.DataFrame:
    """Every utility behind the rotation statistic, classified by what its
    non-zero years actually report. Published panel and weighting."""
    out = classify_zero_capacity(_entity_panel("utility_state"), zero_rule)
    names = utility_panel().drop_duplicates("key").set_index("key").utility
    out.insert(1, "utility", out.key.map(names))
    out["provenance"] = Provenance.MEASURED.value
    return out


FOLLOWUP_STATUSES = ("exact_zero", "measured", "copied")


def followup(frame: pd.DataFrame) -> pd.DataFrame:
    """Capacity followed one reporting year forward, by what it reported first.

    Generic: `frame` needs key, year, potential_peak_mw and actual_peak_mw, and
    may carry a state column. Groups in the first year are exact zero, measured
    (positive and not equal to potential) and copied (positive and equal to
    potential). Next-year delivery is capped at the first year's potential, so
    a program that grew cannot count new capacity as the old capacity
    delivering. Each row names the entity, and the state when there is one,
    that contributed most, because with a few dozen entities a single filing
    can carry a row.
    """
    df = frame[frame.potential_peak_mw > 0].copy()
    copied = _is_copy(df.actual_peak_mw, df.potential_peak_mw, 0.0)
    df["group"] = np.where(df.actual_peak_mw.isna(), "not_reported",
                           np.where(df.actual_peak_mw == 0, "exact_zero", "measured"))
    df.loc[copied, "group"] = "copied"
    df["status"] = df.group.where(df.group != "copied", "measured").replace(
        {"measured": "positive"}
    )
    state = df.drop_duplicates("key").set_index("key").state if "state" in df else None
    pot = df.pivot_table(index="key", columns="year", values="potential_peak_mw", aggfunc="first")
    act = df.pivot_table(index="key", columns="year", values="actual_peak_mw", aggfunc="first")
    grp = df.pivot_table(index="key", columns="year", values="group", aggfunc="first")
    sts = df.pivot_table(index="key", columns="year", values="status", aggfunc="first")
    years = sorted(df.year.unique())
    rows = []
    for t, n in zip(years[:-1], years[1:]):
        for group in FOLLOWUP_STATUSES:
            keys = grp.index[grp[t] == group]
            mw = pot.loc[keys, t]
            seen = keys[act.loc[keys, n].notna()]
            if mw.sum() <= 0 or len(seen) == 0:
                continue
            nxt = sts.loc[keys, n].fillna("absent")
            delivered = np.minimum(act.loc[seen, n], pot.loc[seen, t])
            base = pot.loc[seen, t].sum()
            row = {
                "from_year": int(t),
                "to_year": int(n),
                "group_in_from_year": group,
                "potential_mw": float(mw.sum()),
                "next_positive": float(mw[nxt == "positive"].sum() / mw.sum()),
                "next_exact_zero": float(mw[nxt == "exact_zero"].sum() / mw.sum()),
                "next_not_reported": float(mw[nxt == "not_reported"].sum() / mw.sum()),
                "next_absent": float(mw[nxt == "absent"].sum() / mw.sum()),
                "next_year_delivery": float(delivered.sum() / base),
                "followed_mw": float(base),
                "delivered_mw": float(delivered.sum()),
            }
            if delivered.sum() > 0:
                top = delivered.idxmax()
                rest = base - pot.loc[top, t]
                row.update(
                    {
                        "largest_contributor": str(top),
                        "largest_contributor_share": float(delivered.max() / delivered.sum()),
                        "next_year_delivery_without_largest": float(
                            (delivered.sum() - delivered.max()) / rest
                        ) if rest > 0 else float("nan"),
                    }
                )
                if state is not None:
                    where = state.reindex(delivered.index)
                    by_state = delivered.groupby(where).sum()
                    row.update(
                        {
                            "largest_state": str(by_state.idxmax()),
                            "largest_state_share": float(by_state.max() / by_state.sum()),
                            "utilities_in_largest_state": int(
                                (delivered[where == by_state.idxmax()] > 0).sum()
                            ),
                        }
                    )
            rows.append(row)
    return pd.DataFrame(rows)


def zero_followup() -> pd.DataFrame:
    """Capacity at exactly zero in one year, followed into the next, on the
    published panel.

    The rotation statistic classifies utilities over three years. This follows
    megawatts one year forward, which is what the uncalled reading actually
    turns on: when capacity reports zero, does it deliver the next time the
    data looks? Capacity that delivered a measured amount in the first year is
    the comparison; capacity whose report simply equalled its potential mostly
    does so again, and is shown separately so it does not flatter the baseline.
    """
    up = utility_panel()
    out = followup(up[["key", "year", "state", "potential_peak_mw", "actual_peak_mw"]])
    out["provenance"] = Provenance.MEASURED.value
    return out


def rotation_summary() -> dict:
    grid = rotation_grid_summary()
    comp = rotation_composition()
    comp5 = rotation_composition(NEAR_ZERO)
    by = comp.groupby("class").share_of_ever_zero_mw.sum()
    by5 = comp5.groupby("class").share_of_ever_zero_mw.sum()
    fu = zero_followup()
    z = fu[fu.group_in_from_year == "exact_zero"].set_index("to_year")
    m = fu[fu.group_in_from_year == "measured"].set_index("to_year")
    c = fu[fu.group_in_from_year == "copied"].set_index("to_year")
    top3 = comp.mean_potential_mw.iloc[:3].sum() / comp.mean_potential_mw.sum()
    near_copy = comp[comp["class"] == "near_copy"]
    first, last = int(z.index.min()), int(z.index.max())
    # the named cases the prose describes, read from the panel rather than typed
    panel = _entity_panel("utility_state").sort_values("year")
    resized_key = comp[comp["class"] == "resized"].key.iloc[0]
    resized_rows = panel[panel.key == resized_key]
    copy_key = near_copy.key.iloc[0]
    copy_rows = panel[(panel.key == copy_key) & (panel.actual_peak_mw > 0)]
    near_zero_keys = comp[comp["class"] == "near_zero"].key
    nz = panel[panel.key.isin(near_zero_keys) & (panel.actual_peak_mw > 0)]
    nz_u = nz.actual_peak_mw / nz.potential_peak_mw
    return {
        **{f"grid_{k}": v for k, v in grid.items()},
        **{f"comp_{k}": float(by.get(k, 0.0)) for k in ROTATION_CLASSES},
        **{f"comp5_{k}": float(by5.get(k, 0.0)) for k in ROTATION_CLASSES},
        "comp_utilities": int(len(comp)),
        "comp5_utilities": int(len(comp5)),
        "comp_top3_share": float(top3),
        "comp_rotating_not_measured": float(
            by.drop(["zero_every_year", "measured"], errors="ignore").sum()
        ),
        # the one judgment call that moves the measured share most: whether a
        # report within 1% of enrolled capacity is a full curtailment or a copy
        "comp_measured_if_near_copies_are_real": float(
            by.get("measured", 0.0) + by.get("near_copy", 0.0)
        ),
        "comp_largest_near_copy": str(near_copy.utility.iloc[0]) if len(near_copy) else "",
        "comp_near_copy_actual": float(copy_rows.actual_peak_mw.iloc[0]),
        "comp_near_copy_potential": float(copy_rows.potential_peak_mw.iloc[0]),
        "comp_near_copy_year": int(copy_rows.year.iloc[0]),
        "comp_largest_resized": str(comp[comp.key == resized_key].utility.iloc[0]),
        "comp_largest_resized_potentials": [float(v) for v in resized_rows.potential_peak_mw],
        "comp_largest_resized_first_year": int(resized_rows.year.iloc[0]),
        "comp_near_zero_min": float(nz_u.min()),
        "comp_near_zero_max": float(nz_u.max()),
        "comp5_largest_measured": str(
            comp5[comp5["class"] == "measured"].utility.iloc[0]
        ),
        "comp5_largest_measured_share": float(
            comp5[comp5["class"] == "measured"].share_of_ever_zero_mw.iloc[0]
        ),
        "follow_first_year": first,
        "follow_last_year": last,
        "follow_zero_delivery_first": float(z.loc[first, "next_year_delivery"]),
        "follow_zero_delivery_last": float(z.loc[last, "next_year_delivery"]),
        "follow_zero_delivery_last_without_largest": float(
            z.loc[last, "next_year_delivery_without_largest"]
        ),
        "follow_zero_last_largest_state": str(z.loc[last, "largest_state"]),
        "follow_zero_last_largest_state_share": float(z.loc[last, "largest_state_share"]),
        "follow_zero_last_largest_state_utilities": int(
            z.loc[last, "utilities_in_largest_state"]
        ),
        "follow_zero_first_largest_share": float(z.loc[first, "largest_contributor_share"]),
        "follow_zero_delivery_pooled": float(z.delivered_mw.sum() / z.followed_mw.sum()),
        "follow_measured_delivery_pooled": float(m.delivered_mw.sum() / m.followed_mw.sum()),
        "follow_measured_delivery_min": float(m.next_year_delivery.min()),
        "follow_measured_delivery_max": float(m.next_year_delivery.max()),
        "follow_copied_delivery_min": float(c.next_year_delivery.min()),
        "follow_copied_delivery_max": float(c.next_year_delivery.max()),
        "follow_zero_next_positive_min": float(z.next_positive.min()),
        "follow_zero_next_positive_max": float(z.next_positive.max()),
        "follow_zero_next_zero_min": float(z.next_exact_zero.min()),
        "follow_zero_next_zero_max": float(z.next_exact_zero.max()),
        "follow_zero_next_unreported_min": float((z.next_not_reported + z.next_absent).min()),
        "follow_zero_next_unreported_max": float((z.next_not_reported + z.next_absent).max()),
        "majority_rotates_by_capacity_in_every_spec": bool(
            grid["capacity_above_half"] == grid["capacity_specifications"]
        ),
        "rotation_measures_availability": False,
        "verdict": (
            "robust in sign, overstated in meaning. Most capacity ever reported "
            "at zero belongs to utilities that report something in another year "
            "in most specifications, but most of that something does not show "
            "the zero-year capacity was available. Utilities with a measured "
            "delivery in another year hold a minority of it, and followed one "
            "year forward the zero capacity stayed dark in one transition and "
            "delivered in the other, each carried by a few utilities"
        ),
    }


def utility_panel_summary() -> dict:
    zm = zero_mass_by_year()
    z = zm[zm.status == "exact_zero"]
    nr = zm[zm.status == "not_reported"]
    return {
        "years": [int(y) for y in sorted(zm.year.unique())],
        "exact_zero_share_min": float(z.share_of_potential.min()),
        "exact_zero_share_max": float(z.share_of_potential.max()),
        "not_reported_share_min": float(nr.share_of_potential.min()),
        "not_reported_share_max": float(nr.share_of_potential.max()),
        "combined_share_min": float(
            (z.set_index("year").share_of_potential + nr.set_index("year").share_of_potential).min()
        ),
        "combined_share_max": float(
            (z.set_index("year").share_of_potential + nr.set_index("year").share_of_potential).max()
        ),
        **{f"persist_{k}": v for k, v in zero_persistence().items()},
    }


def composition_summary() -> dict:
    ss = shift_share()
    start, end = ss.attrs["start"], ss.attrs["end"]
    within, mix, inter = ss.within.sum(), ss.mix.sum(), ss.interaction.sum()
    total = within + mix + inter
    frozen = frozen_mix_series()
    disp = dispersion_floor()
    return {
        "start_year": start,
        "end_year": end,
        "national_change": float(total),
        "within_sector": float(within),
        "mix": float(mix),
        "interaction": float(inter),
        "mix_share_of_change": float(mix / total) if total else float("nan"),
        "within_share_of_change": float(within / total) if total else float("nan"),
        "frozen_mix_end": float(frozen[frozen.year == end].frozen_mix.iloc[0]),
        "actual_end": float(frozen[frozen.year == end].actual.iloc[0]),
        "largest_mix_contributor": str(ss.loc[ss["mix"].abs().idxmax(), "sector"]),
        "between_sector_sd_mean": float(disp.between_sector_sd.mean()),
        "sector_spread_mean": float(disp.spread.mean()),
        "dispersion_is_a_floor": True,
    }


def run() -> dict[str, pd.DataFrame | dict]:
    return {
        "utilization_by_year": utilization_table(),
        "shift_share": shift_share(),
        "frozen_mix": frozen_mix_series(),
        "dispersion_floor": dispersion_floor(),
        "utilization_by_sector": sector_summary().reset_index(),
        "identifiability": identifiability_table(),
        "persistence_sweep": persistence_sweep(),
        "misclassification_demo": misclassification_demo(),
        "regional_mix_floor": regional_mix_floor().reset_index(names="division"),
        "utility_table": utility_table(),
        "zero_mass_by_year": zero_mass_by_year(),
        "rotation_grid": rotation_grid(),
        "rotation_composition": rotation_composition(),
        "rotation_composition_near_zero": rotation_composition(NEAR_ZERO),
        "zero_followup": zero_followup(),
        "summary": {
            **national_summary(),
            "composition": composition_summary(),
            "regional": regional_summary(),
            "persistence": persistence_summary(),
            "utility_dispersion": utility_dispersion(),
            "zero_mass": zero_mass_test(),
            "utility_panel": utility_panel_summary(),
            "rotation": rotation_summary(),
        },
    }
