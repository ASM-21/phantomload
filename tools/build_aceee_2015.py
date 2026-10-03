"""Build data/aceee_dr_utilities_2015.csv.

PROVENANCE. Transcribed from the data appendix to:

  Steven Nadel, "Demand response programs can reduce utilities' peak demand an
  average of 10%, complementing savings from energy efficiency programs",
  ACEEE, 9 February 2017.
  https://www.aceee.org/blog/2017/02/demand-response-programs-can-reduce
  Appendix: "Summary of data on 28 utilities reporting at least 200 MW of
  potential demand response savings".

ACEEE's own source is the 2015 Form EIA-861 demand response file, so this is the
utility-level cut of exactly the series the national panel comes from. Its
national footer row, 32,875 MW potential and 13,036 MW actual across all 421
reporting utilities, reproduces the vendored national panel for 2015 to the
digit, which a test asserts.

WHY THIS MATTERS MORE THAN ITS SIZE SUGGESTS. Every other dataset here is an
aggregate. ROADMAP item 1 asked whether a national realisation rate near 40%
means every utility lands near 40%, or whether a large share of the fleet
delivers nothing while the rest delivers most of what it promised. Those two
worlds imply completely different policy and the aggregates cannot tell them
apart. These 28 rows can, for the largest programs in one year.

CAVEATS, all ACEEE's own and carried here:
  - Self-reported and unaudited. ACEEE removed some utilities with obvious
    errors, noting that a few reported demand response savings exceeding their
    own peak demand.
  - Three utilities reported potential but no actual value. Those are blank
    here, never zero, because "did not report" and "called nothing" are the
    distinction this whole repository is about.
  - Duke Energy Carolinas appears twice, once for NC and once for SC, against
    the same 18,490 MW system peak. Rows are kept as published.
  - One year, 2015, and the largest programs only. Not a random sample.
"""

from __future__ import annotations

import csv
import pathlib

# utility, state, potential MW, actual MW (None = not reported), 2015 peak MW
ROWS = [
    ("North Carolina Eastern MPA", "NC", 361, 325, 1_359),
    ("Great River Energy", "MN", 520, 280, 2_524),
    ("Arkansas Electric Coop Corp", "AR", 628, 151, 3_301),
    ("Southern California Edison Co", "CA", 4_086, 2_725, 22_556),
    ("Wisconsin Public Service Corp", "WI", 381, 47, 2_117),
    ("Gulf Power Co", "FL", 369, 369, 2_495),
    ("Alabama Power Co", "AL", 1_667, 120, 12_398),
    ("Duke Energy Florida, Inc", "FL", 1_039, 0, 9_475),
    ("Idaho Power Co", "ID", 345, 31, 3_402),
    ("Duke Energy Indiana, LLC", "IN", 582, 6, 5_748),
    ("Interstate Power and Light Co", "IA", 301, 0, 3_005),
    ("The Toledo Edison Co", "OH", 206, 1, 2_149),
    ("South Carolina Public Service Authority", "SC", 523, 0, 5_869),
    ("JEA", "FL", 254, 165, 2_863),
    ("Indiana Michigan Power Co", "IN", 377, 351, 4_398),
    ("Public Service Co of Colorado", "CO", 489, 489, 6_111),
    ("Florida Power & Light Co", "FL", 1_666, 0, 22_859),
    ("Tennessee Valley Authority", "TN", 2_342, 646, 32_751),
    ("Commonwealth Edison Co", "IL", 1_305, 105, 20_163),
    ("Baltimore Gas & Electric Co", "MD", 394, 0, 6_712),
    ("MidAmerican Energy Co", "IA", 211, None, 4_624),
    ("Duke Energy Carolinas, LLC", "NC", 674, 266, 18_490),
    ("Duke Energy Progress - (NC)", "NC", 520, 426, 14_814),
    ("Nevada Power Co", "NV", 206, 161, 5_864),
    ("Pacific Gas & Electric Co", "CA", 557, 273, 18_631),
    ("Georgia Power Co", "GA", 339, None, 16_104),
    ("Consolidated Edison Co-NY Inc", "NY", 233, None, 12_613),
    ("Duke Energy Carolinas, LLC", "SC", 287, 154, 18_490),
]

# ACEEE's footer row, across every utility in the 2015 EIA-861 file
NATIONAL_2015 = {"utilities": 421, "potential_mw": 32_875, "actual_mw": 13_036}


def build_rows() -> list[dict]:
    out = []
    for utility, state, potential, actual, peak in ROWS:
        out.append(
            {
                "utility": utility,
                "state": state,
                "potential_peak_mw": potential,
                "actual_peak_mw": "" if actual is None else actual,
                "system_peak_mw": peak,
                "reported_actual": actual is not None,
            }
        )
    return out


def main() -> None:
    out = (
        pathlib.Path(__file__).resolve().parents[1]
        / "data"
        / "aceee_dr_utilities_2015.csv"
    )
    rows = build_rows()
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
