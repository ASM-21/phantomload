"""Run every track, write results/ and figures/, print the headline numbers.

    python run_all.py            # everything
    python run_all.py --no-figs  # tables only
"""

from __future__ import annotations

import argparse
import json
import pathlib

import pandas as pd

from phantomload import synthesis
from phantomload.tracks import (
    t1_utilization,
    t2_cost,
    t3_behavioral,
    t4_curtailment,
    t5_double_count,
    t6_overhead,
    t7_crossval,
    t8_falsification,
)

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS = ROOT / "results"

TRACKS = {
    "t1_utilization": t1_utilization,
    "t2_cost": t2_cost,
    "t3_behavioral": t3_behavioral,
    "t4_curtailment": t4_curtailment,
    "t5_double_count": t5_double_count,
    "t6_overhead": t6_overhead,
    "t7_crossval": t7_crossval,
    "t8_falsification": t8_falsification,
    "synthesis": synthesis,
}

# Run order from the spec: shared layer, then track 1 (foundational), then the
# fast reuse track, then cost, overhead, the synthetic pair, cross-validation,
# and falsification last so it can attack finished work.
ORDER = [
    "t1_utilization",
    "t5_double_count",
    "t2_cost",
    "t6_overhead",
    "t3_behavioral",
    "t4_curtailment",
    "t7_crossval",
    "t8_falsification",
    "synthesis",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-figs", action="store_true")
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    findings: dict[str, dict] = {}

    for name in ORDER:
        out = TRACKS[name].run()
        for key, value in out.items():
            if isinstance(value, pd.DataFrame):
                value.to_csv(RESULTS / f"{name}__{key}.csv", index=False)
            elif key == "summary":
                findings[name] = value
        print(f"ran {name}: {len(out)} outputs")

    (RESULTS / "findings.json").write_text(json.dumps(findings, indent=2, default=str))

    if not args.no_figs:
        from phantomload.shared.plotting import make_all

        for path in make_all():
            print(f"figure {path.name}")

    s1, s2 = findings["t1_utilization"], findings["t2_cost"]
    s8, sy = findings["t8_falsification"], findings["synthesis"]
    print("\nheadline")
    print(
        f"  utilization {s1['mean_utilization']:.1%} mean over "
        f"{s1['n_years']} years, so {s1['shortfall_share_mean']:.1%} of enrolled "
        "capability is not realised at peak"
    )
    print(
        f"  cost ${s2['cost_per_kw_enrolled']:.2f}/kW-yr enrolled vs "
        f"${s2['cost_per_kw_delivered']:.2f}/kW-yr delivered "
        f"({s2['basis_gap_ratio']:.2f}x)"
    )
    c = s8["attack_c"]
    print(
        f"  against PJM gross CONE (${c['gross_cone_per_kw_yr']:.2f}/kW-yr) that "
        "still clears with no reserve credit; against net CONE "
        f"(${c['net_cone_per_kw_yr']:.2f}) it needs "
        f"{c['reserve_share_needed_at_net_cone']:.1%} of the shortfall to be "
        "genuine reserve"
    )
    d = s8["attack_d"]
    print(
        f"  and mix-adjusted reporting intensity varies "
        f"{d['mix_adjusted_intensity_spread']:.1f}x across census divisions, "
        "enough room to hold the whole shortfall on its own"
    )
    print(
        f"  across {sy['cells']} pairings of accounting bases DR wins "
        f"{sy['dr_wins_cells']}, and both losses carry a basis mismatch; align "
        "everything and the answer turns on avoided energy worth "
        f"${sy['breakeven_breakeven_price_at_high_hours']:.2f}/kWh, "
        f"{sy['breakeven_multiple_of_annual_avg_needed']:.1f}x PJM's annual "
        "load-weighted average price"
    )


if __name__ == "__main__":
    main()
