"""Track 2. Does DR still look cheap once you price it per kW actually delivered.

MEASURED for DR's own cost: EIA-861 publishes customer incentives and all other
costs by sector, 2015-2024, alongside the enrolled and verified MW. So both
sides of the ratio are real numbers.

MEASURED for the comparator too, as of this version. PJM publishes gross CONE,
the energy and ancillary services revenue offset, and net CONE for the RTO and
every modelled locational deliverability area. The first version of this track
swept an assumed range instead and got the range wrong: it ran 80 to 150 dollars
per kW-year and excluded net CONE, which is where the comparison is actually
decided.

The comparison still cannot be closed, but for a nameable reason rather than
uncertainty. EIA demand response costs are gross: nothing is netted off for the
energy purchases a curtailment avoids. PJM publishes its peaker both ways, and
the offset is more than half of gross CONE for the RTO. So gross-to-gross is the
basis-consistent pairing and it flatters demand response, while net CONE is what
the capacity market actually pays and comparing it to an un-netted demand
response cost is inconsistent in demand response's disfavour. Both are reported.

Design call, and the thing this track exists to say. Dividing program cost by
verified rather than enrolled MW is only the right move if the shortfall is
capacity that would fail to deliver when called. If the shortfall is capacity
that was correctly never called, the delivered-basis cost overstates the true
cost of a capacity product, because insurance you did not claim on is not
wasted money. Track 1 shows the data cannot tell those apart. Both bases are
therefore reported side by side and neither is presented as the true one.
"""

from __future__ import annotations

import pandas as pd

from ..shared.calibration import (
    ENERGY_VALUE,
    annual_avg_lmp,
    PEAKER_CONE,
    STORAGE_CAPACITY_COST,
    cone,
    cone_table,
)
from ..shared.dr_program import load_eia_panel
from ..shared.dr_program import SECTORS, Provenance, load_eia_panel

COST_YEARS = (2015, 2024)  # EIA publishes DR program costs only for these years


def cost_table() -> pd.DataFrame:
    """Cost per kW-year on both bases. $1k / 1 MW == $1 / 1 kW, so the
    thousand-dollar cost columns divide straight into MW to give $/kW-year."""
    wide = load_eia_panel().reset_index()
    df = wide[
        [
            "year",
            "sector",
            "potential_peak_mw",
            "actual_peak_mw",
            "customer_incentives_kusd",
            "other_costs_kusd",
        ]
    ].copy()
    df = df.dropna(subset=["customer_incentives_kusd", "other_costs_kusd"])
    df["total_cost_kusd"] = df["customer_incentives_kusd"] + df["other_costs_kusd"]
    df["utilization"] = df["actual_peak_mw"] / df["potential_peak_mw"]
    df["cost_per_kw_enrolled"] = df["total_cost_kusd"] / df["potential_peak_mw"]
    df["cost_per_kw_delivered"] = df["total_cost_kusd"] / df["actual_peak_mw"]
    df["basis_gap_ratio"] = df["cost_per_kw_delivered"] / df["cost_per_kw_enrolled"]
    df["provenance"] = Provenance.MEASURED.value
    return df.sort_values(["sector", "year"])


def identity_check() -> pd.DataFrame:
    """cost_per_kw_delivered == cost_per_kw_enrolled / utilization.

    Tagged IDENTITY, not a finding. It is here because the whole repo turns on
    it and because a test asserting it holds to 1e-9 catches unit slips.
    """
    df = cost_table()
    df = df.assign(
        implied=df["cost_per_kw_enrolled"] / df["utilization"],
        abs_err=(df["cost_per_kw_enrolled"] / df["utilization"] - df["cost_per_kw_delivered"]).abs(),
    )
    return df[
        ["year", "sector", "cost_per_kw_delivered", "implied", "abs_err"]
    ].assign(provenance=Provenance.IDENTITY.value)


