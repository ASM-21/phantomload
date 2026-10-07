"""Capstone. Is demand response cheap capacity, under every defensible pairing.

Six of the eight tracks end in the same place: the measured quantity is solid
and the contested step is the accounting convention wrapped around it. This
module stops treating that as a caveat and makes it the object of study.

The cost comparison in track 2 requires three separate basis alignments, and
the public record aligns none of them:

  NETTING       PJM prices its peaker gross and net of expected energy and
                ancillary revenue. EIA reports demand response cost gross only,
                with nothing subtracted for the energy a curtailment avoids
                buying. Track 2's `netting_bound` shows how far that can move.

  ACCREDITATION PJM's cost of new entry is quoted per nameplate MW, but the
                capacity market pays per accredited MW, and the reference
                resource accredits at about 77%. Dividing demand response cost
                by realised MW while dividing the peaker's by nameplate MW
                haircuts one side and not the other. The accreditation factor
                used here is not assumed: it is recovered from PJM's own table
                by dividing its net CONE in ICAP dollars per MW-year by its net
                CONE in UCAP dollars per MW-day.

  UTILIZATION   Demand response can be priced per enrolled kW or per delivered
                kW, and track 1 shows the data cannot say which is right,
                because it cannot separate capacity that was never called from
                capacity that would not have delivered.

Eight cells, two of which demand response loses. Both losses are the same
pairing, and applying the corrections that pairing's own inconsistency implies
moves the answer onto the one quantity nobody publishes.
"""

from __future__ import annotations

import pandas as pd

from .shared.calibration import (
    DR_ELCC,
    ENERGY_VALUE,
    annual_avg_lmp,
    cone,
    cone_table,
)
from .tracks import t2_cost as t2

LATEST_BRA = "2027/2028"


def accreditation_factor(delivery_year: str = LATEST_BRA) -> float:
    """Recovered from PJM's table rather than assumed.

    net CONE (ICAP $/MW-yr) / 365 / net CONE (UCAP $/MW-day) = accreditation.
    Computed on the RTO row; the LDA rows imply the same factor to three
    decimals apart from rounding on the smallest net CONE values.
    """
    row = cone("RTO", delivery_year)
    return float(
        row.net_cone_icap_usd_per_mw_yr / 365 / row.net_cone_ucap_usd_per_mw_day
    )


def comparator_grid(delivery_year: str = LATEST_BRA) -> pd.DataFrame:
    factor = accreditation_factor(delivery_year)
    row = cone("RTO", delivery_year)
    return pd.DataFrame(
        [
            {
                "comparator": f"{basis} CONE",
                "accreditation": acc,
                "cost_per_kw_yr": value / (factor if acc == "accredited" else 1.0),
                "netted_of_energy_revenue": basis == "net",
                "provenance": "measured_pjm",
            }
            for basis, value in (
                ("gross", float(row.gross_cone_per_kw_yr)),
                ("net", float(row.net_cone_per_kw_yr)),
            )
            for acc in ("nameplate", "accredited")
        ]
    )


def dr_bases() -> pd.DataFrame:
    cost = t2.cost_table()
    nat = cost[cost.sector == "total"].sort_values("year").iloc[-1]
    return pd.DataFrame(
        [
            {
                "dr_basis": "per kW enrolled",
                "cost_per_kw_yr": float(nat.cost_per_kw_enrolled),
                "haircut_for_non_delivery": False,
                "year": int(nat.year),
            },
            {
                "dr_basis": "per kW delivered",
                "cost_per_kw_yr": float(nat.cost_per_kw_delivered),
                "haircut_for_non_delivery": True,
                "year": int(nat.year),
            },
        ]
    )


