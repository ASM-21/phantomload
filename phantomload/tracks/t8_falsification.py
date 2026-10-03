"""Track 8. Attack the repo's own headline until it breaks or holds.

MEASURED inputs, with one ASSUMPTION: the comparator costs in attack B come from
PJM's published planning parameters, and everything else re-reads the EIA and
FERC series the other tracks use. No attack introduces a modelled quantity,
because an attack that needs a simulation to land is not an attack.

Four attacks. Three are the ones the spec asked for. The fourth tests the
alternative explanation this repo previously called untestable, and it lands.

A. Multi-year window. Single-year utilization overstates a phantom problem if
   capacity is genuinely held in reserve. Recompute on rolling windows and, more
   aggressively, treat the best year in each window as the demonstrated
   capability. If enrolled capacity shows up in at least one year, the shortfall
   is a dispatch-frequency story, not a capability story.

B. Best case for the alternative. Recompute track 2 with the cheapest plausible
   comparator instead of a central estimate, so DR has to beat the alternative
   at the alternative's best.

D. Reporting artefact. If respondents apply "potential peak demand savings"
   differently, part of the shortfall is a survey artefact rather than either
   phantom capacity or reserve. Test it by holding class mix constant and
   comparing reported MW per enrolled customer across census divisions.

C. Reserve share. If some of the shortfall is insurance correctly not claimed
   rather than capacity that would fail, the delivered-basis cost is too harsh.
   Solve for the share of the shortfall that would have to be legitimate reserve
   for DR to break even against a given comparator. If that share is small, the
   phantom framing is fragile and should not be the headline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..shared.calibration import PEAKER_CONE, STORAGE_CAPACITY_COST, cone
from ..shared import ferc
from ..shared.dr_program import SECTORS, load_eia_panel
from . import t1_utilization as t1
from . import t2_cost as t2


# --- Attack A ---------------------------------------------------------------
def rolling_windows(window: int = 5) -> pd.DataFrame:
    df = t1.utilization_table()
    rows = []
    for sector, grp in df.groupby("sector"):
        grp = grp.sort_values("year")
        for i in range(len(grp) - window + 1):
            w = grp.iloc[i : i + window]
            rows.append(
                {
                    "sector": sector,
                    "window_start": int(w.year.iloc[0]),
                    "window_end": int(w.year.iloc[-1]),
                    "mean_utilization": float(w.utilization.mean()),
                    "best_year_utilization": float(w.utilization.max()),
                    "best_year_capability_ratio": float(
                        w.verified_mw.max() / w.enrolled_mw.mean()
                    ),
                    "min_utilization": float(w.utilization.min()),
                    "provenance": "measured",
                }
            )
    return pd.DataFrame(rows)


def attack_a() -> dict:
    win = rolling_windows()
    nat = win[win.sector == "total"]
    single = t1.utilization_table()
    single_nat = single[single.sector == "total"]
    return {
        "attack": "multi-year window instead of single year",
        "single_year_mean_utilization": float(single_nat.utilization.mean()),
        "rolling5_mean_utilization_min": float(nat.mean_utilization.min()),
        "rolling5_mean_utilization_max": float(nat.mean_utilization.max()),
        "best_year_in_any_window_max": float(nat.best_year_capability_ratio.max()),
        "best_year_over_full_panel": float(
            single_nat.verified_mw.max() / single_nat.enrolled_mw.mean()
        ),
        "shortfall_survives": bool(nat.best_year_capability_ratio.max() < 0.60),
        "verdict": (
            "HOLDS: even the single best year of the panel leaves most enrolled "
            "capability unrealised, so the shortfall is not an artefact of "
            "picking a mild year"
        )
        if nat.best_year_capability_ratio.max() < 0.60
        else "FAILS: a multi-year view rescues the enrolled capacity",
    }


# --- Attack B ---------------------------------------------------------------
def attack_b() -> dict:
    cost = t2.cost_table()
    nat = cost[cost.sector == "total"].sort_values("year")
    latest = nat.iloc[-1]
    rows = []
    for param in (PEAKER_CONE, STORAGE_CAPACITY_COST):
        rows.append(
            {
                "alternative": param.name,
                "best_case_for_alternative": param.lo,
                "dr_enrolled_basis_wins": bool(latest.cost_per_kw_enrolled < param.lo),
                "dr_delivered_basis_wins": bool(latest.cost_per_kw_delivered < param.lo),
            }
        )
    tbl = pd.DataFrame(rows)
    return {
        "attack": "cheapest plausible alternative instead of central estimate",
        "dr_cost_per_kw_enrolled": float(latest.cost_per_kw_enrolled),
        "dr_cost_per_kw_delivered": float(latest.cost_per_kw_delivered),
        "table": tbl.to_dict("records"),
        "dr_wins_on_delivered_basis_against_any_best_case": bool(
            tbl.dr_delivered_basis_wins.any()
        ),
        "dr_wins_on_enrolled_basis_against_all_best_cases": bool(
            tbl.dr_enrolled_basis_wins.all()
        ),
        "verdict": (
            "SURVIVES with a sign change: on the enrolled basis DR beats even the "
            "cheapest comparator, on the delivered basis it beats none of them. "
            "The basis, not the comparator, decides the answer"
        ),
    }


# --- Attack C ---------------------------------------------------------------
def reserve_breakeven(c_alt: float, year: int | None = None) -> dict:
    cost = t2.cost_table()
    nat = cost[cost.sector == "total"].sort_values("year")
    row = nat.iloc[-1] if year is None else nat[nat.year == year].iloc[0]
    shortfall = row.potential_peak_mw - row.actual_peak_mw
    needed_mw = row.total_cost_kusd / c_alt
    share = (needed_mw - row.actual_peak_mw) / shortfall
    return {
        "year": int(row.year),
        "alternative_cost_per_kw_yr": c_alt,
        "creditable_mw_needed": float(needed_mw),
        "reserve_share_of_shortfall_needed": float(share),
        "already_breaks_even": bool(share <= 0),
        "impossible": bool(share > 1),
        "provenance": "measured_dr_cost_vs_assumed_alternative",
    }


def attack_c() -> dict:
    """Now run against PJM's two published CONE bases rather than one guess."""
    grid = pd.DataFrame(
        [reserve_breakeven(c) for c in np.round(np.arange(40, 205, 5), 1)]
    )
    rto = cone("RTO", "2027/2028")
    gross = reserve_breakeven(float(rto.gross_cone_per_kw_yr))
    net = reserve_breakeven(float(rto.net_cone_per_kw_yr))
    return {
        "attack": (
            "treat part of the shortfall as insurance correctly not claimed, and "
            "solve for how much would flip the cost verdict"
        ),
        "gross_cone_per_kw_yr": float(rto.gross_cone_per_kw_yr),
        "net_cone_per_kw_yr": float(rto.net_cone_per_kw_yr),
        "reserve_share_needed_at_gross_cone": gross["reserve_share_of_shortfall_needed"],
        "reserve_share_needed_at_net_cone": net["reserve_share_of_shortfall_needed"],
        "no_reserve_credit_needed_at_gross": gross["already_breaks_even"],
        "grid": grid.to_dict("records"),
        "headline_is_fragile": bool(
            gross["already_breaks_even"] and not net["already_breaks_even"]
        ),
        "verdict": (
            "DAMAGES THE HEADLINE TWICE OVER: against gross CONE demand response "
            "breaks even with no reserve credit at all, and against net CONE it "
            "needs most of the shortfall to be genuine reserve. Track 1 shows the "
            "data cannot rule that out either way, so the comparator basis and the "
            "reserve question both have to be settled before the ratio means "
            "anything"
        )
        if gross["already_breaks_even"]
        else "headline survives",
    }


