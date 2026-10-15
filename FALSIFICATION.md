# Falsification

Eight attacks on this repository's own claims, A to H. Two bounced off the
headline. Two landed on it and changed what the repository is allowed to say.
The next three were aimed at mechanisms rather than the headline, and each ended
less certain than it began: two readings first reported as settled are now
open, and one is specification-dependent. The last was aimed at the number every
other attack takes for granted, the delivered figure itself, and it landed in
part.

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
artefact of picking a quiet year. Read against the form's definition (attack H)
it is a statement about one hour: in no year was more than 44.6% of mean
enrolled capability running in the hour that set the year's peak.

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

Respondent-level data for 2016 to 2018 now occupies part of the room directly.
Attack H finds 18 utility-years whose potential exceeds the load in the peak
hour, which the form's definition rules out, all in three Plains states. That
is definitional inconsistency seen in the reports themselves rather than
inferred from a regional spread, and it is small, 3.4% of the capacity that can
be checked. The rest of the room is still unoccupied, not cleared.

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

**First result, now withdrawn: REFUTED as a general explanation.** Pooled,
both concentrate outside. Zero reports carry 37% of their capacity inside RTO
footprints, and unreported ones 48%, against 57% of all enrolled capacity.
Outside RTO footprints 39% of capacity sits at zero or unreported, against 22%
inside. That was read as ruling the mechanism out, and the zero mass as a
feature of utilities that dispatch for themselves.

**What attacking the attack found.** The comparison was run once, pooled,
weighted by capacity. Varied over footprint definition, status, weighting, year
and the treatment of resized programs, with each state dropped in turn, the
outside share is higher in 69 of 96 specifications and stays higher whichever
single state is dropped in only 48. The state that carries it is Florida: 25% of
the capacity outside RTO footprints and 53% of the zero-or-unreported capacity
there, in four utilities that reported zero or nothing in every year. Without
Florida the combined shares are 25% against 22%, and unreported capacity is
more common inside footprints than outside.

**Result: UNDECIDED.** Wholesale bookkeeping is neither supported nor ruled out
as a general explanation. BGE may still be a case of it. The long-capacity
reading may describe Florida and is not shown to describe anything wider.

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

**Result: SPECIFICATION-DEPENDENT, AND NOW MIXED.** Neither "partial delivery
follows system conditions" nor "it does not" survives. The regional lean, once
copied reports are set aside, is slightly toward a dispatch-driven component,
the opposite of the first reading. Attack H then tested the same idea against
each utility's own peak, which is a sharper measure of system conditions than a
footprint, and found no response to its size or timing. So the regional test
leans one way and the utility tests the other. This attack is kept in full
because the first version of it was itself an untested analyst choice presented
as a finding.

## Attack G: does rotation show the capacity was there?

**Hypothesis.** This repository's own reading, and from v0.3.0 to v0.4.2 its
strongest evidence. A program that was not needed in a mild year reports zero
then and something in a hard year; a program that does not work reports zero
every year. Of the capacity ever reported at exactly zero in 2016 to 2018, 79%
belonged to utilities that reported something positive in another year, which
was read as most of the zero mass being available and not called.

**What attacking it found.** Varying the six choices behind the statistic 288
ways left it a majority in 202 of 216 capacity-weighted specifications, so the
number held. Reading the 26 utilities behind it did not. 15% of the capacity
ever reported at exactly zero belongs to utilities with a measured delivery in
another year; 21% stayed at zero; and 64% rotated only into a program resized
twentyfold, a report within 0.02% of enrolled capacity, or positive years under
4% of potential. Followed one year forward, capacity at zero that reported again
delivered 15% of its potential the next year, against 45% for capacity that had
delivered a measured amount.

**Result: WITHDRAWN for most of the zero mass.** Exact zeros remain evidence of
non-dispatch rather than failed dispatch. Availability is shown for 15% of the
zero mass, 34% if one ambiguous report is a real curtailment, and for the rest
three years cannot separate a rarely called reserve from a program that does not
operate. The falsification criterion in FINDINGS that this attack tested was
itself rewritten afterwards, and both versions are kept there, because a
criterion changed after the data arrive deserves suspicion.

