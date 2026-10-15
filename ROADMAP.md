# Research agenda

What is open, how much of the answer each question carries, and exactly where to
start. Ordered by how much a result would change what this repository can say.

The organising fact is the decomposition in FINDINGS section 11: the unrealised
gap is three components with different mechanisms. Each question below is tagged
with the component it addresses and its share of the gap in 2018.

| Component | Share of enrolled capacity, 2018 | Status |
| --- | --- | --- |
| Partial delivery | 34% | open: a regional component in some specifications, no response to each utility's own peak |
| No actual reported | 15% | mostly explained: 73% of it is at utilities reporting an exact zero in another year |
| Exact zero | 10% | partly explained: non-dispatch in the peak hour, with a measured delivery elsewhere for 15% of it |

Underneath all three is a question v0.5.0 opened: the form measures the
delivered figure in one hour, the company's annual system peak hour, and the
reports show no sign of tracking that hour (FINDINGS section 12). Item 1 below
now carries it.

---

## 1. Does partial delivery respond to system conditions? *Partial delivery, half the gap.*

The most important open question. Whether utilization moves with regional
conditions depends on two analyst choices, which reports to include and how many
utilities a footprint needs: across nine specifications the regional share beats
chance in all nine and is significant in three (`t9_mechanisms.specification_grid()`).
Excluding reports where actual simply equals potential tilts it toward a regional,
dispatch-driven component. Against each utility's own peak it points the other
way: no response to the size of the peak, to the January 2018 cold, or to a
change of peak season (`t10_reporting.timing_summary()`). Three explanations fit
and they have opposite implications:

- **Definition.** Potential is a fixed multiple of what the program ever
  delivers, for example a contracted maximum against a typical event. Benign; a
  reporting artefact.
- **Protocol.** The program is always dispatched at a fixed share of enrolment,
  for example cycling a rotating subset of devices. Benign; a design choice.
- **Response.** The same customers fail to respond every time. This is the
  phantom reading, confined to this component.

**What separates them.** Event-level evaluations, which report devices enrolled,
devices dispatched and devices responding for each event. Definition predicts
full response to a partial call against an inflated base; protocol predicts
partial dispatch with full response; response predicts full dispatch with
partial response.

**Where to look.** CALMAC, state commission evaluation archives, and DOE's
Uniform Methods Project protocols. Ten programs would be enough to start. The
most useful single fact per program is how its EIA actual figure was
determined: in the peak hour, as the form asks, or as an event maximum or
average. The 59 utilities the January 2018 cold pushed to new winter peaks are
the place to ask first (`t10_reporting.january_2018_event()`).

**Entry point.** `phantomload/tracks/t9_mechanisms.py`, function
`partial_delivery_panel()`, which identifies the utilities to look for.

**What would change.** A finding of consistent partial response would make part
of the phantom reading true for the largest component, and the README's answer
would have to change in place.

## 2. Who records a contract as a delivery, and why? *Reporting.*

30% of positive reports set actual exactly equal to potential, 55% among the
smallest programs, and 67 utilities do it every year. That convention produced a
size gradient this repository published and withdrew. Whether those utilities
meter response, count devices or simply restate the contract quantity is
answerable from their filings, and the answer decides how much of the national
realised figure is measured at all.

**Entry point.** `t9_mechanisms.exact_equality()`, which lists the utilities.
Metering explains part of it and not most: copying runs at 37% of positive
reports where interval meters are almost absent and 25% where they are nearly
universal (`t10_reporting.copy_vs_metering()`). The filings are what is left.

## 3. What is the unreported group? *No actual reported, a quarter of the gap.*

Utilities reporting potential but no actual hold 15% to 17% of capacity every
year. It looked concentrated outside RTO footprints, which was read as ruling
out wholesale bookkeeping; without Florida it is more common inside, so that
reading is withdrawn (FALSIFICATION attack E).

**Mostly answered in v0.5.0.** Small utilities exempt from the field are ruled
out: short-form filers report no demand response quantities and none appears in
the file. The count this item asked for was run: 73% of the capacity ever left
blank belongs to utilities that report an exact zero in another year, and 31
utility-state units switch between the two. For them a blank is the zero mass
under another label (`t10_reporting.unreported_summary()`). What is left is the
13% that is blank in every year, and the 35% at utilities that report a positive
figure elsewhere, whose blank years are unexplained.

**Entry point.** `t10_reporting.unreported()`, which lists every unit with what
it reported in its other years.

## 4. Was the zero mass available? *Exact zero, a sixth of the gap.*

Exact zeros read as non-dispatch. Whether the capacity would have delivered is
shown for 15% of it, the share held by utilities with a measured delivery in
another year, and is undetermined for the rest (FALSIFICATION attack G). Three
tests would move that number, each scoped to a named place:

- **Florida.** The proposed mechanism, from ACEEE in 2017, is that utilities
  long on capacity do not call demand response. Florida is where it would show,
  since four Florida utilities hold most of the zero and unreported capacity
  outside RTO footprints, and the Public Service Commission describes FPL's
  residential program as used in system emergencies. The Commission's annual
  FEECA report describes the programs but not whether they were called; the
  utilities' own demand-side management filings and ten-year site plans are
  where event records may be. Two facts so far: FPL says it activates its
  residential program a few times a year at most, and the Florida reliability
  council told the Commission that no energy emergency was declared in 2016.
  Neither says whether any activation covered an annual peak hour.
- **South Carolina, January 2018. Answered for Santee Cooper.** Its 2018 annual
  peak was a winter peak set in the January cold, 4.3% above its earlier
  maximum, and its one positive report is in that year (FINDINGS section 1).
  What remains is whether the 2018 figure is a measurement: Santee Cooper's
  curtailment records for January 2018 would say. EIA-930 hourly demand would
  date the peak hour; the form only gives the season.
