"""Track 6. Does bad utilization come bundled with heavy overhead.

MEASURED. EIA-861 splits DR program cost into customer incentives and all other
costs. The second bucket is everything that is not a payment to a participant:
marketing, enrolment, measurement and verification, dispatch systems, staff. It
is the cost of keeping capacity dispatch-ready whether or not it is dispatched.

The spec's hypothesis was compounding: the program types with the worst
utilization also carry the heaviest overhead, so phantom capacity is doubly
expensive. This track tests it and the sign comes out the other way.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ..shared.dr_program import SECTORS, Provenance, load_eia_panel


def overhead_table() -> pd.DataFrame:
    wide = load_eia_panel().reset_index()
    df = wide[
        [
            "year",
            "sector",
            "potential_peak_mw",
            "actual_peak_mw",
            "customers_enrolled",
            "customer_incentives_kusd",
            "other_costs_kusd",
        ]
    ].copy()
    df = df.dropna(subset=["customer_incentives_kusd", "other_costs_kusd"])
    df["total_cost_kusd"] = df["customer_incentives_kusd"] + df["other_costs_kusd"]
    df["overhead_share"] = df["other_costs_kusd"] / df["total_cost_kusd"]
    df["utilization"] = df["actual_peak_mw"] / df["potential_peak_mw"]
    # $1k per MW == $1 per kW
    df["overhead_per_kw_enrolled"] = df["other_costs_kusd"] / df["potential_peak_mw"]
    df["overhead_per_kw_delivered"] = df["other_costs_kusd"] / df["actual_peak_mw"]
    # thousand dollars per customer -> dollars per customer
    df["overhead_per_customer_usd"] = (
        df["other_costs_kusd"] * 1_000 / df["customers_enrolled"]
    )
    df["incentive_per_customer_usd"] = (
        df["customer_incentives_kusd"] * 1_000 / df["customers_enrolled"]
    )
    df["kw_delivered_per_customer"] = (
        df["actual_peak_mw"] * 1_000 / df["customers_enrolled"]
    )
    df["provenance"] = Provenance.MEASURED.value
    return df.sort_values(["sector", "year"])


def compounding_test() -> dict:
    """Correlate utilization against overhead share across sector-years.

    The compounding hypothesis predicts a negative correlation: low utilization
    travels with high overhead. Pooling sector-years is pseudo-replication (the
    same four sectors recur), so the pooled coefficient is reported alongside a
    sector-mean coefficient on n=4 and neither is presented as inferential.
    """
    df = overhead_table()
    df = df[df.sector.isin(SECTORS)].dropna(subset=["utilization", "overhead_share"])
    pooled_r, pooled_p = stats.pearsonr(df.utilization, df.overhead_share)
    by_sector = df.groupby("sector")[["utilization", "overhead_share"]].mean()
    sector_r, sector_p = stats.pearsonr(by_sector.utilization, by_sector.overhead_share)
    return {
        "pooled_r": float(pooled_r),
        "pooled_p": float(pooled_p),
        "pooled_n": int(len(df)),
        "sector_mean_r": float(sector_r),
        "sector_mean_p": float(sector_p),
        "sector_mean_n": int(len(by_sector)),
        "compounding_supported": bool(pooled_r < 0 and pooled_p < 0.05),
        "note": (
            "pooled correlation is pseudo-replicated across 4 recurring sectors; "
            "reported for shape only"
        ),
    }


def sector_profile(year: int | None = None) -> pd.DataFrame:
    df = overhead_table()
    year = int(df.year.max()) if year is None else year
    out = df[(df.year == year) & (df.sector.isin(SECTORS))].set_index("sector")
    cols = [
        "utilization",
        "overhead_share",
        "overhead_per_kw_enrolled",
        "overhead_per_kw_delivered",
        "overhead_per_customer_usd",
        "incentive_per_customer_usd",
        "kw_delivered_per_customer",
    ]
    return out[cols].assign(year=year, provenance=Provenance.MEASURED.value)


def scale_threshold() -> dict:
    """Where the per-customer overhead of a mass-market program stops paying.

    Overhead per delivered kW is overhead-per-customer divided by delivered-kW
    per-customer. So a program with tiny per-customer overhead still loses if
    each customer delivers almost nothing. This reports the implied delivered kW
    per customer that each sector would need to match the best sector's
    overhead per delivered kW, holding its own overhead per customer fixed.
    """
    prof = sector_profile().dropna()
    best = prof["overhead_per_kw_delivered"].min()
    prof = prof.assign(
        kw_per_customer_needed_to_match_best=prof["overhead_per_customer_usd"] / best,
        multiple_of_current_kw_per_customer=(
            prof["overhead_per_customer_usd"] / best
        )
        / prof["kw_delivered_per_customer"],
    )
    return {
        "best_sector": str(prof["overhead_per_kw_delivered"].idxmin()),
        "best_overhead_per_kw_delivered": float(best),
        "table": prof[
            [
                "overhead_per_customer_usd",
                "kw_delivered_per_customer",
                "kw_per_customer_needed_to_match_best",
                "multiple_of_current_kw_per_customer",
            ]
        ],
    }


def summary() -> dict:
    prof = sector_profile()
    comp = compounding_test()
    df = overhead_table()
    nat = df[df.sector == "total"].sort_values("year")
    return {
        "latest_year": int(prof.year.iloc[0]),
        "national_overhead_share_latest": float(nat.overhead_share.iloc[-1]),
        "national_overhead_share_mean": float(nat.overhead_share.mean()),
        "highest_overhead_share_sector": str(prof.overhead_share.idxmax()),
        "highest_overhead_share": float(prof.overhead_share.max()),
        "lowest_overhead_share_sector": str(prof.overhead_share.idxmin()),
        "lowest_overhead_share": float(prof.overhead_share.min()),
        "overhead_per_kw_delivered_spread": float(
            prof.overhead_per_kw_delivered.max() / prof.overhead_per_kw_delivered.min()
        ),
        "overhead_per_customer_spread": float(
            prof.overhead_per_customer_usd.max() / prof.overhead_per_customer_usd.min()
        ),
        "compounding_supported": comp["compounding_supported"],
        "pooled_r": comp["pooled_r"],
        "sector_mean_r": comp["sector_mean_r"],
    }


def run() -> dict[str, pd.DataFrame | dict]:
    return {
        "overhead_by_year": overhead_table(),
        "sector_profile": sector_profile().reset_index(),
        "scale_threshold": scale_threshold()["table"].reset_index(),
        "compounding_test": compounding_test(),
        "summary": summary(),
    }
