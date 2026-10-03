"""Build data/eia861_dr_national.csv from published EIA Electric Power Annual tables.

PROVENANCE. Every number below is transcribed verbatim from two published EIA
HTML tables. Nothing here is modelled, interpolated or imputed.

  Table 10.3  Demand response - yearly energy and demand savings, 2013-2024
              https://www.eia.gov/electricity/annual/html/epa_10_03.html
              (rows 2015-2024; the live page drops 2013-2014)
  Table 10.8  Demand response - yearly energy and demand savings, 2013-2019
              https://www.eia.gov/electricity/annual/html/epa_10_08.html
              (used only for the 2013 and 2014 rows, which agree with 10.3
              on the 2015-2019 overlap; that agreement is asserted in tests)
  Table 10.4  Demand response - program costs, 2013-2024
              https://www.eia.gov/electricity/annual/html/epa_10_04.html
              (rows 2015-2024; cost rows for 2013-2014 are not published there)

Underlying source: U.S. Energy Information Administration, Form EIA-861,
"Annual Electric Power Industry Report." Retrieved 2026-09-04.
US Government work, not subject to domestic copyright.

WHY THIS FILE EXISTS. eia.gov is not reachable from every environment this repo
is developed in, and the published table is small enough that vendoring it in
full is more reproducible than a fetch script that silently fails. Re-run this
script to regenerate the CSV; run tools/check_source.py to diff the vendored
CSV against a live fetch when you do have network access.

"--" in the published table means not applicable or withheld and is written as
an empty cell (NaN), never as zero.
"""

from __future__ import annotations

import csv
import pathlib

SECTORS = ["residential", "commercial", "industrial", "transportation", "total"]

# year -> [residential, commercial, industrial, transportation, total]
# None encodes the published "--".
CUSTOMERS_ENROLLED = {
    2013: [8_419_233, 611_826, 155_893, 398, 9_187_350],
    2014: [8_603_402, 605_094, 57_129, 4, 9_265_629],
    2015: [8_140_688, 890_284, 63_163, 3, 9_094_138],
    2016: [8_739_535, 1_033_649, 66_170, 1, 9_839_355],
    2017: [8_287_913, 1_084_392, 68_630, 3, 9_440_938],
    2018: [8_700_669, 986_816, 64_753, None, 9_752_238],
    2019: [10_447_335, 432_669, 52_841, None, 10_932_845],
    2020: [11_302_017, 324_939, 38_706, 1, 11_665_663],
    2021: [10_196_668, 255_355, 40_560, 1, 10_492_584],
    2022: [10_044_583, 235_825, 39_365, 1, 10_319_774],
    2023: [10_282_113, 245_332, 39_808, 1, 10_567_254],
    2024: [10_658_027, 249_192, 43_608, 1, 10_950_828],
}

ENERGY_SAVINGS_MWH = {
    2013: [799_743, 486_348, 115_895, 1, 1_401_987],
    2014: [881_563, 462_337, 92_549, None, 1_436_449],
    2015: [855_017, 273_089, 122_900, None, 1_251_006],
    2016: [1_005_144, 225_174, 105_818, None, 1_336_136],
    2017: [948_037, 244_603, 118_230, None, 1_310_862],
    2018: [1_099_179, 221_502, 105_536, None, 1_426_211],
    2019: [1_075_567, 306_832, 80_336, None, 1_462_735],
    2020: [1_186_421, 251_719, 70_984, None, 1_509_124],
    2021: [984_129, 88_947, 80_715, None, 1_153_791],
    2022: [1_004_031, 126_867, 162_081, None, 1_292_980],
    2023: [230_285, 107_321, 69_649, None, 407_255],
    2024: [247_973, 88_063, 73_367, None, 409_404],
}

POTENTIAL_PEAK_MW = {
    2013: [7_003, 5_124, 14_800, 168, 27_095],
    2014: [8_118, 6_215, 16_505, 353, 31_191],
    2015: [8_703, 6_989, 17_169, 14, 32_875],
    2016: [10_518, 11_053, 14_339, 14, 35_924],
    2017: [8_996, 6_995, 15_512, 5, 31_508],
    2018: [8_539, 7_021, 15_335, None, 30_895],
    2019: [8_867, 6_907, 15_246, None, 31_020],
    2020: [8_535, 5_837, 15_098, None, 29_470],
    2021: [8_705, 6_646, 13_871, None, 29_222],
    2022: [9_039, 6_545, 14_864, None, 30_448],
    2023: [9_667, 7_035, 13_840, None, 30_542],
    2024: [9_706, 7_346, 14_439, None, 31_491],
}

