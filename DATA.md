# Data

Seven sources. All are vendored in `data/` so the repo runs offline, and all
are re-derivable from the scripts in `tools/`. A test asserts that every CSV
under `data/` is named in this file, so a dataset cannot arrive without
provenance.

## 1. EIA-861 demand response aggregates

`data/eia861_dr_national.csv`, 340 rows, long format: year, sector, metric,
value, note.

| | |
| --- | --- |
| Source | U.S. Energy Information Administration, Form EIA-861, "Annual Electric Power Industry Report", published in Electric Power Annual |
| Tables | 10.3 (savings, 2015-2024), 10.8 (savings, 2013-2014 rows), 10.4 (program costs, 2015-2024) |
| URLs | `eia.gov/electricity/annual/html/epa_10_03.html`, `epa_10_08.html`, `epa_10_04.html` |
| Coverage | 2013-2024, four sectors plus published total, national |
| Retrieved | 2026-09-04 |
| Licence | US Government work, not subject to domestic copyright |

Metrics: `customers_enrolled`, `energy_savings_mwh`, `potential_peak_mw`,
`actual_peak_mw`, `customer_incentives_kusd`, `other_costs_kusd`.

Definitions matter here more than usual:

- **Potential peak demand savings** is the peak reduction the reporting utility
  says its DR programs are able to deliver. It is self-reported and unaudited.
  This repo calls it enrolled capacity.
- **Actual peak demand savings** is the reduction actually realised that year.
  This repo calls it delivered capacity.
- A program not called in a given year contributes its full potential and zero
  actual. That single fact is why track 1 exists.

Regenerate with `python tools/build_eia861_panel.py`, and check the vendored
copy against the live tables with `python tools/check_source.py`, which fails
only on a real mismatch and skips when eia.gov is unreachable. That matters
because EIA revises prior-year values in later vintages and a vendored copy has
no way to notice on its own. The literal published
values live in that script, so a diff against a future EIA vintage shows up as
a source-code diff rather than a silent data change.

Known quirks, all pinned by tests:

- Sector values differ from EIA's own printed totals by up to 8 units in a few
  cells, consistent with rounding in EIA's aggregation. The ingest test allows
  10 absolute or 1e-5 relative and fails on anything larger.
- Program cost rows do not exist before 2015, so cost tracks run 2015-2024 while
  utilization runs 2013-2024. Blanks stay blank rather than becoming zeros.
- The transportation sector drops out of the table in most years. Blank, not
  zero.
- EIA flags a reclassification in the 2023 filings that cut reported energy
  savings sharply. Track 7 is about that break; it is carried in the `note`
  column rather than smoothed away.

## 2. PJM cost of new entry

`data/pjm_cone.csv`, 30 rows: fifteen locations by two delivery years.

| | |
| --- | --- |
| Source | PJM Interconnection, "2027/2028 RPM Base Residual Auction Planning Period Parameters", August 26 2025, Table 3 |
| URL | `pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2027-2028/2027-2028-planning-period-parameters-for-base-residual-auction-pdf.pdf` |
| Coverage | PJM RTO and fifteen modelled LDAs, 2026/2027 and 2027/2028 Base Residual Auctions |
| Retrieved | 2026-09-05 |
| Licence | PJM publishes these parameters for public use; the table is factual auction data |

Columns: gross CONE, energy and ancillary services offset, and net CONE, all in
ICAP dollars per MW-year, plus PJM's net CONE in UCAP dollars per MW-day.

Regenerate with `python tools/build_pjm_cone.py`. Two guards, both tested:

- Gross minus offset must equal net in every row, within PJM's own rounding of
  one dollar. That catches a mistyped digit anywhere in the transcription.
- The implied ICAP-to-UCAP factor is not constant across the two auction
  columns: 78.00% in 2026/2027, the reference resource AUCAP factor, and 77.20%
  in 2027/2028, the pool-wide accredited factor rather than the 77.00%
  reference-resource figure quoted a page earlier in the same document. Anyone
  converting with a single factor is off by about 1%.

The analysis works in ICAP dollars per kW-year, since that is directly
comparable to the EIA cost columns. A UCAP comparison would require accrediting
demand response on PJM's basis too, which is a different exercise from
converting one side of a ratio.

## 3. PJM average energy price

`data/pjm_lmp.csv`, 3 rows.

