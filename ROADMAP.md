# Roadmap

Ordered by how much each would change the conclusions, not by effort.

## 1. Utility-level EIA-861 detailed files

Substantially closed. The 2016 to 2018 detailed files were found vendored inside
an unrelated repository and now drive the central result: exact zeros hold 10%
to 18% of enrolled capacity a year, and 79% of zero-reported capacity rotates
between years rather than persisting, which favours uncalled over absent.

What remains, in order of value:

- **More years.** Three is the minimum that permits a persistence test and not
  enough to separate a weather cycle from a trend. The same file name for 2013
  to 2015 and 2019 onward would extend it. Searching for
  `Demand_Response_2019.xlsx` and its neighbours is the first thing to try.
- **The not-reported group.** Utilities reporting potential but no actual figure
  hold another 15% to 17% of capacity every year. Nothing here explains them.
  Whether they are wholesale-registered programs recorded elsewhere, small
  programs exempt from the field, or simple non-response is answerable from the
  same files with the balancing-authority column, which 2017 and 2018 carry.
- **The BGE hypothesis.** The largest persistent zero is a program that bids
  into PJM. If persistent zeros concentrate in utilities whose programs
  participate in wholesale markets, the persistence result is partly a
  retail-wholesale accounting effect. Testable by joining the BA column to the
  RTO footprints.

## 2. Anything with an event count

The identification problem in track 1 is structural given EIA data. It is not
structural given utility evaluation reports filed with state commissions, which
routinely list events called, duration and measured performance. Even a
convenience sample of twenty programs would separate "never called" from "called
and underdelivered" for the first time in this repo.

## 3. A netted demand response cost

Downgraded, not closed. The asymmetry is real: PJM prices its peaker gross and
net of energy revenue, EIA reports demand response cost gross only. But the
correction is now bounded rather than unknown. Avoided energy per delivered kW
is the implied event hours, which EIA does publish, so the credit is hours times
price, and sweeping both across generous ranges closes none of the $60.43 per
kW-year gap to net CONE.

Measuring it properly would still be worth doing, because the bound is loose and
the same arithmetic in the fully aligned cell of `synthesis.py` sits much closer
to the line. Rough options, in increasing order of effort: apply an RTO-average
on-peak LMP to the reported energy savings; use event-hour LMPs if event timing
ever becomes available through item 2; or take avoided-cost values from utility
program evaluations, which would import their assumptions along with their
numbers.

The higher-value version of this is now item 2 rather than item 3. Event timing
determines the price, and the synthesis shows the whole comparison terminates on
whether demand response is dispatched into scarcity.

## 4. Winter demand response

The seasonal result in track 4 is the most actionable thing this repo produced
and it is barely explored. Winter net load reaches 85 to 91% of the annual
maximum in PJM and ERCOT, a summer call window cannot reach any of it, and the
February 2021 hours that do crack the scarcity tail are understated because
generation data cannot see shed load.

What is missing is the program side, and only for retail. PJM's wholesale market
already requires year-round availability, and reported that seasonal aggregation
was constrained by how little winter-capable resource was offered, so the
physical asymmetry is priced there. EIA does not publish call windows or seasonal
availability for retail programs, so this repo can only show that the hours
exist, not what share of enrolled capacity is contractually reachable in January. Utility tariff
sheets and RTO capacity market rules both carry that, and it would turn a timing
observation into a capacity number.

## 5. Observed curtailment instead of a proxy

Track 4 uses top-decile renewable share as an oversupply proxy. CAISO and ERCOT
publish actual curtailed MWh. Swapping the proxy for the real series would let
the track quantify absorbable energy rather than only window timing.

## 6. Reporting-practice variation

Named in FALSIFICATION.md as the most likely third explanation for the shortfall
and not currently testable. "Potential peak demand savings" is self-reported and
unaudited. If some utilities report contracted capacity and others report a
modelled maximum, part of the gap is a survey artefact. Utility-level data plus a
few program filings would let this be checked directly, and it should be checked
before anyone quotes the headline as an efficiency finding.

## 7. The retail-wholesale overlap

