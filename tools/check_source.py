"""Diff the vendored EIA panel against the live published tables.

`tools/build_eia861_panel.py` holds the transcription. This script checks that
the transcription still matches what EIA publishes, which is the one failure
mode a vendored dataset has that a fetched one does not: EIA revises prior-year
values in later vintages, and a vendored copy will not notice.

Network is optional. If eia.gov is unreachable, which is the normal case in the
environment this repo was built in, the script says so and exits 0. It only
fails on a genuine mismatch, so it is safe to wire into CI without making the
build depend on a government website being up.

    python tools/check_source.py            # compare, tolerate no network
    python tools/check_source.py --require  # fail if the source is unreachable

Caveat worth knowing before trusting a green result: the HTML parser here has
been exercised against a synthetic fixture in tests, not against the live page,
because eia.gov was not reachable from the environment this was written in. If
the published table layout differs from the fixture, the script reports that it
parsed nothing and skips rather than claiming a match. Check the first real run
by hand.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "https://www.eia.gov/electricity/annual/html"

# published table -> (metric label as printed, our column name)
TABLES = {
    f"{BASE}/epa_10_03.html": {
        "Number of Customers Enrolled": "customers_enrolled",
        "Energy Savings (MWh)": "energy_savings_mwh",
        "Potential Peak Demand Savings (MW)": "potential_peak_mw",
        "Actual Peak Demand Savings (MW)": "actual_peak_mw",
    },
    f"{BASE}/epa_10_04.html": {
        "Customer Incentives (thousand dollars)": "customer_incentives_kusd",
        "All Other Costs (thousand dollars)": "other_costs_kusd",
    },
}

SECTOR_ORDER = ["residential", "commercial", "industrial", "transportation", "total"]
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def fetch(url: str, timeout: int = 20) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "phantomload/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def parse(html: str, wanted: dict[str, str]) -> dict[tuple[int, str, str], float]:
    """Walk the flat cell stream, tracking which metric block we are inside."""
    cells = [TAG.sub("", c).replace("&nbsp;", " ").strip() for c in CELL.findall(html)]
    out: dict[tuple[int, str, str], float] = {}
    metric: str | None = None
    i = 0
    while i < len(cells):
        cell = cells[i]
        if cell in wanted:
            metric = wanted[cell]
            i += 1
            continue
        if metric and re.fullmatch(r"(19|20)\d{2}", cell):
            year = int(cell)
            values = cells[i + 1 : i + 1 + len(SECTOR_ORDER)]
            if len(values) == len(SECTOR_ORDER):
                for sector, raw in zip(SECTOR_ORDER, values):
                    clean = raw.replace(",", "").replace("$", "")
                    if clean in {"--", "-", "", "NA", "NM"}:
                        continue
                    try:
                        out[(year, sector, metric)] = float(clean)
                    except ValueError:
                        pass
            i += 1 + len(SECTOR_ORDER)
            continue
        i += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--require", action="store_true", help="fail if unreachable")
    args = ap.parse_args()

    from phantomload.shared.dr_program import load_eia_panel

    panel = load_eia_panel()

    live: dict[tuple[int, str, str], float] = {}
    unreachable = []
    for url, wanted in TABLES.items():
        html = fetch(url)
        if html is None:
            unreachable.append(url)
            continue
        live.update(parse(html, wanted))

    if unreachable:
        print("could not reach:")
        for url in unreachable:
            print(f"  {url}")
        if args.require:
            print("FAIL source unreachable and --require was set")
            return 1
        if not live:
            print("SKIP no live data retrieved, vendored panel left unchecked")
            return 0

    if not live:
        print("SKIP source reachable but no values parsed; the table layout may "
              "have changed, check the parser before trusting this result")
        return 0

    mismatches, missing = [], []
    for (year, sector, metric), value in sorted(live.items()):
        if (year, sector) not in panel.index or metric not in panel.columns:
            missing.append((year, sector, metric, value))
            continue
        vendored = panel.loc[(year, sector), metric]
        if vendored != vendored:  # NaN
            missing.append((year, sector, metric, value))
            continue
        if abs(vendored - value) > 0.5:
            mismatches.append((year, sector, metric, vendored, value))

    for year, sector, metric, vendored, value in mismatches:
        print(f"MISMATCH {year} {sector} {metric}: vendored {vendored} live {value}")
    for year, sector, metric, value in missing:
        print(f"NOT VENDORED {year} {sector} {metric}: live {value}")

    print(f"\ncompared {len(live)} published cells against the vendored panel")
    if mismatches:
        print(f"FAIL {len(mismatches)} mismatch(es). EIA may have revised a prior "
              "year: update tools/build_eia861_panel.py, rerun it, then rerun "
              "the tests and tools/check_claims.py, since headline numbers move.")
        return 1
    if missing:
        print(f"NOTE {len(missing)} published cell(s) are not in the vendored "
              "panel. Expected for years EIA has added since transcription.")
    print("OK vendored panel matches the published tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