| | |
| --- | --- |
| Source | Monitoring Analytics, PJM independent market monitor: 2024 State of the Market Report press briefing (2023 and 2024), and the Members Committee market monitor report of 22 January 2026 (2025) |
| Coverage | real-time load-weighted average LMP, PJM footprint, 2023-2025 |
| Retrieved | 2026-09-10 |
| Licence | published market monitoring reports, factual price series |

Used for exactly one thing: converting a required avoided-energy price into a
multiple of the average price, so a reader can judge it. It is an annual average
across all 8,760 hours, while demand response is called in roughly the top one
percent, where price is higher by a factor this repo does not measure. Every
point of use says so, and the loader's docstring warns against using it as the
price of avoided energy.

## 4. FERC regional and wholesale demand response tables

`data/ferc_dr_regional.csv`, 90 rows, and `data/rto_dr.csv`, 16 rows.

| | |
| --- | --- |
| Source | Federal Energy Regulatory Commission, "2025 Assessment of Demand Response and Advanced Metering", Staff Report, December 2025, tables 3-1, 3-2, 3-3, 5-1 and 5-2 |
| URL | `ferc.gov/sites/default/files/2025-12/25_Annual Assessment of Demand Response_1212.pdf` |
| Coverage | nine census divisions 2022-2023, seven RTOs and ISOs 2023-2024 |
| Retrieved | 2026-09-05 |
| Licence | US Government work, not subject to domestic copyright |

`ferc_dr_regional.csv` is FERC staff's regional aggregation of the same EIA-861
demand response files as the national panel, so it doubles as a cross-source
check: a test asserts that FERC's division sums reproduce EIA's published
national class totals, which they do to within rounding. Finding that two
agencies' independently typed aggregations of one survey agree is the strongest
guard on the transcription in this repo.

`rto_dr.csv` is a different population, compiled by FERC from the RTOs' and
ISOs' own annual reports rather than from EIA. It counts wholesale market
registrations. Track 7 covers what that does and does not let you conclude; the
short version is that the two totals must not be added.

Caveats FERC states and this repo carries: Commission staff has not
independently verified the accuracy of EIA data, and a utility operating across
several states is assigned to the census division of the state it reports in, so
regional attribution is approximate at the margin.

Narrative figures from the same report, the June 2025 PJM deployment and the two
enforcement actions, live in `phantomload/shared/ferc.py` as constants rather
than in a CSV, because they are single facts rather than a series.

## 5. ACEEE utility-level demand response, 2015

`data/aceee_dr_utilities_2015.csv`, 28 rows.

| | |
| --- | --- |
| Source | Steven Nadel, ACEEE, 9 February 2017, data appendix to "Demand response programs can reduce utilities' peak demand an average of 10%" |
| Underlying data | 2015 Form EIA-861 demand response file, aggregated by ACEEE |
| Coverage | every utility reporting at least 200 MW of potential peak savings, 63% of national potential |
| Retrieved | 2026-09-11 |
| Licence | published research note and its data appendix |

The only utility-level data in the repository, and the reason track 1 can say
anything about the shape of the distribution rather than only its level. Its
all-utility footer row reproduces the vendored national panel for 2015 exactly,
which a test asserts: a third independent source agreeing on the transcription.

Two handling rules, both tested. Three utilities reported potential with no
actual value; those are blank, never zero, because "did not report" and "called
nothing" are precisely the distinction under examination. And Duke Energy
Carolinas appears twice, once per state, against the same system peak; rows are
kept as published.

ACEEE's own caveat is carried: the data are self-reported and unaudited, and
ACEEE removed some utilities whose reported savings exceeded their own peak
demand.

## 6. EIA-861 utility-level demand response, 2016 to 2018

`data/eia861_dr_utility_2016_2018.csv`, 1,278 rows, one per utility per state per
year.

| | |
| --- | --- |
| Source | Form EIA-861 detailed data files, `Demand_Response_<year>.xlsx`, sheet "Demand Response_States" |
| Reached via | `IMMM-SFA/electricity_entity_boundaries` on GitHub, which bundles the raw EIA-861 files unmodified as inputs to a county-mapping workflow |
| Coverage | every utility reporting demand response, 2016, 2017, 2018 |
| Retrieved | 2026-09-20 |
| Licence | EIA content is a US Government work; the bundling repository is BSD 2-Clause for its own code |

The most important dataset in the repository and the hardest to find. eia.gov was
blocked and re-tested blocked on the retrieval date. The files were found by
searching for the file name rather than the subject, because the repository that
holds them is about mapping utilities to counties and no search for demand
response would ever surface it.