def verdict_table() -> pd.DataFrame:
    """Every pairing, with the inconsistency each one carries named."""
    rows = []
    for _, dr in dr_bases().iterrows():
        for _, comp in comparator_grid().iterrows():
            ratio = dr.cost_per_kw_yr / comp.cost_per_kw_yr
            inconsistencies = []
            if comp.netted_of_energy_revenue:
                inconsistencies.append("comparator netted, demand response not")
            if dr.haircut_for_non_delivery and comp.accreditation == "nameplate":
                inconsistencies.append("demand response haircut, comparator not")
            if not dr.haircut_for_non_delivery and comp.accreditation == "accredited":
                inconsistencies.append("comparator haircut, demand response not")
            rows.append(
                {
                    "dr_basis": dr.dr_basis,
                    "comparator": comp.comparator,
                    "accreditation": comp.accreditation,
                    "dr_cost_per_kw_yr": dr.cost_per_kw_yr,
                    "comparator_cost_per_kw_yr": comp.cost_per_kw_yr,
                    "ratio": ratio,
                    "dr_wins": ratio < 1,
                    "inconsistencies": "; ".join(inconsistencies) or "none",
                    "n_inconsistencies": len(inconsistencies),
                    "provenance": "measured_both_sides",
                }
            )
    return pd.DataFrame(rows).sort_values(["n_inconsistencies", "ratio"])


def aligned_comparison() -> pd.DataFrame:
    """The only fully aligned cell: both sides netted, both accredited.

    Demand response cost per delivered kW, less the value of the energy the
    curtailment avoided buying, against net CONE per accredited kW. Every term
    is measured except the energy price, which is swept. That is the finding:
    align all three bases and the answer turns entirely on the one quantity
    nobody publishes.
    """
    factor = accreditation_factor()
    net_accredited = float(cone("RTO", LATEST_BRA).net_cone_per_kw_yr) / factor
    grid = t2.netting_bound()
    out = grid.copy()
    out["net_cone_accredited_per_kw_yr"] = net_accredited
    out["clears_aligned"] = out.netted_dr_cost_per_kw_yr < net_accredited
    out["gap_remaining_aligned"] = out.netted_dr_cost_per_kw_yr - net_accredited
    return out[
        [
            "hours_basis",
            "implied_event_hours",
            "energy_price_usd_per_kwh",
            "netted_dr_cost_per_kw_yr",
            "net_cone_accredited_per_kw_yr",
            "clears_aligned",
            "gap_remaining_aligned",
        ]
    ].assign(provenance="measured_except_energy_price")


def breakeven_energy_price() -> dict:
    """What the avoided energy would have to be worth, in the aligned cell."""
    factor = accreditation_factor()
    net_accredited = float(cone("RTO", LATEST_BRA).net_cone_per_kw_yr) / factor
    dr = dr_bases().set_index("dr_basis").loc["per kW delivered", "cost_per_kw_yr"]
    grid = t2.netting_bound()
    hours = sorted(grid.implied_event_hours.unique())
    return {
        "net_cone_accredited_per_kw_yr": net_accredited,
        "dr_delivered_per_kw_yr": float(dr),
        "credit_needed_per_kw_yr": float(dr - net_accredited),
        "breakeven_price_at_high_hours": float((dr - net_accredited) / max(hours)),
        "breakeven_price_at_low_hours": float((dr - net_accredited) / min(hours)),
        "high_hours": float(max(hours)),
        "low_hours": float(min(hours)),
        "inside_swept_price_range": bool(
            (dr - net_accredited) / max(hours) <= ENERGY_VALUE.hi
        ),
        "pjm_annual_avg_lmp_per_kwh": annual_avg_lmp(),
        "multiple_of_annual_avg_needed": float(
            ((dr - net_accredited) / max(hours)) / annual_avg_lmp()
        ),
        "implication": (
            "clearing requires demand response to be dispatched almost entirely "
            "into scarcity-priced hours, which makes the answer a question about "
            "dispatch timing rather than about enrolled capacity"
        ),
    }


