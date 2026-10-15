"""Run the zero-mass test on your own demand response data.

The headline result here rests on EIA-861 for 2016 to 2018. The most useful
thing anyone can do with this repository is test it on different years, a
different country's reporting, or a single utility's program-level records.
This makes that one command.

    python -m phantomload zero-mass your_data.csv
    python -m phantomload benchmark --potential 100 --actual 35 [--peak 2400] [--rto | --non-rto]

Input: a CSV with one row per reporting entity per year and these columns.

    potential_mw   enrolled or available peak reduction        required
    actual_mw      realised peak reduction; leave BLANK if     required
                   not reported, use 0 only for a real zero
    key            stable identifier for the entity            optional
    year           reporting year                              optional

Blank and zero are different and the test depends on keeping them apart:
blank means the entity did not report, zero means it reported calling nothing.

Know what your actual figure measures before reading anything below. EIA's is
"measured at the time of the company's annual system peak hour", so a zero
means nothing was running in that one hour, not that nothing was called all
year. If your figure is the largest reduction in any event, or the average
across events, a zero means something stronger.

With one year you get the shape: how much enrolled capacity sits at exactly
zero. With several years and a key you also get persistence, and the two
checks that decide what persistence means:

  measured rotation   the share of capacity ever at zero held by entities that
                      delivered a measured amount in another year: at least 5%
                      of potential, not within 1% of it, and with enrolled
                      capacity that did not move more than threefold. Only this
                      kind of rotation is evidence the capacity was available.
  follow-up           how much of the capacity at zero in one year delivers in
                      the next, against capacity that delivered a measured
                      amount.

The plain rotating share is printed too, because it is the number this
repository first published. On its own data that number was 79% while measured
rotation was 15%, so do not read the plain share as evidence of availability.
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
            out.update(_what_the_rotation_is_made_of(df))
    return out


def _what_the_rotation_is_made_of(df: pd.DataFrame) -> dict:
    """The same classification and follow-up the repository runs on EIA-861."""
    from .tracks import t1_utilization as t1

    frame = df.rename(
        columns={"potential_mw": "potential_peak_mw", "actual_mw": "actual_peak_mw"}
    )[["key", "year", "potential_peak_mw", "actual_peak_mw"]]
    comp = t1.classify_zero_capacity(frame)
    by = comp.groupby("class").share_of_ever_zero_mw.sum()
    measured = float(by.get("measured", 0.0))
    persistent = float(by.get("zero_every_year", 0.0))
    out = {
        "measured_rotation_share_of_zero_capacity": measured,
        "zero_every_year_share_of_zero_capacity": persistent,
        "rotation_without_a_measurement_share": float(1.0 - measured - persistent),
    }
    fu = t1.followup(frame)
    for group, label in (("exact_zero", "zero"), ("measured", "measured")):
        g = fu[fu.group_in_from_year == group] if len(fu) else fu
        if len(g) and g.followed_mw.sum() > 0:
            out[f"{label}_capacity_next_year_delivery"] = float(
                g.delivered_mw.sum() / g.followed_mw.sum()
            )
    return out


def benchmark(
    potential_mw: float, actual_mw: float | None, in_rto: bool | None, peak_mw: float | None = None
) -> dict:
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
    if peak_mw is not None:
        out.update(_against_peak(potential_mw, actual_mw, peak_mw))
    # Size matters for reading one program's number, mostly because small
    # programs so often report a contract figure, so peers are also drawn from
    # programs of similar size.
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
    if out.get("potential_exceeds_load_at_peak"):
        out["your_status"] = (
            "potential exceeds the load in the peak hour: the form defines potential "
            "at the system peak hour, so this cannot be the defined quantity and is "
            "probably connected or contracted load (CHECKLIST.md question 3)"
        )
    elif actual_mw > 0 and np.isclose(actual_mw, potential_mw):
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


def _against_peak(potential_mw: float, actual_mw: float, peak_mw: float) -> dict:
    """Check one potential figure against the utility's own peak, the way track
    10 checks every utility. The peak EIA collects is net of any demand response
    running at the time, so the load in the peak hour before demand response is
    the peak plus the actual savings achieved in it."""
    from .tracks import t10_reporting as t10

    if peak_mw <= 0:
        raise SystemExit("peak must be positive")
    pop = t10.utility_year()
    pop = pop[pop.checkable]
    share = potential_mw / (peak_mw + actual_mw)
    return {
        "your_potential_share_of_load_at_peak": float(share),
        "us_median_potential_share_of_peak": float(pop.potential_share_of_gross_peak.median()),
        "your_percentile_against_peak": float((pop.potential_share_of_gross_peak < share).mean()),
        "potential_exceeds_load_at_peak": bool(potential_mw > peak_mw + actual_mw + t10.ROUNDING_MW),
    }


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
    bm.add_argument(
        "--peak", type=float, default=None,
        help="the utility's annual peak demand, MW: checks potential against the load in the peak hour",
    )
    where = bm.add_mutually_exclusive_group()
    where.add_argument("--rto", action="store_true", help="compare only inside RTO footprints")
    where.add_argument("--non-rto", action="store_true", help="compare only outside them")
    args = ap.parse_args(argv)

    if args.cmd == "benchmark":
        in_rto = True if args.rto else (False if args.non_rto else None)
        if args.peak is not None and args.actual is None:
            raise SystemExit("--peak needs --actual: the load in the peak hour is the peak plus the actual savings")
        result = benchmark(args.potential, args.actual, in_rto, args.peak)
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
    if "measured_rotation_share_of_zero_capacity" in result:
        print()
        print(_reading(result))
    return 0


def _reading(r: dict) -> str:
    """Plain-language reading. Says what each share is evidence of, and never
    turns persistence into a verdict, because over a short panel a rarely
    called reserve and a program that does not operate look the same."""
    lines = [
        f"{r['measured_rotation_share_of_zero_capacity']:.0%} of the capacity ever "
        "reported at zero belongs to entities that delivered a measured amount in "
        "another year. That part has shown it can deliver, so its zero years read "
        "as not running in the peak hour rather than not there.",
        f"{r['zero_every_year_share_of_zero_capacity']:.0%} stayed at zero in every "
        "year. That is ambiguous over a short panel: a reserve called once a "
        "decade and a program that does not operate both look like this.",
        f"{r['rotation_without_a_measurement_share']:.0%} rotated only into reports "
        "that show nothing about availability: a copy of enrolled capacity, a "
        "delivery under 5%, or a program whose enrolled figure moved more than "
        "threefold.",
    ]
    if "zero_capacity_next_year_delivery" in r and "measured_capacity_next_year_delivery" in r:
        lines.append(
            f"Followed one year forward, capacity at zero delivered "
            f"{r['zero_capacity_next_year_delivery']:.0%} of its potential, against "
            f"{r['measured_capacity_next_year_delivery']:.0%} for capacity that had "
            "delivered a measured amount."
        )
    lines.append(
        "Over a panel long enough to matter, a small measured share beside a large "
        "persistent one would cut against reading zeros as uncalled capacity; over "
        "a few years it would not. Either result is worth reporting."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
