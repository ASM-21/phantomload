"""Every non-measured number in the repo lives here, once.

Design rule: a track may not hard-code a parameter. If a track needs a number
that is not measured, it imports it from this module, where it carries a range
and a provenance tag. Results are then reported as sensitivity bands over the
range rather than as point estimates off the central value.

Honesty rule enforced by tests: a parameter may only be tagged LITERATURE if it
carries a resolvable `citation`. Parameters that come from general familiarity
with the field, rather than a source verified while building this repo, are
tagged ASSUMPTION with `needs_citation=True`. There are several of those. They
are listed in README under "what is not measured" and they are swept, never
pinned. Do not promote one to LITERATURE without adding the actual reference.
"""

from __future__ import annotations

import dataclasses
import functools
import pathlib

import pandas as pd

from .dr_program import Provenance

CONE_TABLE = pathlib.Path(__file__).resolve().parents[2] / "data" / "pjm_cone.csv"
LMP_TABLE = pathlib.Path(__file__).resolve().parents[2] / "data" / "pjm_lmp.csv"
PJM_CONE_CITATION = (
    "PJM Interconnection, 2027/2028 RPM Base Residual Auction Planning Period "
    "Parameters, August 26 2025, Table 3"
)


@dataclasses.dataclass(frozen=True)
class Param:
    name: str
    lo: float
    central: float
    hi: float
    units: str
    provenance: Provenance
    note: str
    citation: str | None = None
    needs_citation: bool = False

    def __post_init__(self) -> None:
        if not (self.lo <= self.central <= self.hi):
            raise ValueError(f"{self.name}: central not inside [lo, hi]")
        if self.provenance is Provenance.LITERATURE and not self.citation:
            raise ValueError(f"{self.name}: LITERATURE requires a citation")

    def sweep(self, n: int = 9) -> list[float]:
        step = (self.hi - self.lo) / (n - 1)
        return [self.lo + i * step for i in range(n)]


# --- Track 2: what DR is being compared against -----------------------------
# These were assumptions in the first version of this repo and are now taken
# from PJM's published RPM planning parameters. See the retraction in README:
# the assumed range ran 80 to 150 dollars per kW-year and excluded net CONE
# entirely, which is the number that decides the comparison.


@functools.lru_cache(maxsize=1)
def cone_table() -> pd.DataFrame:
    """PJM cost of new entry by locational deliverability area, $/kW-year ICAP."""
    df = pd.read_csv(CONE_TABLE)
    for col in ("gross_cone", "eas_offset", "net_cone"):
        df[f"{col}_per_kw_yr"] = df[f"{col}_icap_usd_per_mw_yr"] / 1_000
    df["eas_share_of_gross"] = df.eas_offset_per_kw_yr / df.gross_cone_per_kw_yr
    return df


@functools.lru_cache(maxsize=1)
def lmp_table() -> pd.DataFrame:
    """PJM real-time load-weighted average LMP by year.

    ANNUAL AVERAGE ACROSS ALL HOURS. Not the price in the hours demand response
    is called, which is higher by a factor this repo does not measure. Used only
    to express a required price as a multiple of the average, never as the price
    of avoided energy.
    """
    return pd.read_csv(LMP_TABLE)


def annual_avg_lmp(year: int | None = None) -> float:
    """$/kWh, annual load-weighted average. See the warning on lmp_table."""
    df = lmp_table()
    row = df[df.year == (year or df.year.max())]
    if row.empty:
        raise KeyError(f"no LMP row for {year}")
    return float(row.rt_load_weighted_avg_lmp_usd_per_kwh.iloc[0])


def cone(location: str = "RTO", delivery_year: str = "2027/2028") -> pd.Series:
    df = cone_table()
    hit = df[(df.location == location) & (df.delivery_year == delivery_year)]
    if hit.empty:
        raise KeyError(f"no CONE row for {location} {delivery_year}")
    return hit.iloc[0]


_LATEST = "2027/2028"


PEAKER_CONE = Param(
    name="peaker_cone",
    lo=68.347,   # PJM RTO net CONE, 2027/2028 BRA
    central=149.309,  # PJM RTO gross CONE, 2027/2028 BRA
    hi=158.731,  # dearest modelled LDA gross CONE, COMED 2027/2028
    units="usd_per_kw_year_icap",
    provenance=Provenance.LITERATURE,
    note=(
        "Combustion turbine reference resource. The range deliberately spans net "
        "CONE at the low end and gross CONE at the high end, because the choice "
        "between them moves the comparator by more than a factor of two and is "
        "not a matter of uncertainty. Gross is the basis-consistent comparator "
        "for EIA demand response costs, which are not netted of avoided energy. "
        "ICAP terms, since converting to UCAP would require accrediting demand "
        "response on PJM's basis as well."
    ),
    citation=PJM_CONE_CITATION,
)

