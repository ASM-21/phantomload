# Prior work

This file exists because the repository spent most of its life without one, and
that was its largest weakness. What follows is not a literature review. It is an
honest record of what turned up when the question "has someone already done
this?" was finally asked properly, plus what is still unsearched.

## Nadel, ACEEE, February 2017

**The finding.** Steven Nadel analysed the 2015 Form EIA-861 demand response
file at utility level, taking every utility reporting at least 200 MW of
potential peak demand savings, 28 in total, covering 64% of national potential
and 58% of national actual reductions.

**It anticipates this repository's central question and most of track 1.** Nadel
reported that potential savings averaged 10% of utility peak while actual
savings averaged 4%, an implied dispatch utilization around 40%. The national
dispatch utilization this repository leads with, 39.2% averaged over 2013 to 2024,
is therefore a reproduction of a figure published nine years earlier, not a
discovery. It should be read that way.

**It also states the identification problem, in one sentence.** "Actual savings
address the fact that many utilities did not activate all demand response
capability in 2015." The uncalled-versus-absent distinction that track 1 spends
a closed-form identification argument on was named plainly in 2017, and Nadel
went further, proposing the mechanism: "utilities that are long on capacity are
probably less likely to call much of their available demand response resource."
He listed understanding why some utilities use their resource and others do not
as the open question.

**It corroborates attack D from an independent direction.** Nadel warned that
the EIA data "may contain errors", and reported deleting utilities where "a few
utilities reported demand response savings in excess of their peak demand". Track
8's finding that mix-adjusted reporting intensity varies fivefold across census
divisions is a regional-aggregate version of a data quality problem that was
already visible at utility level as outright impossible values.

**And it supplied data this repository had been calling unavailable.** The
appendix table is now vendored as `data/aceee_dr_utilities_2015.csv` and drives
the utility-level dispersion and zero-mass results in track 1. Roadmap item 1
asked whether a national 40% means everyone at 40% or half the fleet at zero.
Nadel's table answers it for the largest programs in one year, and the answer is
closer to the second. Five of twenty-five reported exactly zero.

**What this repository adds on top, which is less than it looked like.** The
distributional test that reads the point mass at zero as evidence for the
uncalled mechanism. The closed-form window length needed to reject a reserve
hypothesis, and its degradation under persistence. The accounting-basis
enumeration against published PJM cost of new entry. The scarcity-versus-
oversupply targeting asymmetry. None of those appear in Nadel's post. Whether
they appear elsewhere is unknown, because of what follows.

## The demand response evaluation literature

Searched second, and it closed a live parameter rather than only supplying a
citation.

Track 3 needed peak reduction per participating customer under direct load
control, and had been using an assumed 0.5 to 1.5 kW with a central value of
1.0. The evaluation record says otherwise:

- Newsham and Bowker's review of North American air conditioner control
  programs: 0.3 to 1.2 kW per AC unit.
- SDG&E Summer Saver, 2011 ex post load impact evaluation: 0.41 kW per AC unit
  under one-in-two year weather, 0.48 under one-in-ten.
- CenterPoint Energy, 2025 demand response impact evaluation: 0.59 kW per
  thermostat averaged across a two-hour event, with measured precooling and
  rebound either side of it.
- Newsham et al. on Ontario Peaksaver 2008: 0.2 to 0.9 kW per household across
  four analysis methods, with a wide spread between households and only a
  minority contributing to any given event.

The measured central value is about half what this repository assumed, so the
parameter moved from ASSUMPTION to LITERATURE and the range from 0.5-1.5 to
0.2-1.2. The Ontario contribution-heterogeneity finding also widened the
response-rate floor.

That created a tension rather than resolving one, which is written up in
FINDINGS section 3: at central evaluation values a fully controlled residential
fleet delivers less per enrolled customer than EIA reports. The most likely
explanation is a units mismatch, since evaluations count AC units, thermostats
or households while EIA counts customers. Noticing it required reading the
literature, which is the point of this file.

## The resource adequacy and accreditation literature

Searched third, and it scoped the capstone harder than anything else here has
been scoped.

**The asymmetry the synthesis identified is a named, litigated problem.** A 2026
arXiv survey of distributed energy resources in resource adequacy states it
directly: supply-side accreditation is increasingly tied to reliability metrics
such as effective load carrying capability, implemented through
technology-specific derating curves and seasonal factors, while load-modifying
resources are accredited from measured reductions against a counterfactual
baseline. Two sides of one comparison, two different methods. That is the whole
content of `synthesis.py`, and it was not discovered here.

FERC Commissioner Clements wrote a 2023 concurrence on SPP's ELCC accreditation
proposal arguing that an installed-capacity method which "accounts only for
performance in a set test and does not capture historical outages" is the
relevant point of comparison when judging whether an accreditation proposal
discriminates against demand response. A sitting regulator making the
accreditation-basis argument about demand response specifically, three years
before this repository made it.

