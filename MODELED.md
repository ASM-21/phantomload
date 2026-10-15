# Modeled analyses

Everything in this file depends on a simulation, a swept parameter grid or an
assumed central value, and none of it is citable as a finding. It is kept
because the reasoning is useful and because two of the corrections recorded in
FINDINGS were only possible after these models were run and found wanting.

The publication standard this repository follows refuses to assemble generated
results into the citable findings page, and `tools/check_claims.py` enforces it:
a claim classified as modeled in `tools/claim_ledger.py` fails the build if it
appears in README, FINDINGS, FALSIFICATION or PRIOR_WORK. Measured results that
these models were tested against stay in FINDINGS, and FINDINGS points here.

## Track 3. Does price-based demand response match direct load control per customer?

**Answer.** This inversion does not identify the mix. But a purely price-based
residential fleet is excluded, and part of the original uncertainty was
self-inflicted. Since v0.5.0 the mix is also bracketed by measurement, from the
form's own count of direct load control customers, at 45% to 83% of residential
enrolment (FINDINGS section 3), which agrees with the bound below.

SIMULATED, with one measured anchor, and revised after the first version
reported a plain null.

Inverting the simulation against the measured 0.45 kW delivered per enrolled
residential customer gives an implied DLC-equivalent share anywhere from 0.03 to
0.85. **the inversion is not informative**, and the first version of this track
stopped there and told the reader to go measure residential coincident peak
demand.

### Part of that spread was the parameterisation, not the data

Expressing program impacts as a fraction of the customer's coincident peak
forces every absolute answer through a scalar this repo does not measure. The
evaluation literature reports impacts the other way, as kW per participating
customer, which needs no such scalar. Re-running the same inversion in those
units gives a band 23% narrower, 0.31 to 0.94, and moves the dominant driver
from an indirect quantity nobody publishes to the per-participant impact that
utility evaluation reports state directly.

So the research instruction changes. It is no longer "go estimate residential
coincident peak demand", it is "go read one evaluation report". That is a
methodological lesson worth carrying: parameterise in the units the source
literature reports, or the model imports a nuisance parameter that the data
cannot constrain and that will dominate the answer.

### Grounding the impact parameter in evaluations changes the sign of the problem

The per-participant impact was an assumed 0.5 to 1.5 kW with a central value of
1.0. Published evaluations do not support that. Newsham and Bowker's review of
North American air conditioner control programs reports 0.3 to 1.2 kW per unit;
SDG&E's Summer Saver evaluation measured 0.41 kW per AC unit at one-in-two
weather and 0.48 at one-in-ten; CenterPoint's 2025 evaluation measured 0.59 kW
per thermostat across a two-hour event. The measured central value is about half
what this repo assumed.

That produces a tension rather than a tighter answer. At central published
values a fully controlled residential fleet delivers 0.35 kW per enrolled
customer, and EIA reports 0.45, so the observed figure is 1.28x what a fully
controlled fleet delivers and 45% of parameter draws are outright infeasible.
An implied share above one is not a program mix, it is a contradiction.

### Resolved: it was the denominator

The commissioned literature search confirmed the cause and supplied the missing
piece. Evaluations report per AC unit, per thermostat or per participating home;
EIA counts customers. Saturation among enrollees pushes the per-customer figure
below the per-device one, multi-device households push it above, and neither
source publishes the bridge. Solving for it rather than assuming it, about 1.3
controlled devices per enrolled customer reconciles the two, which sits inside
any plausible range. The contradiction dissolves into a units mismatch.

The search also gave a benchmark worth keeping: a mass-market residential
program reporting much above 1 kW per enrolled customer has almost certainly
mixed a per-device numerator into a per-customer denominator. This one reports
0.45, which is weak evidence that EIA's denominator is genuinely per customer.

The original three candidate explanations are kept below because the reasoning
is worth more than the answer.

Three explanations, and this repository could not choose between them at the
time. The most likely was units: evaluations report per AC unit, per thermostat or per
household, while EIA counts customers, and a household with two controlled units
delivers twice the per-unit figure. The comparison is unit-inconsistent in
exactly the direction that inflates the EIA number, which is an instance of the
first rule in METHOD.md arriving as a live problem rather than a lesson. The
second is composition, if the national fleet skews to higher-impact programs
than the evaluated samples. The third is reporting, which is attack D's question
arriving from a third direction.

Resolving it needs device counts alongside customer counts, which EIA does not
collect.

### And the null was hiding a bound

The inversion does not identify the mix. But the measured delivery per enrolled residential
customer is 1.8x to 9.0x what a pure time-of-use fleet could produce, across the
entire parameter range, so the residential demand response fleet is not
predominantly price-based. Every draw of the sweep requires some direct load
control, and with the evaluation-grounded impacts the floor is at least 22% of
enrolment behaving as direct load control.

The reverse does not hold. A predominantly direct load control fleet is
compatible with the measured value at the low end of the impact range, so the
result is one-sided: price-based-only is excluded, control-based-only is not.
A bound in one direction is not a point estimate, and it is worth more than the
null this track used to report.


## Track 5. How much of demand response's claimed peak reduction is really the tariff?

**Answer.** Under a pre-program baseline, about a fifth of the claim. The
genuinely ambiguous part is small; the convention is what does the damage.

SIMULATED, and small enough to check by hand.

With a TOU effect a and a DR effect b, joint reduction is a + b - ab. Under a
pre-program baseline the DR program is credited with the whole joint reduction
and so absorbs the entire tariff effect: 22% more than its marginal contribution
at central parameters. The genuinely ambiguous interaction term, the part no
convention can assign cleanly, is 3.7% of the claim.

The overcredit exceeds the interaction in every draw of the sweep, by a median
factor of 5.3x. So the fix is a baseline convention, not a better attribution
method: evaluate against a same-rate control group and the double count goes
away, while the Shapley split only ever moves the small piece.


### What the decomposition implies in megawatts, conditionally

Carried through the decomposition, and conditional on evaluations using a
pre-program baseline, the double-counted residential peak credit lies between
97 and 886 MW, or 2.4% to 21.7% of residential realised peak savings. The
customer counts behind it are measured and sit in FINDINGS section 5; the
overcredit share they are multiplied by is modeled, which is why this figure
lives here.
