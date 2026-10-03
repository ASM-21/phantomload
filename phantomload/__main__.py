"""Run the zero-mass test on your own demand response data.

The headline result here rests on EIA-861 for 2016 to 2018. The most useful
thing anyone can do with this repository is test it on different years, a
different country's reporting, or a single utility's program-level records.
This makes that one command.

    python -m phantomload zero-mass your_data.csv

Input: a CSV with one row per reporting entity per year and these columns.

    potential_mw   enrolled or available peak reduction        required
    actual_mw      realised peak reduction; leave BLANK if     required
                   not reported, use 0 only for a real zero
    key            stable identifier for the entity            optional
    year           reporting year                              optional

Blank and zero are different and the test depends on keeping them apart:
blank means the entity did not report, zero means it reported calling nothing.

With one year you get the shape: how much enrolled capacity sits at exactly
zero. With several years and a key you also get persistence: whether the same
entities report zero every year (a program that does not operate) or the zero
mass moves around (capacity available but not called).
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

MIN_ENTITIES = 20


def zero_mass(df: pd.DataFrame) -> dict:
    missing = {"potential_mw", "actual_mw"} - set(df.columns)
    if missing:
        raise SystemExit(f"input is missing required columns: {sorted(missing)}")
    df = df[pd.to_numeric(df.potential_mw, errors="coerce") > 0].copy()
    df["potential_mw"] = pd.to_numeric(df.potential_mw)
    df["actual_mw"] = pd.to_numeric(df.actual_mw, errors="coerce")
    if len(df) < MIN_ENTITIES:
        raise SystemExit(
            f"only {len(df)} entities with positive potential; the test needs at "
            f"least {MIN_ENTITIES} to say anything about a distribution, and "
            "refuses rather than return a number that looks meaningful"
        )
    total = df.potential_mw.sum()
    zero = df[df.actual_mw == 0]
    blank = df[df.actual_mw.isna()]
    out = {
        "entities": int(len(df)),
        "exact_zero_entities": int(len(zero)),
        "exact_zero_share_of_potential": float(zero.potential_mw.sum() / total),
        "not_reported_entities": int(len(blank)),
        "not_reported_share_of_potential": float(blank.potential_mw.sum() / total),
    }
    if {"key", "year"} <= set(df.columns) and df.year.nunique() >= 2:
        reported = df[df.actual_mw.notna()]
        years = reported.groupby("key").year.nunique()
        complete = years[years == df.year.nunique()].index
        z = reported[reported.key.isin(complete)].assign(z=lambda d: d.actual_mw == 0)
        per_key = z.groupby("key").z.sum()
        ever = per_key[per_key >= 1].index
        always = per_key[per_key == df.year.nunique()].index
        mean_mw = df.groupby("key").potential_mw.mean()
        if len(ever):
            out.update(
                {
                    "years": int(df.year.nunique()),
                    "entities_reporting_every_year": int(len(complete)),
                    "zero_every_year": int(len(always)),
                    "ever_zero": int(len(ever)),
                    "rotating_share_of_zero_capacity": float(
                        1 - mean_mw.loc[always].sum() / mean_mw.loc[ever].sum()
                    ),
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m phantomload")
    sub = ap.add_subparsers(dest="cmd", required=True)
    zm = sub.add_parser("zero-mass", help="run the zero-mass test on a CSV")
    zm.add_argument("csv")
    args = ap.parse_args(argv)

    result = zero_mass(pd.read_csv(args.csv))
    width = max(len(k) for k in result)
    for k, v in result.items():
        shown = f"{v:.1%}" if isinstance(v, float) else v
        print(f"{k:<{width}}  {shown}")
    if "rotating_share_of_zero_capacity" in result:
        r = result["rotating_share_of_zero_capacity"]
        print()
        print(
            "Most zero-reported capacity moves between years, which is what "
            "available-but-uncalled capacity looks like."
            if r > 0.5
            else "Most zero-reported capacity stays at zero every year, which is "
            "what a program that does not operate, or does not report its "
            "dispatch in this accounting, looks like. That would cut against "
            "this repository's reading, and is worth reporting."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
