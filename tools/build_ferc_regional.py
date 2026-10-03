"""Build data/ferc_dr_regional.csv and data/rto_dr.csv.

PROVENANCE. Transcribed verbatim from:

  Federal Energy Regulatory Commission, "2025 Assessment of Demand Response and
  Advanced Metering", Staff Report, December 2025.
  https://www.ferc.gov/sites/default/files/2025-12/
  25_Annual%20Assessment%20of%20Demand%20Response_1212.pdf
  Retrieved 2026-09-05. US Government work, not subject to domestic copyright.

  Table 3-1  potential peak demand savings by census division, 2022 and 2023
  Table 3-2  potential peak demand savings by census division and class, 2023
  Table 3-3  demand response resource participation in RTOs and ISOs, 2023-2024
  Table 5-1  retail demand response enrolment by census division, 2022-2023
  Table 5-2  retail dynamic pricing enrolment by census division, 2022-2023

WHY THIS MATTERS TO THE REPO. Tables 3-1, 3-2 and 5-1 are FERC staff's own
aggregation of the same EIA-861 files the national panel comes from, so they
give a regional cut of a series this repo previously only had nationally, and a
cross-source check: FERC's division sums must reproduce EIA's national class
totals. A test asserts they do.

Tables 3-3 and 5-2 are different animals. Table 3-3 counts wholesale market
registrations reported by the RTOs and ISOs, not utility programs reported to
EIA, so it is a partly disjoint population and the two totals must not be added.
Table 5-2 counts customers on time-varying rates, which is the denominator
track 5's double-counting arithmetic was missing.

CAVEAT CARRIED THROUGH EVERY ROW. FERC states plainly that Commission staff has
not independently verified the accuracy of EIA data, and that utilities are
assigned to a census division by the state they report in even when they operate
across several. Regional attribution is therefore approximate at the margin.
"""

from __future__ import annotations

import csv
import pathlib

DIVISIONS = [
    "East North Central",
    "East South Central",
    "Middle Atlantic",
    "Mountain",
    "New England",
    "Pacific",
    "South Atlantic",
    "West North Central",
    "West South Central",
]

# Table 3-1: potential peak demand savings (MW), 2022 and 2023
POTENTIAL_PEAK_MW = {
    "East North Central": (4_974.0, 4_680.8),
    "East South Central": (4_223.4, 4_062.6),
    "Middle Atlantic": (842.1, 1_303.7),
    "Mountain": (2_389.4, 2_602.7),
    "New England": (309.2, 295.1),
    "Pacific": (1_390.3, 1_330.0),
    "South Atlantic": (8_449.2, 9_146.4),
    "West North Central": (4_787.4, 4_285.9),
    "West South Central": (3_082.6, 2_834.7),
}
POTENTIAL_PEAK_TOTAL = (30_447.6, 30_542.0)

# Table 3-2: potential peak demand savings (MW) by class, 2023
# division -> (residential, commercial, industrial, all classes)
POTENTIAL_PEAK_BY_CLASS_2023 = {
    "East North Central": (861.92, 829.38, 2_989.50, 4_680.80),
    "East South Central": (363.28, 104.00, 3_595.32, 4_062.60),
    "Middle Atlantic": (242.06, 928.50, 133.18, 1_303.74),
    "Mountain": (1_233.79, 414.02, 954.86, 2_602.66),
    "New England": (128.45, 106.78, 59.90, 295.13),
    "Pacific": (454.84, 290.03, 585.14, 1_330.00),
    "South Atlantic": (3_997.15, 2_601.26, 2_547.99, 9_146.41),
    "West North Central": (1_924.58, 824.56, 1_536.78, 4_285.92),
    "West South Central": (460.56, 936.59, 1_437.59, 2_834.74),
}
POTENTIAL_PEAK_BY_CLASS_TOTAL_2023 = (9_666.60, 7_035.11, 13_840.27, 30_541.98)

# Table 5-1: retail demand response enrolment (customers), 2022 and 2023
DR_ENROLMENT = {
    "East North Central": (1_431_542, 1_516_053),
    "East South Central": (203_712, 204_373),
    "Middle Atlantic": (184_804, 230_625),
    "Mountain": (1_356_157, 653_102),
    "New England": (86_732, 100_576),
    "Pacific": (773_107, 1_348_727),
    "South Atlantic": (4_034_799, 4_328_784),
    "West North Central": (1_295_155, 1_265_964),
    "West South Central": (953_766, 919_050),
}
DR_ENROLMENT_TOTAL = (10_319_774, 10_567_254)

