"""Figures. Every chart is drawn from a track's own result frame, never from a
number typed into this file, so a figure cannot drift away from the analysis.
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
# Pinned so a figure rebuilt on another machine uses the same font as the
# committed one. A site matplotlibrc can change the default family, and one did
# in the environment v0.4.3 was built in; DejaVu Sans ships with matplotlib
# itself. Antialiasing still differs slightly between matplotlib builds, so a
# rebuilt figure matches the committed one visually, not byte for byte.
matplotlib.rcParams["font.family"] = "DejaVu Sans"
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

from ..tracks import t1_utilization as t1  # noqa: E402
from ..tracks import t2_cost as t2  # noqa: E402
from ..tracks import t4_curtailment as t4  # noqa: E402
from ..tracks import t6_overhead as t6  # noqa: E402
from .. import synthesis  # noqa: E402
from ..tracks import t7_crossval as t7  # noqa: E402
from ..tracks import t8_falsification as t8  # noqa: E402
from ..tracks import t9_mechanisms as t9  # noqa: E402
from .calibration import cone  # noqa: E402

FIG_DIR = pathlib.Path(__file__).resolve().parents[2] / "figures"
MEASURED = "#1f4e79"
SIM = "#a34b2a"
GREY = "#7a7a7a"
ZERO = "#c9a227"        # exact zero, the same colour in every figure
UNINFORMATIVE = "#c4c4c4"  # reports that say nothing about the question asked


def _save(fig, name: str) -> pathlib.Path:
    FIG_DIR.mkdir(exist_ok=True)
    path = FIG_DIR / name
    fig.tight_layout()
    # no Software stamp, so the file does not record which matplotlib drew it
    fig.savefig(path, dpi=140, metadata={"Software": None})
    plt.close(fig)
    return path


def fig_utilization() -> pathlib.Path:
    df = t1.utilization_table()
    sec = t1.sector_summary()
    sec = sec[sec.index != "transportation"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    ax1.bar(sec.index, sec["mean_utilization"], color=MEASURED)
    ax1.errorbar(
        sec.index,
        sec["mean_utilization"],
        yerr=[sec["mean_utilization"] - sec["min"], sec["max"] - sec["mean_utilization"]],
        fmt="none",
        ecolor=GREY,
        capsize=4,
    )
    ax1.set_ylabel("verified / enrolled peak MW")
    ax1.set_title("Utilization by sector, mean and range 2013-2024")
    ax1.set_ylim(0, 1)
    ax1.axhline(1.0, color="k", lw=0.8, ls=":")
    nat = df[df.sector == "total"]
    ax2.plot(nat.year, nat.utilization, marker="o", color=MEASURED)
    ax2.set_ylim(0, 1)
    ax2.set_title("National utilization, no trend")
    ax2.set_xlabel("year")
    ax2.axhline(nat.utilization.mean(), color=GREY, ls="--", lw=1)
    fig.suptitle(
        "EIA-861: most enrolled peak-reduction capability is not realised at peak",
        fontsize=11,
    )
    return _save(fig, "fig1_utilization.png")


def fig_cost_basis() -> pathlib.Path:
    df = t2.cost_table()
    year = int(df.year.max())
    cur = df[(df.year == year) & (df.sector != "transportation")].set_index("sector")
    order = ["residential", "commercial", "industrial", "total"]
    cur = cur.loc[[s for s in order if s in cur.index]]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    x = range(len(cur))
    ax.bar([i - 0.2 for i in x], cur.cost_per_kw_enrolled, width=0.4,
           label="per kW enrolled", color=MEASURED)
    ax.bar([i + 0.2 for i in x], cur.cost_per_kw_delivered, width=0.4,
           label="per kW delivered", color=SIM)
    rto = cone("RTO", "2027/2028")
    ax.axhline(rto.gross_cone_per_kw_yr, color="#2f6b3a", lw=1.6,
               label=f"PJM RTO gross CONE ${rto.gross_cone_per_kw_yr:.0f}")
    ax.axhline(rto.net_cone_per_kw_yr, color="#2f6b3a", lw=1.6, ls="--",
               label=f"PJM RTO net CONE ${rto.net_cone_per_kw_yr:.0f}")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cur.index)
    ax.set_ylabel("$ per kW-year")
    ax.set_title(f"DR program cost, {year}, against PJM's peaker on both bases")
    ax.legend(fontsize=8)
    return _save(fig, "fig2_cost_basis.png")


def fig_identifiability() -> pathlib.Path:
    tbl = t1.identifiability_table()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(tbl.return_period_years, tbl.min_window_years, marker="o", color=MEASURED)
    ax.axhline(t1.PANEL_YEARS, color=SIM, ls="--",
               label=f"panel length ({t1.PANEL_YEARS} y)")
    ax.axvline(t1.max_identifiable_return_period(t1.PANEL_YEARS), color=GREY, ls=":",
               label="largest identifiable return period")
    ax.set_xlabel("design return period of the reserve event (years)")
    ax.set_ylabel("years of quiet needed to reject reserve, alpha=0.05")
    ax.set_title("Phantom and reserve are not separable in a short panel")
    ax.legend(fontsize=8)
    return _save(fig, "fig3_identifiability.png")


def fig_curtailment() -> pathlib.Path:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    for ax, region in zip(axes, t4.REGIONS):
        df = t4.tag_windows(t4.load_region(region))
        prof = df.groupby("local_hour").renewable_share.mean()
        ax.plot(prof.index, prof.values, color=MEASURED)
        ax.axvspan(min(t4.DR_HOURS), max(t4.DR_HOURS), color=SIM, alpha=0.2)
        ax.axhline(df.risk_threshold.iloc[0], color=GREY, ls=":")
        ax.set_title(region)
        ax.set_xlabel("local hour")
    axes[0].set_ylabel("mean solar+wind share of generation")
    fig.suptitle(
        "Mean renewable share by local hour; dotted line is the top-decile threshold "
        "on individual hours, shading is the DR call window",
        fontsize=10,
    )
    return _save(fig, "fig4_curtailment_overlap.png")


def fig_reserve_breakeven() -> pathlib.Path:
    import pandas as pd

    grid = pd.DataFrame(t8.attack_c()["grid"])
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(grid.alternative_cost_per_kw_yr, grid.reserve_share_of_shortfall_needed,
            color=MEASURED)
    ax.axhline(0, color="k", lw=0.8)
    rto = cone("RTO", "2027/2028")
    ax.axvline(rto.gross_cone_per_kw_yr, color="#2f6b3a", lw=1.6,
               label="PJM RTO gross CONE")
    ax.axvline(rto.net_cone_per_kw_yr, color="#2f6b3a", lw=1.6, ls="--",
               label="PJM RTO net CONE")
    ax.set_ylim(-0.2, 1.0)
    ax.set_xlabel("alternative capacity cost, $ per kW-year")
    ax.set_ylabel("share of shortfall that must be genuine reserve")
    ax.set_title("How little insurance it takes to erase the phantom finding")
    ax.legend(fontsize=8)
    return _save(fig, "fig5_reserve_breakeven.png")


def fig_overhead() -> pathlib.Path:
    prof = t6.sector_profile().dropna()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    ax1.bar(prof.index, prof.overhead_per_kw_delivered, color=MEASURED)
    ax1.set_ylabel("$ per kW delivered")
    ax1.set_title("Non-incentive cost per delivered kW")
    ax2.scatter(prof.utilization, prof.overhead_share, color=SIM, s=70)
    for name, row in prof.iterrows():
        ax2.annotate(name, (row.utilization, row.overhead_share),
                     textcoords="offset points", xytext=(6, 4), fontsize=8)
    ax2.set_xlabel("utilization")
    ax2.set_ylabel("overhead share of program cost")
    ax2.set_title("Compounding hypothesis: sign is wrong")
    return _save(fig, "fig6_overhead.png")


def fig_composition() -> pathlib.Path:
    ss = t1.shift_share()
    ss = ss[ss.sector != "transportation"]
    frozen = t1.frozen_mix_series()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    x = range(len(ss))
    ax1.bar([i - 0.2 for i in x], ss.within, width=0.4, color=MEASURED,
            label="within sector")
    ax1.bar([i + 0.2 for i in x], ss["mix"], width=0.4, color=SIM, label="mix")
    ax1.axhline(0, color="k", lw=0.8)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(ss.sector)
    ax1.set_ylabel("contribution to change in national utilization")
    ax1.set_title(f"{ss.attrs['start']} to {ss.attrs['end']} decomposition")
    ax1.legend(fontsize=8)
    ax2.plot(frozen.year, frozen.actual, marker="o", color=MEASURED, label="actual")
    ax2.plot(frozen.year, frozen.frozen_mix, marker="s", ls="--", color=SIM,
             label="sector mix frozen at 2013")
    ax2.set_ylim(0.25, 0.55)
    ax2.set_xlabel("year")
    ax2.set_title("Mix is not what holds the ratio up")
    ax2.legend(fontsize=8)
    return _save(fig, "fig7_composition.png")


def fig_scope() -> pathlib.Path:
    mix = t1.regional_mix_floor()
    rv = t7.retail_vs_wholesale().set_index("year")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))
    ax1.barh(range(len(mix)), mix.mix_implied_utilization, color=MEASURED)
    ax1.set_yticks(range(len(mix)))
    ax1.set_yticklabels(mix.index, fontsize=8)
    ax1.axvline(float(mix.national_utilization.iloc[0]), color=GREY, ls="--", lw=1,
                label="national")
    ax1.set_xlim(0.25, 0.42)
    ax1.set_xlabel("class-mix implied utilization (a floor, not a measure)")
    ax1.set_title("Regional dispersion, mix effect only")
    ax1.legend(fontsize=8)
    year = int(rv.index.max())
    bars = {
        "retail\npotential": rv.loc[year, "retail_potential_mw"],
        "retail\nrealised": rv.loc[year, "retail_actual_mw"],
        "wholesale\nregistered": rv.loc[year, "wholesale_registered_mw"],
    }
    ax2.bar(list(bars), list(bars.values()),
            color=[MEASURED, MEASURED, SIM])
    ax2.set_ylabel("MW")
    ax2.set_title(f"Two accountings, {year}\noverlap unpublished, not additive", fontsize=11)
    for i, v in enumerate(bars.values()):
        ax2.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=9)
    return _save(fig, "fig8_scope.png")


def fig_verdicts() -> pathlib.Path:
    v = synthesis.verdict_table()
    labels = [
        f"{r.dr_basis.replace('per kW ', '')} vs {r.comparator.split()[0]}\n"
        f"({r.accreditation})"
        for _, r in v.iterrows()
    ]
    colors = [
        "#2f6b3a" if w else SIM for w in v.dr_wins
    ]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.barh(range(len(v)), v.ratio, color=colors)
    ax.axvline(1.0, color="k", lw=1.2)
    ax.set_yticks(range(len(v)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("demand response cost / comparator cost  (below 1 favours DR)")
    ax.set_title(
        "Eight defensible pairings. The two DR loses are both internally "
        "inconsistent",
        fontsize=11,
    )
    for i, (_, r) in enumerate(v.iterrows()):
        mark = "" if r.n_inconsistencies == 0 else f"  {r.n_inconsistencies} mismatch"
        ax.text(r.ratio + 0.02, i, f"{r.ratio:.2f}{mark}", va="center", fontsize=8)
    ax.set_xlim(0, 2.4)
    return _save(fig, "fig9_verdicts.png")


def fig_reporting() -> pathlib.Path:
    r = t8.reporting_intensity()
    d = t8.attack_d()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))
    ax1.barh(range(len(r)), r.intensity_index, color=MEASURED)
    ax1.axvline(1.0, color="k", lw=1.1)
    ax1.set_yticks(range(len(r)))
    ax1.set_yticklabels(r.index, fontsize=8)
    ax1.set_xlabel("mix-adjusted MW reported per enrolled customer, index")
    ax1.set_title("Same nominal quantity, reported 5.5x apart")
    bars = {
        "as reported": d["reported_utilization"],
        "at median\nstandard": d["utilization_at_median_standard"],
        "at least intense\nstandard": d["utilization_at_least_intense_standard"],
    }
    ax2.bar(list(bars), list(bars.values()), color=[MEASURED, GREY, SIM])
    ax2.set_ylim(0, 1.0)
    ax2.set_ylabel("national utilization")
    ax2.set_title("A bound on the room, not an estimate of the artefact",
                  fontsize=10)
    for i, v in enumerate(bars.values()):
        ax2.text(i, v, f"{v:.1%}", ha="center", va="bottom", fontsize=9)
    return _save(fig, "fig10_reporting.png")


def fig_targeting() -> pathlib.Path:
    st = t4.scarcity_targeting()
    ov = t4.overlap_table().set_index("region")
    at94 = st[st.depth_hours == 94].set_index("region")
    regions = list(t4.REGIONS)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))
    x = range(len(regions))
    ax1.bar([i - 0.2 for i in x], [ov.loc[r, "lift"] for r in regions],
            width=0.4, color=SIM, label="oversupply hours")
    ax1.bar([i + 0.2 for i in x], [at94.loc[r, "lift"] for r in regions],
            width=0.4, color=MEASURED, label="scarcity hours (top 94)")
    ax1.axhline(1.0, color="k", lw=1.1)
    ax1.set_yscale("log")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(regions)
    ax1.set_ylabel("lift over chance, log scale")
    ax1.set_title("The same call window, two questions")
    ax1.legend(fontsize=8)
    for i, r in enumerate(regions):
        if ov.loc[r, "lift"] == 0:
            ax1.text(i - 0.2, 0.035, "0", ha="center", fontsize=8, color=SIM)
    for region in regions:
        df = t4.load_region(region).copy()
        df["net_load"] = t4.net_load(region)
        prof = df.groupby("month").net_load.max() / df.net_load.max()
        ax2.plot(prof.index, prof.values, marker="o", ms=3, label=region)
    ax2.axvspan(min(t4.DR_MONTHS), max(t4.DR_MONTHS), color=SIM, alpha=0.15)
    ax2.set_xlabel("month")
    ax2.set_ylabel("monthly max net load, share of annual max")
    ax2.set_title("The blind spot is seasonal, not hourly", fontsize=11)
    ax2.legend(fontsize=8)
    return _save(fig, "fig11_targeting.png")


def fig_decomposition() -> pathlib.Path:
    dec = t9.decomposition().set_index("year")
    size = t9.size_gradient()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    parts = [
        ("realised", "realised", MEASURED),
        ("gap_partial_delivery", "partial delivery (open)", SIM),
        ("gap_unreported", "no actual reported", GREY),
        ("gap_zero_mass", "exact zero (non-dispatch)", ZERO),
    ]
    bottom = None
    for col, label, colour in parts:
        ax1.bar(dec.index.astype(str), dec[col], bottom=bottom, label=label, color=colour)
        bottom = dec[col] if bottom is None else bottom + dec[col]
    ax1.set_ylim(0, 1)
    ax1.set_ylabel("share of enrolled capacity")
    ax1.set_title("The gap is three things", fontsize=11)
    ax1.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2,
               frameon=False)
    import numpy as np
    import pandas as pd

    pan = t9.panel()
    pos = pan[pan.status != "not_reported"].copy()
    pos["band"] = pd.qcut(pos.potential_peak_mw.rank(method="first"), 4,
                          labels=["smallest", "second", "third", "largest"])
    pos["copied"] = np.isclose(pos.actual_peak_mw, pos.potential_peak_mw) & (pos.actual_peak_mw > 0)
    raw = pos.groupby("band", observed=True).utilization.median()
    meas = pos[~pos.copied].groupby("band", observed=True).utilization.median()
    copied = pos[pos.actual_peak_mw > 0].groupby("band", observed=True).copied.mean()
    x = np.arange(len(raw))
    ax2.bar(x - 0.2, raw.values, width=0.4, color=GREY, label="all reports")
    ax2.bar(x + 0.2, meas.values, width=0.4, color=MEASURED, label="measured reports only")
    ax2.plot(x, copied.values, color=SIM, marker="o", label="share with actual = potential")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(list(raw.index))
    ax2.set_ylim(0, 1)
    ax2.set_xlabel("program size, quartile of enrolled MW")
    ax2.set_ylabel("median dispatch utilization / share")
    ax2.set_title("Most of the size gradient is copied reports", fontsize=11)
    ax2.legend(fontsize=8)
    return _save(fig, "fig12_decomposition.png")


def fig_rotation() -> pathlib.Path:
    """What the published rotation statistic was made of, and what zero
    capacity did the following year. Both panels label every bar, so no reading
    depends on colour."""
    import numpy as np

    comp = t1.rotation_composition()
    by = comp.groupby("class").share_of_ever_zero_mw.sum()
    rows = [
        ("measured delivery in another year", by.get("measured", 0.0), MEASURED),
        ("zero in every year", by.get("zero_every_year", 0.0), ZERO),
        ("enrolled capacity moved over threefold", by.get("resized", 0.0), UNINFORMATIVE),
        ("other year within 1% of enrolment",
         by.get("near_copy", 0.0) + by.get("copied", 0.0), UNINFORMATIVE),
        ("positive years all under 5%", by.get("near_zero", 0.0), UNINFORMATIVE),
    ]
    fu = t1.zero_followup()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8),
                                   gridspec_kw={"width_ratios": [1.05, 1]})
    y = np.arange(len(rows))[::-1]
    for yi, (label, share, colour) in zip(y, rows):
        ax1.barh(yi, share, color=colour, height=0.62, edgecolor="white", linewidth=2)
        ax1.text(share + 0.008, yi, f"{share:.0%}", va="center", fontsize=9)
    ax1.set_yticks(y)
    ax1.set_yticklabels([r[0] for r in rows], fontsize=9)
    ax1.set_xlim(0, 0.40)
    ax1.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax1.set_xlabel("share of capacity ever reported at exactly zero, 2016 to 2018")
    rotating = 1 - by.get("zero_every_year", 0.0)
    ax1.set_title(
        f"The published {rotating:.0%} rotation, by what the other years show.\n"
        "Only the blue bar shows the capacity could deliver",
        fontsize=10,
    )
    for side in ("top", "right"):
        ax1.spines[side].set_visible(False)

    groups = [("exact_zero", "zero", ZERO), ("measured", "measured", MEASURED),
              ("copied", "copied", GREY)]
    transitions = list(fu.groupby(["from_year", "to_year"]).groups)
    ticks, labels = [], []
    for k, (a, b) in enumerate(transitions):
        base = k * (len(groups) + 1)
        for j, (key, name, colour) in enumerate(groups):
            row = fu[(fu.from_year == a) & (fu.to_year == b)
                     & (fu.group_in_from_year == key)].iloc[0]
            x = base + j
            ax2.bar(x, row.next_year_delivery, color=colour, width=0.8,
                    edgecolor="white", linewidth=2)
            value = row.next_year_delivery
            ax2.text(x, value + 0.02, f"{value:.1%}" if value < 0.1 else f"{value:.0%}",
                     ha="center", fontsize=9)
            ticks.append(x)
            labels.append(name)
        ax2.text(base + 1, -0.17, f"in {a}, followed into {b}", ha="center",
                 fontsize=9, transform=ax2.get_xaxis_transform())
    last = fu[(fu.to_year == transitions[-1][1]) & (fu.group_in_from_year == "exact_zero")].iloc[0]
    ax2.annotate(
        f"{last.largest_state_share:.0%} of this from\n"
        f"{last.utilities_in_largest_state} utilities in {last.largest_state}",
        xy=(len(groups) + 0.7, last.next_year_delivery), xytext=(len(groups) - 0.45, 0.6),
        fontsize=8, arrowprops={"arrowstyle": "-", "color": GREY, "lw": 0.8},
    )
    ax2.set_xticks(ticks)
    ax2.set_xticklabels(labels, fontsize=8.5)
    ax2.set_ylim(0, 1)
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax2.set_ylabel("next-year delivery, share of first-year potential")
    ax2.set_title("Capacity grouped by what it reported first,\nfollowed one year on",
                  fontsize=10)
    for side in ("top", "right"):
        ax2.spines[side].set_visible(False)
    fig.suptitle(
        "EIA-861 utility files: zero-reported capacity mostly stays dark, and most of "
        "its rotation measures nothing",
        fontsize=11,
    )
    return _save(fig, "fig13_rotation.png")


def make_all() -> list[pathlib.Path]:
    return [
        fig_utilization(),
        fig_cost_basis(),
        fig_identifiability(),
        fig_curtailment(),
        fig_reserve_breakeven(),
        fig_overhead(),
        fig_composition(),
        fig_scope(),
        fig_verdicts(),
        fig_reporting(),
        fig_targeting(),
        fig_decomposition(),
        fig_rotation(),
    ]