def breakeven_table() -> pd.DataFrame:
    """For each sector-year, the alternative cost at which DR flips.

    On the delivered basis the breakeven IS the delivered cost. On the enrolled
    basis it is the enrolled cost. The spread between them is the range of
    comparator costs where the two framings give opposite answers, which is the
    number worth reporting.
    """
    df = cost_table()
    out = df[
        ["year", "sector", "utilization", "cost_per_kw_enrolled", "cost_per_kw_delivered"]
    ].copy()
    out["ambiguous_low"] = out["cost_per_kw_enrolled"]
    out["ambiguous_high"] = out["cost_per_kw_delivered"]
    out["ambiguous_width"] = out["ambiguous_high"] - out["ambiguous_low"]
    out["cone_range_straddles"] = (PEAKER_CONE.lo < out["ambiguous_high"]) & (
        PEAKER_CONE.hi > out["ambiguous_low"]
    )
    out["provenance"] = "measured_dr_cost_vs_assumed_alternative"
    return out


def comparator_sweep(sector: str = "total", year: int | None = None) -> pd.DataFrame:
    """Verdict as a function of the assumed alternative cost."""
    df = cost_table()
    df = df[df.sector == sector]
    year = int(df.year.max()) if year is None else year
    row = df[df.year == year].iloc[0]
    rows = []
    for param in (PEAKER_CONE, STORAGE_CAPACITY_COST):
        for c_alt in param.sweep(11):
            rows.append(
                {
                    "year": year,
                    "sector": sector,
                    "alternative": param.name,
                    "alternative_cost_per_kw_yr": round(c_alt, 2),
                    "dr_cheaper_on_enrolled_basis": row.cost_per_kw_enrolled < c_alt,
                    "dr_cheaper_on_delivered_basis": row.cost_per_kw_delivered < c_alt,
                    "framings_disagree": (row.cost_per_kw_enrolled < c_alt)
                    != (row.cost_per_kw_delivered < c_alt),
                    "provenance": param.provenance.value,
                }
            )
    return pd.DataFrame(rows)


def pjm_comparison(year: int | None = None) -> pd.DataFrame:
    """Demand response against PJM's published peaker, by LDA and basis.

    Breakeven utilization is the utilization at which the two are level:
        u* = cost_per_kw_enrolled / comparator
    Measured utilization above u* means demand response wins on the delivered
    basis. A u* above 1 means it cannot win at any utilization, because its
    enrolled-basis cost alone already exceeds the comparator.
    """
    dr = cost_table()
    nat = dr[dr.sector == "total"].sort_values("year")
    row = nat.iloc[-1] if year is None else nat[nat.year == year].iloc[0]
    out = cone_table().copy()
    out["dr_year"] = int(row.year)
    out["dr_utilization"] = row.utilization
    out["dr_cost_per_kw_enrolled"] = row.cost_per_kw_enrolled
    out["dr_cost_per_kw_delivered"] = row.cost_per_kw_delivered
    for basis in ("gross", "net"):
        comparator = out[f"{basis}_cone_per_kw_yr"]
        out[f"breakeven_utilization_vs_{basis}"] = row.cost_per_kw_enrolled / comparator
        out[f"dr_wins_delivered_vs_{basis}"] = row.cost_per_kw_delivered < comparator
        out[f"unwinnable_vs_{basis}"] = row.cost_per_kw_enrolled > comparator
    out["provenance"] = "measured_both_sides"
    return out


def basis_sensitivity() -> pd.DataFrame:
    """How much of the answer is each side's denominator choice worth.

    Demand response has two cost bases and the peaker has two CONE bases. The
    spread each contributes says which denominator matters more, and they turn
    out to be the same order of magnitude, so neither can be waved through.
    """
    dr = cost_table()
    nat = dr[dr.sector == "total"].sort_values("year").iloc[-1]
    rto = cone_table()
    rto = rto[(rto.location == "RTO") & (rto.delivery_year == "2027/2028")].iloc[0]
    return pd.DataFrame(
        [
            {
                "side": "demand response",
                "low_basis": "per kW enrolled",
                "low_value": nat.cost_per_kw_enrolled,
                "high_basis": "per kW delivered",
                "high_value": nat.cost_per_kw_delivered,
                "spread_ratio": nat.cost_per_kw_delivered / nat.cost_per_kw_enrolled,
                "provenance": "measured",
            },
            {
                "side": "pjm peaker",
                "low_basis": "net CONE",
                "low_value": rto.net_cone_per_kw_yr,
                "high_basis": "gross CONE",
                "high_value": rto.gross_cone_per_kw_yr,
                "spread_ratio": rto.gross_cone_per_kw_yr / rto.net_cone_per_kw_yr,
                "provenance": "measured",
            },
        ]
    )


