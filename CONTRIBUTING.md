# Contributing

The bar here is provenance, not polish.

## Before you open a PR

```bash
pip install -e ".[dev]"
python run_all.py
pytest -q
python tools/check_claims.py
python tools/check_source.py   # skips silently if eia.gov is unreachable
```

All three must be green. `check_claims.py` will fail if you change a number
without changing the prose that quotes it, or the prose without the number.

Read [METHOD.md](METHOD.md) first. The rules below are the subset a contributor
trips over; METHOD.md explains why each exists and which ones a test can catch.

## Rules that are not negotiable

1. **No hard-coded parameters in track modules.** If a track needs a number that
   is not measured, add it to `phantomload/shared/calibration.py` with a range,
   a note and an honest provenance tag, then sweep it. Point estimates off an
   assumed central value do not go in results.
2. **Do not promote a parameter to LITERATURE without a real citation.** The
   dataclass raises if you try, and a test checks it. If you have the reference,
   add it; if you have a memory of the reference, it stays ASSUMPTION.
3. **Simulated rows go through `synthetic_program()`.** It stamps provenance at
   construction. Do not build `ProgramYear` directly for modelled data.
4. **Every result frame carries a `provenance` column.** A test enforces it.
5. **Pin new headline numbers.** Anything that lands in README or FINDINGS needs
   an entry in `tools/check_claims.py` and a test with a tolerance tight enough
   to fail on real drift.
6. **Negative and null results are first-class.** Track 3 reports that its own
   inversion is uninformative, track 6 reports that the spec's hypothesis had
   the wrong sign, and track 8 damages the repo's own headline. Do not tidy any
   of that away.

## Adding data

Vendored data needs an entry in `DATA.md` (source, coverage, retrieval date,
licence), an entry in `NOTICE` if it is not public domain, and a builder or
fetch command in `tools/`. Transcribed values live in a Python file so a source
revision shows up as a code diff.

## First contributions

Each of these is scoped, needs no blocked data, and has a finish line. The first
is the most valuable by a wide margin.

**1. Test the headline on data this repo has never seen.** *Most valuable.* The
central result, that most zero-reported capacity rotates between years rather
than persisting, rests on EIA-861 for 2016 to 2018 only. Run it on other years,
another country's reporting, or one utility's program-level records:

    python -m phantomload zero-mass your_data.csv

The docstring in `phantomload/__main__.py` gives the input format. Finish line:
open an issue with the output and the source of the data. A result where the
zero mass persists rather than rotates would cut against this repository's
reading and is just as welcome.

**2. Extend the utility panel by file name.** Search for
`Demand_Response_2019.xlsx` and its neighbours, as described in METHOD.md rule
13. Start in `tools/build_eia861_utility.py`, which already parses the layout;
add the years to `YEARS`. Finish line: the reconciliation test passes for the
new years and `zero_persistence()` runs on the longer panel.

**3. Explain the not-reported group.** Utilities reporting potential but no
actual figure hold 15% to 17% of enrolled capacity every year and nothing here
explains them. Start in `phantomload/tracks/t1_utilization.py`, function
`utility_panel()`; the 2017 and 2018 files carry a balancing-authority column.
Finish line: a table of the not-reported group by balancing authority, and a
sentence saying whether it concentrates in RTO footprints.

**4. Pin the DLC denominator.** One utility evaluation that reports both kW per
controlled device and devices per enrolled customer would move a modeled result
in MODELED.md into the citable findings. Start in
`phantomload/shared/calibration.py`, parameter `DEVICES_PER_ENROLLED_CUSTOMER`.
Finish line: the parameter moves to LITERATURE with a citation.

**5. Build the PJM price duration curve.** PJM Data Miner hourly LMP, paired with
the net-load ranking track 4 already computes, would replace the last swept
parameter in the repository with a measured one. Start in
`phantomload/tracks/t2_cost.py`, function `netting_bound()`. Finish line:
`ENERGY_VALUE` is measured for the called hours rather than swept.