# Table 5-2: retail dynamic pricing enrolment (customers), 2022 and 2023
DYNAMIC_PRICING_ENROLMENT = {
    "East North Central": (997_574, 2_512_498),
    "East South Central": (69_859, 141_917),
    "Middle Atlantic": (276_014, 279_248),
    "Mountain": (1_868_528, 2_253_880),
    "New England": (136_319, 144_308),
    "Pacific": (7_983_495, 7_772_829),
    "South Atlantic": (2_357_868, 2_005_858),
    "West North Central": (828_644, 1_549_726),
    "West South Central": (1_078_678, 1_579_824),
}
DYNAMIC_PRICING_TOTAL = (15_596_979, 18_240_088)

# Table 3-3: wholesale demand response registrations, MW and share of the
# market's own non-coincident peak demand
RTO_DR = {
    "CAISO": {"2023": (4_154.3, 0.093), "2024": (4_373.0, 0.090)},
    "ERCOT": {"2023": (3_612.8, 0.042), "2024": (4_099.1, 0.048)},
    "ISO-NE": {"2023": (456.0, 0.019), "2024": (431.0, 0.017)},
    "MISO": {"2023": (12_663.0, 0.101), "2024": (12_954.0, 0.106)},
    "NYISO": {"2023": (1_708.7, 0.055), "2024": (1_920.9, 0.061)},
    "PJM": {"2023": (9_666.8, 0.067), "2024": (8_526.0, 0.057)},
    "SPP": {"2023": (793.0, 0.014), "2024": (968.0, 0.018)},
}
RTO_DR_TOTAL = {"2023": (33_054.5, 0.065), "2024": (33_272.0, 0.065)}

# Reference facts used in prose and pinned by tests, same source.
FERC_FACTS = {
    "total_meters_millions_2023": 167.2,
    "advanced_meters_millions_2023": 128.4,
    "advanced_meter_penetration_2023": 0.768,
    "dynamic_pricing_share_of_customers_2023": 0.11,
    "rto_noncoincident_peak_gw_2024": 515,
    # PJM, June 23-25 2025 heat event: third-highest all-time peak
    "pjm_june2025_dr_deployed_mw": 4_000,
    "pjm_june2025_peak_mw": 162_000,
    # PJM/BGE, August 11 2025 substation loss
    "bge_aug2025_dr_reduction_mw": 230,
    "bge_aug2025_load_shed_avoided_mw": 1_200,
    "bge_aug2025_load_shed_actual_mw": 20,
}


def build_regional_rows() -> list[dict]:
    rows: list[dict] = []

    def add(division, year, metric, value, cls="all"):
        rows.append(
            {
                "division": division,
                "year": year,
                "customer_class": cls,
                "metric": metric,
                "value": value,
            }
        )

    for division in DIVISIONS:
        for i, year in enumerate((2022, 2023)):
            add(division, year, "potential_peak_mw", POTENTIAL_PEAK_MW[division][i])
            add(division, year, "dr_customers", DR_ENROLMENT[division][i])
            add(
                division,
                year,
                "dynamic_pricing_customers",
                DYNAMIC_PRICING_ENROLMENT[division][i],
            )
        res, com, ind, _ = POTENTIAL_PEAK_BY_CLASS_2023[division]
        for cls, value in (
            ("residential", res),
            ("commercial", com),
            ("industrial", ind),
        ):
            add(division, 2023, "potential_peak_mw", value, cls)

    for i, year in enumerate((2022, 2023)):
        add("US total", year, "potential_peak_mw", POTENTIAL_PEAK_TOTAL[i])
        add("US total", year, "dr_customers", DR_ENROLMENT_TOTAL[i])
        add("US total", year, "dynamic_pricing_customers", DYNAMIC_PRICING_TOTAL[i])
    res, com, ind, _ = POTENTIAL_PEAK_BY_CLASS_TOTAL_2023
    for cls, value in (("residential", res), ("commercial", com), ("industrial", ind)):
        add("US total", 2023, "potential_peak_mw", value, cls)
    return rows


def build_rto_rows() -> list[dict]:
    rows = []
    for market, years in list(RTO_DR.items()) + [("All RTO/ISO", RTO_DR_TOTAL)]:
        for year, (mw, share) in years.items():
            rows.append(
                {
                    "market": market,
                    "year": int(year),
                    "dr_resources_mw": mw,
                    "share_of_market_peak": share,
                    "implied_market_peak_mw": round(mw / share, 1),
                }
            )
    return rows


def main() -> None:
    data = pathlib.Path(__file__).resolve().parents[1] / "data"
    regional = build_regional_rows()
    with (data / "ferc_dr_regional.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(regional[0]))
        w.writeheader()
        w.writerows(regional)
    rto = build_rto_rows()
    with (data / "rto_dr.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rto[0]))
        w.writeheader()
        w.writerows(rto)
    print(f"wrote {len(regional)} regional rows and {len(rto)} RTO rows")


if __name__ == "__main__":
    main()
