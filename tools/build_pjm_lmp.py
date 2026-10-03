"""Build data/pjm_lmp.csv from the PJM independent market monitor's reports.

PROVENANCE. Real-time load-weighted average locational marginal price for the
PJM footprint, as reported by Monitoring Analytics:

  2023, 2024  "2024 State of the Market Report for PJM", IMM press briefing,
              March 2025, PJM market summary statistics table.
              https://www.monitoringanalytics.com/reports/PJM_State_of_the_Market/
              2024/2024-som-pjm-press-briefing.pdf
  2025        "Market Monitor Report", IMM Members Committee presentation,
              22 January 2026: real-time hourly load-weighted average LMP
              through 31 December 2025.
              https://www.pjm.com/-/media/DotCom/committees-groups/committees/
              mc/2026/20260122/20260122-item-06---market-monitoring-report---
              presentation.pdf

Retrieved 2026-09-10.

WHAT THIS IS FOR, AND THE TRAP IN USING IT. Track 2 and the synthesis both end
on the value of the energy a curtailment avoids buying, which is not published.
This series does not supply it. It is an ANNUAL LOAD-WEIGHTED AVERAGE across
every hour of the year, while demand response is called in roughly the top one
percent of hours, where price is higher by a factor nothing here measures.

So it is used one way only: as a denominator that converts an abstract dollars
per kWh requirement into a multiple of the average price, which a reader can
judge. Anyone using it as the price of avoided energy in called hours will
understate that value badly, and the code says so at every point of use.

The hourly series that would settle it exists in PJM Data Miner, which is not
reachable from the environment this was built in.
"""

from __future__ import annotations

import csv
import pathlib

# year -> ($/MWh real-time load-weighted average LMP, coverage note)
LOAD_WEIGHTED_AVERAGE_LMP = {
    2023: (31.08, "full year, 2024 SOM report comparison column"),
    2024: (33.74, "full year, 2024 SOM report"),
    2025: (50.73, "through 2025-12-31, IMM Members Committee report"),
}


def build_rows() -> list[dict]:
    return [
        {
            "year": year,
            "rt_load_weighted_avg_lmp_usd_per_mwh": value,
            "rt_load_weighted_avg_lmp_usd_per_kwh": round(value / 1_000, 6),
            "coverage": note,
            "basis": "annual average across all hours, NOT called-hour price",
        }
        for year, (value, note) in sorted(LOAD_WEIGHTED_AVERAGE_LMP.items())
    ]


def main() -> None:
    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "pjm_lmp.csv"
    rows = build_rows()
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
