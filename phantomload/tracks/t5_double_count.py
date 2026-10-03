"""Track 5. How much of DR's claimed peak reduction is really the tariff.

SIMULATED, but the model is small enough to be checked by hand, and the useful
output is a decomposition rather than a magnitude.

A customer on a time-of-use rate already shifts some load off peak. Put a DR
program on top and the joint reduction is not additive:

    joint = 1 - (1 - a)(1 - b) = a + b - ab

where a is the TOU effect and b the DR effect, both as fractions of the
customer's unmanaged peak. What DR gets credited with depends entirely on the
baseline convention:

    pre-program baseline    credit = a + b - ab   (DR is handed the whole tariff
                                                   effect)
    same-rate control group credit = b(1 - a)     (marginal, defensible)
    Shapley split           credit = b - ab/2     (interaction shared evenly)

The headline is that the double count is dominated by the baseline convention,
not by the genuinely ambiguous interaction term. The interaction is small. The
convention is not.

Reuse note: grid-lab's tariff-explorer holds the TOU archetypes and load shapes
this track would ideally run on. That repo is not vendored here, so the
customer is represented by a single coincident-peak scalar from
calibration.CUSTOMER_PEAK_KW rather than an 8760. Everything in this module is
scale-free in that parameter, so the attribution shares do not depend on it;
only the kW magnitudes do.
"""

from __future__ import annotations

import itertools

import pandas as pd

from ..shared.calibration import (
    CPP_PEAK_REDUCTION,
    CUSTOMER_PEAK_KW,
    DLC_NOTIFICATION_DECAY,
    DLC_PEAK_REDUCTION,
    TOU_PEAK_REDUCTION,
)
from ..shared import ferc
from ..shared.dr_program import Provenance, load_eia_panel


def attribute(a: float, b: float) -> dict[str, float]:
    """a = TOU effect, b = DR effect, both fractions of unmanaged peak."""
    joint = a + b - a * b
    interaction = a * b
    return {
        "tou_effect": a,
        "dr_effect": b,
        "joint": joint,
        "interaction": interaction,
        "credit_pre_program_baseline": joint,
        "credit_same_rate_control": b * (1 - a),
        "credit_shapley": b - interaction / 2,
        "shapley_tou": a - interaction / 2,
        "overcredit_vs_control": joint - b * (1 - a),
        "overcredit_share_of_claim": (joint - b * (1 - a)) / joint,
        "interaction_share_of_claim": interaction / joint,
    }


def sweep(n: int = 9) -> pd.DataFrame:
    rows = []
    dr_params = {
        "cpp": CPP_PEAK_REDUCTION.sweep(n),
        "dlc": [
            v * DLC_NOTIFICATION_DECAY.central for v in DLC_PEAK_REDUCTION.sweep(n)
        ],
    }
    for kind, bs in dr_params.items():
        for a, b in itertools.product(TOU_PEAK_REDUCTION.sweep(n), bs):
            rec = attribute(a, b)
            rec["dr_program"] = kind
            rec["provenance"] = Provenance.SIMULATED.value
            rows.append(rec)
    return pd.DataFrame(rows)


def kw_view() -> pd.DataFrame:
    """Same decomposition in kW per customer, for the scale-dependent reader."""
    rows = []
    for peak in CUSTOMER_PEAK_KW.sweep(3):
        rec = attribute(TOU_PEAK_REDUCTION.central, CPP_PEAK_REDUCTION.central)
        rows.append(
            {
                "peak_kw": peak,
                "joint_kw": rec["joint"] * peak,
                "credit_pre_program_kw": rec["credit_pre_program_baseline"] * peak,
                "credit_control_kw": rec["credit_same_rate_control"] * peak,
                "overcredit_kw": rec["overcredit_vs_control"] * peak,
                "provenance": Provenance.SIMULATED.value,
            }
        )
    return pd.DataFrame(rows)


# --- how many customers this actually applies to ----------------------------
# The decomposition above is scale-free. What it needed was a denominator, and
# FERC publishes one: enrolment in retail dynamic pricing programs, meaning
# time-of-use, real-time, variable peak, critical peak pricing and critical peak
# rebates, alongside enrolment in incentive-based demand response.
#
# The intersection is not published. It is bounded: at least the product of the
# two rates if enrolment were independent, at most the smaller of the two if
# every demand response customer were also on a time-varying rate. Independence
# is the wrong prior here (both programs concentrate in AMI-equipped customers
# of the same utilities), so treat the lower bound as genuinely a lower bound.


