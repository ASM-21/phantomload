"""Track 4. Could existing DR be redirected to absorb curtailed renewables.

MEASURED generation, PROXY curtailment. Observed curtailment volumes live on ISO
portals that are not reachable here, so this track does not claim to measure
curtailment. It measures the hours when curtailment risk is concentrated, using
real hourly generation by fuel from CarbonCast (CISO, ERCO, PJM, 2020-2021,
Apache-2.0), and asks whether those hours coincide with the hours a summer peak
shaving program is called.

The substitution is stated here rather than buried: "curtailment-risk hour" in
this module means an hour in the top decile of instantaneous renewable share for
its balancing authority. That is a proxy for oversupply conditions, not a
measurement of MWh curtailed. Every number below inherits that caveat.
"""

from __future__ import annotations

import functools
import pathlib

import numpy as np
import pandas as pd

from ..shared import ferc
from ..shared.dr_program import Provenance

DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "carboncast"

REGIONS = {
    "CISO": "US/Pacific",
    "ERCO": "US/Central",
    "PJM": "US/Eastern",
}

FUELS = ["coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "other"]
RENEWABLE = ["solar", "wind"]

# Typical incentive-based summer peak shaving window. Stated assumption.
DR_MONTHS = (6, 7, 8, 9)
DR_HOURS = (16, 17, 18, 19, 20)
DR_WEEKDAYS_ONLY = True

RISK_QUANTILE = 0.90


@functools.lru_cache(maxsize=8)
def load_region(region: str) -> pd.DataFrame:
    path = DATA_DIR / f"{region}_direct_emissions.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. See DATA.md for the CarbonCast fetch instructions."
        )
    df = pd.read_csv(path)
    df = df.rename(columns={df.columns[0]: "row"})
    df["utc"] = pd.to_datetime(df["UTC time"], utc=True)
    present = [f for f in FUELS if f in df.columns]
    df["total_gen"] = df[present].sum(axis=1)
    df["renewable_gen"] = df[[f for f in RENEWABLE if f in df.columns]].sum(axis=1)
    df = df[df.total_gen > 0].copy()
    df["renewable_share"] = df["renewable_gen"] / df["total_gen"]
    local = df["utc"].dt.tz_convert(REGIONS[region])
    df["local_hour"] = local.dt.hour
    df["month"] = local.dt.month
    df["weekday"] = local.dt.weekday
    df["region"] = region
    return df[
        [
            "utc",
            "region",
            "local_hour",
            "month",
            "weekday",
            "total_gen",
            "renewable_gen",
            "renewable_share",
        ]
    ]


def tag_windows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    threshold = df["renewable_share"].quantile(RISK_QUANTILE)
    df["curtailment_risk"] = df["renewable_share"] >= threshold
    in_dr = df["month"].isin(DR_MONTHS) & df["local_hour"].isin(DR_HOURS)
    if DR_WEEKDAYS_ONLY:
        in_dr &= df["weekday"] < 5
    df["in_dr_window"] = in_dr
    df["risk_threshold"] = threshold
    return df


def overlap_table() -> pd.DataFrame:
    rows = []
    for region in REGIONS:
        df = tag_windows(load_region(region))
        n = len(df)
        risk = df.curtailment_risk
        win = df.in_dr_window
        both = (risk & win).sum()
        p_risk = risk.mean()
        p_win = win.mean()
        p_risk_given_win = both / win.sum() if win.sum() else np.nan
        rows.append(
            {
                "region": region,
                "hours": n,
                "risk_threshold_renewable_share": float(df.risk_threshold.iloc[0]),
                "p_curtailment_risk": float(p_risk),
                "p_in_dr_window": float(p_win),
                "p_risk_given_dr_window": float(p_risk_given_win),
                "lift": float(p_risk_given_win / p_risk) if p_risk else np.nan,
                "share_of_risk_hours_inside_dr_window": float(both / risk.sum()),
                "expected_share_if_independent": float(p_win),
                "provenance": "measured_generation_proxy_curtailment",
            }
        )
    return pd.DataFrame(rows)


def when_is_risk() -> pd.DataFrame:
    """Month and hour concentration of curtailment-risk hours, by region."""
    frames = []
    for region in REGIONS:
        df = tag_windows(load_region(region))
        risk = df[df.curtailment_risk]
        by_month = risk.groupby("month").size() / len(risk)
        by_hour = risk.groupby("local_hour").size() / len(risk)
        frames.append(
            pd.DataFrame(
                {
                    "region": region,
                    "peak_risk_month": int(by_month.idxmax()),
                    "peak_risk_month_share": float(by_month.max()),
                    "share_in_dr_months": float(
                        by_month.reindex(DR_MONTHS).fillna(0).sum()
                    ),
                    "peak_risk_hour_local": int(by_hour.idxmax()),
                    "share_in_dr_hours": float(by_hour.reindex(DR_HOURS).fillna(0).sum()),
                },
                index=[region],
            )
        )
    return pd.concat(frames).assign(provenance="measured_generation_proxy_curtailment")


