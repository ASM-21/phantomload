"""Build data/pjm_cone.csv from PJM's published RPM planning parameters.

PROVENANCE. Transcribed verbatim from Table 3, "Net CONE for PJM RTO and LDAs
for 2026/2027 and 2027/2028 BRAs", in:

  PJM Interconnection, "2027/2028 RPM Base Residual Auction Planning Period
  Parameters", August 26, 2025.
  https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2027-2028/
  2027-2028-planning-period-parameters-for-base-residual-auction-pdf.pdf
  Retrieved 2026-09-05.

Three columns per delivery year: gross cost of new entry, the energy and
ancillary services revenue offset, and net CONE, all in ICAP terms and dollars
per MW-year, plus PJM's net CONE in UCAP terms and dollars per MW-day.

WHY ICAP $/MW-YEAR IS THE WORKING UNIT HERE. It divides by 1,000 straight into
dollars per kW-year, which is what the EIA-derived demand response costs are in.
Converting to UCAP requires an accreditation factor, and PJM accredits demand
response on its own basis, so a UCAP comparison would need both sides
re-accredited rather than one side converted. The UCAP column is carried anyway
so the transcription can be checked against PJM's own arithmetic.

Ingest trap, pinned by a test: the implied ICAP-to-UCAP factor is not the same
in the two columns. The 2026/2027 column implies 78.00%, the reference resource
AUCAP factor. The 2027/2028 column implies 77.20%, the pool-wide accredited
UCAP factor, not the 77.00% reference resource factor quoted a page earlier.
Anyone converting CONE between bases with one factor is off by about 1%.
"""

from __future__ import annotations

import csv
import pathlib

# location -> (gross, eas_offset, net_icap, net_ucap_per_day) per BRA
# all dollars; gross/eas/net_icap are $/MW-year ICAP, net_ucap is $/MW-day UCAP
TABLE_3 = {
    "RTO": {
        "2026/2027": (143_980, 83_584, 60_396, 212.14),
        "2027/2028": (149_309, 80_962, 68_347, 242.52),
    },
    "MAAC": {
        "2026/2027": (140_920, 63_028, 77_891, 267.33),
        "2027/2028": (147_295, 58_990, 88_305, 301.50),
    },
    "EMAAC": {
        "2026/2027": (136_000, 44_041, 91_959, 323.00),
        "2027/2028": (142_216, 41_088, 101_128, 358.84),
    },
    "SWMAAC": {
        "2026/2027": (142_000, 93_310, 48_690, 171.02),
        "2027/2028": (147_601, 85_945, 61_655, 218.78),
    },
    "PS, PS NORTH": {
        "2026/2027": (136_000, 30_863, 105_137, 369.29),
        "2027/2028": (142_216, 27_958, 114_258, 405.43),
    },
    "DPL SOUTH": {
        "2026/2027": (136_000, 74_458, 61_542, 216.17),
        "2027/2028": (142_216, 68_207, 74_009, 262.61),
    },
    "PEPCO": {
        "2026/2027": (142_000, 67_672, 74_328, 261.07),
        "2027/2028": (147_601, 65_224, 82_377, 292.30),
    },
    "ATSI, Cleveland": {
        "2026/2027": (147_600, 89_511, 58_089, 204.03),
        "2027/2028": (152_979, 88_624, 64_355, 228.35),
    },
    "COMED": {
        "2026/2027": (150_800, 50_515, 100_285, 352.25),
        "2027/2028": (158_731, 51_900, 106_831, 379.08),
    },
    "BGE": {
        "2026/2027": (142_000, 118_949, 23_051, 80.97),
        "2027/2028": (147_601, 106_667, 40_934, 145.25),
    },
    # PPL's locational deliverability area
    "PL": {
        "2026/2027": (143_500, 53_210, 90_290, 317.14),
        "2027/2028": (145_017, 56_131, 88_886, 315.40),
    },
    "DAYTON": {
        "2026/2027": (147_600, 101_270, 46_330, 162.73),
        "2027/2028": (152_979, 98_356, 54_623, 193.82),
    },
    "DEOK": {
        "2026/2027": (147_600, 92_307, 55_293, 194.21),
        "2027/2028": (152_979, 91_138, 61_841, 219.44),
    },
    "DOM": {
        "2026/2027": (147_600, 105_911, 41_689, 146.43),
        "2027/2028": (152_979, 102_776, 50_203, 178.14),
    },
    "JCPL": {
        "2026/2027": (136_000, 33_118, 102_882, 361.37),
        "2027/2028": (142_216, 29_620, 112_595, 399.53),
    },
}


def build_rows() -> list[dict]:
    rows = []
    for location, by_year in TABLE_3.items():
        for bra, (gross, eas, net_icap, net_ucap) in by_year.items():
            rows.append(
                {
                    "location": location,
                    "delivery_year": bra,
                    "gross_cone_icap_usd_per_mw_yr": gross,
                    "eas_offset_icap_usd_per_mw_yr": eas,
                    "net_cone_icap_usd_per_mw_yr": net_icap,
                    "net_cone_ucap_usd_per_mw_day": net_ucap,
                }
            )
    return rows


def main() -> None:
    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "pjm_cone.csv"
    rows = build_rows()
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