## Attack H: does the delivered figure follow its own definition?

**Hypothesis.** Every attack above reads EIA's actual peak demand savings as the
reduction delivered during the year. The form defines it as the reduction
"measured at the time of the company's annual system peak hour", and potential
as the savings possible in that hour. If utilities report to that definition,
their reports must obey two things checkable against the rest of the same form:
potential cannot exceed the load in the peak hour, and the delivered figure
should follow the peak, rising in harder years and dropping for summer-only
programs when the peak comes in winter.

**Result: LANDED IN PART.** Some reports cannot be the defined quantity: **18
utility-years** from 8 utilities in North Dakota, Minnesota and Nebraska report
more potential than the load in their peak hour. For the rest, no test finds the
delivered figure following the peak. Within utilities it does not rise with the
size of the peak, where a rise of 2 points of utilization per percent of peak
would have been detected; the January 2018 cold did not raise it at the 59
utilities it pushed to new winter peaks, where a 20-point rise would have been
detected; and utilities whose peak moved between seasons show no difference,
though that test is weak. Either most capacity runs in either season and is not
called harder in a harder year, or most reports do not follow the definition.

**What it changes.** Nothing numeric, and the scope of everything. The shortfall
is measured in one hour, which makes a low ratio weaker evidence of failure than
any earlier version said. And whether reports follow that hour is now an open
question in its own right, which bears on attack D directly and on attack F.
FINDINGS section 12 has the tests and their power.

## Retractions

Claims in this repository that were withdrawn after looking harder, recorded here
rather than quietly edited out, because the patterns in them are worth naming.

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

Later withdrawals have a different shape, and it is the more dangerous one,
because each was a positive claim backed by a computed, pinned, tested number.

3. **The size gradient** (v0.4.0, withdrawn in v0.4.2). An apparently steep fall
   in utilization with program size, which reports copying enrolled capacity
   into the delivered field produced. METHOD rule 15.
4. **Rotation as evidence of availability** (v0.3.0, withdrawn in v0.4.3).
   Attack G. The number was right and robust; it did not measure what the prose
   said it measured. METHOD rule 16.
5. **The footprint split as ruling out wholesale bookkeeping** (v0.4.0,
   withdrawn in v0.4.3). Attack E. The number was right; one state carried it.
   METHOD rule 17.
6. **The winter accreditation value** (present by v0.3.0, corrected in v0.4.3). The winter
   four-hour cell was computed at 50% while labelled with E3's winter figure,
   which is 55%. The cell is still lost, by 3.5% instead of 14%.
7. **What the delivered figure is** (from the first version, corrected in
   v0.5.0). Described as the reduction realised during the year; the form
   defines it at the company's annual system peak hour. Attack H. No number
   moved, and every reading of a low ratio got weaker. METHOD rule 18.

In each of the first three a guard was green throughout, because the guard
checks that the prose quotes the number, not that the number means what the
prose says. What caught them was reading the observations behind the number one
at a time.

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

- No jackknife over utilities for the rotation statistic. With 26 utilities
  behind it the case-by-case table in FINDINGS section 1 shows more than a
  jackknife would; the footprint comparison, which pools hundreds of utilities,
  is jackknifed by state instead (attack E). The national aggregates in attacks
  A to D cannot be jackknifed at all, since they are already summed.
- No attempt to estimate the retail-wholesale overlap. Both populations are
  measured, neither reporter publishes the intersection, and this repo does not
  guess at it.
- No full utility-level version of attack D. Attack H checks potential
  against each utility's own peak, which catches reports that cannot be the
  defined quantity; it cannot catch a figure that is wrong but possible.
  Separating the rest of the reporting hypothesis from genuine program-design
  differences needs program-level data, which is roadmap item 1.
- Track 4's proxy is not validated against observed curtailment, because
  observed curtailment is not reachable here.
- The cost comparison is still one-sided: PJM's peaker is priced both gross and
  net of energy revenue, while demand response costs are not netted of avoided
  energy purchases at all. Every verdict in track 2 inherits that asymmetry, and
  no attack in this file repairs it.
