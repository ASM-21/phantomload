# Method

Eighteen rules this repository runs on. Each is here because it was learned during
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
`test_guard_tolerates_line_wrapping_but_not_drift` checks that reflowed prose passes
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
separate alignments: netting, accreditation and dispatch utilization. Picking one
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

## 14. Totals cannot see a duplicated key; counts can

**What happened.** The utility panel reconciled to the national series to the
megawatt in every year, and still carried a bug. Wabash Valley Power reports in
Indiana under two balancing authorities, so utility plus state was not a unique
key, and three functions resolved the duplicate three different ways: one kept
the first row, one averaged two different programs, one put both into a single
footprint. Summing never notices, because the rows sum correctly whichever way
they are grouped. It surfaced only when the raw row count for one year came out
one higher than PUDL's independently published expected count.

**The rule.** Reconcile counts as well as totals, against a third party's
processing where one exists, and assert that every key you group on is unique
before grouping on it. A total that matches shows the values sum correctly; it says
nothing about whether each entity appears once.

**Enforcement.** Yes. `test_utility_panel_key_is_unique_per_year` and
`test_raw_rows_reconcile_to_pudl_expected_counts`.

## 15. Find the observations that cannot vary, before testing anything

**What happened.** Two results published here rested on reports that carried no
measurement. Nearly a third of positive reports set actual exactly equal to
potential, a contract recorded as a delivery, and 67 utilities did it every
year. Those reports produced an apparently steep fall in utilization with program
size, published in v0.4.0, which vanished within every customer class once they
were set aside. And because a report fixed at 1.0 every year adds no variance and
pulls every regional average toward zero, they biased the common-shock test
toward a null, so attack F reported "no regional effect" where removing them
shows one in some specifications.

**The rule.** Before testing variation, find the observations that are fixed by
convention rather than by the world: values equal to a bound, values identical
year after year, a field equal to another field. They contribute nothing to a
test of variation except a bias toward finding none, and they contribute a level
effect to anything that averages them. Test with and without them, and report
both.

**Enforcement.** Yes. `test_t9_copied_reports_bias_the_common_shock_test_toward_null`
pins the mechanism, `test_t9_common_shock_verdict_is_specification_dependent`
keeps the verdict honest, and
`test_t9_size_gradient_vanishes_within_every_class_on_measured_reports` pins the
withdrawal.

## 16. A robust number can still be the wrong number: read the cases

**What happened.** From v0.3.0 to v0.4.2 the README's strongest evidence was that
79% of the capacity ever reported at zero rotated: zero one year, positive
another, read as capacity that was available and not called. When the six
choices behind that statistic were varied 288 ways it held as a majority in 202
of 216 capacity-weighted specifications, which looked like a clean bill of
health. Then the 26 utilities behind it were read one at a time. Most of the
rotating capacity rotated into reports that show nothing about availability: a
program whose enrolled figure fell twentyfold, a report within 0.02% of enrolled
capacity, positive years under 4% of potential. Utilities with a measured
delivery in another year held 15% of it. The grid had tested whether the number
was fragile; nobody had tested whether it measured the claim.

**The rule.** A specification grid answers "would a different analyst get a
different number?" It cannot answer "does this number mean what the sentence
says?" When a statistic summarises a few dozen units, or when a few units carry
most of its weight, list them with what each actually reported, and write down
for each one whether it supports the sentence. Do that before the grid, because
a grid that agrees with itself makes a misread number more convincing, not
less.

**Enforcement.** Partial. `t1_utilization.rotation_composition()` classifies
every case, `test_rotation_mostly_does_not_measure_availability` pins the
classes and the gap between the published number and the measured share, and
`test_classifier_on_a_constructed_panel` checks the classifier on cases built by
hand. Nothing can make someone read the cases of the next statistic.

## 17. Drop clusters, not observations, and see what moves

**What happened.** Zero and unreported capacity was 39% of capacity outside RTO
footprints against 22% inside, and that was read as ruling out wholesale
bookkeeping. Dropping each state in turn showed the gap was mostly Florida,
where four utilities with large load management programs reported zero or
nothing in every year: without Florida the shares were 25% and 22%, and
unreported capacity was more common inside footprints. Utilities in one state
share a regulator, a climate and often a reporting habit, so they are closer to
one observation than several, and a comparison over hundreds of utilities can
rest on one state.

**The rule.** When observations cluster, by state, regulator, parent company or
reporting form, report the result with each cluster dropped in turn and name
the cluster whose removal moves it most. A conclusion that one cluster can
reverse is a statement about that cluster.

**Enforcement.** Yes for this comparison. `t9_mechanisms.footprint_grid()`
jackknifes every specification by state, `test_t9_footprint_result_rests_on_one_state`
pins the result, and `test_t9_footprint_jackknife_matches_a_direct_recomputation`
checks the vectorised jackknife against dropping the state and recomputing.

## 18. Read the form's definition of the number, then check the reports against it

**What happened.** Through v0.4.3 this repository described EIA's actual peak
demand savings as the reduction realised during the year, and every
interpretation was built on that. The form's instructions say something
narrower: the reduction "measured at the time of the company's annual system
peak hour", against a potential defined in the same hour. The instructions had
been read once, for whether an event count is collected, and not for what the
numerator is. Read for the definition, they also made the reports checkable.
Savings in the peak hour cannot exceed the load in that hour, and the same form
asks each utility for its peak: 18 utility-years report more potential than
that. The file holding those peaks had been sitting beside the demand response
workbook in the same mirrored directory since the first utility file was found.

**The rule.** Before interpreting a reported quantity, find the instruction that
defines it and quote it, not paraphrase it. Then check the reports against
whatever else the same respondent reports on the same form, because a
respondent's own figures are the one comparison no definitional mismatch
between reporters can explain away. And when a source is found, list what else
sits beside it before leaving.

**Enforcement.** Partly. The definitions are held verbatim in
`phantomload/shared/eia861.py` and `test_definition_is_quoted_from_the_form`
fails if the single-hour wording leaves the code or DATA.md;
`test_t10_impossible_potential_rule_on_a_constructed_utility` pins the
consistency rule. Reading the instruction in the first place is not enforceable.

---

## What is not on this list

Rules that sound good and did nothing here. Precision about uncertainty
intervals never mattered, because sampling variability was never the binding
uncertainty: reporting practice, accounting basis and identification were. More
tests never caught anything a first well-chosen test missed. And until v0.4.3
every significant correction in this repository came from finding a second
source or a second definition, never from analysing the first one harder. The
two corrections in v0.4.3 broke that pattern, and both came from the same move:
reading the first source's cases one at a time (rules 16 and 17). The v0.5.0
correction came from a third move, reading the source's own instructions for
what its numbers mean (rule 18).

One operational rule that belongs in the same spirit. `verify.sh` built its
virtual environment in a temp directory and never removed it, leaking about
400 MB per run until the disk filled and builds started failing with I/O errors
that looked like anything but a full disk. Clean up after yourself in the script
that runs most often.
