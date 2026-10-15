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

**1. Run the zero-mass classification on data this repo has never seen.**
*Most valuable.* The utility-level results, that exact zeros read as
non-dispatch and that only 15% of the capacity ever reported at exactly zero
shows a measured delivery in another year, rest on EIA-861 for 2016 to 2018
only. Run it on other years, another country's reporting, or one utility's
program-level records:

    python -m phantomload zero-mass your_data.csv

The docstring in `phantomload/__main__.py` gives the input format. Finish line:
open an issue with the output and the source of the data. A longer panel is the
only thing that can move the persistent and undetermined shares toward reserve
or toward non-performance, and a result in either direction is welcome.

**2. Extend the utility panel by file name.** Search for
`Demand_Response_2019.xlsx` and its neighbours, as described in METHOD.md rule
13, and take the files next to it too (rule 18): `Operational_Data`,
`Advanced_Meters`, `Dynamic_Pricing`, `Sales_Ult_Cust` and `Short_Form`. Start
in `tools/build_eia861_utility.py` and `tools/build_eia861_context.py`, which
already parse the layouts; add the years to `YEARS`. Finish line: the
reconciliation test passes for the new years, and `zero_persistence()` and
track 10's timing tests run on the longer panel.

**3. Ask ten utilities how they fill in the actual figure.** The form measures
it at the company's annual system peak hour, and the reports show no sign of
tracking that hour (FINDINGS section 12). Whether a utility reports the peak
hour, its largest event or its contract quantity is answerable from its
evaluation reports or one email. Start with the 59 utilities the January 2018
cold pushed to new winter peaks, listed by
`phantomload/tracks/t10_reporting.py`, function `january_2018_event()` and the
frame behind it. Finish line: a table of utility, method and source, which
decides whether the timing tests in track 10 are about programs or about
paperwork.

**4. Pin the DLC denominator.** One utility evaluation that reports both kW per
controlled device and devices per enrolled customer would move a modeled result
in MODELED.md into the citable findings. Start in
`phantomload/shared/calibration.py`, parameter `DEVICES_PER_ENROLLED_CUSTOMER`.
Finish line: the parameter moves to LITERATURE with a citation.

**5. Find out whether Florida called its load management.** Four Florida
utilities hold most of the zero and unreported capacity outside RTO footprints,
and the Public Service Commission describes FPL's residential program as used
in system emergencies; FPL itself says it activates the program a few times a
year at most. Their demand-side management filings and ten-year site plans may
record whether load management was activated in 2016 to 2018, and at what
hours. Finish line: a table of activations by utility and year with the source
document for each, which tests the long-on-capacity explanation in the one place
the data points to, and shows whether any activation covered an annual peak
hour.

**6. Build the PJM price duration curve.** PJM Data Miner hourly LMP, paired with
the net-load ranking track 4 already computes, would replace the last swept
parameter in the repository with a measured one. Start in
`phantomload/tracks/t2_cost.py`, function `netting_bound()`. Finish line:
`ENERGY_VALUE` is measured for the called hours rather than swept.