def window_sensitivity() -> pd.DataFrame:
    """Does the conclusion depend on the assumed DR call window."""
    rows = []
    windows = {
        "summer_evening_16_20": (DR_MONTHS, (16, 17, 18, 19, 20)),
        "summer_afternoon_14_18": (DR_MONTHS, (14, 15, 16, 17, 18)),
        "all_year_evening_16_20": (tuple(range(1, 13)), (16, 17, 18, 19, 20)),
        "all_year_midday_10_15": (tuple(range(1, 13)), (10, 11, 12, 13, 14, 15)),
    }
    for region in REGIONS:
        base = load_region(region)
        threshold = base["renewable_share"].quantile(RISK_QUANTILE)
        risk = base["renewable_share"] >= threshold
        for name, (months, hours) in windows.items():
            win = base["month"].isin(months) & base["local_hour"].isin(hours)
            if DR_WEEKDAYS_ONLY:
                win &= base["weekday"] < 5
            rows.append(
                {
                    "region": region,
                    "window": name,
                    "p_risk_given_window": float((risk & win).sum() / win.sum()),
                    "lift": float(((risk & win).sum() / win.sum()) / risk.mean()),
                    "provenance": "measured_generation_proxy_curtailment",
                }
            )
    return pd.DataFrame(rows)


# --- the other side of the same question ------------------------------------
# The overlap result above says the call window misses oversupply. The synthesis
# ends on the opposite question: is the window aimed at the hours that carry the
# value. Both are answerable from the same series, and the answers are opposite
# in sign, which is the point. A summer weekday evening window is a bad instrument
# for absorbing surplus and a good one for shaving scarcity, because it was built
# for the second job.
#
# Hour counts are not arbitrary. Track 7's implied event hours put a real demand
# response fleet at roughly 33 to 94 called hours a year, which is the top 0.4%
# to 1.1% of hours, so those are the depths tested.

EVENT_HOUR_DEPTHS = (33, 94, 200)


def net_load(region: str) -> pd.Series:
    df = load_region(region)
    return (df.total_gen - df.renewable_gen).rename("net_load")


def scarcity_targeting() -> pd.DataFrame:
    """How much of the highest-net-load tail falls inside the call window."""
    rows = []
    for region in REGIONS:
        df = load_region(region).copy()
        df["net_load"] = net_load(region)
        win = df.month.isin(DR_MONTHS) & df.local_hour.isin(DR_HOURS)
        if DR_WEEKDAYS_ONLY:
            win &= df.weekday < 5
        base = float(win.mean())
        for depth in EVENT_HOUR_DEPTHS:
            top = df.net_load.rank(ascending=False, method="first") <= depth
            inside = int((top & win).sum())
            rows.append(
                {
                    "region": region,
                    "depth_hours": depth,
                    "depth_share_of_year": depth / len(df),
                    "hours_inside_window": inside,
                    "share_inside_window": inside / depth,
                    "lift": (inside / depth) / base,
                    "net_load_vs_annual_mean": float(
                        df.net_load.nlargest(depth).mean() / df.net_load.mean()
                    ),
                    "provenance": "measured_generation_proxy_net_load",
                }
            )
    return pd.DataFrame(rows)


def seasonal_blind_spot() -> pd.DataFrame:
    """Winter hours in the scarcity tail, which a summer window cannot reach.

    CAVEAT THAT MATTERS MORE THAN THE RESULT. CarbonCast reports generation, not
    demand. In a supply-side failure, generation collapses and load is shed, so
    measured generation understates the demand that existed. The single event in
    this window where demand response mattered most, the February 2021 ERCOT
    crisis, is therefore the event this dataset can least measure, and its true
    position in the ranking is higher than shown. Treat the winter counts below
    as a floor.
    """
    rows = []
    for region in REGIONS:
        df = load_region(region).copy()
        df["net_load"] = net_load(region)
        local = df.utc.dt.tz_convert(REGIONS[region])
        df["date"] = local.dt.date
        for depth in (94, 200, 500):
            top = df.nlargest(depth, "net_load")
            winter = top[top.month.isin([12, 1, 2])]
            rows.append(
                {
                    "region": region,
                    "depth_hours": depth,
                    "winter_hours_in_tail": int(len(winter)),
                    "winter_share_of_tail": len(winter) / depth,
                    "reachable_by_summer_window": False if len(winter) else None,
                    "dates": ", ".join(sorted({str(d) for d in winter.date})[:4]),
                    "provenance": "measured_generation_understates_shed_load",
                }
            )
    return pd.DataFrame(rows)