def years_that_beat_gross_cone() -> pd.DataFrame:
    """The margin against gross CONE is thin. Which years clear it."""
    dr = cost_table()
    nat = dr[dr.sector == "total"].sort_values("year").copy()
    gross = float(
        cone_table().query("location == 'RTO' and delivery_year == '2027/2028'")
        .gross_cone_per_kw_yr.iloc[0]
    )
    nat["gross_cone_per_kw_yr"] = gross
    nat["breakeven_utilization"] = nat.cost_per_kw_enrolled / gross
    nat["clears_gross_cone"] = nat.cost_per_kw_delivered < gross
    nat["headroom"] = gross - nat.cost_per_kw_delivered
    return nat[
        [
            "year",
            "utilization",
            "cost_per_kw_enrolled",
            "cost_per_kw_delivered",
            "gross_cone_per_kw_yr",
            "breakeven_utilization",
            "clears_gross_cone",
            "headroom",
            "provenance",
        ]
    ]


def netting_bound() -> pd.DataFrame:
    """Could correcting the netting asymmetry rescue demand response.

    The gap: demand response cost is gross, PJM's net CONE is not. The
    consistent fix is to subtract the value of the energy a curtailment avoids
    buying. That value is not published, but it is bounded, because the energy
    column gives the hours: avoided energy per delivered kW is just the implied
    event hours, and the credit is hours times price.

    So the question becomes whether any plausible pair of (event hours, energy
    price) covers the distance between demand response on the delivered basis
    and net CONE. This function computes that grid. The answer does not depend
    on picking a price, only on whether the whole grid clears.
    """
    panel = load_eia_panel()
    dr = cost_table()
    nat = dr[dr.sector == "total"].sort_values("year").iloc[-1]
    net_cone = float(cone("RTO", "2027/2028").net_cone_per_kw_yr)
    gap = nat.cost_per_kw_delivered - net_cone

    # implied event hours per delivered kW, both sides of the 2023 break
    hours = {}
    for label, year in (("post_reclassification", int(nat.year)), ("pre_reclassification", 2022)):
        e = float(panel.loc[(year, "total"), "energy_savings_mwh"])
        a = float(panel.loc[(year, "total"), "actual_peak_mw"])
        hours[f"{label}_{year}"] = e / a

    rows = []
    for label, h in hours.items():
        for price in ENERGY_VALUE.sweep(9):
            # round first, then multiply, so the three columns of the emitted
            # table are internally consistent for anyone checking by hand
            price = round(price, 4)
            credit = h * price  # kWh per kW-year times $/kWh
            rows.append(
                {
                    "hours_basis": label,
                    "implied_event_hours": h,
                    "energy_price_usd_per_kwh": price,
                    "avoided_energy_credit_per_kw_yr": credit,
                    "netted_dr_cost_per_kw_yr": nat.cost_per_kw_delivered - credit,
                    "net_cone_per_kw_yr": net_cone,
                    "clears_net_cone": (nat.cost_per_kw_delivered - credit) < net_cone,
                    "gap_remaining": gap - credit,
                    "provenance": "measured_hours_vs_assumed_price",
                }
            )
    return pd.DataFrame(rows)


def netting_summary() -> dict:
    grid = netting_bound()
    nat = cost_table()
    nat = nat[nat.sector == "total"].sort_values("year").iloc[-1]
    net_cone = float(cone("RTO", "2027/2028").net_cone_per_kw_yr)
    gap = float(nat.cost_per_kw_delivered - net_cone)
    best = grid.loc[grid.avoided_energy_credit_per_kw_yr.idxmax()]
    hours_hi = float(grid.implied_event_hours.max())
    return {
        "gap_to_net_cone_per_kw_yr": gap,
        "implied_event_hours_low": float(grid.implied_event_hours.min()),
        "implied_event_hours_high": hours_hi,
        "energy_price_needed_at_high_hours": gap / hours_hi,
        "energy_price_needed_at_low_hours": gap / float(grid.implied_event_hours.min()),
        "max_credit_in_grid_per_kw_yr": float(best.avoided_energy_credit_per_kw_yr),
        "max_credit_covers_gap": bool(best.clears_net_cone),
        "share_of_grid_that_clears": float(grid.clears_net_cone.mean()),
        "netted_dr_cost_at_max_credit": float(best.netted_dr_cost_per_kw_yr),
        "still_over_net_cone_by": float(best.netted_dr_cost_per_kw_yr / net_cone),
        "assumed_price_range": [ENERGY_VALUE.lo, ENERGY_VALUE.hi],
        # anchor the requirement to something a reader can judge
        "pjm_annual_avg_lmp_per_kwh": annual_avg_lmp(),
        "price_multiple_needed_vs_annual_avg": (gap / hours_hi) / annual_avg_lmp(),
        "credit_at_annual_avg_price_per_kw_yr": hours_hi * annual_avg_lmp(),
        "credit_at_annual_avg_covers_share_of_gap": (
            hours_hi * annual_avg_lmp() / gap
        ),
        "annual_avg_is_a_floor_on_called_hour_price": True,
    }


