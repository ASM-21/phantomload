"""Loaders for the FERC-sourced regional and wholesale tables.

Kept next to the EIA registry rather than inside a track, because three tracks
read it: track 1 for regional dispersion, track 5 for the time-varying-rate
denominator, track 7 for the wholesale comparison.

The two files describe different populations and must not be added together.
`ferc_dr_regional.csv` is FERC staff's regional aggregation of the same EIA-861
demand response files the national panel comes from. `rto_dr.csv` is wholesale
market registrations reported by the RTOs and ISOs themselves. See
`t7_crossval` for what the overlap is and is not known to be.
"""

from __future__ import annotations

import functools
import pathlib

import pandas as pd

DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data"
REGIONAL = DATA_DIR / "ferc_dr_regional.csv"
RTO = DATA_DIR / "rto_dr.csv"

DIVISIONS = (
    "East North Central",
    "East South Central",
    "Middle Atlantic",
    "Mountain",
    "New England",
    "Pacific",
    "South Atlantic",
    "West North Central",
    "West South Central",
)
US_TOTAL = "US total"

# FERC 2025 assessment, chapter 2 and chapter 6. Used as denominators.
TOTAL_METERS_2023 = 167_200_000
ADVANCED_METERS_2023 = 128_400_000

# PJM heat event, June 23-25 2025, and the BGE substation loss, August 11 2025.
# Reported by FERC as narrative rather than in a table, so they are stored here
# with the same provenance and used only where the text supports them.
PJM_JUNE_2025 = {
    "dr_deployed_mw_at_least": 4_000,
    "system_peak_mw": 162_000,
    "registered_dr_mw_2024": 8_526.0,
    "note": "third-highest all-time PJM peak; DR deployed reported as 'more than'",
}
BGE_AUG_2025 = {
    "dr_reduction_mw": 230,
    "load_shed_avoided_mw": 1_200,
    "load_shed_actual_mw": 20,
}


@functools.lru_cache(maxsize=1)
def regional() -> pd.DataFrame:
    if not REGIONAL.exists():
        raise FileNotFoundError(
            f"{REGIONAL} missing. Run tools/build_ferc_regional.py to regenerate it."
        )
    return pd.read_csv(REGIONAL)


@functools.lru_cache(maxsize=1)
def rto() -> pd.DataFrame:
    if not RTO.exists():
        raise FileNotFoundError(
            f"{RTO} missing. Run tools/build_ferc_regional.py to regenerate it."
        )
    return pd.read_csv(RTO)


def regional_metric(
    metric: str, year: int, customer_class: str = "all", include_total: bool = False
) -> pd.Series:
    df = regional()
    hit = df[
        (df.metric == metric)
        & (df.year == year)
        & (df.customer_class == customer_class)
    ]
    if not include_total:
        hit = hit[hit.division != US_TOTAL]
    return hit.set_index("division")["value"].sort_index()


# FERC enforcement actions involving demand response capacity, from chapter 5 of
# the same assessment. Characterisations follow the source exactly: Ketchup
# Caddy was adjudicated, Voltus was resolved by consent agreement and the source
# states no finding of fraud, so neither is described beyond what FERC wrote.
ENFORCEMENT = {
    "Ketchup Caddy, LLC": {
        "year": 2024,
        "market": "MISO",
        "finding": (
            "Commission found fraudulent activity and market manipulation, and "
            "that uncontracted resources were offered into MISO's capacity "
            "market without the demand resources' knowledge or consent"
        ),
        "adjudicated": True,
        "disgorgement_usd": 506_502,
        "civil_penalty_usd": 26_500_000,  # 25,000,000 plus 1,500,000 co-owner
    },
    "Voltus, Inc.": {
        "year": 2025,
        "market": "MISO",
        "finding": (
            "investigation into whether MISO's tariff or Commission regulations "
            "were violated, resolved by stipulation and consent agreement; the "
            "source states no adjudicated finding"
        ),
        "adjudicated": False,
        "disgorgement_usd": 7_080_543,
        "civil_penalty_usd": 11_919_457,  # 10,919,457 plus 1,000,000 former CEO
    },
}


# Market rules that bear directly on track 4's seasonal finding.
#
# PROVENANCE IS WEAKER HERE THAN ANYWHERE ELSE IN THIS REPO. These are dates and
# rule descriptions taken from trade press and one PJM committee presentation,
# not from the tariff or Manual 18, neither of which was read in the environment
# this was built in. They are recorded because leaving them out would let track 4
# imply that nobody has noticed the winter problem, which is false. Verify
# against the tariff before citing.
MARKET_RULES = {
    "pjm_capacity_performance": {
        "market": "PJM",
        "rule": (
            "Capacity Performance requires year-round availability, with "
            "Performance Assessment Hours that can fall in summer or winter"
        ),
        "summer_only_products_retired": {
            "Limited DR": "after the 2017/2018 delivery year",
            "Summer Extended DR": "after the 2017/2018 delivery year",
            "Base Capacity": "after the 2019/2020 delivery year",
        },
        "sole_forward_dr_product_from": "2020/2021 delivery year",
        "seasonal_workaround": (
            "summer-only resources may aggregate with winter-only resources to "
            "form a qualifying bid"
        ),
        "market_observation": (
            "PJM stakeholders reported seasonal aggregation was limited by how "
            "little winter-capable resource was offered"
        ),
        "source_quality": "trade press and a PJM committee presentation, tariff not read",
        "applies_to": "wholesale capacity market registrations, not EIA retail programs",
    }
}
