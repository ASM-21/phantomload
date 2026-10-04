"""Run the zero-mass test on your own demand response data.

The headline result here rests on EIA-861 for 2016 to 2018. The most useful
thing anyone can do with this repository is test it on different years, a
different country's reporting, or a single utility's program-level records.
This makes that one command.

    python -m phantomload zero-mass your_data.csv
    python -m phantomload benchmark --potential 100 --actual 35 [--rto | --non-rto]

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


def benchmark(potential_mw: float, actual_mw: float | None, in_rto: bool | None) -> dict:
    """Place one program among every US utility program, 2016 to 2018.

    For a planner asking whether their program is unusual, or a reviewer asking
    whether a filing is. Answers with percentiles in the measured population,
    and never with a judgement: an unusual number is a reason to ask the
    checklist questions, not an answer to them.
    """
    import numpy as np

    from .tracks import t9_mechanisms as t9

    if potential_mw <= 0:
        raise SystemExit("potential must be positive")
    pop = t9.panel()
    if in_rto is not None:
        pop = pop[pop.in_rto == in_rto]
    reported = pop[pop.status != "not_reported"]
    # Reports where actual exactly equals potential are usually a contract
    # quantity, not a measurement, and they are far more common among small
    # programs. Comparing against them flatters small programs, so peers are
    # drawn only from reports that carry a measurement.
    copied = np.isclose(reported.actual_peak_mw, reported.potential_peak_mw) & (
        reported.actual_peak_mw > 0
    )
    reported = reported[~copied]
    out = {
        "population": f"{len(pop):,} utility-years"
        + ("" if in_rto is None else (" inside RTO footprints" if in_rto else " outside RTO footprints")),
        "population_share_reporting_zero": float((reported.actual_peak_mw == 0).mean()),
        "population_share_not_reporting": float((pop.status == "not_reported").mean()),
        "population_median_utilization": float(reported.utilization.median()),
        "peers_exclude_copied_reports": True,
    }
    if actual_mw is None:
        out["your_status"] = "not reported, like the share above"
        return out
    u = actual_mw / potential_mw
    out["your_utilization"] = float(u)
    out["your_percentile"] = float((reported.utilization < u).mean())
    # Utilization falls steeply with program size, so the fair comparison is
    # against programs of similar size, not against everyone.
    edges = reported.potential_peak_mw.quantile([0, 0.25, 0.5, 0.75, 1.0]).to_numpy()
    band = int(np.clip(np.searchsorted(edges, potential_mw, side="right") - 1, 0, 3))
    names = ["smallest", "second", "third", "largest"]
    lo, hi = edges[band], edges[band + 1]
    peers = reported[reported.potential_peak_mw.between(lo, hi)]
    span = (f"{lo:,.0f} MW and above" if band == 3
            else f"up to {hi:,.0f} MW" if band == 0
            else f"{lo:,.0f} to {hi:,.0f} MW")
    out["size_band"] = f"{names[band]} quarter, {span}"
    out["size_band_median_utilization"] = float(peers.utilization.median())
    out["your_percentile_within_size_band"] = float((peers.utilization < u).mean())
    if actual_mw > 0 and np.isclose(actual_mw, potential_mw):
        out["your_status"] = (
            "actual equals potential: this is usually a contract figure rather than "
            "a measurement, so check how actual was determined before comparing "
            "(CHECKLIST.md question 0)"
        )
    elif actual_mw == 0:
        out["your_status"] = (
            "exact zero: ask whether the program was called (CHECKLIST.md question 1)"
        )
    elif u < peers.utilization.quantile(0.25):
        out["your_status"] = (
            "bottom quartile for its size: ask how potential is defined and whether "
            "the ratio is stable year to year (CHECKLIST.md questions 3 and 4)"
        )
    elif u > 1:
        out["your_status"] = (
            "above potential: check the definition, since realised should not "
            "exceed what the program can deliver"
        )
    else:
        out["your_status"] = "within the usual range"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m phantomload")
    sub = ap.add_subparsers(dest="cmd", required=True)
    zm = sub.add_parser("zero-mass", help="run the zero-mass test on a CSV")
    zm.add_argument("csv")
    bm = sub.add_parser(
        "benchmark", help="place one program among every US program, 2016-2018"
    )
    bm.add_argument("--potential", type=float, required=True, help="potential MW")
    bm.add_argument("--actual", type=float, default=None, help="actual MW; omit if not reported")
    where = bm.add_mutually_exclusive_group()
    where.add_argument("--rto", action="store_true", help="compare only inside RTO footprints")
    where.add_argument("--non-rto", action="store_true", help="compare only outside them")
    args = ap.parse_args(argv)

    if args.cmd == "benchmark":
        in_rto = True if args.rto else (False if args.non_rto else None)
        result = benchmark(args.potential, args.actual, in_rto)
        width = max(len(k) for k in result)
        for k, v in result.items():
            shown = f"{v:.1%}" if isinstance(v, float) else v
            print(f"{k:<{width}}  {shown}")
        return 0

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