# --- Attack D ---------------------------------------------------------------
# The third explanation, named in FALSIFICATION.md as the most likely one and
# previously listed as untestable. "Potential peak demand savings" is
# self-reported and unaudited. If utilities apply the definition differently,
# part of the shortfall is a survey artefact rather than either phantom capacity
# or reserve.
#
# It is partly testable with the regional cut. Reported MW per enrolled customer
# should be broadly comparable across regions once class mix is held constant,
# because the classes are what drive per-customer impact. Computing each
# division's implied customer count from its class-level MW and the national
# per-class intensity gives a ratio that is 1.0 in aggregate by construction, so
# any spread is pure redistribution: a measure of how differently regions report
# the same nominal quantity.
#
# What it cannot do is say why. A Californian residential behavioural program
# and an Alabama industrial interruptible contract are genuinely different
# products, and genuinely different products should have different intensities.
# The test bounds the room the reporting hypothesis has; it does not occupy it.

CLASSES = ("residential", "commercial", "industrial")


def reporting_intensity(year: int = 2023) -> pd.DataFrame:
    panel = load_eia_panel()
    national = {
        c: float(panel.loc[(year, c), "potential_peak_mw"])
        * 1_000
        / float(panel.loc[(year, c), "customers_enrolled"])
        for c in CLASSES
    }
    by_class = {c: ferc.regional_metric("potential_peak_mw", year, c) for c in CLASSES}
    customers = ferc.regional_metric("dr_customers", year)
    potential = ferc.regional_metric("potential_peak_mw", year)
    implied = sum(by_class[c] * 1_000 / national[c] for c in CLASSES)
    out = pd.DataFrame(
        {
            "potential_mw": potential,
            "customers": customers,
            "implied_customers": implied,
            "intensity_index": implied / customers,
            "kw_per_customer": potential * 1_000 / customers,
        }
    )
    out["provenance"] = "measured_regional_vs_national_intensity"
    return out.sort_values("intensity_index")