STORAGE_CAPACITY_COST = Param(
    name="storage_capacity_cost",
    lo=70.0,
    central=120.0,
    hi=200.0,
    units="usd_per_kw_year",
    provenance=Provenance.ASSUMPTION,
    note=(
        "Annualised fixed cost of 4-hour lithium-ion storage offering capacity, "
        "order of magnitude only, before any arbitrage revenue stack. Unverified."
    ),
    needs_citation=True,
)

DR_ELCC_CITATION = (
    "Energy and Environmental Economics (E3), 'Demand Response as a Capacity "
    "Resource in SPP's Era of Data Center Growth', white paper, October 2025, "
    "partially funded by Google LLC: at 2025 adoption a four-hour curtailment "
    "program earns an ELCC of about 83% in summer and 55% in winter, a ten-hour "
    "program about 100% and 82%; four-hour ELCC falls from about 83% at 2 GW of "
    "adoption to about 50% at 6 GW"
)

DR_ELCC = Param(
    name="dr_elcc",
    lo=0.55,
    central=0.83,
    hi=1.00,
    units="fraction_of_enrolled_capacity",
    provenance=Provenance.LITERATURE,
    note=(
        "Effective load carrying capability of curtailment demand response: the "
        "share of enrolled capacity that counts as dependable for reliability. "
        "This is what the resource adequacy field uses to accredit demand "
        "response, and it is NOT the dispatch utilization. ELCC measures "
        "contribution during critical hours; the dispatch utilization also counts "
        "years in which nothing was called. Using the latter as an accreditation "
        "factor over-penalises demand response by construction. "
        "TWO SPLICES, both stated because neither is resolvable here: the ELCC "
        "figures are SPP-specific and 2025-specific, and they are applied to "
        "national EIA cost data, so this is a cross-footprint comparison. The "
        "range spans the winter four-hour case (55%) to the summer ten-hour case "
        "(100%). Until v0.4.3 the low end was 0.50 under the winter four-hour "
        "label; 0.50 is E3's four-hour figure at 6 GW of adoption, not its "
        "winter figure, so the label and the value disagreed."
    ),
    citation=DR_ELCC_CITATION,
)

DEVICES_PER_ENROLLED_CUSTOMER = Param(
    name="devices_per_enrolled_customer",
    lo=0.6,
    central=1.0,
    hi=1.8,
    units="controlled_devices_per_enrolled_customer",
    provenance=Provenance.ASSUMPTION,
    note=(
        "The conversion nobody publishes, and the reason a per-device impact "
        "cannot be multiplied by an EIA customer count. Two effects run in "
        "opposite directions and neither is reported: not every enrolled "
        "customer has a controlled air conditioner or a paired thermostat, "
        "which pushes the ratio below one, while a household with two "
        "controlled units delivers twice the per-unit figure, which pushes it "
        "above. Evaluations report per AC unit, per thermostat or per "
        "participating home; EIA counts customers. Track 3 inverts for the "
        "value that reconciles them rather than assuming one."
    ),
    needs_citation=True,
)

ENERGY_VALUE = Param(
    name="energy_value",
    lo=0.03,
    central=0.10,
    hi=0.50,
    units="usd_per_kwh",
    provenance=Provenance.ASSUMPTION,
    note=(
        "Value of a kWh of energy a curtailment avoids buying, averaged across "
        "the hours a program is actually called. Used only to BOUND the netting "
        "asymmetry in track 2, never to produce a point estimate, and the high "
        "end is deliberately generous: 50 cents per kWh is 500 dollars per MWh "
        "sustained across every event hour of a year, well above any plausible "
        "on-peak average outside sustained scarcity."
    ),
    needs_citation=True,
)

# --- Track 3: price-based vs direct load control ----------------------------
# These are the classic dynamic-pricing pilot ranges. They are swept end to end
# and the track reports a band, never a point.
TOU_PEAK_REDUCTION = Param(
    name="tou_peak_reduction",
    lo=0.02,
    central=0.045,
    hi=0.07,
    units="fraction_of_customer_peak",
    provenance=Provenance.ASSUMPTION,
    note="Time-of-use rate, residential, no enabling technology.",
    needs_citation=True,
)

CPP_PEAK_REDUCTION = Param(
    name="cpp_peak_reduction",
    lo=0.10,
    central=0.17,
    hi=0.25,
    units="fraction_of_customer_peak",
    provenance=Provenance.ASSUMPTION,
    note="Critical peak pricing, residential, no enabling technology.",
    needs_citation=True,
)

DLC_PEAK_REDUCTION = Param(
    name="dlc_peak_reduction",
    lo=0.15,
    central=0.30,
    hi=0.45,
    units="fraction_of_customer_peak",
    provenance=Provenance.ASSUMPTION,
    note=(
        "Direct load control of central AC or water heating, per enrolled and "
        "responding customer, during an event."
    ),
    needs_citation=True,
)

