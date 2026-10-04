# Falsification

Three attacks on this repo's own headline. Two bounced. One landed and changed
what the repo is allowed to say.

Run them with `python -c "from phantomload.tracks import t8_falsification as t; import json; print(json.dumps(t.run()['summary'], indent=2, default=str))"`.

## Attack A: the mild-year artefact

**Hypothesis.** A single-year utilization ratio overstates phantom capacity,
because a resource held in reserve and correctly not called in a mild year looks
identical to a resource that does not exist. Recompute on rolling five-year
windows, and more aggressively, credit each window with its best year as the
demonstrated capability. If enrolled capacity shows up in at least one year of
a window, the shortfall is about dispatch frequency, not about capability.

**Result: HOLDS.** Rolling five-year means barely move off the single-year mean.
Crediting the single best year of the entire 12-year panel against mean enrolled
capability still realises only 44.6%. Enrolled capacity does not show up in some
other year; it does not show up in any year.

This is the strongest thing in the repo. Whatever the shortfall is, it is not an
artefact of picking a quiet year.

## Attack B: the alternative's best case

**Hypothesis.** Track 2 compares demand response against a peaker or storage
cost. Give the alternative its cheapest published cost instead, PJM's net CONE,
and see whether the conclusion survives the comparator at its best.

**Result: SURVIVES, with a sign change worth more than the survival.** At the
bottom of the swept range, demand response still beats every comparator on the
enrolled basis and loses to all of them on the delivered basis at $128.78 per
kW-year. Squeezing the comparator does not change the answer, because the answer
was never being driven by the comparator. It is being driven by the choice of
denominator.

That reframes track 2's contribution: the useful output is not "DR is expensive"
but "the enrolled-basis number that appears in program filings and the
delivered-basis number are far enough apart to give opposite recommendations
across most of the plausible comparator range."

## Attack C: the reserve share

**Hypothesis.** Suppose some fraction of the shortfall is legitimate reserve:
capacity that was correctly held, correctly not called, and should not be
haircut out of the cost calculation, because insurance you did not claim on is
not wasted spending. Solve for the fraction that would have to be legitimate for
demand response to break even against a given comparator.

**Result: THE HEADLINE TAKES DAMAGE FROM BOTH DIRECTIONS.** **only a small share
of the shortfall has to be genuine reserve** for the verdict to move, and with
PJM's real numbers the required share straddles zero. Against gross CONE of
$149.31 per kW-year it is -8.8%, meaning demand response already breaks even
with no reserve credit whatsoever. Against net CONE of $68.35 it is 56.8%,
meaning most of the shortfall would have to be legitimate insurance. Above
roughly $129 per kW-year, none of it has to be.

And track 1 shows the published data cannot rule that out. Twelve years of
national aggregates can only exclude reserve designs with return periods under
4.5 years. Anything held for a rarer condition than that is indistinguishable
from phantom capacity in this dataset.

**What this repo changed as a result.** The tagline stays, because the shortfall
is real and measured. What is not claimed anywhere is that the shortfall is
waste. The first version of track 2 hid this behind an assumed comparator range
that excluded net CONE, which made the cost question look like a close call
about uncertainty rather than a choice between two published accounting bases.
That retraction is in the README. The README leads with the ratio and the identification problem in the
same paragraph, tracks 2 and 8 report both cost bases side by side, and
`tools/check_claims.py` fails the build if the caveat sentence goes missing.

## Attack D: the reporting artefact

**Hypothesis.** "Potential peak demand savings" is self-reported and unaudited.
If utilities apply the definition differently, part of the shortfall is a survey
artefact rather than either phantom capacity or reserve. Earlier versions of this
file listed this as the most likely third explanation and as untestable. The
regional cut makes it partly testable.

**Method.** Reported MW per enrolled customer should be broadly comparable across
regions once class mix is held constant, since class is what drives per-customer
impact. Computing each division's implied customer count from its class-level MW
and the national per-class intensity gives an index that is 1.0 in aggregate by
construction, so any spread is pure redistribution.

**Result: OPENS A THIRD EXPLANATION THIS REPO CANNOT CLOSE.** The index spans
5.5-fold, from the Pacific to the Mountain division. Force the least intense
division's standard on everyone and national utilization moves from **35.2% to
90.6%**, which erases the shortfall completely. Force the median standard instead
and utilization falls to 26.4%, making it worse.

Weighting by capacity rather than counting divisions does not rescue it: only
**30% of enrolled MW** sits within 25% of the national norm, so most reported
capacity comes from divisions reporting well off it.

**What that does and does not establish.** It bounds the room the reporting
hypothesis has, and the room is large enough to hold the entire headline. It does
not occupy that room, because genuine program-design differences produce the
same signature: a Californian residential behavioural program and an Alabama
industrial interruptible contract are different products and should have
different intensities. Nothing in the public data separates a definitional
inconsistency from a real difference in what is being enrolled.

**Persistence separates the two mechanisms partway.** They leave different
fingerprints over time. Genuine differences in what is enrolled persist, since a
fleet of industrial interruptible contracts does not become a fleet of
residential thermostats in a year. Reporting instability does not persist; it
shows up as a discontinuity when a respondent changes how it counts.

Across the two published years, **7 of 9 divisions** hold their reported MW per
enrolled customer within 25%, which favours genuine differences for most of the
spread. The two exceptions do not look like fleets at all. **Mountain lost 51.8%
of its enrolled customers in one year while its reported capacity rose 8.9%**,
and the Pacific moved the other way, adding 74.5% more customers while capacity
fell. No real program fleet moves headcount and capacity in opposite directions
at that scale in twelve months.