- **Reserve margins.** Pair each utility's zero years with its reserve margin,
  which state integrated resource plans and FERC Form 1 report.

**Entry point.** `t1_utilization.rotation_composition()` lists every utility
behind the zero mass with its class; `t1_utilization.zero_followup()` names the
utilities and the state carrying each year's follow-up.

## 5. More years. *All components.*

Every utility-level result rests on 2016 to 2018, the minimum for a persistence
test and too short to separate a weather cycle from a trend. More years would
also give track 10's timing tests more than one winter event to work with.

**The route.** Catalyst Cooperative's PUDL archives the raw EIA-861 release for
every year from 1990 to 2025 on Zenodo (record 10.5281/zenodo.4127028, per-year
zips of 1 to 5 MB) and publishes a cleaned demand response table,
`core_eia861__yearly_demand_response`, for 2013 onward, also as Parquet in its
public S3 bucket. Neither Zenodo nor the bucket is reachable from the
environment this was built in; from anywhere else either is a download. A search
for the file names turned up no other vendored copies, and the one mirror found
holds only 2016 to 2018.

**The traps, from PUDL's own column maps,** which anyone extending the panel will
hit:

- 2013 to 2016 carry no balancing-authority column. A utility reporting under
  two authorities in one state, as Wabash Valley Power does in Indiana, appears
  as two indistinguishable rows. `utility_panel()` sums them into one entity.
- 2019 adds a short-form flag and shifts the balancing-authority column by one.
  From 2019 EIA folded short-form respondents into the main tables, so a panel
  that crosses 2019 has a definitional break in who is included.
- Utility-state rows fall from about 450 in 2019 to about 330 by 2021. Whether
  that is fewer programs or the reporting change is a question in itself.

**Check new years against.** PUDL's expected row counts, four per utility and
state, which this repository's parse already matches for 2017 and 2018 and
misses in 2016 by exactly the Wabash pair; and the national panel, which every
year must reconcile to within the published table's rounding.

**Entry point.** `tools/build_eia861_utility.py` and
`tools/build_eia861_context.py`, constant `YEARS`, plus a column map for 2019
onward.

## 6. The price in the hours demand response is called. *Cost comparison.*

The cost comparison terminates on the value of avoided energy in called hours,
which is bounded here and not measured. Hourly PJM LMP from Data Miner, paired
with the net-load ranking track 4 already computes, would measure it. Two
independent routes in this repository put the implied premium near 2.5 times an
average hour against the roughly 8.5 times the strictest comparison needs; a
measured figure would settle it.

**Entry point.** `t2_cost.netting_bound()`, parameter `ENERGY_VALUE`.

## 7. Winter callability of retail programs. *Cross-cutting.*

The firmest result here is that summer-shaped programs cannot reach winter
stress, reached three independent ways, two of them firmly and the accreditation
route by a margin of 3.5%. A fourth, the January 2018 cold in the utility files,
says nothing either way: utilization at the utilities it pushed to new peaks did
not change. PJM's wholesale market already requires
year-round availability. What is missing is the retail side: what share of
utility-administered programs can be called in January. Utility tariff sheets
carry it.

**Entry point.** `t4_curtailment.winter_shoulder()`.

## 8. The retail-wholesale overlap. *Scope.*

Both populations are measured, about 30 GW retail and 33 GW wholesale, and no
published source estimates the intersection. Matching EIA respondents to RTO
registration lists would. Until then no defensible national total for demand
response capacity exists.

## 9. The DLC denominator. *Modeled results.*

One evaluation reporting both kW per controlled device and devices per enrolled
customer would move track 3's modeled reconciliation into the citable findings.
The other side of it is now measured: utilities whose residential enrolment is
almost all direct load control deliver 0.94 kW per enrolled customer
(`t3_behavioral.kw_by_dlc_share()`).

**Entry point.** `calibration.DEVICES_PER_ENROLLED_CUSTOMER`.

## 10. A literature review

Four ad hoc searches and one commissioned systematic search each changed
something material, recorded in PRIOR_WORK.md. The claims most exposed to
literature not yet read: that no published source decomposes the EIA gap into
uncalled and absent capacity, and that the accounting-basis asymmetry in demand
response cost comparisons has not been named. The DOE Uniform Methods Project and
the resource adequacy accreditation literature are where a correction would come
from.

---

## Before pushing

Housekeeping that cannot be done from the environment this was built in, since
there are no git credentials here. The repo is committed and tagged locally.

- [ ] Decide the name before creating the remote. "Phantom load" already means
      standby draw in this field, an exact-name repository exists on GitHub, and
      the name claims more than the findings support. `tools/rename.sh` does the
      whole rename in one command and re-runs the tests and the claims guard.
      `dispatchgap` is free on PyPI and under ASM-21 and names the measurement
      without presuming its meaning. `benchstrength`, also free, presumes the
      capacity was available, which v0.4.3 no longer supports. `dr-realization`,
      recommended earlier, would have named the wrong quantity and is
      withdrawn. Renaming after publication costs far more than renaming now.
- [ ] Create the remote and push, including the version tags.
- [ ] Add `[project.urls]` to `pyproject.toml` and `repository-code` to
      `CITATION.cff` once the remote exists. Both were left out rather than
      shipped with a URL that does not resolve.
- [ ] Set repo topics: `demand-response`, `grid-reliability`,
      `utility-economics`, `capacity-market`.
- [ ] Set the social preview to `figures/fig1_utilization.png`.
- [ ] Run `python tools/check_source.py` once from an unblocked network. It has
      never been exercised against the live page, only against a fixture, so
      confirm by hand that it parses rather than skipping.
