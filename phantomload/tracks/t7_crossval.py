"""Track 7. Does the utilization ratio survive a second, independent estimate.

> **RETRACTED.** The first version of this track concluded that no genuine
> two-method cross-validation was possible with public data, because EIA
> collects no dispatch-event count. That was wrong, and wrong in the way that
> matters: a claim about the world made from having looked in one place. FERC's
> annual assessment publishes wholesale demand response registrations reported
> by the seven RTOs and ISOs, which is a second measurement of demand response
> capacity by different reporters using different methods, plus deployment
> figures from real events. The corrected finding is below. It is weaker than a
> clean validation and more useful than the retraction it replaces.

MEASURED throughout, from three separate reporters: EIA for the retail series,
the RTOs and ISOs for wholesale registrations, and FERC for the event and
enforcement record. Nothing in this track is modelled.

Three candidate second estimators, in ascending order of usefulness.

1. The energy column, from the same EIA table. Not independent, not the same
   estimand, and it carries a reclassification break the peak column does not.
   Kept below because ruling it out is part of the answer.

2. Wholesale registrations from the RTO and ISO reports. Genuinely independent
   reporters. Measures a partly disjoint population: EIA counts programs run by
   utilities, RTO reports count registrations in wholesale markets, many of them
   third-party aggregations that appear nowhere in EIA's numbers. The two totals
   are the same order of magnitude and must not be added.

3. Deployment during a real event. PJM registered 8,526 MW of demand response
   for 2024 and deployed more than 4,000 MW during the June 2025 heat event, at
   the third-highest system peak in its history. That is a dispatch utilization in
   the same range as the national retail figure, reached by a different route.

What none of them do is resolve the identification problem from track 1. The
wholesale figure inherits it exactly: PJM deployed what it chose to call, so the
unrealised remainder is again either capacity that was not needed or capacity
that was not there.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..shared import ferc
from ..shared.dr_program import SECTORS, Provenance, load_eia_panel

RECLASSIFICATION_YEAR = 2023  # EIA footnote on table 10.3


def implied_hours_table() -> pd.DataFrame:
    wide = load_eia_panel().reset_index()
    df = wide[
        ["year", "sector", "potential_peak_mw", "actual_peak_mw", "energy_savings_mwh"]
    ].copy()
    df = df.dropna(subset=["actual_peak_mw", "energy_savings_mwh"])
    df["utilization_peak_basis"] = df["actual_peak_mw"] / df["potential_peak_mw"]
    df["implied_event_hours"] = df["energy_savings_mwh"] / df["actual_peak_mw"]
    df["implied_event_hours_on_enrolled"] = (
        df["energy_savings_mwh"] / df["potential_peak_mw"]
    )
    df["era"] = np.where(
        df.year >= RECLASSIFICATION_YEAR, "post_reclassification", "pre_reclassification"
    )
    df["provenance"] = Provenance.MEASURED.value
    return df.sort_values(["sector", "year"])


def structural_break() -> pd.DataFrame:
    """How each series moves across the 2023 filing change, by sector."""
    df = implied_hours_table()
    rows = []
    for sector in list(SECTORS) + ["total"]:
        s = df[df.sector == sector]
        pre = s[s.era == "pre_reclassification"]
        post = s[s.era == "post_reclassification"]
        if pre.empty or post.empty:
            continue
        rows.append(
            {
                "sector": sector,
                "energy_pre_mean_mwh": pre.energy_savings_mwh.mean(),
                "energy_post_mean_mwh": post.energy_savings_mwh.mean(),
                "energy_change": post.energy_savings_mwh.mean()
                / pre.energy_savings_mwh.mean()
                - 1,
                "actual_peak_pre_mean_mw": pre.actual_peak_mw.mean(),
                "actual_peak_post_mean_mw": post.actual_peak_mw.mean(),
                "actual_peak_change": post.actual_peak_mw.mean()
                / pre.actual_peak_mw.mean()
                - 1,
                "utilization_pre": pre.utilization_peak_basis.mean(),
                "utilization_post": post.utilization_peak_basis.mean(),
                "utilization_change": post.utilization_peak_basis.mean()
                / pre.utilization_peak_basis.mean()
                - 1,
                "implied_hours_pre": pre.implied_event_hours.mean(),
                "implied_hours_post": post.implied_event_hours.mean(),
                "implied_hours_change": post.implied_event_hours.mean()
                / pre.implied_event_hours.mean()
                - 1,
                "provenance": Provenance.MEASURED.value,
            }
        )
    return pd.DataFrame(rows)


def plausibility_check() -> pd.DataFrame:
    """Are the implied event hours consistent with how DR programs are run.

    A typical incentive-based curtailment program contracts for something like
    10 to 15 events a year of 2 to 6 hours, so tens of hours annually. A number
    in the hundreds means the reported energy is not coming from discrete
    dispatch events, which would make the energy column a different animal from
    the peak column rather than a second view of it. The bounds below are a
    stated assumption about program design, not a measurement.
    """
    df = implied_hours_table()
    latest = df[df.year == df.year.max()]
    pre = df[(df.year == RECLASSIFICATION_YEAR - 1)]
    out = pre[["sector", "implied_event_hours"]].merge(
        latest[["sector", "implied_event_hours"]],
        on="sector",
        suffixes=("_2022", "_latest"),
    )
    out["exceeds_60h_in_2022"] = out.implied_event_hours_2022 > 60
    out["exceeds_60h_latest"] = out.implied_event_hours_latest > 60
    out["provenance"] = "measured_ratio_vs_assumed_program_design"
    return out


# --- estimator 2: wholesale registrations -----------------------------------
def wholesale_table() -> pd.DataFrame:
    df = ferc.rto().copy()
    df["provenance"] = "measured_rto_reported"
    return df.sort_values(["year", "market"])


def retail_vs_wholesale() -> pd.DataFrame:
    """The two accountings side by side, in the years they overlap."""
    panel = load_eia_panel()
    rto = ferc.rto()
    rows = []
    for year in (2023, 2024):
        retail = float(panel.loc[(year, "total"), "potential_peak_mw"])
        retail_actual = float(panel.loc[(year, "total"), "actual_peak_mw"])
        wholesale = float(
            rto[(rto.market == "All RTO/ISO") & (rto.year == year)].dr_resources_mw.iloc[0]
        )
        rows.append(
            {
                "year": year,
                "retail_potential_mw": retail,
                "retail_actual_mw": retail_actual,
                "wholesale_registered_mw": wholesale,
                "wholesale_over_retail_potential": wholesale / retail,
                "naive_sum_mw": retail + wholesale,
                "populations_disjoint": False,
                "overlap_published": False,
                "provenance": "measured_two_sources",
            }
        )
    return pd.DataFrame(rows)


def pjm_event_utilization() -> dict:
    """Deployment against registration, from the one event FERC quantifies."""
    reg = ferc.PJM_JUNE_2025["registered_dr_mw_2024"]
    deployed = ferc.PJM_JUNE_2025["dr_deployed_mw_at_least"]
    panel = load_eia_panel()
    national_u = float(
        panel.loc[(2024, "total"), "actual_peak_mw"]
        / panel.loc[(2024, "total"), "potential_peak_mw"]
    )
    return {
        "market": "PJM",
        "registered_mw": reg,
        "deployed_mw_at_least": deployed,
        "utilization_at_least": deployed / reg,
        "is_a_lower_bound": True,
        "national_retail_utilization_2024": national_u,
        "same_order_of_magnitude": abs(deployed / reg - national_u) < 0.15,
        "system_peak_mw": ferc.PJM_JUNE_2025["system_peak_mw"],
        "identification_resolved": False,
        "note": (
            "PJM deployed what it chose to call, so the unrealised remainder is "
            "the same ambiguity track 1 describes, not a performance measurement"
        ),
    }


def documented_double_registration() -> pd.DataFrame:
    """Registration-level double counting, from the regulatory record.

    Track 5 models double counting between a tariff and a program. These are the
    same failure one level up, between two wholesale programs, and they are
    documented rather than modelled.
    """
    return pd.DataFrame(
        [
            {
                "market": "MISO",
                "docket": "ER25-2050-000",
                "accepted": "2025-07-18",
                "issue": (
                    "resources could register as both Emergency Demand Response "
                    "and Load Modifying Resource, drawing capacity payments while "
                    "reducing the chance of being called as either"
                ),
                "resolution": "dual registration removed",
                "provenance": Provenance.MEASURED.value,
            },
            {
                "market": "PJM",
                "docket": "n/a",
                "accepted": "",
                "issue": (
                    "Economic and Load Management registrations may include the "
                    "same resource, so PJM reports a de-duplicated unique MW total"
                ),
                "resolution": "reported as unique MW",
                "provenance": Provenance.MEASURED.value,
            },
        ]
    )


def enforcement_cases() -> pd.DataFrame:
    """Capacity that was registered and did not exist, as adjudicated.

    These establish that literal phantom capacity happens and is prosecutable.
    They do not explain the aggregate shortfall: the disgorgement amounts imply
    a footprint orders of magnitude smaller than the roughly 19 GW gap between
    national potential and actual peak savings.
    """
    return pd.DataFrame(
        [
            {
                "respondent": name,
                "year": info["year"],
                "market": info["market"],
                "adjudicated": info["adjudicated"],
                "finding": info["finding"],
                "disgorgement_usd": info["disgorgement_usd"],
                "civil_penalty_usd": info["civil_penalty_usd"],
                "provenance": Provenance.MEASURED.value,
            }
            for name, info in ferc.ENFORCEMENT.items()
        ]
    )


def summary() -> dict:
    br = structural_break().set_index("sector")
    tot = br.loc["total"]
    df = implied_hours_table()
    nat = df[df.sector == "total"]
    rv = retail_vs_wholesale().set_index("year")
    pjm = pjm_event_utilization()
    enf = enforcement_cases()
    wholesale_2024 = wholesale_table().query(
        "year == 2024 and market != 'All RTO/ISO'"
    )
    return {
        "second_estimator_exists": True,
        "retracted_claim": (
            "no genuine two-method cross-validation is possible with public data"
        ),
        "energy_column_is_independent": False,
        "energy_change_at_break": float(tot.energy_change),
        "actual_peak_change_at_break": float(tot.actual_peak_change),
        "utilization_change_at_break": float(tot.utilization_change),
        "implied_hours_2022_total": float(
            nat[nat.year == 2022].implied_event_hours.iloc[0]
        ),
        "implied_hours_latest_total": float(nat.implied_event_hours.iloc[-1]),
        "residential_implied_hours_2022": float(
            df[(df.sector == "residential") & (df.year == 2022)].implied_event_hours.iloc[0]
        ),
        "industrial_implied_hours_2022": float(
            df[(df.sector == "industrial") & (df.year == 2022)].implied_event_hours.iloc[0]
        ),
        "wholesale_registered_mw_2024": float(rv.loc[2024, "wholesale_registered_mw"]),
        "retail_potential_mw_2023": float(rv.loc[2023, "retail_potential_mw"]),
        "wholesale_over_retail_2023": float(
            rv.loc[2023, "wholesale_over_retail_potential"]
        ),
        "largest_wholesale_market": str(
            wholesale_2024.set_index("market").dr_resources_mw.idxmax()
        ),
        "markets_counted": int(len(wholesale_2024)),
        "totals_may_be_added": False,
        "pjm_utilization_at_least": pjm["utilization_at_least"],
        "pjm_registered_mw": pjm["registered_mw"],
        "estimators_agree_in_magnitude": pjm["same_order_of_magnitude"],
        "identification_resolved": False,
        "documented_double_registration_cases": int(
            len(documented_double_registration())
        ),
        "enforcement_cases": int(len(enf)),
        "enforcement_total_penalties_usd": float(enf.civil_penalty_usd.sum()),
        "enforcement_total_disgorgement_usd": float(enf.disgorgement_usd.sum()),
    }


def run() -> dict:
    return {
        "implied_hours": implied_hours_table(),
        "structural_break": structural_break(),
        "plausibility": plausibility_check(),
        "wholesale": wholesale_table(),
        "retail_vs_wholesale": retail_vs_wholesale(),
        "double_registration": documented_double_registration(),
        "enforcement": enforcement_cases(),
        "summary": summary(),
    }