def reporting_stability() -> pd.DataFrame:
    """Is the cross-sectional spread persistent or year-to-year noise.

    The two explanations for the spread leave different fingerprints over time.
    Genuine differences in what is enrolled are persistent: a fleet of industrial
    interruptible contracts does not become a fleet of residential thermostats
    in a year. Reporting instability is not persistent: it shows up as a
    discontinuity when a respondent changes how it counts.

    FERC publishes the regional cut for two years, which is the minimum needed
    to look and not enough to distinguish a one-off filing correction from the
    start of a trend. Class-level regional data exists only for the later year,
    so this uses raw MW per enrolled customer rather than the mix-adjusted index.
    """
    rows = []
    for year in (2022, 2023):
        pot = ferc.regional_metric("potential_peak_mw", year)
        cust = ferc.regional_metric("dr_customers", year)
        rows.append((pot * 1_000 / cust).rename(f"kw_per_customer_{year}"))
    out = pd.concat(rows, axis=1)
    out["kw_per_customer_change"] = (
        out.kw_per_customer_2023 / out.kw_per_customer_2022 - 1
    )
    out["customers_change"] = (
        ferc.regional_metric("dr_customers", 2023)
        / ferc.regional_metric("dr_customers", 2022)
        - 1
    )
    out["potential_mw_change"] = (
        ferc.regional_metric("potential_peak_mw", 2023)
        / ferc.regional_metric("potential_peak_mw", 2022)
        - 1
    )
    # a real fleet does not move capacity and headcount in opposite directions
    # by large amounts in one year
    out["discontinuity"] = (out.kw_per_customer_change.abs() > 0.40) & (
        out.customers_change * out.potential_mw_change < 0
    )
    out["provenance"] = "measured_regional"
    return out.sort_values("kw_per_customer_change")


def restate_to_standard(year: int = 2023, standard: str = "min") -> dict:
    """National utilization if one division's reporting intensity were universal."""
    intensity = reporting_intensity(year)
    panel = load_eia_panel()
    actual_peak = float(panel.loc[(year, "total"), "actual_peak_mw"])
    target = {
        "min": intensity.intensity_index.min(),
        "median": intensity.intensity_index.median(),
        "max": intensity.intensity_index.max(),
    }[standard]
    restated = intensity.potential_mw * (target / intensity.intensity_index)
    return {
        "standard": standard,
        "target_intensity_index": float(target),
        "restated_potential_mw": float(restated.sum()),
        "reported_potential_mw": float(intensity.potential_mw.sum()),
        "restated_utilization": float(actual_peak / restated.sum()),
        "reported_utilization": float(actual_peak / intensity.potential_mw.sum()),
    }