# Brattle computed exactly this netting for energy efficiency in 2021, which
# makes it an independent check on the demand response number rather than a
# comparison: Gross CONE $235/kW-ICAP-year less $177 of energy savings and $35
# of transmission and distribution savings gives an efficiency Net CONE of
# $23/kW-ICAP-year. The energy credit there is enormous. Here it is a few
# dollars. The ratio should be roughly the ratio of hours each resource is
# saving energy in, and it is, which is the point.
BRATTLE_EE_NETTING = {
    "source": (
        "Brattle, Gross Avoidable Cost Rates for Existing Generation and Net "
        "Cost of New Entry for New Energy Efficiency, 2021"
    ),
    "gross_cone_per_kw_icap_yr": 235.0,
    "energy_savings_credit_per_kw_yr": 177.0,
    "td_savings_credit_per_kw_yr": 35.0,
    "net_cone_per_kw_icap_yr": 23.0,
    "resource": "energy efficiency",
}


def netting_cross_check() -> dict:
    """Is the demand response netting credit the right size.

    Energy efficiency saves energy in every hour of the year. Demand response
    saves it only in the hours a program is called, which the energy column puts
    at roughly 33 to 94 a year. If both credits are computed correctly, the ratio
    between them should be near the ratio of hours, and that is a check on this
    repo's arithmetic using a number computed by someone else for a different
    resource.
    """
    grid = netting_bound()
    hours = float(grid.implied_event_hours.max())
    avg = annual_avg_lmp()
    dr_credit_at_avg = hours * avg
    ee_credit = BRATTLE_EE_NETTING["energy_savings_credit_per_kw_yr"]
    hours_ratio = 8_760 / hours
    credit_ratio = ee_credit / dr_credit_at_avg
    # If both credits are right and the hours are right, the leftover factor is
    # the premium demand response's called hours carry over an average hour.
    implied_multiple = hours_ratio / credit_ratio
    needed = float(netting_summary()["price_multiple_needed_vs_annual_avg"])
    return {
        "dr_credit_at_annual_avg_per_kw_yr": dr_credit_at_avg,
        "dr_event_hours": hours,
        "ee_credit_per_kw_yr": ee_credit,
        "hours_ratio": hours_ratio,
        "credit_ratio": credit_ratio,
        "implied_event_hour_price_multiple": implied_multiple,
        "implied_event_hour_price_per_mwh": implied_multiple * avg * 1_000,
        "multiple_needed_to_close_gap": needed,
        "shortfall_factor": needed / implied_multiple,
        "netting_can_close_the_gap": bool(implied_multiple >= needed),
        "note": (
            "energy efficiency's netting credit accrues in every hour, demand "
            "response's in a few dozen, so the ratio of the two credits should "
            "track the ratio of hours. It does not, and the leftover factor is "
            "an independent estimate of the premium demand response's called "
            "hours carry: about 2.5 times an average hour, against the 8.5 "
            "times the synthesis needs. Two different routes to the same "
            "conclusion, that the netting correction does not close the gap"
        ),
    }


