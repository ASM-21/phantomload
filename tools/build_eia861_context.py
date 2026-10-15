"""Build the EIA-861 context files for 2016 to 2018 from the detailed data files.

These are the other schedules of the same survey whose demand response schedule
is vendored in data/eia861_dr_utility_2016_2018.csv. They exist here to check
the demand response figures against things the same utilities reported about
themselves on other pages of the same form.

  data/eia861_peaks_2016_2018.csv
      Operational_Data_<year>.xlsx, sheet "States". One row per utility per
      year: summer peak (maximum hourly load, June to September) and winter
      peak (maximum hourly load, January to March and the previous December),
      both on the net energy of the system, in MW.
  data/eia861_meters_2016_2018.csv
      Advanced_Meters_<year>.xlsx, first sheet. One row per utility, state and
      balancing authority: AMI meters, all meters, and Schedule 6 Part D line
      8, "the number of customers with direct load control, by customer class".
  data/eia861_dynamic_pricing_2017_2018.csv
      Dynamic_Pricing_<year>.xlsx, first sheet. Customers enrolled in
      time-of-use, real-time, variable peak, critical peak pricing or critical
      peak rebate programs, by class. The 2016 file is not in the mirror.
  data/eia861_customers_2016_2018.csv
      Sales_Ult_Cust_<year>.xlsx, sheet "States". Customer counts by class, one
      row per utility, state, balancing authority and part (A bundled, B energy
      only, C delivery only, D bundled service by energy service providers,
      which the instructions say is typically Texas alone).
  data/eia861_short_form_2016_2018.csv
      Short_Form_<year>.xlsx. The utilities that filed the abbreviated Form
      EIA-861S, which collects no demand response quantities, only a yes or no
      flag for demand-side management.

PROVENANCE. Form EIA-861 "Annual Electric Power Industry Report", detailed data
files for 2016, 2017 and 2018. US Government work, not subject to domestic
copyright. Reached the same way as the demand response files, vendored
unmodified as inputs to an unrelated project:

  IMMM-SFA/electricity_entity_boundaries, EIA_861_Dataset/<year>/,
  https://github.com/IMMM-SFA/electricity_entity_boundaries (BSD 2-Clause for
  that project's code; the EIA files it bundles are public domain).

The demand response files were found there in September 2026; nobody looked at
the files next to them until October. They were found by asking what else the
same directory held, which is cheaper than any search and is recorded in
METHOD.md.

HANDLING, all tested:
  - "." means not applicable or not reported and becomes blank, never zero.
  - Utility number 88888 is EIA's placeholder for withheld retail marketers
    in Texas. It reports no peak and is dropped from the peaks file.
  - Only the States sheets are used, matching the demand response panel.
  - Values are written exactly as stored in the workbook, without rounding.

    python tools/build_eia861_context.py /path/to/EIA_861_Dataset
"""

from __future__ import annotations

import csv
import pathlib
import sys

YEARS = (2016, 2017, 2018)
CLASSES = ("residential", "commercial", "industrial", "transportation", "total")
WITHHELD = "88888"


def _clean(v) -> str:
    s = "" if v is None else str(v).strip()
    return "" if s in {".", "", "nan", "None", "NaN"} else s


def _number(v) -> str:
    """Utility numbers arrive as '55' or '55.0' depending on the workbook."""
    s = _clean(v)
    return s.split(".")[0] if s else s


def _sheet(path: pathlib.Path, sheet=0):
    import pandas as pd

    return pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)


def _expect(raw, row: int, col: int, text: str, path) -> None:
    got = _clean(raw.iat[row, col])
    if not got.lower().startswith(text.lower()):
        raise ValueError(f"{path.name}: expected {text!r} at ({row},{col}), found {got!r}")


def peaks(root: pathlib.Path, year: int) -> list[dict]:
    path = root / str(year) / f"Operational_Data_{year}.xlsx"
    raw = _sheet(path, "States")
    for col, text in [(1, "Utility Number"), (2, "Utility Name"), (3, "State"),
                      (4, "Ownership"), (5, "NERC Region"), (6, "Summer Peak Demand"),
                      (7, "Winter Peak Demand")]:
        _expect(raw, 2, col, text, path)
    rows = []
    for r in raw.iloc[3:].itertuples(index=False):
        number = _number(r[1])
        if not number or number == WITHHELD:
            continue
        rows.append({
            "year": year,
            "utility_number": number,
            "utility": _clean(r[2]),
            "state": _clean(r[3]),
            "ownership": _clean(r[4]),
            "nerc_region": _clean(r[5]),
            "summer_peak_mw": _clean(r[6]),
            "winter_peak_mw": _clean(r[7]),
        })
    return rows


# Advanced_Meters: six identifier columns, then eight blocks of five classes.
METER_BLOCKS = {
    "Number AMI": "ami",
    "Total Numbers of Meters": "meters",
    "Customers with Direct Load": "dlc",
}