**And the field's own method gives a materially different answer.** E3's October
2025 white paper accredits SPP demand response by ELCC and finds that at 2025
adoption a four-hour curtailment program earns about 83% in summer and 55% in
winter, while a ten-hour program reaches about 100% and 82%. Four-hour ELCC
falls from about 83% at 2 GW of adoption to about 50% at 6 GW.

That matters because this repository had been haircutting demand response by its
dispatch utilization, about 39%, and treating that as an accreditation factor. It
is not one. ELCC asks what share of enrolled capacity is dependable during
critical hours; the dispatch utilization also counts the years in which nothing was
called. Accrediting demand response the way the field does rather than the way
this repo invented moves its cost from $128.78 to $60.71 per accredited kW-year,
a factor of 2.12, and it wins 5 of 6 cells instead of losing on the strict
pairing.

**The one cell it still loses is the winter four-hour case**, which is track 4's
seasonal finding arriving by a third independent route: hourly generation data,
PJM's market rules and the scarcity of winter-capable bids, and now the
accreditation literature's own metric. It arrives narrowly, losing by 3.5% at
E3's 55%. Until v0.4.3 the repository used 50% for this cell under the winter
label; 50% is E3's four-hour figure at 6 GW of adoption, so the label and the
value disagreed and the loss looked larger than the source supports.

## The rare-event statistics literature

Searched fourth. The result was the flattest of the four and the most useful to
know: track 1's identification bound is a textbook result from 1983.

Hanley and Lippman-Hand, "If nothing goes wrong, is everything all right?
Interpreting zero numerators", JAMA 1983, set out the **rule of three**:
observing zero events in n trials puts the 95% upper confidence bound on the
event rate at about 3/n. The exact form solves (1 - p)^n = alpha for n, which is
character for character the closed form in `t1_utilization.min_window`, reached
here by deriving it rather than by reading it. The textbook approximation, 3T
years for a one-in-T-year resource, sits one year above the exact answer at
every return period this repo reports: 30 against 29 at T = 10, 60 against 59 at
T = 20.

Eypasch and colleagues gave the clinical version in the BMJ in 1995, and Tuyl
reviewed the variants and extensions in the International Statistical Review in
2009. The rule has been extended to small non-zero numerators, which is the
version this repository would actually want, since utilities report near-zero
rather than exactly zero.

So the honest statement is that track 1 applies a standard result to demand
response reserve identification. The application looks new; the statistic is
forty-three years old and taught in introductory courses. The Markov extension
for persistent extreme conditions relaxes the rule's independence assumption,
which is the kind of thing that also has a literature this repository has not
read.

## The systematic search, and what it changed

A commissioned search across eight questions followed the four ad hoc ones. It
confirmed some things, killed a terminology error, resolved a contradiction, and
produced one independent estimate this repository could not have reached alone.

**It killed a term.** Drafts called the actual-over-potential ratio a
*realization rate*. In evaluation practice that term means evaluated savings
over *claimed* savings for a program that was dispatched, and it measures
measurement error. The ratio here measures dispatch behaviour instead, and no
established term for it was found, so it is now **dispatch utilization**,
defined in the README. A program can post a realization rate of 1.0 and a
dispatch utilization of 0.0 in one year.

**It resolved the units contradiction.** Track 3 had reported that measured
delivery per enrolled customer exceeds what a fully controlled fleet should
produce. The search confirmed the cause: evaluations report per AC unit, per
thermostat or per participating home, and EIA counts customers, with saturation
pushing the ratio one way and multi-device households the other. Neither source
publishes the bridge. Solving for the device count that reconciles them gives a
value inside any plausible range, so the contradiction dissolves into a
denominator mismatch rather than a finding. The number itself depends on an
assumed response rate and is therefore recorded in MODELED.md rather than here. The search also
supplied a benchmark: a mass-market residential program reporting much above
1 kW per enrolled customer has almost certainly mixed a per-device numerator
into a per-customer denominator. This one reports 0.45, which is weak evidence
that EIA's denominator is genuinely per customer.

**It gave the netting bound an independent check, and the check disagreed
usefully.** Brattle performed exactly this netting for energy efficiency in
2021: gross CONE of $235 per kW-ICAP-year less $177 of energy savings and $35 of
transmission and distribution savings, giving an efficiency net CONE of $23.
Energy efficiency saves energy in all 8,760 hours; demand response in roughly 94.
If both credits are right, the ratio between them should track the ratio of
hours. It does not: the hours ratio is 94 and the credit ratio is 37, and the
leftover factor of 2.5 is an independent estimate of the premium demand
response's called hours carry over an average hour. The synthesis needs 8.5.
So a second route reaches the same conclusion as the first, and the shortfall is
a factor of five.

**It put a number on how implausible the strong-targeting case is.** PJM's
market monitor reports that of the $2.66 per MWh increase in the 2024
load-weighted average LMP, $0.10 was the scarcity component. A year with almost
no scarcity pricing cannot deliver avoided energy at many times the average, so
the $430 per MWh figure is a strong-targeting scenario and not a base case, and
the docs now say so.