Integrity: potential and actual peak savings summed across utilities reproduce
the vendored national panel exactly in every year, the fourth independent source
agreeing on the same series and the first at utility grain. A test asserts it.

Handling, tested: "." becomes blank, never zero, because a utility that reported
no actual figure and a utility that reported zero actual are the two categories
the central result depends on. A utility reporting in several states appears
once per state, keyed on utility number plus state.

Regenerate with `python tools/build_eia861_utility.py <path-to-EIA_861_Dataset>`.

Two more checks, both tested. Raw row counts match PUDL's independently
published expected counts for 2017 and 2018, and exceed them in 2016 by exactly
one pair: Wabash Valley Power, which reports in Indiana under both PJM and MISO
and, before EIA added the balancing-authority column, appears as two identical
looking rows. The analysis treats one utility within one state as one entity,
summed across balancing authorities, so the key it groups on is unique.

For other years see ROADMAP item 5: PUDL archives every release on Zenodo, which
was not reachable here.

## 7. CarbonCast hourly generation by fuel

`data/carboncast/CISO_direct_emissions.csv`,
`data/carboncast/ERCO_direct_emissions.csv` and
`data/carboncast/PJM_direct_emissions.csv`, 17,544 hourly rows each.

| | |
| --- | --- |
| Source | carbonfirst/CarbonCast on GitHub, `data/<REGION>/<REGION>_direct_emissions.csv` |
| Upstream data | EIA hourly grid monitor, via CarbonCast's cleaning pipeline |
| Coverage | 2020-01-01 to 2021-12-31, UTC hourly, generation by fuel |
| Licence | Apache-2.0, text in `data/carboncast/LICENSE-Apache-2.0.md` and attribution in `NOTICE` |

Used only by track 4, and only for the timing of high renewable share hours.
Columns consumed: `UTC time`, `solar`, `wind`, and the fuel columns that make up
total generation. Local time conversion uses IANA zones, so `tzdata` is a
dependency on systems that do not ship it.

Refresh:

```bash
curl -sSL https://raw.githubusercontent.com/carbonfirst/CarbonCast/main/data/CISO/CISO_direct_emissions.csv \
  -o data/carboncast/CISO_direct_emissions.csv
```

## What is not here, and why

Each absence below names the sources actually checked, so the claim is
falsifiable by anyone who knows a source this repo missed. That convention comes
from FALSIFICATION.md: two withdrawn claims in this repo were both negative
claims about what public data contains, made without saying where anyone had
looked.

- **Program-level or utility-level demand response records.** Checked: EIA
  Electric Power Annual chapter 10 HTML tables (national and by sector only);
  FERC's 2025 assessment tables 3-1, 3-2, 5-1 and 5-2 (census division, and
  potential peak savings but not actual). EIA-861 detailed files carry state,
  sector and balancing-authority splits including actual peak savings, but they
  are distributed as bulk ZIPs from eia.gov, which was blocked in the
  environment this was built in. Not checked: state commission filings, which
  would have it utility by utility.

- **Event-level dispatch logs.** Checked: the EIA-861 form instructions, which
  show no event count is collected; FERC's assessment, which gives narrative
  deployment figures for individual events but no per-program series. Not
  checked: individual utility evaluation reports filed with state commissions,
  which routinely contain events called, duration and measured performance. That
  is where this would come from.

- **The retail-wholesale overlap.** Checked: FERC's assessment, which publishes
  both populations and states neither reporter's intersection. Not available
  anywhere this repo looked. See ROADMAP item 6.

- **Observed renewable curtailment.** Checked: CarbonCast, which carries
  generation by fuel but not curtailment. CAISO and ERCOT publish actual
  curtailed MWh on their own portals, which were not reachable here. Track 4
  uses a stated proxy instead and says so in every output row.

- **A netted demand response cost.** PJM prices its peaker both gross and net of
  energy and ancillary revenue. EIA reports demand response program cost gross
  only, with nothing subtracted for the energy purchases a curtailment avoids.
  Checked: EIA-861 cost columns and the form instructions. That asymmetry is the
  one thing standing between track 2 and a clean verdict, and no source checked
  here closes it.

- **A sourced storage comparator.** Checked: PJM's planning parameters, which
  give a combustion turbine reference resource. Storage capacity cost is still a
  swept assumption. Only the peaker is sourced.
