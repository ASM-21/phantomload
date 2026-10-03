# Method

Thirteen rules this repository runs on. Each is here because it was learned during
the build, usually by being violated first. Each says what went wrong, what the
general rule is, and whether anything mechanically enforces it, because a rule
nothing enforces is a hope.

The list is written to be portable. Most of it has nothing to do with demand
response.

---

## 1. Parameterise in the units the source literature reports

**What happened.** Track 3 expressed program impact as a fraction of the
customer's coincident peak. That forced every absolute answer through a scalar
this repo does not measure, the scalar dominated the result, and the track
reported a null while telling the reader to go measure the wrong thing.
Evaluation reports state impact as kW per participating customer. Re-running the
identical inversion in those units was 23% narrower and moved the binding
uncertainty onto a number one report would supply.

**The rule.** A model expressed in units the sources do not use will import a
conversion parameter, and an imported parameter the data cannot constrain looks
exactly like irreducible uncertainty.

**Enforcement.** Partial. `test_t3_units_choice_cost_a_quarter_of_the_band` pins
the reduction and `test_t3_absolute_sweep_carries_no_peak_scalar` fails if the
nuisance parameter returns. Nothing stops the mistake being repeated in a new
track.

**Postscript, and it is the better half of the lesson.** Reading the evaluation
literature later replaced the assumed impact range with a measured one and
revealed that the two sides of the comparison count different things:
evaluations report per AC unit or per thermostat, EIA reports per customer. So
the units problem was never only about the model's internal parameterisation. It
was also a units mismatch between two sources, and it was invisible until
someone read both. See FINDINGS section 3.

## 2. A claims guard cannot catch a claim about absence

**What happened.** Two claims were retracted and both were negative claims about
what public data contains: an assumed comparator range described as the commonly
quoted one, and a flat statement that no second estimator existed. The guard
recomputes every positive figure and could touch neither, because neither was a
number.

**The rule.** Any sentence asserting that something is not publicly available
names the specific sources checked, so the claim is falsifiable by someone who
knows a source you missed.

**Enforcement.** Convention only, applied throughout `DATA.md`. The weakest rule
here and the one that has failed most often.

## 3. A guard that false-fails gets ignored

**What happened.** A required caveat straddled a line break after ordinary prose
editing and the guard failed the build although the phrase was present.

**The rule.** Distinguish failures caused by the analysis from failures caused
by editing. A guard that cries wolf teaches people to bypass it, at which point
it protects nothing.

**Enforcement.** Yes. Matching is whitespace-normalised and
`test_guard_tolerates_line_wrapping_but_not_drift` proves reflowed prose passes
while a changed number still fails.

## 4. Check whether your finding is already addressed

**What happened.** Track 4 found that a summer call window cannot reach the
winter shoulder, and the first draft implied nobody had noticed. PJM retired its
summer-only demand response products and required year-round availability from
its sole forward capacity product five years earlier.

**The rule.** Before publishing a gap, look for the rule, tariff or practice
that already closes it. The finding usually survives with a narrower scope, and
the search often turns up corroboration: here, the market's own report that
seasonal aggregation was limited by a scarcity of winter-capable bids, which is
the same asymmetry priced rather than modelled.

**Enforcement.** Yes, narrowly. `test_t4_seasonal_finding_is_scoped_to_retail`
fails if the scope statement disappears.

## 5. Two agencies publishing the same survey is a free transcription check

**What happened.** EIA publishes national demand response aggregates; FERC
publishes its own regional aggregation of the same EIA-861 filings. FERC's
division sums reproduce EIA's national class totals to within rounding.

**The rule.** When a second organisation independently aggregates a source you
transcribed, reconcile against it. It is the strongest guard available on a
vendored dataset and it costs one test.

**Enforcement.** Yes. `test_ferc_regional_reproduces_the_eia_national_panel`.

## 6. Bound the unmeasurable rather than leaving it open

**What happened.** Demand response costs are not netted of avoided energy while
the peaker comparator is published both ways, and no source closes the gap. That
sat as an open blocker until it turned out the credit is hours times price, both
bounded: the hours are published, and no plausible price closes the distance.

**The rule.** An unmeasured quantity is not automatically an open question. Try
to decompose it into things that are bounded, and sweep. A bound that rules out
the whole plausible range settles the matter as firmly as a measurement.

**Enforcement.** Yes. `test_t2_netting_cannot_close_the_gap` and
`test_t2_netting_credit_is_hours_times_price`.

## 7. When a comparison needs basis alignment, enumerate the pairings

**What happened.** Comparing demand response cost to a peaker needs three
separate alignments: netting, accreditation and realization. Picking one
combination and reporting it would have produced a confident answer that a
different, equally defensible combination reverses.