DLC_NOTIFICATION_DECAY = Param(
    name="dlc_notification_decay",
    lo=0.40,
    central=0.70,
    hi=0.95,
    units="fraction_of_enrolled_responding",
    provenance=Provenance.ASSUMPTION,
    note=(
        "Share of enrolled DLC customers whose device actually contributes on an "
        "event: opt-outs, comms failures, thermostats already off, air "
        "conditioners not running. The lower bound was widened from 0.60 after "
        "the Ontario Peaksaver analysis reported a wide spread across households "
        "with only a minority contributing to any given event. Still an "
        "assumption: that finding describes contribution heterogeneity rather "
        "than a response rate, and the two are not the same quantity."
    ),
    needs_citation=True,
)

# --- Track 3, second parameterisation ---------------------------------------
# The parameters above express program impact as a FRACTION of the customer's
# coincident peak, which forces every absolute answer through
# CUSTOMER_PEAK_KW, a quantity this repo does not measure. The evaluation
# literature reports impacts the other way, as kW per participating customer,
# which needs no such scalar. Track 3 runs both and reports what the choice of
# units costs, because the answer is not zero.
DLC_EVALUATION_CITATION = (
    "Newsham and Bowker 2010 review of North American AC direct load control "
    "programs, 0.3-1.2 kW per AC unit; SDG&E Summer Saver 2011 ex post load "
    "impact evaluation, 0.41 kW per AC unit at 1-in-2 weather and 0.48 at "
    "1-in-10; CenterPoint Energy 2025 demand response impact evaluation, 0.59 "
    "kW per thermostat averaged over a two-hour event; Newsham et al. analysis "
    "of Ontario Peaksaver 2008, 0.2-0.9 kW per household"
)

DLC_KW_PER_CUSTOMER = Param(
    name="dlc_kw_per_customer",
    lo=0.2,
    central=0.5,
    hi=1.2,
    units="kw_per_participating_customer",
    provenance=Provenance.LITERATURE,
    note=(
        "Peak reduction per participating household or AC unit during a direct "
        "load control event, from published program evaluations. An earlier "
        "version of this repo assumed 0.5 to 1.5 with a central value of 1.0, "
        "which the evaluation record does not support: the measured central "
        "value is about half that. UNIT WARNING, and it is not resolvable here: "
        "evaluations report per AC unit, per thermostat or per household, while "
        "EIA counts customers. A household with two controlled units delivers "
        "twice the per-unit figure, so comparing the two is unit-inconsistent "
        "in a direction that inflates the apparent EIA number."
    ),
    citation=DLC_EVALUATION_CITATION,
)

TOU_KW_PER_CUSTOMER = Param(
    name="tou_kw_per_customer",
    lo=0.05,
    central=0.15,
    hi=0.25,
    units="kw_per_enrolled_customer",
    provenance=Provenance.LITERATURE,
    note=(
        "Peak reduction per residential customer on a time-varying rate with no "
        "enabling technology. Unlike direct load control, these evaluations "
        "report per enrolled customer, so the denominator matches EIA's and no "
        "conversion is needed. The published values sit well inside this range: "
        "0.11 kW per customer for critical peak pricing and 0.13 kW per site for "
        "a time-of-use pilot. The upper bound is deliberately generous, which "
        "makes the exclusion bound in track 3 conservative."
    ),
    citation=(
        "PG&E 2023 SmartRate critical peak pricing load impact evaluation, "
        "CALMAC, 0.11 kW (4.7%) per enrolled residential customer per event "
        "hour; PG&E smart-thermostat time-of-use pilot, 0.13 kW per site"
    ),
)

# --- Track 5: TOU and DR interaction ----------------------------------------
CUSTOMER_PEAK_KW = Param(
    name="customer_peak_kw",
    lo=2.0,
    central=4.0,
    hi=8.0,
    units="kw",
    provenance=Provenance.ASSUMPTION,
    note="Residential coincident peak demand, used only as a scale factor.",
    needs_citation=True,
)

# --- Track 1: how often an insurance-style resource is genuinely needed ------
RESERVE_RETURN_PERIOD = Param(
    name="reserve_return_period",
    lo=5.0,
    central=10.0,
    hi=20.0,
    units="years",
    provenance=Provenance.ASSUMPTION,
    note=(
        "Return period of the extreme system condition a reserve-style DR "
        "program exists to cover. Swept, because the identifiability result in "
        "track 1 is a function of it and of nothing else."
    ),
    needs_citation=True,
)

ALL_PARAMS = [
    PEAKER_CONE,
    STORAGE_CAPACITY_COST,
    TOU_PEAK_REDUCTION,
    CPP_PEAK_REDUCTION,
    DLC_PEAK_REDUCTION,
    DLC_NOTIFICATION_DECAY,
    CUSTOMER_PEAK_KW,
    RESERVE_RETURN_PERIOD,
]