def meters(root: pathlib.Path, year: int) -> list[dict]:
    path = root / str(year) / f"Advanced_Meters_{year}.xlsx"
    raw = _sheet(path, 0)
    for col, text in [(1, "Utility Number"), (3, "Short Form"), (4, "State")]:
        _expect(raw, 1, col, text, path)
    _expect(raw, 1, 5, "BA", path)
    blocks = {}
    top = raw.iloc[0].ffill()
    for j in range(6, raw.shape[1]):
        for prefix, key in METER_BLOCKS.items():
            if _clean(top.iloc[j]).startswith(prefix):
                blocks[(key, _clean(raw.iat[1, j]).lower())] = j
    wanted = [("ami", "total"), ("meters", "total")] + [("dlc", c) for c in CLASSES if c != "transportation"]
    missing = [w for w in wanted if w not in blocks]
    if missing:
        raise ValueError(f"{path.name}: columns not found {missing}")
    rows = []
    for r in raw.iloc[2:].itertuples(index=False):
        number = _number(r[1])
        if not number:
            continue
        rec = {"year": year, "utility_number": number, "state": _clean(r[4]),
               "ba_code": _clean(r[5]), "short_form": _clean(r[3])}
        for key, cls in wanted:
            rec[f"{key}_{cls}"] = _clean(r[blocks[(key, cls)]])
        rows.append(rec)
    return rows


def dynamic_pricing(root: pathlib.Path, year: int) -> list[dict]:
    path = root / str(year) / f"Dynamic_Pricing_{year}.xlsx"
    if not path.exists():
        return []
    raw = _sheet(path, 0)
    for col, text in [(1, "Utility Number"), (3, "State"), (4, "BA")]:
        _expect(raw, 2, col, text, path)
    _expect(raw, 1, 5, "Customers Enrolled", path)
    cols = {c: 5 + i for i, c in enumerate(CLASSES)}
    for c, j in cols.items():
        _expect(raw, 2, j, c, path)
    rows = []
    for r in raw.iloc[3:].itertuples(index=False):
        number = _number(r[1])
        if not number:
            continue
        rec = {"year": year, "utility_number": number, "state": _clean(r[3]), "ba_code": _clean(r[4])}
        for c in CLASSES:
            if c != "transportation":
                rec[f"dp_{c}"] = _clean(r[cols[c]])
        rows.append(rec)
    return rows


def customers(root: pathlib.Path, year: int) -> list[dict]:
    path = root / str(year) / f"Sales_Ult_Cust_{year}.xlsx"
    raw = _sheet(path, "States")
    for col, text in [(1, "Utility Number"), (3, "Part"), (4, "Service Type"), (6, "State")]:
        _expect(raw, 2, col, text, path)
    _expect(raw, 2, 8, "BA", path)
    top = raw.iloc[0].ffill()
    cols = {}
    for j in range(9, raw.shape[1]):
        if _clean(raw.iat[1, j]) == "Customers":
            cols[_clean(top.iloc[j]).lower()] = j
    if set(cols) != set(CLASSES):
        raise ValueError(f"{path.name}: customer blocks {sorted(cols)}")
    rows = []
    for r in raw.iloc[3:].itertuples(index=False):
        number = _number(r[1])
        if not number:
            continue
        rec = {"year": year, "utility_number": number, "state": _clean(r[6]),
               "ba_code": _clean(r[8]), "part": _clean(r[3]), "service_type": _clean(r[4])}
        for c in CLASSES:
            if c != "transportation":
                rec[f"customers_{c}"] = _clean(r[cols[c]])
        rows.append(rec)
    return rows


def short_form(root: pathlib.Path, year: int) -> list[dict]:
    path = root / str(year) / f"Short_Form_{year}.xlsx"
    raw = _sheet(path, 0)
    for col, text in [(1, "Utility Number"), (3, "Ownership"), (4, "State"),
                      (11, "Demand Side Management")]:
        _expect(raw, 0, col, text, path)
    rows = []
    for r in raw.iloc[1:].itertuples(index=False):
        number = _number(r[1])
        if not number:
            continue
        rows.append({"year": year, "utility_number": number, "ownership": _clean(r[3]),
                     "state": _clean(r[4]), "demand_side_management": _clean(r[11])})
    return rows


OUTPUTS = {
    "eia861_peaks_2016_2018.csv": peaks,
    "eia861_meters_2016_2018.csv": meters,
    "eia861_dynamic_pricing_2017_2018.csv": dynamic_pricing,
    "eia861_customers_2016_2018.csv": customers,
    "eia861_short_form_2016_2018.csv": short_form,
}


def main() -> None:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "EIA_861_Dataset")
    data = pathlib.Path(__file__).resolve().parents[1] / "data"
    for name, parse in OUTPUTS.items():
        rows = [r for y in YEARS for r in parse(root, y)]
        out = data / name
        with out.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows -> {out.relative_to(data.parent)}")


if __name__ == "__main__":
    main()