So both mechanisms are present and neither dominates. Two years is also the
minimum window that permits this test and not enough to tell a one-off filing
correction from the start of a trend. The two discontinuity divisions are where
respondent-level data would pay off first.

The practical consequence is a third thing that has to be settled before the
ratio means anything, alongside the reserve question from attack C and the
accounting bases from the synthesis. Reading the shortfall as non-performance
requires an argument that reporting is consistent across respondents, and no
such argument appears in the source.

## Attack E: is the zero mass just wholesale bookkeeping?

**Hypothesis.** This repository's own. The largest persistent zero, BGE, runs a
program that bids into PJM, so its realised reduction might be recorded in the
wholesale settlement and reported as zero in the retail filing. If that were the
general mechanism, zero and unreported actuals would concentrate inside RTO
footprints.

**Result: REFUTED as a general explanation.** Both concentrate outside. Zero
reports carry 37% of their capacity inside RTO footprints, and unreported ones
48%, against 57% of all enrolled capacity. Outside RTO footprints 39% of
capacity sits at zero or unreported, against 22% inside. BGE may still be a case
of it; the pattern is not.

What the refutation leaves standing is more interesting than the hypothesis: the
zero mass is a feature of utilities that dispatch for themselves, which is where
a long capacity position would show up as a program nobody calls.

## Attack F: does partial delivery follow system conditions?

**Hypothesis.** If the largest piece of the gap were also reserve, held back
until conditions demanded it, utilization would rise and fall together across
utilities in the same footprint in the same year.

**First result, now rescoped.** In the specification first run, common shocks
explained no more year-to-year variation than shuffled labels, p = 0.36, and a
power check showed a regional shock of SD 0.05 would have been caught. That was
reported as evidence that partial delivery is a fixed property of each program.

**What attacking the attack found.** The test rested on two choices made once.
One was to include 63 utilities whose reported utilization is exactly 1.0 every
year, because their actual figure is their potential. Observations fixed by
convention add no variance and pull every regional average toward zero, so they
bias the test toward a null. The other was the minimum number of utilities a
footprint needs. Across the nine combinations the regional share beats chance
every time and is significant in three, p from 0.0055 to 0.36.

**Result: SPECIFICATION-DEPENDENT.** Neither "partial delivery follows system
conditions" nor "it does not" survives. The lean, once copied reports are set
aside, is slightly toward a regional, dispatch-driven component, which is the
opposite of the first reading. This attack is kept in full because the first
version of it was itself an untested analyst choice presented as a finding.

## Retractions

Two claims in this repo have been withdrawn after looking harder. Both are
recorded here rather than quietly edited out, because the pattern in them is the
same and it is worth naming.

1. **Track 2's assumed comparator range.** Swept 80 to 150 dollars per kW-year
   as "the commonly quoted CT range". PJM's published planning parameters put
   net CONE at $68.35, below the assumed floor, and net versus gross is what
   decides the comparison. An assumed range dressed a choice up as uncertainty.

2. **Track 7's claim that no second estimator existed.** Withdrawn. FERC
   publishes wholesale registrations from seven RTOs and ISOs plus deployment
   figures from real events. The claim was not a finding about the data, it was
   a report on where this repo had looked.

A third correction, smaller and same shape: track 4's seasonal blind spot was
written as though the winter gap were unaddressed. PJM has required year-round
availability from its only forward capacity demand response product since the
2020/2021 delivery year. The finding is now scoped to the retail population and
the market's own experience is reported alongside it, where the scarcity of
winter-capable bids corroborates the measurement.

Both of the retractions above were negative claims about what public data
contains. Neither was tested
the way the positive claims were, because `check_claims.py` can catch a number
that drifts and cannot catch an absence that was never searched for. The
practical fix adopted here: any sentence asserting that something is not
publicly available now names the specific sources checked, so the claim is
falsifiable by someone who knows a source this repo missed.

## What would settle it

Any one of these would break the tie, and none is reachable from public
aggregates:

1. Event counts per program-year. Utilities report them to their regulators;
   EIA does not collect them, and the RTO reports give registrations plus
   occasional narrative deployment figures rather than a per-program series.
2. Performance during called events, separated from availability. This is the
   quantity everyone thinks the utilization ratio measures.
3. A long enough panel. Thirty years of consistent reporting would identify a
   1-in-10-year reserve. The current series has a reclassification break at
   2023, so it is not even continuous over twelve.

## Attacks not run

Stated so the absence is not mistaken for a clean bill of health.

- No jackknife over utilities. The panel is already aggregated to national by
  sector, so utility-level influence cannot be tested here.
- No attempt to estimate the retail-wholesale overlap. Both populations are
  measured, neither reporter publishes the intersection, and this repo does not
  guess at it.
- No utility-level version of attack D. The regional test above shows the
  reporting hypothesis has room; separating it from genuine program-design
  differences needs respondent-level data, which is roadmap item 1.
- Track 4's proxy is not validated against observed curtailment, because
  observed curtailment is not reachable here.
- The cost comparison is still one-sided: PJM's peaker is priced both gross and
  net of energy revenue, while demand response costs are not netted of avoided
  energy purchases at all. Every verdict in track 2 inherits that asymmetry, and
  no attack in this file repairs it.