def elcc_comparison() -> pd.DataFrame:
    """Accredit both sides the way the field accredits them.

    The verdict grid above haircuts demand response by its dispatch utilization,
    which this repository reached on its own and which the resource adequacy
    literature does not use. That literature accredits supply-side resources by
    effective load carrying capability or a performance-based derate, and
    accredits demand-side resources from measured load reductions against a
    counterfactual baseline. The two methods are not the same, which is the
    asymmetry the synthesis identified, and it is a named and litigated problem
    rather than a new one. See PRIOR_WORK.md.

    Applying an ELCC to demand response instead of its dispatch utilization matters
    a great deal, because they are different quantities. ELCC asks what fraction
    of enrolled capacity is dependable during critical hours. The dispatch utilization
    ratio also counts the years nothing was called, so it is systematically
    harsher, and the gap between 39% and roughly 83% is the size of that
    difference.
    """
    factor = accreditation_factor()
    row = cone("RTO", LATEST_BRA)
    dr_enrolled = float(
        dr_bases().set_index("dr_basis").loc["per kW enrolled", "cost_per_kw_yr"]
    )
    dr_delivered = float(
        dr_bases().set_index("dr_basis").loc["per kW delivered", "cost_per_kw_yr"]
    )
    rows = []
    for label, elcc in (
        ("winter four-hour", DR_ELCC.lo),
        ("summer four-hour", DR_ELCC.central),
        ("summer ten-hour", DR_ELCC.hi),
    ):
        dr_accredited = dr_enrolled / elcc
        for basis, cone_icap in (
            ("gross", float(row.gross_cone_per_kw_yr)),
            ("net", float(row.net_cone_per_kw_yr)),
        ):
            comparator = cone_icap / factor
            rows.append(
                {
                    "dr_elcc_case": label,
                    "dr_elcc": elcc,
                    "dr_cost_per_accredited_kw": dr_accredited,
                    "comparator": f"{basis} CONE, accredited",
                    "comparator_cost_per_kw": comparator,
                    "ratio": dr_accredited / comparator,
                    "dr_wins": dr_accredited < comparator,
                    "vs_delivered_basis_ratio": dr_delivered / comparator,
                    "provenance": "measured_cost_literature_accreditation",
                }
            )
    return pd.DataFrame(rows)


def elcc_summary() -> dict:
    df = elcc_comparison()
    central = df[df.dr_elcc_case == "summer four-hour"]
    delivered_cost = float(
        dr_bases().set_index("dr_basis").loc["per kW delivered", "cost_per_kw_yr"]
    )
    enrolled = float(
        dr_bases().set_index("dr_basis").loc["per kW enrolled", "cost_per_kw_yr"]
    )
    return {
        "dr_elcc_central": DR_ELCC.central,
        "dispatch_utilization_used_elsewhere": enrolled / delivered_cost,
        "elcc_over_dispatch_utilization": DR_ELCC.central / (enrolled / delivered_cost),
        "dr_cost_per_accredited_kw_central": float(
            central.dr_cost_per_accredited_kw.iloc[0]
        ),
        "dr_cost_per_delivered_kw": delivered_cost,
        "accreditation_choice_moves_cost_by": delivered_cost
        / float(central.dr_cost_per_accredited_kw.iloc[0]),
        "cells": int(len(df)),
        "dr_wins_cells": int(df.dr_wins.sum()),
        "dr_wins_all_gross": bool(
            df[df.comparator.str.startswith("gross")].dr_wins.all()
        ),
        "dr_wins_all_net": bool(df[df.comparator.str.startswith("net")].dr_wins.all()),
        "worst_case": str(df.loc[df.ratio.idxmax(), "dr_elcc_case"]),
        "worst_ratio": float(df.ratio.max()),
        # how narrowly the one lost cell is lost, and the ELCC that would win it
        "worst_margin": float(df.ratio.max() - 1.0),
        "worst_elcc_to_win": float(
            enrolled / df.loc[df.ratio.idxmax(), "comparator_cost_per_kw"]
        ),
        # the same cell at 0.50, the value used under the winter label until
        # v0.4.3, which is E3's four-hour figure at 6 GW of adoption
        "worst_margin_at_superseded_value": float(
            enrolled / 0.50 / df.loc[df.ratio.idxmax(), "comparator_cost_per_kw"] - 1.0
        ),
        "splices": ["SPP ELCC applied to national cost", "2025 adoption level"],
    }