def winter_shoulder() -> pd.DataFrame:
    """How high winter peaks reach relative to the annual maximum.

    The February 2021 hours are one storm. This asks whether the seasonal blind
    spot is structural: if winter routinely reaches most of the way to the annual
    peak, a June-to-September window is excluded from a large share of the
    system's stress by construction, storm or no storm.
    """
    rows = []
    for region in REGIONS:
        df = load_region(region).copy()
        df["net_load"] = net_load(region)
        monthly = df.groupby("month").net_load.max() / df.net_load.max()
        winter = monthly.reindex([12, 1, 2]).dropna()
        rows.append(
            {
                "region": region,
                "winter_peak_share_of_annual": float(winter.max()),
                "winter_peak_month": int(winter.idxmax()),
                "summer_window_peak_share": float(
                    monthly.reindex(list(DR_MONTHS)).max()
                ),
                "months_outside_window_above_80pct": int(
                    (monthly.drop(index=list(DR_MONTHS), errors="ignore") > 0.80).sum()
                ),
                "provenance": "measured_generation_proxy_net_load",
            }
        )
    return pd.DataFrame(rows)


def rule_scoping() -> dict:
    """Who the seasonal finding actually applies to.

    Written after the winter result, because the result on its own implies that
    nobody has noticed, and that is false. PJM retired its summer-only demand
    response products and has required year-round availability from its sole
    forward capacity product since the 2020/2021 delivery year, with performance
    assessed in winter as well as summer. So the wholesale market addressed this
    by rule roughly five years before this repo measured it.

    Two things survive that correction and one of them is stronger for it.

    First, scope. This repo measures the EIA retail population, which is
    utility-administered programs, not wholesale registrations, and EIA publishes
    no seasonal availability at all. Nothing here says whether a retail program
    can be called in January.

    Second, corroboration from the market side. PJM's own workaround, letting
    summer-only resources aggregate with winter-only ones, was reported as
    limited by how little winter-capable resource was offered. That is the same
    asymmetry this track measures from hourly generation, observed instead as a
    scarcity of bids, which is the more meaningful confirmation because it is
    priced rather than modelled.
    """
    rule = ferc.MARKET_RULES["pjm_capacity_performance"]
    return {
        "finding_scope": "EIA retail utility-administered programs",
        "wholesale_already_addressed": True,
        "wholesale_market": rule["market"],
        "year_round_required_from": rule["sole_forward_dr_product_from"],
        "summer_products_retired": len(rule["summer_only_products_retired"]),
        "eia_publishes_seasonal_availability": False,
        "corroborated_from_market_side": True,
        "source_quality": rule["source_quality"],
        "verify_before_citing": True,
    }


def targeting_summary() -> dict:
    st = scarcity_targeting()
    bs = seasonal_blind_spot()
    ov = overlap_table().set_index("region")
    at94 = st[st.depth_hours == 94].set_index("region")
    winter = bs[(bs.depth_hours == 200) & (bs.winter_hours_in_tail > 0)]
    return {
        "depths_tested": list(EVENT_HOUR_DEPTHS),
        "depth_94_share_of_year": float(st[st.depth_hours == 94].depth_share_of_year.iloc[0]),
        "scarcity_lift_min": float(st.lift.min()),
        "scarcity_lift_max": float(st.lift.max()),
        "share_inside_window_at_94_min": float(at94.share_inside_window.min()),
        "share_inside_window_at_94_max": float(at94.share_inside_window.max()),
        "oversupply_lift_max": float(ov.lift.max()),
        "targeting_asymmetry": float(st.lift.min() / ov.lift.max()),
        "window_is_built_for_scarcity_not_surplus": bool(
            st.lift.min() > 1 and ov.lift.max() < 1
        ),
        "net_load_multiple_at_94_pjm": float(
            at94.loc["PJM", "net_load_vs_annual_mean"]
        ),
        "regions_with_winter_scarcity": sorted(winter.region.unique().tolist()),
        "winter_hours_erco_top200": int(
            bs[(bs.region == "ERCO") & (bs.depth_hours == 200)].winter_hours_in_tail.iloc[0]
        ),
        "winter_counts_are_a_floor": True,
        "winter_peak_share_max": float(winter_shoulder().winter_peak_share_of_annual.max()),
        "winter_peak_share_max_region": str(
            winter_shoulder()
            .set_index("region")
            .winter_peak_share_of_annual.idxmax()
        ),
        "winter_peak_share_min": float(winter_shoulder().winter_peak_share_of_annual.min()),
        "months_outside_window_above_80pct_max": int(
            winter_shoulder().months_outside_window_above_80pct.max()
        ),
        **{f"rules_{k}": v for k, v in rule_scoping().items()},
    }