**The rule.** Enumerate every pairing, mark which are internally consistent, and
report how many favour each side. If the consistent ones agree, that is the
finding. If they disagree, the question is not answerable at that level.

**Enforcement.** Yes. `synthesis.py` computes the grid and
`test_synthesis_consistent_cells_carry_no_mismatch` pins it.

## 8. Prefer statistics that are fixed by construction

**What happened.** The reporting-heterogeneity index in attack D is built from
national per-class intensities, so its aggregate value is 1.0 whatever the data
says. Any spread is pure redistribution, and a deviation from 1.0 means the
class mapping has broken rather than that the world changed.

**The rule.** A statistic with a known value under correct construction gives a
free integrity test and an unambiguous interpretation. PJM's
gross-minus-offset-equals-net is the same idea from the other direction.

**Enforcement.** Yes. `test_t8_intensity_index_is_pure_redistribution` and
`test_pjm_cone_identity_gross_minus_eas_equals_net`.

## 9. A null result may be hiding a one-sided bound

**What happened.** Track 3 could not identify the program mix and reported
nothing for several revisions. The same sweep showed that measured delivery per
customer exceeds what any price-based fleet could produce, in every draw.

**The rule.** Failing to identify a point is not failing to exclude a region.
Check both edges of the parameter space before declaring a null, and report the
bound as one-sided when only one edge binds.

**Enforcement.** Yes. `test_t3_bound_is_one_sided` fails if the result is ever
stated symmetrically.

## 10. Stamp provenance at construction, not at write time

**What happened.** Nothing, which is the point. Simulated program records are
built through `synthetic_program()`, which forces `SIMULATED` and discards any
provenance argument passed to it.

**The rule.** If a record can be created without its provenance, eventually one
will be, and it will surface downstream in a table where it looks like
measurement. Make the constructor the only door.

**Enforcement.** Yes. `test_synthetic_program_cannot_claim_measured` passes a
`MEASURED` tag in deliberately and asserts it is ignored.

## 11. Label identities as identities

**What happened.** Cost per delivered kW equals cost per enrolled kW divided by
utilization. The minimum observation window follows from the return period by
algebra. Both look like findings and neither is one.

**The rule.** Tag anything true by construction as an identity in the results
themselves, not only in prose. It stops a tautology being quoted as evidence and
it makes the arithmetic a useful unit test of everything around it.

**Enforcement.** Yes. `Provenance.IDENTITY` is a first-class tag and
`test_t2_cost_identity_holds` asserts the algebra to 1e-9.

## 12. Sweep a proxy's definition, and say when a definition is circular

**What happened.** Track 4 defines curtailment risk by a threshold on renewable
share. Both the threshold and the definition were swept, 24 combinations, all
agreeing. One of the two definitions, lowest net load, is close to
definitionally anti-correlated with a peak-shaving window.

**The rule.** Report a proxy's robustness across definitions, then say which of
those definitions are independent evidence and which merely restate the
mechanism. Counting a circular definition as confirmation inflates confidence.

**Enforcement.** Partial. The sweep is tested; the circularity note is prose.

## 13. When the subject search is exhausted, search for the file name

**What happened.** For most of this repository's life, utility-level demand
response data was listed as unavailable: the EIA-861 detailed files are bulk
downloads from eia.gov, which was blocked. Every search was for the subject.
The files were sitting, unmodified, inside a public repository about mapping
utilities to counties, which had bundled the whole EIA-861 release as an input.
A search for `Demand_Response_2017.xlsx` would have found it on the first day.
It was actually found because the repo had appeared in this project's very first
search and been dismissed as off-topic.

**The rule.** A blocked primary source is often vendored somewhere as an
incidental input to an unrelated project. Search for the exact file name the
publisher uses. Reconcile what you find against an independent aggregate before
trusting it, which here meant matching the national panel to the megawatt.

**Enforcement.** Partial. `test_utility_panel_reconciles_to_the_national_panel`
guards the data once found. Nothing can make the search happen.

---

## What is not on this list

Rules that sound good and did nothing here. Precision about uncertainty
intervals never mattered, because sampling variability was never the binding
uncertainty: reporting practice, accounting basis and identification were. More
tests never caught anything a first well-chosen test missed. And every
significant correction in this repository came from finding a second source or a
second definition, never from analysing the first one harder.

One operational rule that belongs in the same spirit. `verify.sh` built its
virtual environment in a temp directory and never removed it, leaking about
400 MB per run until the disk filled and builds started failing with I/O errors
that looked like anything but a full disk. Clean up after yourself in the script
that runs most often.
