"""Track 10. What the reported numbers measure, and whether the reports follow it.

MEASURED, EIA-861 2016 to 2018. The demand response schedule is checked against
what the same utilities reported about themselves on other schedules of the
same form in the same year: their peak load, their filing type and their meters.
No outside source is involved, so nothing here depends on matching two
reporters' definitions.

THE DEFINITION. Every ratio in this repository divides EIA's actual peak demand
savings by its potential peak demand savings. The form instructions define both
at a single hour (quoted in phantomload/shared/eia861.py):

    potential  savings that could occur at the time of the system peak hour
               assuming all demand response is called
    actual     reduction actually achieved, measured at the time of the
               company's annual system peak hour

So the dispatch utilization is not the share of enrolled capacity that was
used during the year. It is the share that was operating in the one hour that
set the company's annual peak. A program called on ten other afternoons and
not in that hour reports zero. That is a stronger reason than any earlier
version of this repository gave for not reading a low ratio as failure, and it
makes four things checkable.

1. PHYSICAL CONSISTENCY. Savings at the peak hour cannot exceed the load in
   that hour. That load, before demand response, is the reported net peak plus
   the actual savings achieved in it. A utility whose potential exceeds that
   sum is not reporting the defined quantity, and the comparison uses the larger
   of its summer and winter peaks so the test is as lenient as the data allows.
2. TIMING. If reports follow the definition, the actual figure depends on what
   was running in the peak hour, so it should move when the peak moves: between
   summer and winter, and in a year when an unusual event sets the peak. Three
   tests, each with a stated power.
3. WHAT A BLANK IS. A sixth of enrolled capacity carries potential and no actual
   figure. Short-form filers could explain it; none of them appears in the
   demand response file. What does explain most of it is that the same
   utilities report an exact zero in another year.
4. WHY ACTUAL EQUALS POTENTIAL. A third of positive reports copy potential into
   actual. If that were inability to measure, it would follow metering. It
   does, partly: copying is more common without interval meters, even within
   programs of the same size, but a quarter of fully metered utilities' reports
   copy too.
"""

from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from ..shared import eia861
from ..shared.dr_program import Provenance
from . import t1_utilization as t1

SEED = 20261014
PERMUTATIONS = 4_000
POWER_TRIALS = 400
# Rounding: EIA reports savings to 0.1 MW, so two figures can differ by that
# much from rounding alone.
ROUNDING_MW = 0.1
IMPLAUSIBLE_SHARE = 0.5
# January 2018 event thresholds: how far above its 2016-2017 maximum a utility's
# 2018 winter peak had to rise to count as pushed to a new peak by the cold.
EVENT_THRESHOLDS = (0.0, 0.02, 0.05, 0.10)
PUBLISHED_EVENT_THRESHOLD = 0.05
SANTEE_COOPER = "17543"


# --- the utility-year frame ------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _utility_year() -> pd.DataFrame:
    df = t1.utility_panel()
    df = df[df.potential_peak_mw > 0]
    g = df.groupby(["year", "utility_number"])
    out = pd.DataFrame(
        {
            "utility": g.utility.first(),
            "states": g.state.nunique(),
            "potential_mw": g.potential_peak_mw.sum(),
            "actual_mw": g.actual_peak_mw.sum(min_count=1),
            # a utility filing in several states can leave one state blank
            "actual_complete": g.actual_peak_mw.apply(lambda s: bool(s.notna().all())),
        }
    ).reset_index()
    pk = eia861.peaks()[
        ["year", "utility_number", "state", "ownership", "nerc_region",
         "summer_peak_mw", "winter_peak_mw", "annual_peak_mw", "peak_season"]
    ].rename(columns={"state": "home_state"})
    out = out.merge(pk, on=["year", "utility_number"], how="left", validate="1:1")
    out["gross_peak_mw"] = out.annual_peak_mw + out.actual_mw
    out["checkable"] = out.actual_complete & (out.annual_peak_mw > 0)
    out["potential_share_of_gross_peak"] = out.potential_mw / out.gross_peak_mw
    out["exceeds_gross_peak"] = out.checkable & (
        out.potential_mw > out.gross_peak_mw + ROUNDING_MW
    )
    out["over_half_gross_peak"] = out.checkable & (
        out.potential_mw > IMPLAUSIBLE_SHARE * out.gross_peak_mw
    )
    out["actual_exceeds_potential"] = out.actual_mw > out.potential_mw + ROUNDING_MW
    out["provenance"] = Provenance.MEASURED.value
    return out