**It named the persistence correction.** The Markov adjustment in track 1 is an
effective-sample-size correction in the sense of Kish's design effect, with the
AR(1) effective size n(1-rho)/(1+rho) as the standard form. No published source
states the dependence-corrected rule of three for the zero-event case, but the
components are all standard, and the power-system literature reaches the same
problem from the other side: Wilson and Zachary estimate loss-of-load from seven
winter seasons with autocorrelation and report a 95% interval of 1.92 to 9.37
hours against a mean of 5.08, block-bootstrapping seasons rather than assuming
independence. Dent and Zachary find two thirds of calculated loss-of-load
arising from six days.

**What it did not find.** No published decomposition of the EIA gap into
uncalled versus absent capacity, and no use of the utility-level point mass at
zero as evidence for either. No prior naming of the accounting-basis asymmetry
in demand response cost comparisons, though the ingredients are in Brattle and
in the distributed-resource accreditation literature. No quantified estimate of
the retail-wholesale overlap, only qualitative warnings and the rules written to
prevent double registration. Those three remain this repository's contribution,
stated as "no prior published treatment located" rather than as "does not
exist", which is the honest form.

The first of them needs a qualification the search could not supply. The search
described the zero-mass decomposition as this repository then stated it, with
most of the zero mass shown to be available. v0.4.3 withdrew that: the point
mass identifies non-dispatch, and availability is shown for 15% of the capacity
ever reported at exactly zero. What is new is the decomposition and the
classification, including how little of the gap they can identify, not an
answer to the uncalled-versus-absent question.

## Specification grids and influential clusters

Searched after the v0.4.3 re-examination, to name what this repository had been
doing. Running every reasonable combination of analyst choices and reporting
the distribution rather than one result is a specification curve in the sense
of Simonsohn, Simmons and Nelson ("Specification curve analysis", *Nature Human
Behaviour* 4, 1208 to 1214, 2020), and a multiverse analysis in the sense of
Steegen, Tuerlinckx, Gelman and Vanpaemel ("Increasing transparency through a
multiverse analysis", *Perspectives on Psychological Science* 11(5), 2016). Both
present it as protection against selective reporting. Neither presents it as
protection against a statistic that measures the wrong thing, which is what the
rotation grid ran into: 202 of 216 capacity-weighted specifications agreed, and
the agreement was about a number whose meaning failed when the cases behind it
were read (METHOD rule 16).

Dropping each state in turn is the leave-one-cluster-out diagnostic that
MacKinnon, Nielsen and Webb recommend reporting whenever a few clusters may
dominate an estimate ("Cluster-robust inference: a guide to empirical
practice", arXiv:2205.03285, 2022). Their setting is regression standard
errors; the logic carries over unchanged to a ratio of shares, and here it
found that one state carried the footprint result (METHOD rule 17).

## Corrections are invited

The claims most likely to be wrong because of literature this repository has not
read, in order: that no published source decomposes the EIA gap into uncalled and
absent capacity; that the accounting-basis asymmetry in demand response cost
comparisons has not been named; and that no estimate of the retail-wholesale
overlap exists. Each is stated as "no prior published treatment located", which
is a report on a search, not a fact about the world. Anyone who knows a source
that addresses one of them should open an issue citing it, and the claim will be
rescoped in place.

## What is still unsearched

The searches above reached government and market monitor reports, evaluation
archives, preprints and open-access papers. They did not reach paywalled
journals except through abstracts. Three gaps are worth naming, in descending
order of how likely they are to change something here:

1. **Peer-reviewed resource adequacy work on accreditation asymmetries.** The
   synthesis rests on the accounting-basis asymmetry not having been named in a
   cost comparison. Journal work on demand-side accreditation is the likeliest
   place for that claim to be wrong.
2. **Survey methodology and administrative data quality.** The mix-adjusted
   index in attack D is a shift-share construction under another name, and the
   copied-report convention and the zero-or-blank switching in section 11 are
   item-response problems that survey statisticians have vocabulary for.
3. **Utility filings to state commissions.** Not a literature, but the place
   the answers live. Event counts, dispatch logs and evaluation reports for the
   programs named in FINDINGS sections 1 and 11, starting with Florida's four
   load management utilities and Santee Cooper's 2018 interruptible curtailment,
   would settle questions no amount of reading can.

Until a journal search happens, nothing here should be presented as novel
without the "no prior published treatment located" qualifier. It should be
presented as computed, checked and reproducible, which it is.

## The lesson worth carrying

The prior work was one search away and the repository ran for its entire life
without making it. The search that found it was not clever: "has anyone compared
EIA-861 potential against actual demand response savings". Everything in
`METHOD.md` about naming the sources you checked applies with more force to the
literature than to the data, because a dataset that does not exist leaves a gap
you notice, while prior work that you have not read leaves nothing at all.
