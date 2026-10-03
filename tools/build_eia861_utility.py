"""Build data/eia861_dr_utility_2016_2018.csv from EIA-861 detailed files.

PROVENANCE. Form EIA-861 "Annual Electric Power Industry Report", detailed data
files Demand_Response_2016.xlsx, Demand_Response_2017.xlsx and
Demand_Response_2018.xlsx, sheet "Demand Response_States". US Government work,
not subject to domestic copyright.

HOW THEY WERE REACHED. eia.gov is blocked from the environment this repository
was built in, and was re-tested and still blocked on 2026-09-20. The files were
found vendored, unmodified, as incidental inputs to an unrelated project:

  IMMM-SFA/electricity_entity_boundaries, EIA_861_Dataset/<year>/,
  https://github.com/IMMM-SFA/electricity_entity_boundaries (BSD 2-Clause for
  that project's code; the EIA files it bundles are public domain).

That project maps utilities to counties. No search for the subject of this
repository would ever surface it. It was found by searching for the FILE NAME,
Demand_Response_<year>.xlsx, which is the lesson worth carrying and is recorded
in METHOD.md.

INTEGRITY. Every year reconciles to the vendored national panel to the megawatt,
potential and actual, which a test asserts. That is the fourth independent
source agreeing on the same series, and the first at utility grain.

HANDLING, all tested:
  - "." in the source means not applicable or not reported. It becomes blank,
    never zero. Blank actual with positive potential and zero actual with
    positive potential are the two categories this repository exists to
    distinguish, and conflating them is the error that would matter most.
  - A utility reporting in several states appears once per state. The key is
    utility number plus state, as published.

    python tools/build_eia861_utility.py /path/to/EIA_861_Dataset
"""

from __future__ import annotations

import csv
import pathlib
import sys

YEARS = (2016, 2017, 2018)
SHEET = "Demand Response_States"
SECTIONS = {
    "Number of Customers Enrolled|Total": "customers_enrolled",
    "Potential Peak Demand Savings (MW)|Total": "potential_peak_mw",
    "Actual Peak Demand Savings (MW)|Total": "actual_peak_mw",
    "Energy Savings (MWh)|Total": "energy_savings_mwh",
    "Customer Incentives (Thousand Dollars)|Total": "customer_incentives_kusd",
    "All Other Costs (Thousand Dollars)|Total": "other_costs_kusd",
}


def parse_year(root: pathlib.Path, year: int) -> list[dict]:
    import pandas as pd

    path = root / str(year) / f"Demand_Response_{year}.xlsx"
    raw = pd.read_excel(path, sheet_name=SHEET, header=None)
    section = raw.iloc[1].ffill()
    klass = raw.iloc[2]
    cols = [
        f"{s}|{c}" if pd.notna(s) and str(s) != "nan" else str(c)
        for s, c in zip(section, klass)
    ]
    body = raw.iloc[3:].copy()
    body.columns = cols
    rows = []
    for _, r in body.iterrows():
        rec = {
            "year": year,
            "utility_number": str(r["Utility Number"]).split(".")[0],
            "utility": str(r["Utility Name"]).strip(),
            "state": str(r["State"]).strip(),
            "ba_code": str(r["BA Code"]).strip() if "BA Code" in body.columns else "",
        }
        for src, dst in SECTIONS.items():
            v = r.get(src)
            rec[dst] = "" if v is None or str(v).strip() in {".", "", "nan"} else v
        rows.append(rec)
    return rows


def main() -> None:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "EIA_861_Dataset")
    rows = [r for y in YEARS for r in parse_year(root, y)]
    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "eia861_dr_utility_2016_2018.csv"
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