def summary() -> dict:
    df = cost_table()
    nat = df[df.sector == "total"].sort_values("year")
    latest = nat.iloc[-1]
    sec = df[(df.sector.isin(SECTORS)) & (df.year == latest.year)]
    sweep = comparator_sweep()
    return {
        "cost_years": [int(nat.year.min()), int(nat.year.max())],
        "latest_year": int(latest.year),
        "cost_per_kw_enrolled": float(latest.cost_per_kw_enrolled),
        "cost_per_kw_delivered": float(latest.cost_per_kw_delivered),
        "basis_gap_ratio": float(latest.basis_gap_ratio),
        "mean_cost_per_kw_enrolled": float(nat.cost_per_kw_enrolled.mean()),
        "mean_cost_per_kw_delivered": float(nat.cost_per_kw_delivered.mean()),
        "cheapest_sector_enrolled": str(sec.loc[sec.cost_per_kw_enrolled.idxmin(), "sector"]),
        "cheapest_sector_delivered": str(sec.loc[sec.cost_per_kw_delivered.idxmin(), "sector"]),
        "dearest_sector_delivered": str(sec.loc[sec.cost_per_kw_delivered.idxmax(), "sector"]),
        "share_of_swept_comparators_where_framings_disagree": float(
            sweep.framings_disagree.mean()
        ),
        "sectors_dearer_than_gross_cone_on_delivered": [
            str(x)
            for x in sec.loc[
                sec.cost_per_kw_delivered
                > cone_table()
                .query("location == 'RTO' and delivery_year == '2027/2028'")
                .gross_cone_per_kw_yr.iloc[0],
                "sector",
            ]
        ],
        "cone_range_straddles_breakeven": bool(
            PEAKER_CONE.lo < latest.cost_per_kw_delivered
            and PEAKER_CONE.hi > latest.cost_per_kw_enrolled
        ),
        **_pjm_summary(),
        **{f"netting_{k}": v for k, v in netting_summary().items()},
        **{f"xcheck_{k}": v for k, v in netting_cross_check().items()},
    }


def _pjm_summary() -> dict:
    pjm = pjm_comparison()
    rto = pjm[(pjm.location == "RTO") & (pjm.delivery_year == "2027/2028")].iloc[0]
    pl = pjm[(pjm.location == "PL") & (pjm.delivery_year == "2027/2028")].iloc[0]
    latest = pjm[pjm.delivery_year == "2027/2028"]
    yrs = years_that_beat_gross_cone()
    bs = basis_sensitivity().set_index("side")
    return {
        "pjm_delivery_year": "2027/2028",
        "rto_gross_cone_per_kw_yr": float(rto.gross_cone_per_kw_yr),
        "rto_net_cone_per_kw_yr": float(rto.net_cone_per_kw_yr),
        "rto_eas_share_of_gross": float(rto.eas_share_of_gross),
        "breakeven_utilization_vs_rto_gross": float(rto.breakeven_utilization_vs_gross),
        "breakeven_utilization_vs_rto_net": float(rto.breakeven_utilization_vs_net),
        "dr_beats_rto_gross_on_delivered": bool(rto.dr_wins_delivered_vs_gross),
        "dr_beats_rto_net_on_delivered": bool(rto.dr_wins_delivered_vs_net),
        "pl_net_cone_per_kw_yr": float(pl.net_cone_per_kw_yr),
        "breakeven_utilization_vs_pl_net": float(pl.breakeven_utilization_vs_net),
        "ldas_where_dr_beats_net_cone": int(latest.dr_wins_delivered_vs_net.sum()),
        "ldas_where_dr_cannot_win_vs_net": int(latest.unwinnable_vs_net.sum()),
        "ldas_modelled": int(len(latest)),
        "years_clearing_gross_cone": int(yrs.clears_gross_cone.sum()),
        "years_total": int(len(yrs)),
        "dr_basis_spread_ratio": float(bs.loc["demand response", "spread_ratio"]),
        "cone_basis_spread_ratio": float(bs.loc["pjm peaker", "spread_ratio"]),
    }


def run() -> dict[str, pd.DataFrame | dict]:
    return {
        "cost_by_year": cost_table(),
        "identity_check": identity_check(),
        "breakeven": breakeven_table(),
        "comparator_sweep": comparator_sweep(),
        "pjm_comparison": pjm_comparison(),
        "basis_sensitivity": basis_sensitivity(),
        "years_vs_gross_cone": years_that_beat_gross_cone(),
        "netting_bound": netting_bound(),
        "summary": summary(),
    }
