# Reading a demand response gap: questions to ask before concluding anything

A utility reports that its demand response programs could deliver a certain
peak reduction, and that they actually delivered much less. Nationally the
shortfall averages about 61% of enrolled capacity and has held for twelve years.
It is tempting to read that as capacity paid for and never there.

This page is for anyone who has to interpret one of those numbers: commission
staff reviewing a filing, a planner benchmarking a program, an analyst building
a resource adequacy case, a journalist, or an advocate. Each question says why it
matters, what this repository found, and how to answer it with data you are
likely to have. None of them needs this repository's code.

## 0. How big is the program?

**Why.** Every other question depends on it. The national shortfall is
capacity-weighted, so it describes the largest programs, and utilization falls
steeply with size.

**What the evidence says.** The median utility realises 67% of its potential.
By program size the median runs from 94% of potential in the smallest quarter
of programs and 48% in the largest, and the largest quarter holds 88% of
enrolled capacity. A small program at 40% is in the bottom fifth of its peers; a
large one at 40% is near the middle.

**How to answer it.** Compare against programs of similar size, never against
the national figure: `python -m phantomload benchmark --potential <MW> --actual <MW>`.

## 1. Was the program called at all?

**Why.** A program that was not dispatched reports zero realised reduction,
whether or not it would have performed. Zero is what an unneeded reserve looks
like in a mild year.

**What the evidence says.** Across every utility reporting to EIA from 2016 to
2018, exact zeros held 10.0% to 17.8% of enrolled capacity a year, and of the
capacity ever reported at zero, 79% of the capacity moved between zero and
positive across those years. Only 9 of 304 utilities reported zero every year.

**How to answer it.** Ask for the number of events called each year. A zero
with no events is a dispatch decision, not a performance failure.

## 2. Is the utility long on capacity?

**Why.** A utility that does not need its demand response has no reason to call
it, and the program will look idle however well it works.

**What the evidence says.** Zero and unreported actuals concentrate in
utilities that dispatch for themselves: 39% outside RTO footprints against 22%
inside, the reverse of what wholesale bookkeeping would produce. That fits the
long-on-capacity explanation ACEEE proposed in 2017, though this repository
cannot test it directly.

**How to answer it.** Compare the program's dispatch record against the
utility's reserve margin in the same years.

## 3. How is "potential" defined?

**Why.** Potential peak demand savings is self-reported and unaudited. If one
utility reports its contracted maximum and another its modelled expectation, the
same program looks very different.

**What the evidence says.** After holding customer-class mix constant, reported
capacity per enrolled customer varies 5.5-fold across census divisions. Imposing
the least intense division's standard everywhere would move national utilization
from 35.2% to 90.6%. That bounds how much a definition can matter; it does not
show which definitions are in use.

**How to answer it.** Ask what the potential figure represents: a contract
quantity, a device count times an engineering estimate, or a measured
historical maximum.

## 4. Is the partial-delivery ratio stable from year to year?

**Why.** This is the largest piece of the gap and the one this repository could
not settle. If a program delivers a stable fraction of its potential every year
regardless of conditions, that ratio is a property of the program, whether its
definition, its protocol or a consistent shortfall in response.

**What the evidence says.** Partial delivery is 49% to 57% of the gap. It is
sticky within a utility, a within-utility SD of 0.076, and it does not move with
regional conditions: footprint-wide shocks explain 6.0% of year-to-year
variation, p = 0.35.

**How to answer it.** If the ratio is stable, ask why: what fraction of devices
respond per event, and what share of enrolment is ever dispatched. Event-level
evaluation reports usually contain both.

## 5. Which basis is the cost being compared on?

**Why.** Demand response cost per kW enrolled and per kW delivered differ by a
factor of about 2.6. The peaker it is compared against has the same problem,
gross versus net of energy revenue, and accredited versus nameplate.

**What the evidence says.** Across the eight defensible pairings of these bases,
demand response is cheaper in 6 of 8, including both pairings that apply the
same basis to each side. It loses only when demand response is haircut and the
peaker is not.

**How to answer it.** Confirm that the same netting, accreditation and
realization treatment is applied to both sides before comparing.

## 6. Is the haircut a realization rate or an accreditation?

**Why.** These are different quantities and are routinely confused. The share of
enrolled capacity that was realised in a year counts years when nothing was
called. Effective load carrying capability asks what share is dependable in the
hours that matter.

**What the evidence says.** Published accreditation for a four-hour curtailment
program runs about 83% in summer, against roughly 39% realised. Using the latter
as a capacity haircut roughly doubles demand response's apparent cost.

**How to answer it.** Use an accreditation study for capacity value, and keep
dispatch statistics for questions about dispatch.

## 7. Can the program be called in winter?

**Why.** Winter peaks are long, and a program designed for four-hour summer
afternoons may not cover them.

**What the evidence says.** This is the most robust result in the repository,
reached three independent ways: hourly net load reaches 91% of its annual
maximum in ERCO and 85% in PJM in winter months; the winter four-hour case is the
only accreditation pairing demand response loses; and PJM's own seasonal
aggregation was limited by a shortage of winter-capable resource.

**How to answer it.** Ask for the program's seasonal call window and its winter
event record.

---

## What this checklist cannot tell you

Whether a specific program would perform if called. Only event-level evaluation
can answer that, and nothing above substitutes for it. The questions narrow what
a gap could mean; they do not say which meaning is true for a given program.

Every figure on this page is recomputed from the repository's data on each build
and listed with its provenance in [CLAIMS.md](CLAIMS.md).