def proxy_robustness() -> pd.DataFrame:
    """Does the conclusion depend on how the proxy is defined.

    Two knobs. The threshold, which decides how rare a curtailment-risk hour
    has to be, and the definition itself. The renewable-share proxy flags hours
    when renewables dominate the mix. A net-load proxy flags hours when the
    residual left for everything else is smallest, which is closer to how an
    operator experiences oversupply. If the DR-window lift stays below 1 under
    every combination, the finding is about the calendar rather than about the
    proxy.
    """
    rows = []
    for region in REGIONS:
        base = load_region(region)
        net_load = base.total_gen - base.renewable_gen
        win = base["month"].isin(DR_MONTHS) & base["local_hour"].isin(DR_HOURS)
        if DR_WEEKDAYS_ONLY:
            win &= base["weekday"] < 5
        for quantile in (0.75, 0.80, 0.90, 0.95):
            for definition, series, high_is_risky in (
                ("renewable_share", base.renewable_share, True),
                ("net_load", net_load, False),
            ):
                if high_is_risky:
                    risk = series >= series.quantile(quantile)
                else:
                    risk = series <= series.quantile(1 - quantile)
                rows.append(
                    {
                        "region": region,
                        "definition": definition,
                        "quantile": quantile,
                        "risk_hours": int(risk.sum()),
                        "p_risk_given_window": float((risk & win).sum() / win.sum()),
                        "lift": float(((risk & win).sum() / win.sum()) / risk.mean()),
                        "provenance": "measured_generation_proxy_curtailment",
                    }
                )
    return pd.DataFrame(rows)


def robustness_summary() -> dict:
    rb = proxy_robustness()
    worst = rb.loc[rb.lift.idxmax()]
    agree = rb.pivot_table(
        index=["region", "quantile"], columns="definition", values="lift"
    )
    return {
        "combinations_tested": int(len(rb)),
        "definitions": sorted(rb.definition.unique()),
        "quantiles": sorted(rb["quantile"].unique()),
        "max_lift_across_all": float(rb.lift.max()),
        "max_lift_case": f"{worst.region}/{worst.definition}/q{worst['quantile']}",
        "all_below_one": bool((rb.lift < 1).all()),
        "share_below_half": float((rb.lift < 0.5).mean()),
        "definitions_correlate": float(
            agree["renewable_share"].corr(agree["net_load"])
        ),
        "conclusion_is_proxy_independent": bool((rb.lift < 1).all()),
    }


def summary() -> dict:
    ov = overlap_table().set_index("region")
    wr = when_is_risk()
    ws = window_sensitivity()
    best = ws.loc[ws.lift.idxmax()]
    return {
        "regions": list(REGIONS),
        "hours_per_region": int(ov.hours.iloc[0]),
        "curtailment_proxy": (
            f"top {round((1 - RISK_QUANTILE) * 100)}% of hours by instantaneous "
            "solar+wind share, per region"
        ),
        "dr_window": "Jun-Sep, weekdays, local hours 16-20",
        "lift_ciso": float(ov.loc["CISO", "lift"]),
        "lift_erco": float(ov.loc["ERCO", "lift"]),
        "lift_pjm": float(ov.loc["PJM", "lift"]),
        "min_lift": float(ov.lift.min()),
        "max_lift": float(ov.lift.max()),
        "share_of_ciso_risk_hours_in_dr_window": float(
            ov.loc["CISO", "share_of_risk_hours_inside_dr_window"]
        ),
        "ciso_peak_risk_hour_local": int(wr.loc["CISO", "peak_risk_hour_local"]),
        "ciso_peak_risk_month": int(wr.loc["CISO", "peak_risk_month"]),
        "best_window_for_absorption": f"{best.region}/{best.window}",
        "best_window_lift": float(best.lift),
        "redirect_requires_load_increase": True,
        **{f"robust_{k}": v for k, v in robustness_summary().items()},
        **{f"target_{k}": v for k, v in targeting_summary().items()},
    }


def run() -> dict:
    return {
        "overlap": overlap_table(),
        "when_is_risk": when_is_risk().reset_index(names="region_idx"),
        "window_sensitivity": window_sensitivity(),
        "proxy_robustness": proxy_robustness(),
        "scarcity_targeting": scarcity_targeting(),
        "seasonal_blind_spot": seasonal_blind_spot(),
        "winter_shoulder": winter_shoulder(),
        "summary": summary(),
    }