Both populations are now measured, 30.5 GW retail and 33.3 GW wholesale, and
neither reporter publishes the intersection. Estimating it would need utility
and CSP registration lists matched to EIA respondents, which is a records
exercise rather than an analysis. Until someone does it, no defensible national
total for demand response capacity exists, and any figure that adds the two is
wrong by an unknown amount.

## 8. One utility evaluation report

The cheapest open item in this file. Track 3's inversion is not identified, and
after re-parameterising into the units evaluations actually use, the entire
remaining spread is driven by one number: peak reduction in kW per participating
customer under direct load control. Utility evaluation reports state it directly.
One report from a large residential program would collapse a band that currently
runs 0.31 to 0.94.

The wider lesson is already written into FINDINGS section 3 and is worth more
than the number: parameterise in the units the source literature reports, or the
model imports a nuisance parameter the data cannot constrain, and it will
dominate the answer while looking like irreducible uncertainty.

## 9. Hourly prices in the called hours

Half done. The annual anchor is in: PJM's market monitor publishes the
real-time load-weighted average LMP, so the capstone's requirement is now
expressed as 8.5x the annual average rather than as a bare dollars-per-kWh
figure, and the netting gap as 12.7x.

The half that remains is the one that matters. Demand response is called in
roughly the top one percent of hours, and the annual average says nothing about
what those hours price at. PJM Data Miner carries hourly LMP and was not
reachable here. Pairing it with the net-load ranking already computed in track 4
would give the called-hour price directly, and would turn the last swept
parameter in the repository into a measured one.

## 10. A literature review

The largest single gap in the work and the one a reviewer would raise first.
Nothing here has been checked against the published literature, because the
environment this was built in could reach government data portals and market
monitor reports but not journals. Several results are the kind of thing that
plausibly exists already.

Where to look, roughly in order of how likely the result is to be there
already:

- Demand response evaluation and measurement-and-verification literature, for
  the realisation rate itself and for per-participant impact values, which would
  also close item 8.
- Capacity accreditation and effective load carrying capability work, for the
  accounting-basis problem in the synthesis. Resource adequacy modellers have
  almost certainly written about netting and accreditation asymmetries.
- Survey methodology and administrative data quality, for the reporting
  heterogeneity test in attack D. The mix-adjusted index is a standard
  shift-share construction under another name.
- Reliability statistics, for the identification bound. Estimating the frequency
  of rare events from short records is an old problem with a large literature,
  and the closed form in track 1 is elementary enough that it will have one.

Until that is done, nothing in this repository should be presented as novel. It
should be presented as computed, checked and reproducible, which it is.

## 11. Cross-repo reuse

Track 5 currently represents a customer as a single coincident-peak scalar.
Wiring it to grid-lab's tariff-explorer archetypes and load shapes would let the
TOU and DR interaction run on 8760s and produce a bill impact rather than a
dimensionless attribution share. The attribution shares themselves are scale-free
and would not move.

## Before pushing

Housekeeping that cannot be done from the environment this was built in, since
there are no git credentials here. The repo is committed and tagged locally.

- [ ] Decide the name before creating the remote. "Phantom load" already means
      standby draw in this field, an exact-name repository exists on GitHub, and
      the name claims more than the findings support. `tools/rename.sh` does the
      whole rename in one command and re-runs the tests and the claims guard;
      `benchstrength` and `dispatchgap` are free on PyPI and under ASM-21;
      `dr-realization`, recommended earlier, would have named the wrong
      quantity and is withdrawn. Renaming after
      publication costs far more than renaming now.
- [ ] Create the remote and push, including the `findings-2026-09` tag.
- [ ] Add `[project.urls]` to `pyproject.toml` once the remote exists. It was
      left out rather than shipped with a placeholder URL.
- [ ] Set repo topics: `demand-response`, `grid-reliability`,
      `utility-economics`, `capacity-market`.
- [ ] Set the social preview to `figures/fig1_utilization.png`.
- [ ] Run `python tools/check_source.py` once from an unblocked network. It has
      never been exercised against the live page, only against a fixture, so
      confirm by hand that it parses rather than skipping.