def utility_year() -> pd.DataFrame:
    """Demand response summed to the utility, beside the utility's own peaks."""
    return _utility_year().copy()


# --- 1. physical consistency ---------------------------------------------------------
def peak_check() -> pd.DataFrame:
    """Utility-years whose potential cannot be the defined quantity."""
    df = utility_year()
    flagged = df[df.exceeds_gross_peak | df.over_half_gross_peak | df.actual_exceeds_potential]
    return flagged.sort_values("potential_mw", ascending=False)[
        ["year", "utility_number", "utility", "home_state", "ownership", "nerc_region",
         "summer_peak_mw", "winter_peak_mw", "actual_mw", "potential_mw",
         "potential_share_of_gross_peak", "exceeds_gross_peak", "over_half_gross_peak",
         "actual_exceeds_potential", "provenance"]
    ]


def _national_utilization(df: pd.DataFrame) -> pd.Series:
    rep = df[df.actual_mw.notna()]
    g = rep.groupby("year")
    return g.actual_mw.sum() / g.potential_mw.sum()


def peak_check_summary() -> dict:
    df = utility_year()
    chk = df[df.checkable]
    total = chk.potential_mw.sum()
    out = {
        "utility_years": int(len(df)),
        "utility_years_matched_to_peaks": int(df.annual_peak_mw.notna().sum()),
        "utility_years_checkable": int(len(chk)),
        "checkable_share_of_potential": float(total / df.potential_mw.sum()),
        "potential_over_peak_capacity_weighted": float(
            chk.potential_mw.sum() / chk.annual_peak_mw.sum()
        ),
        "potential_over_peak_median": float((chk.potential_mw / chk.annual_peak_mw).median()),
    }
    base = _national_utilization(df)
    for flag in ("exceeds_gross_peak", "over_half_gross_peak"):
        f = chk[chk[flag]]
        rest = chk[~chk[flag]]
        without = _national_utilization(df[~df[flag]])
        out.update(
            {
                f"{flag}_utility_years": int(len(f)),
                f"{flag}_utilities": int(f.utility_number.nunique()),
                f"{flag}_mw": float(f.potential_mw.sum()),
                f"{flag}_share_of_checkable_potential": float(f.potential_mw.sum() / total),
                f"{flag}_cooperative_share": float((f.ownership == "Cooperative").mean()),
                f"{flag}_top_states": ", ".join(
                    f.groupby("home_state").potential_mw.sum().sort_values(ascending=False).index[:3]
                ),
                f"{flag}_winter_peaking_share": float((f.peak_season == "winter").mean()),
                f"{flag}_utilization": float(f.actual_mw.sum() / f.potential_mw.sum()),
                f"{flag}_rest_utilization": float(rest.actual_mw.sum() / rest.potential_mw.sum()),
                f"{flag}_national_effect_points_max": float(((without - base) * 100).max()),
                f"{flag}_national_effect_points_min": float(((without - base) * 100).min()),
            }
        )
    worst = chk[chk.exceeds_gross_peak].sort_values("potential_share_of_gross_peak", ascending=False)
    top = worst.iloc[0]
    largest = chk[chk.exceeds_gross_peak].sort_values("potential_mw", ascending=False).iloc[0]
    aep = df[df.actual_exceeds_potential]
    out.update(
        {
            "worst_ratio_utility": str(top.utility),
            "worst_ratio": float(top.potential_share_of_gross_peak),
            "largest_impossible_utility": str(largest.utility),
            "largest_impossible_potential_mw": float(largest.potential_mw),
            "largest_impossible_gross_peak_mw": float(largest.gross_peak_mw),
            "largest_impossible_year": int(largest.year),
            "actual_exceeds_potential_utility_years": int(len(aep)),
            "actual_exceeds_potential_mw": float((aep.actual_mw - aep.potential_mw).sum()),
        }
    )
    return out