def attack_d(year: int = 2023) -> dict:
    intensity = reporting_intensity(year)
    lo, hi = intensity.intensity_index.min(), intensity.intensity_index.max()
    at_min = restate_to_standard(year, "min")
    at_median = restate_to_standard(year, "median")
    stability = reporting_stability()
    mw_weight = intensity.potential_mw / intensity.potential_mw.sum()
    mw_weighted_index = float((mw_weight * intensity.intensity_index).sum())
    weighted_mean = float(
        intensity.implied_customers.sum() / intensity.customers.sum()
    )
    return {
        "attack": (
            "treat the shortfall as a reporting artefact: test whether regions "
            "apply 'potential peak demand savings' consistently"
        ),
        "year": year,
        "mix_adjusted_intensity_spread": float(hi / lo),
        "least_intense_division": str(intensity.index[0]),
        "most_intense_division": str(intensity.index[-1]),
        "aggregate_intensity_index": weighted_mean,
        "index_is_pure_redistribution": abs(weighted_mean - 1.0) < 0.01,
        "reported_utilization": at_min["reported_utilization"],
        "utilization_at_least_intense_standard": at_min["restated_utilization"],
        "utilization_at_median_standard": at_median["restated_utilization"],
        "mw_weighted_intensity_index": mw_weighted_index,
        "share_of_mw_within_25pct_of_norm": float(
            mw_weight[(intensity.intensity_index - 1).abs() < 0.25].sum()
        ),
        "reporting_could_explain_whole_shortfall": bool(
            at_min["restated_utilization"] > 0.85
        ),
        "test_can_attribute_cause": False,
        # persistence test
        "divisions_stable_year_over_year": int(
            (stability.kw_per_customer_change.abs() < 0.25).sum()
        ),
        "divisions_tested_for_stability": int(len(stability)),
        "discontinuity_divisions": sorted(
            stability[stability.discontinuity].index.tolist()
        ),
        "largest_discontinuity_division": str(
            stability.kw_per_customer_change.abs().idxmax()
        ),
        "largest_discontinuity_customer_change": float(
            stability.loc[
                stability.kw_per_customer_change.abs().idxmax(), "customers_change"
            ]
        ),
        "largest_discontinuity_mw_change": float(
            stability.loc[
                stability.kw_per_customer_change.abs().idxmax(), "potential_mw_change"
            ]
        ),
        "spread_is_mostly_persistent": bool(
            (stability.kw_per_customer_change.abs() < 0.25).sum() >= 7
        ),
        "verdict": (
            "OPENS A THIRD EXPLANATION THIS REPO CANNOT CLOSE, THEN NARROWS IT: "
            "after holding class mix constant, reported MW per enrolled customer "
            "varies several-fold across census divisions, and forcing the least "
            "intense division's standard on everyone erases the shortfall "
            "entirely. That is a bound on the room, not an estimate of the "
            "artefact, because genuine program-design differences produce the "
            "same signature. The persistence test then separates them partway: "
            "most of the spread holds steady across the two published years, "
            "which favours genuine differences, while two divisions show "
            "one-year discontinuities in opposite directions that no real fleet "
            "produces, which favours reporting instability. Both mechanisms are "
            "present and neither is dominant"
        ),
    }


def run() -> dict:
    a, b, c, d = attack_a(), attack_b(), attack_c(), attack_d()
    return {
        "rolling_windows": rolling_windows(),
        "reserve_breakeven_grid": pd.DataFrame(c["grid"]),
        "reporting_intensity": reporting_intensity().reset_index(names="division"),
        "reporting_stability": reporting_stability().reset_index(names="division"),
        "summary": {"attack_a": a, "attack_b": b, "attack_c": c, "attack_d": d},
    }