def exposure_bounds(year: int = 2023) -> dict:
    dr = float(ferc.regional_metric("dr_customers", year, include_total=True).loc[
        ferc.US_TOTAL
    ])
    dp = float(
        ferc.regional_metric("dynamic_pricing_customers", year, include_total=True).loc[
            ferc.US_TOTAL
        ]
    )
    meters = ferc.TOTAL_METERS_2023
    lower = dp / meters * dr          # independent enrolment
    upper = min(dr, dp)               # complete overlap
    return {
        "year": year,
        "dr_customers": dr,
        "dynamic_pricing_customers": dp,
        "all_meters": meters,
        "dynamic_pricing_share_of_meters": dp / meters,
        "overlap_lower_customers": lower,
        "overlap_upper_customers": upper,
        "overlap_lower_share_of_dr": lower / dr,
        "overlap_upper_share_of_dr": upper / dr,
        "independence_is_a_lower_bound": True,
    }


def exposed_mw(year: int = 2023) -> dict:
    """Double-counted residential peak credit, bounded, IF a pre-program baseline
    is used. That conditional is doing real work and is not a measurement: it is
    the evaluation convention track 5 models. Utilities that evaluate against a
    same-rate control group do not incur any of this.
    """
    bounds = exposure_bounds(year)
    panel = load_eia_panel()
    residential_actual = float(panel.loc[(year, "residential"), "actual_peak_mw"])
    overcredit = attribute(
        TOU_PEAK_REDUCTION.central, CPP_PEAK_REDUCTION.central
    )["overcredit_share_of_claim"]
    return {
        "year": year,
        "residential_actual_peak_mw": residential_actual,
        "overcredit_share_of_claim": overcredit,
        "double_counted_mw_low": bounds["overlap_lower_share_of_dr"]
        * overcredit
        * residential_actual,
        "double_counted_mw_high": bounds["overlap_upper_share_of_dr"]
        * overcredit
        * residential_actual,
        "double_counted_share_of_residential_low": bounds["overlap_lower_share_of_dr"]
        * overcredit,
        "double_counted_share_of_residential_high": bounds["overlap_upper_share_of_dr"]
        * overcredit,
        "conditional_on": "evaluation against a pre-program baseline",
    }


def regional_exposure(year: int = 2023) -> pd.DataFrame:
    """Where the exposure concentrates. Ratio of time-varying-rate enrolment to
    demand response enrolment by census division. Above 1 means there are more
    customers on a dynamic rate than in a demand response program, so the
    overlap can in principle cover the whole demand response population."""
    dr = ferc.regional_metric("dr_customers", year)
    dp = ferc.regional_metric("dynamic_pricing_customers", year)
    out = pd.DataFrame({"dr_customers": dr, "dynamic_pricing_customers": dp})
    out["dp_per_dr_customer"] = out.dynamic_pricing_customers / out.dr_customers
    out["overlap_can_cover_all_dr"] = out.dp_per_dr_customer >= 1
    out["provenance"] = Provenance.MEASURED.value
    return out.sort_values("dp_per_dr_customer", ascending=False)


def summary() -> dict:
    df = sweep()
    central = attribute(TOU_PEAK_REDUCTION.central, CPP_PEAK_REDUCTION.central)
    return {
        "central_tou_effect": TOU_PEAK_REDUCTION.central,
        "central_cpp_effect": CPP_PEAK_REDUCTION.central,
        "central_joint": central["joint"],
        "central_overcredit_share": central["overcredit_share_of_claim"],
        "central_interaction_share": central["interaction_share_of_claim"],
        "overcredit_share_p05": float(df.overcredit_share_of_claim.quantile(0.05)),
        "overcredit_share_median": float(df.overcredit_share_of_claim.median()),
        "overcredit_share_p95": float(df.overcredit_share_of_claim.quantile(0.95)),
        "interaction_share_max": float(df.interaction_share_of_claim.max()),
        "overcredit_exceeds_interaction_always": bool(
            (df.overcredit_share_of_claim > df.interaction_share_of_claim).all()
        ),
        "overcredit_over_interaction_median": float(
            (df.overcredit_share_of_claim / df.interaction_share_of_claim).median()
        ),
        **{f"exposure_{k}": v for k, v in exposure_bounds().items()},
        **{f"mw_{k}": v for k, v in exposed_mw().items()},
        "divisions_where_overlap_can_cover_all_dr": int(
            regional_exposure().overlap_can_cover_all_dr.sum()
        ),
        "highest_exposure_division": str(regional_exposure().index[0]),
        "highest_exposure_ratio": float(
            regional_exposure().dp_per_dr_customer.iloc[0]
        ),
    }


def run() -> dict:
    return {
        "sweep": sweep(),
        "kw_view": kw_view(),
        "regional_exposure": regional_exposure().reset_index(names="division"),
        "summary": summary(),
    }
