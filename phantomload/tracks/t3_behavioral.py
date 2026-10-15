"""Track 3. Price-based vs direct load control, per enrolled customer.

SIMULATED. There is no public per-program-type impact data, so this track builds
the comparison from stated parameter ranges. Every number it produces is a band
across the full range in calibration.py, never a point estimate.

To keep the simulation from being self-answering, it is run backwards against a
measured quantity. EIA-861 gives real delivered peak reduction per enrolled
residential customer. The simulation is inverted to ask what mix of program
types is consistent with that observed number. The result is that the inversion
is not informative, and the reason is worth more than a fake point estimate:
the answer is dominated by residential coincident peak demand, a parameter this
repo does not measure. That tells you exactly which number to go get.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from ..shared.calibration import (
    CPP_PEAK_REDUCTION,
    DEVICES_PER_ENROLLED_CUSTOMER,
    DLC_KW_PER_CUSTOMER,
    TOU_KW_PER_CUSTOMER,
    CUSTOMER_PEAK_KW,
    DLC_NOTIFICATION_DECAY,
    DLC_PEAK_REDUCTION,
    TOU_PEAK_REDUCTION,
)
from ..shared.dr_program import Provenance, ProgramType, load_eia_panel, synthetic_program

N_SWEEP = 7


def delivery_per_customer(
    peak_kw: float, tou: float, cpp: float, dlc: float, decay: float
) -> dict[str, float]:
    """kW of peak reduction per ENROLLED customer under each program type.

    Price-based programs apply to everyone on the rate, so no notification
    decay. Direct load control only delivers from devices that actually respond,
    so enrolled and responding are different populations.
    """
    return {
        "tou": peak_kw * tou,
        "cpp": peak_kw * cpp,
        "dlc": peak_kw * dlc * decay,
    }


def sweep() -> pd.DataFrame:
    rows = []
    grid = itertools.product(
        CUSTOMER_PEAK_KW.sweep(N_SWEEP),
        TOU_PEAK_REDUCTION.sweep(N_SWEEP),
        CPP_PEAK_REDUCTION.sweep(N_SWEEP),
        DLC_PEAK_REDUCTION.sweep(N_SWEEP),
        DLC_NOTIFICATION_DECAY.sweep(3),
    )
    for peak_kw, tou, cpp, dlc, decay in grid:
        d = delivery_per_customer(peak_kw, tou, cpp, dlc, decay)
        rows.append(
            {
                "peak_kw": peak_kw,
                "tou_frac": tou,
                "cpp_frac": cpp,
                "dlc_frac": dlc,
                "dlc_decay": decay,
                "kw_tou": d["tou"],
                "kw_cpp": d["cpp"],
                "kw_dlc": d["dlc"],
                "dlc_over_tou": d["dlc"] / d["tou"],
                "dlc_over_cpp": d["dlc"] / d["cpp"],
                "cpp_beats_dlc": d["cpp"] > d["dlc"],
                "provenance": Provenance.SIMULATED.value,
            }
        )
    return pd.DataFrame(rows)


def bands() -> pd.DataFrame:
    df = sweep()
    out = []
    for col in ["kw_tou", "kw_cpp", "kw_dlc", "dlc_over_tou", "dlc_over_cpp"]:
        out.append(
            {
                "quantity": col,
                "p05": df[col].quantile(0.05),
                "median": df[col].median(),
                "p95": df[col].quantile(0.95),
                "min": df[col].min(),
                "max": df[col].max(),
                "provenance": Provenance.SIMULATED.value,
            }
        )
    return pd.DataFrame(out)


def observed_kw_per_customer(sector: str = "residential") -> pd.Series:
    """MEASURED. Delivered peak reduction per enrolled customer, EIA-861."""
    wide = load_eia_panel().reset_index()
    s = wide[wide.sector == sector].copy()
    s["kw_per_customer"] = s["actual_peak_mw"] * 1_000 / s["customers_enrolled"]
    return s.set_index("year")["kw_per_customer"]


def implied_dlc_share() -> pd.DataFrame:
    """What DLC-equivalent share of enrolment reproduces the observed delivery.

    f solves f * kw_dlc + (1 - f) * kw_tou = observed. Values outside [0, 1]
    mean the parameter draw cannot reproduce the observed number at all, which
    is itself reported rather than clipped away.
    """
    observed = observed_kw_per_customer().iloc[-1]
    df = sweep()
    f = (observed - df.kw_tou) / (df.kw_dlc - df.kw_tou)
    out = df.assign(observed_kw_per_customer=observed, implied_dlc_share=f)
    out["feasible"] = out.implied_dlc_share.between(0, 1)
    return out


def inversion_summary() -> dict:
    inv = implied_dlc_share()
    feas = inv[inv.feasible]
    # which parameter drives the spread: correlation of |f| with each input
    drivers = {
        c: float(np.corrcoef(feas[c], feas.implied_dlc_share)[0, 1])
        for c in ["peak_kw", "tou_frac", "cpp_frac", "dlc_frac", "dlc_decay"]
    }
    obs = observed_kw_per_customer()
    return {
        "observed_kw_per_customer_latest": float(obs.iloc[-1]),
        "observed_kw_per_customer_year": int(obs.index[-1]),
        "observed_kw_per_customer_mean": float(obs.mean()),
        "feasible_share_of_draws": float(inv.feasible.mean()),
        "implied_dlc_share_p05": float(feas.implied_dlc_share.quantile(0.05)),
        "implied_dlc_share_median": float(feas.implied_dlc_share.median()),
        "implied_dlc_share_p95": float(feas.implied_dlc_share.quantile(0.95)),
        "dominant_driver": max(drivers, key=lambda k: abs(drivers[k])),
        "driver_correlations": drivers,
        "informative": bool(
            feas.implied_dlc_share.quantile(0.95) - feas.implied_dlc_share.quantile(0.05)
            < 0.4
        ),
        **{f"param_{k}": v for k, v in parameterization_cost().items()},
        **{f"bound_{k}": v for k, v in pure_tou_ruled_out().items()},
        **{f"infeas_{k}": v for k, v in infeasible_share().items()},
        **{f"denom_{k}": v for k, v in denominator_reconciliation().items()},
        **{f"mix_{k}": v for k, v in measured_mix_summary().items()},
    }


# --- the same inversion, in the units the literature uses -------------------
# Expressing impacts as a fraction of an unmeasured customer peak means every
# draw multiplies by a scalar the data cannot constrain. Expressing them as kW
# per participating customer removes that scalar entirely. Running both says how
# much of the original uninformativeness was the data and how much was the
# choice of units.


def absolute_sweep(n: int = 7) -> pd.DataFrame:
    observed = float(observed_kw_per_customer().iloc[-1])
    rows = []
    for dlc_kw in DLC_KW_PER_CUSTOMER.sweep(n):
        for decay in DLC_NOTIFICATION_DECAY.sweep(n):
            for tou_kw in TOU_KW_PER_CUSTOMER.sweep(n):
                delivered_dlc = dlc_kw * decay
                if delivered_dlc <= tou_kw:
                    continue
                share = (observed - tou_kw) / (delivered_dlc - tou_kw)
                rows.append(
                    {
                        "dlc_kw_per_customer": dlc_kw,
                        "dlc_decay": decay,
                        "tou_kw_per_customer": tou_kw,
                        "kw_dlc_per_enrolled": delivered_dlc,
                        "observed_kw_per_customer": observed,
                        "implied_dlc_share": share,
                        "feasible": 0.0 <= share <= 1.0,
                        "provenance": Provenance.SIMULATED.value,
                    }
                )
    return pd.DataFrame(rows)


def parameterization_cost() -> dict:
    """What the choice of units cost the answer."""
    frac = implied_dlc_share()
    frac_f = frac[frac.feasible].implied_dlc_share
    absolute = absolute_sweep()
    abs_f = absolute[absolute.feasible].implied_dlc_share
    width = lambda s: float(s.quantile(0.95) - s.quantile(0.05))
    drivers = {
        c: float(np.corrcoef(absolute[absolute.feasible][c], abs_f)[0, 1])
        for c in ("dlc_kw_per_customer", "dlc_decay", "tou_kw_per_customer")
    }
    return {
        "fractional_band_width": width(frac_f),
        "absolute_band_width": width(abs_f),
        "width_reduction": 1 - width(abs_f) / width(frac_f),
        "absolute_p05": float(abs_f.quantile(0.05)),
        "absolute_p95": float(abs_f.quantile(0.95)),
        "still_uninformative": bool(width(abs_f) > 0.4),
        "dominant_driver": max(drivers, key=lambda k: abs(drivers[k])),
        "driver_correlations": drivers,
        "remaining_driver_is_directly_measurable": True,
    }


def pure_tou_ruled_out() -> dict:
    """The finding the inversion was hiding.

    The share of demand response that is direct load control is not identified.
    But the measured delivery per enrolled residential customer is larger than
    any plausible time-of-use fleet could produce, in every draw of the sweep,
    which rules out a predominantly price-based residential fleet without
    identifying the mix. A bound is not a point estimate and is worth more than
    the null this track previously reported.
    """
    observed = float(observed_kw_per_customer().iloc[-1])
    ratios = [observed / t for t in TOU_KW_PER_CUSTOMER.sweep(9)]
    absolute = absolute_sweep()
    return {
        "observed_kw_per_customer": observed,
        "tou_only_max_kw_per_customer": TOU_KW_PER_CUSTOMER.hi,
        "observed_over_tou_min": min(ratios),
        "observed_over_tou_max": max(ratios),
        "tou_only_ruled_out_in_all_draws": bool(
            observed > TOU_KW_PER_CUSTOMER.hi
        ),
        "dlc_only_ruled_out": bool(
            observed > DLC_KW_PER_CUSTOMER.hi * DLC_NOTIFICATION_DECAY.hi
            or observed < DLC_KW_PER_CUSTOMER.lo * DLC_NOTIFICATION_DECAY.lo
        ),
        "share_of_draws_needing_some_dlc": float((absolute.implied_dlc_share > 0).mean()),
        "asymmetric": True,
    }


def infeasible_share() -> dict:
    """How often the observed delivery exceeds a fully-DLC fleet's capability.

    Once the per-participant impact comes from evaluations rather than from an
    assumed range, a new tension appears: under central published values a
    100%-DLC residential fleet delivers less per enrolled customer than EIA
    reports. The implied share exceeds one, which is not a program mix, it is a
    contradiction.

    Three explanations and this repo cannot choose between them:

      UNITS         evaluations report per AC unit, per thermostat or per
                    household while EIA counts customers. A household with two
                    controlled units delivers twice the per-unit figure. This is
                    the most likely explanation and it is not resolvable without
                    device counts.
      COMPOSITION   the residential fleet may skew toward higher-impact program
                    types than the evaluated samples.
      REPORTING     reported actual savings may be optimistic relative to
                    evaluated impacts, which is track 8 attack D's question
                    arriving from a third direction.
    """
    sweep = absolute_sweep()
    over = sweep[sweep.implied_dlc_share > 1.0]
    observed = float(observed_kw_per_customer().iloc[-1])
    central_pure_dlc = DLC_KW_PER_CUSTOMER.central * DLC_NOTIFICATION_DECAY.central
    return {
        "observed_kw_per_customer": observed,
        "central_pure_dlc_delivery_per_enrolled": central_pure_dlc,
        "observed_exceeds_central_pure_dlc": observed > central_pure_dlc,
        "observed_over_central_pure_dlc": observed / central_pure_dlc,
        "share_of_draws_infeasible": float(len(over) / len(sweep)),
        "min_implied_share": float(sweep.implied_dlc_share.min()),
        "explanations": ["units", "composition", "reporting"],
        "repo_can_choose": False,
    }


def denominator_reconciliation() -> dict:
    """What device count per customer would reconcile the two sources.

    The infeasibility above is most likely a denominator mismatch rather than a
    finding about demand response. Evaluations measure kW per controlled device
    or per participating home; EIA divides by enrolled customers. The bridge
    between them is the number of controlled devices per enrolled customer,
    which neither source publishes.

    Rather than assume it, solve for it. If the residential fleet were entirely
    direct load control, the devices per enrolled customer that reproduces the
    measured delivery is

        d* = observed / (impact_per_device * response_rate)

    A d* near one means the two sources agree once the denominators are lined
    up. A d* far above the plausible range means something other than units is
    going on.

    An independent sanity check comes from the evaluation record itself: a
    mass-market residential program reporting much above 1 kW per enrolled
    customer has almost certainly mixed a per-device numerator into a
    per-customer denominator. This repo's measured figure sits below that line,
    which is weak evidence that EIA's denominator is genuinely per customer.
    """
    observed = float(observed_kw_per_customer().iloc[-1])
    rows = []
    for impact in DLC_KW_PER_CUSTOMER.sweep(5):
        for rate in DLC_NOTIFICATION_DECAY.sweep(3):
            rows.append(
                {
                    "impact_per_device_kw": impact,
                    "response_rate": rate,
                    "devices_per_customer_needed": observed / (impact * rate),
                }
            )
    df = pd.DataFrame(rows)
    plausible = df[
        df.devices_per_customer_needed.between(
            DEVICES_PER_ENROLLED_CUSTOMER.lo, DEVICES_PER_ENROLLED_CUSTOMER.hi
        )
    ]
    central = observed / (
        DLC_KW_PER_CUSTOMER.central * DLC_NOTIFICATION_DECAY.central
    )
    return {
        "observed_kw_per_customer": observed,
        "mass_market_benchmark_kw": 1.0,
        "below_mixed_denominator_benchmark": observed < 1.0,
        "devices_per_customer_at_central": central,
        "devices_per_customer_min": float(df.devices_per_customer_needed.min()),
        "devices_per_customer_max": float(df.devices_per_customer_needed.max()),
        "share_of_draws_in_plausible_device_range": float(len(plausible) / len(df)),
        "units_explanation_sufficient": bool(
            DEVICES_PER_ENROLLED_CUSTOMER.lo
            <= central
            <= DEVICES_PER_ENROLLED_CUSTOMER.hi
        ),
        "neither_source_publishes_this": True,
    }


# --- the mix, measured where the form counts it --------------------------------
# Everything above infers the program mix from one national ratio. The form
# itself counts part of it. Schedule 6 Part D, line 8, asks every utility filing
# the long form for "the number of customers with direct load control, by
# customer class", on the same form and in the same year as the demand response
# enrolment. Divided into residential enrolment it measures the direct load
# control share of the residential fleet, bounded rather than pinned because
# many utilities leave the line blank: a blank is counted as no direct load
# control for the floor and as all direct load control for the ceiling. Counts
# above a utility's own enrolment are capped at it, which is itself a sign that
# the two lines are not always filled on the same basis.

MIX_YEARS = (2016, 2017, 2018)
DLC_BANDS = ((0.0, 0.1, "under 10%"), (0.1, 0.9, "10% to 90%"), (0.9, 1.01, "90% or more"))


def _mix_frame() -> pd.DataFrame:
    from ..shared import eia861

    dr = eia861.demand_response_by_class()
    res = dr[dr.customer_class == "residential"]
    g = res.groupby(["year", "utility_number"])
    out = pd.DataFrame(
        {
            "enrolled": g.customers_enrolled.sum(),
            "potential_mw": g.potential_peak_mw.sum(min_count=1),
            "actual_mw": g.actual_peak_mw.sum(min_count=1),
        }
    )
    m = eia861.meters()
    dlc = m.groupby(["year", "utility_number"]).dlc_residential.sum(min_count=1)
    out = out.join(dlc.rename("dlc_customers")).reset_index()
    return out[out.enrolled > 0]


def measured_dlc_share() -> pd.DataFrame:
    df = _mix_frame()
    rows = []
    for year, f in df.groupby("year"):
        total = f.enrolled.sum()
        reported = f.dlc_customers.notna()
        # skipna=False: a blank line must stay blank here, not fall back to the
        # enrolment it is being compared with
        counted = f[["dlc_customers", "enrolled"]].min(axis=1, skipna=False).fillna(0).sum()
        rows.append(
            {
                "year": int(year),
                "residential_enrolled": float(total),
                "dlc_customers_reported": float(f.dlc_customers.sum()),
                "enrolment_where_line_is_filled": float(f[reported].enrolled.sum() / total),
                "utilities_reporting_more_dlc_than_enrolled": int(
                    (f.dlc_customers > f.enrolled).sum()
                ),
                "dlc_share_floor": float(counted / total),
                "dlc_share_ceiling": float((counted + f[~reported].enrolled.sum()) / total),
                "provenance": Provenance.MEASURED.value,
            }
        )
    return pd.DataFrame(rows)


def kw_by_dlc_share() -> pd.DataFrame:
    """Delivered kW per enrolled residential customer, by how much of each
    utility's residential enrolment is direct load control. Positive reports
    only, and not those copying potential into actual, which are not
    measurements."""
    df = _mix_frame()
    df = df[(df.actual_mw > 0) & df.dlc_customers.notna() & (df.enrolled >= 100)]
    df = df[~np.isclose(df.actual_mw, df.potential_mw)].copy()
    df["dlc_share"] = (df.dlc_customers / df.enrolled).clip(upper=1.0)
    df["kw_per_enrolled"] = df.actual_mw * 1_000 / df.enrolled
    rows = []
    for lo, hi, label in DLC_BANDS:
        b = df[(df.dlc_share >= lo) & (df.dlc_share < hi)]
        rows.append(
            {
                "dlc_share_band": label,
                "utility_years": int(len(b)),
                "utilities": int(b.utility_number.nunique()),
                "median_kw_per_enrolled": float(b.kw_per_enrolled.median()),
                "provenance": Provenance.MEASURED.value,
            }
        )
    return pd.DataFrame(rows)


def measured_mix_summary() -> dict:
    from scipy import stats

    share = measured_dlc_share()
    bands = kw_by_dlc_share().set_index("dlc_share_band")
    df = _mix_frame()
    df = df[(df.actual_mw > 0) & df.dlc_customers.notna() & (df.enrolled >= 100)]
    df = df[~np.isclose(df.actual_mw, df.potential_mw)]
    per_utility = df.assign(
        dlc_share=(df.dlc_customers / df.enrolled).clip(upper=1.0),
        kw=df.actual_mw * 1_000 / df.enrolled,
    ).groupby("utility_number")[["dlc_share", "kw"]].mean()
    rho, p = stats.spearmanr(per_utility.dlc_share, per_utility.kw)
    return {
        "floor_min": float(share.dlc_share_floor.min()),
        "floor_max": float(share.dlc_share_floor.max()),
        "ceiling_min": float(share.dlc_share_ceiling.min()),
        "ceiling_max": float(share.dlc_share_ceiling.max()),
        "line_filled_min": float(share.enrolment_where_line_is_filled.min()),
        "line_filled_max": float(share.enrolment_where_line_is_filled.max()),
        "more_dlc_than_enrolled_max": int(share.utilities_reporting_more_dlc_than_enrolled.max()),
        "kw_mostly_dlc": float(bands.loc["90% or more", "median_kw_per_enrolled"]),
        "kw_little_dlc": float(bands.loc["under 10%", "median_kw_per_enrolled"]),
        "utilities_in_rank_test": int(len(per_utility)),
        "rho_dlc_share_vs_kw": float(rho),
        "p_dlc_share_vs_kw": float(p),
    }


def synthetic_registry() -> list:
    """Two modelled programs, routed through the shared registry so they carry
    SIMULATED provenance and cannot be pooled with measured rows by accident."""
    peak = CUSTOMER_PEAK_KW.central
    d = delivery_per_customer(
        peak,
        TOU_PEAK_REDUCTION.central,
        CPP_PEAK_REDUCTION.central,
        DLC_PEAK_REDUCTION.central,
        DLC_NOTIFICATION_DECAY.central,
    )
    n = 100_000
    return [
        synthetic_program(
            year=2024,
            sector="residential",
            program_type=ProgramType.PRICE_BASED,
            enrolled_mw=n * peak * CPP_PEAK_REDUCTION.hi / 1_000,
            verified_mw=n * d["cpp"] / 1_000,
            note="modelled CPP population, track 3",
        ),
        synthetic_program(
            year=2024,
            sector="residential",
            program_type=ProgramType.DIRECT_LOAD_CONTROL,
            enrolled_mw=n * peak * DLC_PEAK_REDUCTION.hi / 1_000,
            verified_mw=n * d["dlc"] / 1_000,
            note="modelled DLC population, track 3",
        ),
    ]


def run() -> dict:
    return {
        "bands": bands(),
        "absolute_sweep": absolute_sweep(),
        "implied_dlc_share": implied_dlc_share()
        .groupby("peak_kw")["implied_dlc_share"]
        .describe()
        .reset_index(),
        "measured_dlc_share": measured_dlc_share(),
        "kw_by_dlc_share": kw_by_dlc_share(),
        "summary": inversion_summary(),
    }