# --- 2. timing ---------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _timing_panel() -> pd.DataFrame:
    """Utilities with a complete actual figure, a peak and a stable enrolled
    figure in all three years. Resized programs are dropped because a program
    that changed size several-fold is not the same program across years."""
    df = utility_year()
    df = df[df.checkable].copy()
    years = df.groupby("utility_number").year.nunique()
    df = df[df.utility_number.isin(years[years == 3].index)]
    spread = df.groupby("utility_number").potential_mw.agg(lambda s: s.max() / s.min())
    df = df[df.utility_number.isin(spread[spread <= t1.RESIZE_FACTOR].index)].copy()
    df["utilization"] = (df.actual_mw / df.potential_mw).clip(upper=1.0)
    copied = df.groupby("utility_number").apply(
        lambda f: bool((np.isclose(f.actual_mw, f.potential_mw) & (f.actual_mw > 0)).any()),
        include_groups=False,
    )
    df["ever_copied"] = df.utility_number.map(copied)
    return df


def _perm_diff(values, weights, labels, rng, n=PERMUTATIONS):
    """Weighted difference in means between labelled and unlabelled units, with
    a two-sided permutation p-value that reshuffles the labels."""
    v, w, lab = np.asarray(values, float), np.asarray(weights, float), np.asarray(labels, bool)
    perms = np.argsort(rng.random((n, len(lab))), axis=1)
    labs = np.vstack([lab, lab[perms]])
    vw = v * w
    t_mean = (labs * vw).sum(axis=1) / (labs * w).sum(axis=1)
    c_mean = (~labs * vw).sum(axis=1) / (~labs * w).sum(axis=1)
    stat = t_mean - c_mean
    return float(stat[0]), float((np.abs(stat[1:]) >= abs(stat[0])).mean())


def season_switch_test(rng=None) -> dict:
    """Within utilities whose annual peak moved between summer and winter, is
    utilization lower in the winter-peak years? A summer-only program cannot be
    running at a winter peak hour, so if reports follow the definition and much
    of the capacity is summer-only, it must be."""
    rng = rng or np.random.default_rng(SEED)
    df = _timing_panel()
    seasons = df.groupby("utility_number").peak_season.nunique()
    sw = df[df.utility_number.isin(seasons[seasons == 2].index)]
    a = sw.groupby(["utility_number", "peak_season"]).utilization.mean().unstack()
    diff = (a["summer"] - a["winter"]).to_numpy()
    w = sw.groupby("utility_number").potential_mw.mean().loc[a.index].to_numpy()
    summer_u = a["summer"].to_numpy()

    signs = rng.choice([-1.0, 1.0], size=(PERMUTATIONS, len(diff)))

    def flip_p(d):
        obs = (d * w).sum() / w.sum()
        null = signs @ (d * w) / w.sum()
        return float(obs), float((np.abs(null) >= abs(obs)).mean())

    obs, p = flip_p(diff)
    # power: suppose a share of each utility's summer delivery could not run in
    # winter. Each trial draws null-like differences by flipping the observed
    # ones at random, adds that loss, and re-tests.
    power = {}
    for lost in (0.1, 0.25, 0.5):
        hits = 0
        for _ in range(POWER_TRIALS):
            noise = diff * rng.choice([-1.0, 1.0], size=len(diff))
            _, pp = flip_p(noise + lost * summer_u)
            hits += pp < 0.05
        power[lost] = hits / POWER_TRIALS
    detectable = [k for k, v in power.items() if v >= 0.8]
    return {
        "utilities": int(len(diff)),
        "capacity_mw": float(w.sum()),
        "summer_minus_winter_capacity_weighted": obs,
        "p_value": p,
        "summer_minus_winter_mean": float(diff.mean()),
        "share_identical_both_seasons": float(np.mean(np.isclose(diff, 0))),
        "power_if_10pct_lost": power[0.1],
        "power_if_25pct_lost": power[0.25],
        "power_if_50pct_lost": power[0.5],
        "smallest_reliably_detected_loss": float(min(detectable)) if detectable else None,
    }