ACTUAL_PEAK_MW = {
    2013: [3_381, 2_548, 5_805, 149, 11_883],
    2014: [3_147, 2_652, 6_883, 1, 12_683],
    2015: [3_430, 3_047, 6_546, 13, 13_036],
    2016: [3_608, 3_598, 4_632, 4, 11_841],
    2017: [3_960, 2_743, 5_546, None, 12_248],
    2018: [3_788, 2_694, 6_040, None, 12_522],
    2019: [3_426, 2_403, 5_505, None, 11_334],
    2020: [3_504, 2_115, 4_768, None, 10_387],
    2021: [3_836, 2_807, 5_569, None, 12_211],
    2022: [4_606, 2_608, 6_613, None, 13_827],
    2023: [4_082, 2_661, 4_009, None, 10_752],
    2024: [4_785, 2_457, 5_080, None, 12_322],
}

CUSTOMER_INCENTIVES_KUSD = {
    2015: [320_683, 338_153, 461_271, 339, 1_120_446],
    2016: [306_635, 448_332, 284_584, 339, 1_039_890],
    2017: [292_443, 345_226, 365_451, None, 1_003_124],
    2018: [310_892, 347_235, 531_157, None, 1_189_284],
    2019: [306_152, 322_611, 490_119, None, 1_118_882],
    2020: [274_021, 281_304, 432_328, None, 987_653],
    2021: [293_293, 314_739, 580_358, None, 1_188_390],
    2022: [265_186, 287_785, 596_309, None, 1_149_280],
    2023: [262_583, 306_095, 550_092, None, 1_118_770],
    2024: [273_346, 348_692, 602_656, None, 1_224_694],
}

OTHER_COSTS_KUSD = {
    2015: [256_519, 78_758, 46_613, 28, 381_918],
    2016: [253_180, 66_084, 60_443, None, 379_707],
    2017: [245_231, 68_251, 57_221, None, 370_700],
    2018: [235_159, 66_024, 59_534, None, 360_718],
    2019: [223_129, 49_407, 70_677, None, 343_214],
    2020: [213_592, 59_905, 53_365, 10, 326_872],
    2021: [218_758, 70_615, 22_709, 10, 312_091],
    2022: [244_430, 62_832, 21_782, 10, 329_053],
    2023: [222_739, 64_259, 24_935, 10, 311_943],
    2024: [262_017, 68_914, 31_132, 10, 362_073],
}

METRICS = {
    "customers_enrolled": CUSTOMERS_ENROLLED,
    "energy_savings_mwh": ENERGY_SAVINGS_MWH,
    "potential_peak_mw": POTENTIAL_PEAK_MW,
    "actual_peak_mw": ACTUAL_PEAK_MW,
    "customer_incentives_kusd": CUSTOMER_INCENTIVES_KUSD,
    "other_costs_kusd": OTHER_COSTS_KUSD,
}

# Rows the published table carries an explicit caveat on.
EIA_FOOTNOTES = {
    ("energy_savings_mwh", 2023): "EIA note: energy savings dropped due to a "
    "reclassification in the 2023 annual filings",
    ("energy_savings_mwh", 2024): "post-reclassification basis, not comparable "
    "with 2013-2022",
}


def build_rows() -> list[dict]:
    rows = []
    for metric, table in METRICS.items():
        for year in sorted(table):
            for sector, value in zip(SECTORS, table[year]):
                rows.append(
                    {
                        "year": year,
                        "sector": sector,
                        "metric": metric,
                        "value": "" if value is None else value,
                        "note": EIA_FOOTNOTES.get((metric, year), ""),
                    }
                )
    return rows


def main() -> None:
    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "eia861_dr_national.csv"
    rows = build_rows()
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["year", "sector", "metric", "value", "note"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