def headline_sweep() -> pd.DataFrame:
    """Attack the headline's analyst choices, one at a time.

    "Demand response wins 6 of 8 pairings" rests on three choices made once:
    the cost year (the latest), the comparator delivery year (the latest
    auction), and the zone (the RTO). Each is swept here and the outcome
    recorded whether or not the claim survives. A sweep that cannot vary on the
    data at hand is labelled vacuous rather than counted as robustness.
    """
    cost = t2.cost_table()
    nat = cost[cost.sector == "total"].sort_values("year")
    table = cone_table()
    rows = []
    for _, dr in nat.iterrows():
        for bra in sorted(table.delivery_year.unique()):
            for location in sorted(table.location.unique()):
                row = table[(table.location == location) & (table.delivery_year == bra)].iloc[0]
                factor = float(
                    row.net_cone_icap_usd_per_mw_yr / 365 / row.net_cone_ucap_usd_per_mw_day
                )
                wins = 0
                for dr_cost in (dr.cost_per_kw_enrolled, dr.cost_per_kw_delivered):
                    for icap in (row.gross_cone_per_kw_yr, row.net_cone_per_kw_yr):
                        for acc in (1.0, factor):
                            wins += int(dr_cost < icap / acc)
                rows.append(
                    {
                        "dr_cost_year": int(dr.year),
                        "delivery_year": bra,
                        "location": location,
                        "dr_wins_of_8": wins,
                        "provenance": "measured_both_sides",
                    }
                )
    return pd.DataFrame(rows)


def headline_sweep_summary() -> dict:
    sw = headline_sweep()
    rto_latest = sw[(sw.location == "RTO") & (sw.delivery_year == LATEST_BRA)]
    by_year = rto_latest.set_index("dr_cost_year").dr_wins_of_8
    return {
        "configurations": int(len(sw)),
        "dr_wins_min": int(sw.dr_wins_of_8.min()),
        "dr_wins_max": int(sw.dr_wins_of_8.max()),
        "share_of_configurations_where_dr_wins_majority": float(
            (sw.dr_wins_of_8 >= 5).mean()
        ),
        "rto_cost_years_tested": int(len(by_year)),
        "rto_wins_min_across_cost_years": int(by_year.min()),
        "rto_wins_max_across_cost_years": int(by_year.max()),
        "headline_6_of_8_holds_every_cost_year": bool((by_year == 6).all()),
        "worst_configuration": str(
            sw.loc[sw.dr_wins_of_8.idxmin(), ["dr_cost_year", "delivery_year", "location"]]
            .to_dict()
        ),
        "delivery_years_available": int(sw.delivery_year.nunique()),
        "delivery_year_sweep_vacuous": bool(sw.delivery_year.nunique() < 2),
    }


def summary() -> dict:
    v = verdict_table()
    clean = v[v.n_inconsistencies == 0]
    be = breakeven_energy_price()
    aligned = aligned_comparison()
    return {
        "cells": int(len(v)),
        "dr_wins_cells": int(v.dr_wins.sum()),
        "dr_loses_cells": int((~v.dr_wins).sum()),
        "losing_pairings": sorted(
            f"{r.dr_basis} vs {r.comparator} ({r.accreditation})"
            for _, r in v[~v.dr_wins].iterrows()
        ),
        "internally_consistent_cells": int(len(clean)),
        "dr_wins_among_consistent": int(clean.dr_wins.sum()),
        "accreditation_factor": accreditation_factor(),
        "widest_ratio": float(v.ratio.max()),
        "narrowest_ratio": float(v.ratio.min()),
        "ratio_spread": float(v.ratio.max() / v.ratio.min()),
        "aligned_cells_that_clear": int(aligned.clears_aligned.sum()),
        "aligned_cells": int(len(aligned)),
        **{f"breakeven_{k}": v_ for k, v_ in be.items()},
        **{f"elcc_{k}": v_ for k, v_ in elcc_summary().items()},
        **{f"sweep_{k}": v_ for k, v_ in headline_sweep_summary().items()},
    }


def run() -> dict:
    return {
        "verdicts": verdict_table(),
        "comparators": comparator_grid(),
        "aligned": aligned_comparison(),
        "elcc": elcc_comparison(),
        "headline_sweep": headline_sweep(),
        "summary": summary(),
    }