def january_2018_event(
    threshold: float = PUBLISHED_EVENT_THRESHOLD, drop_copied=False, rng=None, with_power=False
) -> dict:
    """Utilities whose 2018 annual peak was a winter peak above their 2016-2017
    maximum, the January 2018 cold, against every other utility: did their
    utilization in 2018 change more than everyone else's?"""
    rng = rng or np.random.default_rng(SEED)
    df = _timing_panel()
    if drop_copied:
        df = df[~df.ever_copied]
    w = df.pivot(index="utility_number", columns="year",
                 values=["utilization", "potential_mw", "annual_peak_mw", "winter_peak_mw", "summer_peak_mw"])
    prior = w["annual_peak_mw"][[2016, 2017]].max(axis=1)
    rise = w["winter_peak_mw"][2018] / prior - 1
    winter = w["winter_peak_mw"][2018] > w["summer_peak_mw"][2018]
    treated = (winter & (rise > threshold)).to_numpy()
    change = (w["utilization"][2018] - w["utilization"][[2016, 2017]].mean(axis=1)).to_numpy()
    cap = w["potential_mw"].mean(axis=1).to_numpy()
    did_cap, p_cap = _perm_diff(change, cap, treated, rng)
    did_cnt, p_cnt = _perm_diff(change, np.ones_like(cap), treated, rng)
    out = {
        "threshold": threshold,
        "drop_copied": drop_copied,
        "treated": int(treated.sum()),
        "control": int((~treated).sum()),
        "treated_mw": float(cap[treated].sum()),
        "difference_capacity_weighted": did_cap,
        "p_capacity_weighted": p_cap,
        "difference_count_weighted": did_cnt,
        "p_count_weighted": p_cnt,
    }
    if with_power:
        # power: shuffle the changes across utilities (null), add a known rise
        # in utilization to the utilities the cold hit, and re-test
        for rise_pts in (0.05, 0.10, 0.20):
            hits = 0
            for _ in range(POWER_TRIALS // 2):
                null_change = change[rng.permutation(len(change))]
                _, pp = _perm_diff(null_change + rise_pts * treated, cap, treated, rng, n=1_000)
                hits += pp < 0.05
            out[f"power_at_{int(rise_pts * 100)}_points"] = hits / (POWER_TRIALS // 2)
    return out


def january_2018_grid() -> pd.DataFrame:
    rows = []
    for thr in EVENT_THRESHOLDS:
        for drop in (False, True):
            r = january_2018_event(thr, drop, rng=np.random.default_rng(SEED))
            rows.append({**r, "provenance": Provenance.MEASURED.value})
    return pd.DataFrame(rows)


def _peak_size_arrays():
    """Within-utility deviations for the peak-size test, one row per utility and
    one column per year: the peak's percent deviation from the utility's own
    three-year mean, and utilization's deviation from its own mean."""
    df = _timing_panel().sort_values(["utility_number", "year"])
    share = df.groupby("utility_number").potential_mw.mean() / df.groupby(
        "utility_number"
    ).annual_peak_mw.mean()
    panel_mw = df.potential_mw.sum()
    df = df[df.utility_number.isin(share[share < 0.05].index)]
    n = df.utility_number.nunique()
    peak = df.annual_peak_mw.to_numpy().reshape(n, 3)
    util = df.utilization.to_numpy().reshape(n, 3)
    w = df.potential_mw.to_numpy().reshape(n, 3).mean(axis=1)
    x = (peak / peak.mean(axis=1, keepdims=True) - 1) * 100
    x = x - x.mean(axis=1, keepdims=True)
    y = util - util.mean(axis=1, keepdims=True)
    return x, y, w, panel_mw, df


def peak_size_frame() -> pd.DataFrame:
    """The peak-size test's points, for plotting and inspection."""
    x, y, w, _, df = _peak_size_arrays()
    return pd.DataFrame(
        {
            "peak_deviation_pct": x.ravel(),
            "utilization_deviation": y.ravel(),
            "mean_potential_mw": np.repeat(w, 3),
            "provenance": Provenance.MEASURED.value,
        }
    )


def peak_size_test(rng=None) -> dict:
    """Within a utility, is utilization higher in the year its peak was
    highest? The utility's own NET peak is used, which demand response lowers
    in the years it runs, so any bias works against finding an effect; the
    gross peak would build the effect in by adding the savings back. Only
    utilities whose enrolled capacity is under 5% of their peak are used, where
    the net peak is barely moved by demand response at all."""
    rng = rng or np.random.default_rng(SEED)
    x, y, w, panel_mw, df = _peak_size_arrays()
    n = len(w)
    den = (w[:, None] * x * x).sum()
    # every within-utility reordering of three years, drawn per utility
    orders = np.array([[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]])
    draws = orders[rng.integers(0, 6, size=(PERMUTATIONS // 4, n))]
    xp = np.take_along_axis(np.broadcast_to(x, draws.shape), draws, axis=2)

    def slope_and_p(yy):
        obs = (w[:, None] * x * yy).sum() / den
        null = (w[None, :, None] * xp * yy[None]).sum(axis=(1, 2)) / den
        return float(obs), float((np.abs(null) >= abs(obs)).mean())

    obs, p = slope_and_p(y)
    constant = np.all(np.isclose(y, 0), axis=1)
    varying_slope = float(
        (w[~constant, None] * x[~constant] * y[~constant]).sum()
        / (w[~constant, None] * x[~constant] ** 2).sum()
    )
    # power: shuffle each utility's observed deviations across its own years,
    # which keeps their size and breaks any link to the peak, then add a known
    # slope in utilization points per percent of peak and re-test
    power = {}
    for beta in (0.01, 0.02, 0.05):
        hits = 0
        for _ in range(POWER_TRIALS // 4):
            noise = np.take_along_axis(y, orders[rng.integers(0, 6, size=n)], axis=1)
            _, pp = slope_and_p(noise + beta * x)
            hits += pp < 0.05
        power[beta] = hits / (POWER_TRIALS // 4)
    detectable = [k for k, v in power.items() if v >= 0.8]
    return {
        "utilities": int(n),
        "share_of_timing_panel_capacity": float(df.potential_mw.sum() / panel_mw),
        "anomaly_sd_pct": float(x.std()),
        "slope_per_pct_of_peak": obs,
        "p_value": p,
        "share_reporting_identical_utilization": float(constant.mean()),
        "slope_among_utilities_that_vary": varying_slope,
        "power_at_1pt_per_pct": power[0.01],
        "power_at_2pt_per_pct": power[0.02],
        "power_at_5pt_per_pct": power[0.05],
        "smallest_reliably_detected_slope": float(min(detectable)) if detectable else None,
    }


def santee_cooper() -> dict:
    """The case ROADMAP item 4 named: zero in 2016 and 2017, a report within
    0.1 MW of enrolled capacity in 2018. What the same form says about its peaks."""
    df = utility_year()
    s = df[df.utility_number == SANTEE_COOPER].set_index("year").sort_index()
    out = {"utility": str(s.utility.iloc[0])}
    for y, r in s.iterrows():
        out.update(
            {
                f"potential_{y}": float(r.potential_mw),
                f"actual_{y}": float(r.actual_mw),
                f"summer_peak_{y}": float(r.summer_peak_mw),
                f"winter_peak_{y}": float(r.winter_peak_mw),
                f"peak_season_{y}": str(r.peak_season),
            }
        )
    annual = s.annual_peak_mw
    out["peak_2018_over_prior_max"] = float(annual.loc[2018] / annual.loc[[2016, 2017]].max() - 1)
    out["positive_only_in_highest_peak_year"] = bool(
        (s.actual_mw > 0).sum() == 1 and s.actual_mw.idxmax() == annual.idxmax()
    )
    return out


def timing_summary() -> dict:
    return dict(_timing_summary())


@functools.lru_cache(maxsize=1)
def _timing_summary() -> dict:
    ss = season_switch_test()
    ev = january_2018_grid()
    pk = peak_size_test()
    sc = santee_cooper()
    pw = january_2018_event(rng=np.random.default_rng(SEED), with_power=True)
    pub = ev[(ev.threshold == PUBLISHED_EVENT_THRESHOLD) & ~ev.drop_copied].iloc[0]
    return {
        "panel_utilities": int(_timing_panel().utility_number.nunique()),
        "event_power_at_5_points": pw["power_at_5_points"],
        "event_power_at_10_points": pw["power_at_10_points"],
        "event_power_at_20_points": pw["power_at_20_points"],
        **{f"season_{k}": v for k, v in ss.items()},
        "event_specifications": int(len(ev)),
        "event_significant_any": int(
            ((ev.p_capacity_weighted < 0.05) | (ev.p_count_weighted < 0.05)).sum()
        ),
        "event_difference_min": float(
            ev[["difference_capacity_weighted", "difference_count_weighted"]].min().min()
        ),
        "event_difference_max": float(
            ev[["difference_capacity_weighted", "difference_count_weighted"]].max().max()
        ),
        "event_published_treated": int(pub.treated),
        "event_published_treated_mw": float(pub.treated_mw),
        "event_published_difference": float(pub.difference_capacity_weighted),
        "event_published_p": float(pub.p_capacity_weighted),
        **{f"size_{k}": v for k, v in pk.items()},
        **{f"santee_{k}": v for k, v in sc.items()},
        "verdict": (
            "no test finds the reported actual moving with the size or timing of "
            "the peak. The size test would detect a rise of two points of "
            "utilization per percent of peak, the event test a rise of twenty "
            "points, and the season test is too weak to rule out much. Either most "
            "enrolled capacity runs in either season and is not called harder in a "
            "harder year, or reports do not follow the single-hour definition, and "
            "these files cannot separate the two"
        ),
    }


# --- 3. what a blank is ---------------------------------------------------------------
def unreported() -> pd.DataFrame:
    """Every utility-state key that left the actual figure blank in some year,
    with what it reported in its other years."""
    df = t1.utility_panel()
    df = df[df.potential_peak_mw > 0]
    st = df.pivot(index="key", columns="year", values="status")
    pot = df.groupby("key").potential_peak_mw.mean()
    names = df.drop_duplicates("key").set_index("key").utility
    ever_blank = st.eq("not_reported").any(axis=1)
    out = pd.DataFrame(
        {
            "utility": names.reindex(st.index),
            "mean_potential_mw": pot,
            "also_zero": st.eq("exact_zero").any(axis=1),
            "also_positive": st.eq("positive").any(axis=1),
        }
    )
    for y in st.columns:
        out[f"status_{y}"] = st[y]
    out = out[ever_blank]
    out["category"] = np.select(
        [out.also_positive, out.also_zero],
        ["blank and positive in other years", "blank and exactly zero, never positive"],
        default="blank in every year reported",
    )
    out["provenance"] = Provenance.MEASURED.value
    return out.sort_values("mean_potential_mw", ascending=False).reset_index()


def unreported_summary() -> dict:
    df = t1.utility_panel()
    sf = eia861.short_form()
    overlap = {
        int(y): len(set(sf[sf.year == y].utility_number) & set(df[df.year == y].utility_number))
        for y in (2016, 2017, 2018)
    }
    u = unreported()
    mw = u.groupby("category").mean_potential_mw.sum()
    total = mw.sum()
    keys = df[df.potential_peak_mw > 0].groupby("key").status.agg(set)
    switchers = keys[keys.apply(lambda s: {"exact_zero", "not_reported"} <= s)]
    return {
        "short_form_filers_min": int(sf.groupby("year").utility_number.nunique().min()),
        "short_form_filers_in_dr_file": int(sum(overlap.values())),
        "short_form_dsm_flag_yes_max": int(
            sf[sf.demand_side_management == "Y"].groupby("year").utility_number.nunique().max()
        ),
        "ever_blank_keys": int(len(u)),
        "ever_blank_mw": float(total),
        "blank_and_zero_never_positive_share": float(
            mw.get("blank and exactly zero, never positive", 0) / total
        ),
        "blank_and_positive_share": float(mw.get("blank and positive in other years", 0) / total),
        "blank_every_year_share": float(mw.get("blank in every year reported", 0) / total),
        "blank_with_zero_elsewhere_share": float(
            u[u.also_zero].mean_potential_mw.sum() / total
        ),
        "zero_blank_switcher_keys": int(len(switchers)),
        "largest_blank": str(u.utility.iloc[0]),
        "largest_blank_mw": float(u.mean_potential_mw.iloc[0]),
    }


# --- 4. why actual equals potential ---------------------------------------------------
AMI_BANDS = ((0.0, 0.10, "under 10%"), (0.10, 0.90, "10% to 90%"), (0.90, 1.01, "90% or more"))


@functools.lru_cache(maxsize=1)
def _copy_frame() -> pd.DataFrame:
    df = t1.utility_panel()
    pos = df[(df.potential_peak_mw > 0) & (df.actual_peak_mw > 0)].copy()
    pos["is_copy"] = np.isclose(pos.actual_peak_mw, pos.potential_peak_mw)
    m = eia861.meters()
    m["key"] = m.utility_number + "_" + m.state
    ami = m.groupby(["year", "key"]).agg(ami=("ami_total", "sum"), meters=("meters_total", "sum"))
    ami = ami[ami.meters > 0]
    ami["ami_share"] = (ami.ami / ami.meters).clip(upper=1.0)
    pos = pos.join(ami.ami_share, on=["year", "key"]).dropna(subset=["ami_share"])
    pos["size_quartile"] = pd.qcut(pos.potential_peak_mw, 4, labels=False)
    return pos


def copy_vs_metering() -> dict:
    return dict(_copy_vs_metering())


@functools.lru_cache(maxsize=1)
def _copy_vs_metering() -> dict:
    """Is copying potential into actual a sign of being unable to measure?
    Interval meters are what a measured reduction needs. Compared within size
    quarters, because small programs both copy more and meter less."""
    rng = np.random.default_rng(SEED)
    pos = _copy_frame()
    out = {"reports": int(len(pos))}
    for lo, hi, label in AMI_BANDS:
        b = pos[(pos.ami_share >= lo) & (pos.ami_share < hi)]
        out[f"copy_rate_ami_{label}"] = float(b.is_copy.mean())
        out[f"reports_ami_{label}"] = int(len(b))
    ext = pos[(pos.ami_share < 0.10) | (pos.ami_share >= 0.90)]
    full = (ext.ami_share >= 0.90).to_numpy()
    copied = ext.is_copy.to_numpy(float)
    quart = ext.size_quartile.to_numpy()
    strata = [np.where(quart == q)[0] for q in np.unique(quart)]

    def stratified(lab):
        diffs, weights = [], []
        for ix in strata:
            a, b = ix[lab[ix]], ix[~lab[ix]]
            if len(a) and len(b):
                diffs.append(copied[b].mean() - copied[a].mean())
                weights.append(1 / (1 / len(a) + 1 / len(b)))
        return float(np.average(diffs, weights=weights))

    obs = stratified(full)
    null = []
    for _ in range(PERMUTATIONS // 4):
        lab = full.copy()
        for ix in strata:
            lab[ix] = rng.permutation(lab[ix])
        null.append(stratified(lab))
    out["no_ami_minus_full_ami_within_size"] = obs
    out["p_value"] = float(np.mean(np.abs(np.array(null)) >= abs(obs)))
    return out


# --- summary and run ---------------------------------------------------------------
def definition() -> dict:
    return {
        "potential": eia861.POTENTIAL_DEFINITION,
        "actual": eia861.ACTUAL_DEFINITION,
        "source": eia861.INSTRUCTIONS_SOURCE,
        "consequence": (
            "the dispatch utilization is the share of enrolled capacity operating "
            "in the hour that set the company's annual peak, not the share used "
            "during the year"
        ),
    }


def summary() -> dict:
    return {
        **{f"def_{k}": v for k, v in definition().items()},
        **{f"pk_{k}": v for k, v in peak_check_summary().items()},
        **{f"tm_{k}": v for k, v in timing_summary().items()},
        **{f"un_{k}": v for k, v in unreported_summary().items()},
        **{f"cp_{k}": v for k, v in copy_vs_metering().items()},
    }


def run() -> dict:
    return {
        "peak_check": peak_check(),
        "january_2018_grid": january_2018_grid(),
        "unreported": unreported(),
        "summary": summary(),
    }
