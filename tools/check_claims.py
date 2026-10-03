"""Every number quoted in the prose is recomputed here and matched against the
docs. Exits non-zero on drift.

Why this exists. A retracted or stale claim that lives only in README prose does
not break anything when it stops being true, because no test covers prose. This
script pairs each quoted figure with the code that produces it, so editing the
analysis without editing the text fails the build, and editing the text without
the analysis fails it too.

It also enforces two things prose can quietly lose:

  REQUIRED   caveat sentences that must stay. Deleting the sentence that says
             the comparator cost is unverified, or the one that says phantom
             and reserve are not separable, breaks the build.
  FORBIDDEN  phrasings this repo's evidence does not support: claims of proof,
             claims to have measured dispatch events, universal quantifiers on
             the falsification results.

    python tools/check_claims.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ["README.md", "FINDINGS.md", "FALSIFICATION.md", "PRIOR_WORK.md", "MODELED.md"]
CITABLE = ["README.md", "FINDINGS.md", "FALSIFICATION.md", "PRIOR_WORK.md"]

# Claims whose value depends on a simulation, a swept grid or an assumed central
# parameter. The publication standard refuses to assemble generated results into
# the citable findings, so these may appear in MODELED.md and nowhere else.
MODELED = {
    "t3 implied share band",
    "t3 absolute band",
    "t3 parameterisation cost",
    "t3 infeasible",
    "t3 over central",
    "t3 dlc floor",
    "t3 devices",
    "t5 overcredit",
    "t5 interaction",
    "t5 ratio",
    "t5 exposed mw",
}


def _load_summaries() -> dict:
    sys.path.insert(0, str(ROOT))
    from phantomload import synthesis  # noqa: E402
    from phantomload.tracks import (  # noqa: E402
        t1_utilization,
        t2_cost,
        t3_behavioral,
        t4_curtailment,
        t5_double_count,
        t6_overhead,
        t7_crossval,
        t8_falsification,
    )

    return {
        "t1": t1_utilization,
        "t2": t2_cost,
        "t3": t3_behavioral,
        "t4": t4_curtailment,
        "t5": t5_double_count,
        "t6": t6_overhead,
        "t7": t7_crossval,
        "t8": t8_falsification,
        "s1": t1_utilization.national_summary(),
        "sc": t1_utilization.composition_summary(),
        "sr": t1_utilization.regional_summary(),
        "su": t1_utilization.utility_dispersion(),
        "sz": t1_utilization.zero_mass_test(),
        "sup": t1_utilization.utility_panel_summary(),
        "s2": t2_cost.summary(),
        "s3": t3_behavioral.inversion_summary(),
        "s4": t4_curtailment.summary(),
        "s5": t5_double_count.summary(),
        "s6": t6_overhead.summary(),
        "s7": t7_crossval.summary(),
        "s8a": t8_falsification.attack_a(),
        "s8b": t8_falsification.attack_b(),
        "s8c": t8_falsification.attack_c(),
        "s8d": t8_falsification.attack_d(),
        "sy": synthesis.summary(),
        "sp": t1_utilization.persistence_summary(),
        "s4r": t4_curtailment.robustness_summary(),
    }


def build_claims(m: dict) -> list[tuple[str, str]]:
    """(label, exact string that must appear somewhere in the docs)."""
    s1, s2, s3, s4 = m["s1"], m["s2"], m["s3"], m["s4"]
    sc, sr, sy, sp, s4r = m["sc"], m["sr"], m["sy"], m["sp"], m["s4r"]
    su, sz, sup = m["su"], m["sz"], m["sup"]
    s5, s6, s7 = m["s5"], m["s6"], m["s7"]
    s8a, s8b, s8c, s8d = m["s8a"], m["s8b"], m["s8c"], m["s8d"]
    t1 = m["t1"]
    return [
        ("t1 mean utilization", f"{s1['mean_utilization']:.1%}"),
        ("t1 shortfall share", f"{s1['shortfall_share_mean']:.1%}"),
        ("t1 headline rounded",
         f"the {s1['shortfall_share_mean']:.0%} of US demand response capacity"),
        ("t1 panel", f"{s1['first_year']} to {s1['last_year']}"),
        ("t1 utilization range",
         f"{s1['min_utilization']:.1%} in {s1['min_year']} to "
         f"{s1['max_utilization']:.1%} in {s1['max_year']}"),
        ("t1 trend r2", f"r2 {s1['trend_r2']:.2f}"),
        ("t1 max identifiable T",
         f"{t1.max_identifiable_return_period(t1.PANEL_YEARS):.1f} years"),
        ("t1 min window T=10", f"{t1.min_window(10)} years of quiet"),
        ("t1 composition change",
         f"{sc['national_change'] * 100:.1f} points"),
        ("t1 within share", f"{sc['within_share_of_change']:.0%} of it"),
        ("t1 frozen mix",
         f"{sc['frozen_mix_end']:.1%} instead of {sc['actual_end']:.1%}"),
        ("t1 commercial slide",
         f"commercial, which fell from {sc['start_year']}'s 49.7% to 33.4%"),
        ("t1 dispersion floor", f"{sc['sector_spread_mean']:.1%}"),
        ("t1 utility zeros",
         f"{sz['zero_mass_utilities']} of {su['utilities_with_actual']}"),
        ("t1 utility zero share",
         f"{su['zero_or_missing_share_of_national']:.1%} of national enrolled capacity"),
        ("t1 utility median",
         f"median {su['median_realisation']:.0%}"),
        ("t1 largest zero",
         f"{su['largest_zero_utility']} reported {su['largest_zero_mw']:,.0f} MW"),
        ("t1 panel exact zero",
         f"{sup['exact_zero_share_min']:.1%} to {sup['exact_zero_share_max']:.1%} of enrolled"),
        ("t1 panel not reported",
         f"{sup['not_reported_share_min']:.1%} to {sup['not_reported_share_max']:.1%}"),
        ("t1 panel rotation",
         f"{sup['persist_rotating_share_of_ever_zero_mw']:.0%} of the capacity"),
        ("t1 panel every year",
         f"{sup['persist_zero_every_year']} of {sup['persist_utilities_reporting_every_year']}"),
        ("synthesis sweep majority",
         f"{sy['sweep_share_of_configurations_where_dr_wins_majority']:.1%} of "
         f"{sy['sweep_configurations']} configurations"),
        ("t1 regional floor",
         f"{sr['mix_floor_min']:.1%} in the {sr['mix_floor_min_division']} to "
         f"{sr['mix_floor_max']:.1%} in {sr['mix_floor_max_division']}"),
        ("t1 persistence",
         f"{sp['min_window_at_max_persistence']} years at persistence "
         f"{sp['persistence_max_tested']:.1f}"),
        ("t1 persistence multiplier",
         f"{sp['window_multiplier_at_max_persistence']:.1f}x longer"),
        ("t2 netting gap",
         f"${s2['netting_gap_to_net_cone_per_kw_yr']:.2f} per kW-year"),
        ("t2 netting price needed",
         f"${s2['netting_energy_price_needed_at_high_hours']:.2f} per kWh"),
        ("t2 price multiple",
         f"{s2['netting_price_multiple_needed_vs_annual_avg']:.1f}x the annual "
         "load-weighted average"),
        ("t2 credit at average",
         f"{s2['netting_credit_at_annual_avg_covers_share_of_gap']:.1%} of the gap"),
        ("synthesis elcc central",
         f"about {sy['elcc_dr_elcc_central']:.0%} in summer"),
        ("synthesis elcc cost",
         f"${sy['elcc_dr_cost_per_accredited_kw_central']:.2f} per accredited kW"),
        ("synthesis elcc factor",
         f"a factor of {sy['elcc_accreditation_choice_moves_cost_by']:.2f}"),
        ("synthesis elcc cells",
         f"{sy['elcc_dr_wins_cells']} of {sy['elcc_cells']} cells"),
        ("synthesis multiple",
         f"{sy['breakeven_multiple_of_annual_avg_needed']:.1f}x"),
        ("t2 xcheck multiple",
         f"{s2['xcheck_implied_event_hour_price_multiple']:.1f} times an average hour"),
        ("t2 xcheck shortfall",
         f"a factor of {s2['xcheck_shortfall_factor']:.1f}"),
        ("t3 devices",
         f"about {s3['denom_devices_per_customer_at_central']:.1f} controlled devices"),
        ("t3 benchmark",
         f"reports {s3['denom_observed_kw_per_customer']:.2f}"),
        ("t1 design effect",
         f"design effect of {sp['design_effect_at_max_persistence']:.1f}"),
        ("t2 netting share clears",
         f"{s2['netting_share_of_grid_that_clears']:.0%} of that grid"),
        ("t4 robustness",
         f"{s4r['combinations_tested']} combinations"),
        ("t4 max lift", f"max lift {s4r['max_lift_across_all']:.2f}"),
        ("t4 scarcity lift",
         f"{s4['target_scarcity_lift_min']:.0f}x to "
         f"{s4['target_scarcity_lift_max']:.0f}x"),
        ("t4 targeting asymmetry",
         f"{s4['target_targeting_asymmetry']:.0f}-fold"),
        ("t4 share inside",
         f"{s4['target_share_inside_window_at_94_min']:.0%} to "
         f"{s4['target_share_inside_window_at_94_max']:.0%}"),
        ("t4 rule scoping",
         f"since the {s4['target_rules_year_round_required_from']}"),
        ("t4 products retired",
         f"{s4['target_rules_summer_products_retired']} summer-only products"),
        ("t4 winter shoulder",
         f"{s4['target_winter_peak_share_max']:.0%} of its annual maximum in "
         f"{s4['target_winter_peak_share_max_region']}"),
        ("t4 winter",
         f"{s4['target_winter_hours_erco_top200']} of ERCOT's top 200"),
        ("synthesis cells",
         f"{sy['dr_wins_cells']} of {sy['cells']}"),
        ("synthesis consistent",
         f"{sy['dr_wins_among_consistent']} of "
         f"{sy['internally_consistent_cells']} internally consistent"),
        ("synthesis accreditation",
         f"{sy['accreditation_factor']:.1%}"),
        ("synthesis breakeven",
         f"${sy['breakeven_breakeven_price_at_high_hours']:.2f} per kWh"),
        ("t1 regional concentration",
         f"{sr['top3_share']:.1%} of enrolled capacity"),
        ("t5 dynamic pricing customers",
         f"{s5['exposure_dynamic_pricing_customers']:,.0f}"),
        ("t5 overlap bounds",
         f"{s5['exposure_overlap_lower_share_of_dr']:.1%} and 100%"),
        ("t5 exposed mw",
         f"{s5['mw_double_counted_mw_low']:.0f} and {s5['mw_double_counted_mw_high']:.0f} MW"),
        ("t5 top exposure",
         f"{s5['highest_exposure_division']} at "
         f"{s5['highest_exposure_ratio']:.2f}"),
        ("t7 wholesale mw", f"{s7['wholesale_registered_mw_2024']:,.0f} MW"),
        ("t7 wholesale over retail", f"{s7['wholesale_over_retail_2023']:.2f}x"),
        ("t7 pjm realization", f"{s7['pjm_realization_at_least']:.1%}"),
        ("t7 enforcement",
         f"${s7['enforcement_total_penalties_usd'] / 1e6:.1f}M in civil penalties"),
        ("t2 enrolled cost", f"${s2['cost_per_kw_enrolled']:.2f}"),
        ("t2 delivered cost", f"${s2['cost_per_kw_delivered']:.2f}"),
        ("t2 basis gap", f"{s2['basis_gap_ratio']:.2f}x"),
        ("t2 disagree share",
         f"{s2['share_of_swept_comparators_where_framings_disagree']:.0%}"),
        ("t2 pjm gross", f"${s2['rto_gross_cone_per_kw_yr']:.2f}"),
        ("t2 pjm net", f"${s2['rto_net_cone_per_kw_yr']:.2f}"),
        ("t2 eas share", f"{s2['rto_eas_share_of_gross']:.1%}"),
        ("t2 breakeven vs gross",
         f"{s2['breakeven_utilization_vs_rto_gross']:.1%} to clear gross CONE"),
        ("t2 breakeven vs net",
         f"{s2['breakeven_utilization_vs_rto_net']:.1%} to clear net CONE"),
        ("t2 lda sweep",
         f"{s2['ldas_where_dr_beats_net_cone']} of {s2['ldas_modelled']}"),
        ("t2 pl net", f"${s2['pl_net_cone_per_kw_yr']:.2f}"),
        ("t2 dearer than gross",
         f"{s2['sectors_dearer_than_gross_cone_on_delivered'][0]} demand response "
         "costs more per delivered kW than building the peaker"),
        ("t2 basis spreads",
         f"{s2['dr_basis_spread_ratio']:.2f}x against {s2['cone_basis_spread_ratio']:.2f}x"),
        ("t2 years clearing gross",
         f"{s2['years_clearing_gross_cone']} of {s2['years_total']}"),
        ("t8d spread", f"{s8d['mix_adjusted_intensity_spread']:.1f}-fold"),
        ("t8d divisions",
         f"{s8d['least_intense_division']} to the {s8d['most_intense_division']}"),
        ("t8d persistence",
         f"{s8d['divisions_stable_year_over_year']} of "
         f"{s8d['divisions_tested_for_stability']} divisions"),
        ("t8d discontinuity",
         f"{s8d['largest_discontinuity_division']} lost "
         f"{abs(s8d['largest_discontinuity_customer_change']):.1%} of its enrolled "
         f"customers in one year while its reported capacity rose "
         f"{s8d['largest_discontinuity_mw_change']:.1%}"),
        ("t8d mw weighted",
         f"{s8d['share_of_mw_within_25pct_of_norm']:.0%} of enrolled MW"),
        ("t8d restated",
         f"{s8d['reported_utilization']:.1%} to {s8d['utilization_at_least_intense_standard']:.1%}"),
        ("t8c gross", f"{s8c['reserve_share_needed_at_gross_cone']:.1%}"),
        ("t8c net", f"{s8c['reserve_share_needed_at_net_cone']:.1%}"),
        ("t2 cheapest flip",
         f"{s2['cheapest_sector_enrolled']} on the enrolled basis and "
         f"{s2['cheapest_sector_delivered']} on the delivered basis"),
        ("t3 observed kw/customer", f"{s3['observed_kw_per_customer_latest']:.2f} kW"),
        ("t3 parameterisation cost",
         f"{s3['param_width_reduction']:.0%} narrower"),
        ("t3 absolute band",
         f"{s3['param_absolute_p05']:.2f} to {s3['param_absolute_p95']:.2f}"),
        ("t3 infeasible",
         f"{s3['infeas_share_of_draws_infeasible']:.0%} of parameter draws"),
        ("t3 over central",
         f"{s3['infeas_observed_over_central_pure_dlc']:.2f}x what a fully "
         "controlled fleet delivers"),
        ("t3 dlc floor",
         f"at least {s3['infeas_min_implied_share']:.0%}"),
        ("t3 tou bound",
         f"{s3['bound_observed_over_tou_min']:.1f}x to "
         f"{s3['bound_observed_over_tou_max']:.1f}x"),
        ("t3 implied share band",
         f"{s3['implied_dlc_share_p05']:.2f} to {s3['implied_dlc_share_p95']:.2f}"),
        ("t4 lifts",
         f"CISO {s4['lift_ciso']:.2f}, PJM {s4['lift_pjm']:.2f}, ERCO "
         f"{s4['lift_erco']:.2f}"),
        ("t4 best window lift", f"{s4['best_window_lift']:.2f}x"),
        ("t4 ciso risk hour", f"hour {s4['ciso_peak_risk_hour_local']}"),
        ("t5 overcredit",
         f"{s5['central_overcredit_share']:.0%} more than its marginal contribution"),
        ("t5 interaction", f"{s5['central_interaction_share']:.1%} of the claim"),
        ("t5 ratio", f"factor of {s5['overcredit_over_interaction_median']:.1f}x"),
        ("t6 residential overhead", f"{s6['highest_overhead_share']:.1%}"),
        ("t6 industrial overhead", f"{s6['lowest_overhead_share']:.1%}"),
        ("t6 overhead spread", f"{s6['overhead_per_kw_delivered_spread']:.1f}x"),
        ("t6 pooled r", f"r = +{s6['pooled_r']:.2f}"),
        ("t7 energy break", f"{s7['energy_change_at_break']:.1%}"),
        ("t7 peak break", f"{s7['actual_peak_change_at_break']:.1%}"),
        ("t7 implied hours split",
         f"{s7['residential_implied_hours_2022']:.0f} hours for residential and "
         f"{s7['industrial_implied_hours_2022']:.0f} for industrial"),
        ("t8a best year", f"{s8a['best_year_over_full_panel']:.1%}"),
        ("t8b delivered", f"${s8b['dr_cost_per_kw_delivered']:.2f}"),

    ]


REQUIRED = [
    # the remaining inconsistency in the cost comparison, now that both sides
    # are measured: only one side is netted of energy revenue
    "demand response costs are not netted of avoided energy purchases",
    # the central epistemic caveat
    "cannot separate capacity that was never called from capacity that would "
    "not have delivered",
    # track 4's proxy
    "proxy for oversupply conditions, not a measurement of curtailed MWh",
    # the wholesale and retail populations are not additive
    "must not be added",
    # scope: this repo measures utility-administered retail programs
    "utility-administered retail demand response",
    # attack D's limit: the test bounds the room, it does not attribute cause
    "genuine program-design differences produce the same signature",
    # the seasonal finding is scoped to retail, and its sourcing is weaker
    "tariff not read",
    # the headline number is a reproduction, not a discovery
    "not a discovery",
    # the identification bound is a standard statistic
    "rule of three",
    # the borrowed term was wrong and the correction must stay stated
    "dispatch utilization",
    # the price figure is conditional on targeting, not a base case
    "strong-targeting scenario",
    # track 3 is simulation
    "the inversion is not informative",
    # the falsification result must stay in the headline area
    "only a small share of the shortfall has to be genuine reserve",
]

FORBIDDEN = [
    r"\bprove[sd]?\b",
    r"\bproof\b",
    r"\bconclusively\b",
    r"\bmeasured dispatch events?\b",
    r"\bevery (?:utility|program) (?:is|has)\b",
    r"\balways (?:phantom|wasted)\b",
    r"\bdefinitiv(?:e|ely)\b",
]

# Retraction blockquotes may use stronger language when describing a claim that
# was withdrawn, so lines inside them are exempt from FORBIDDEN.
EXEMPT_PREFIX = "> "

# Values that were once claims and have been superseded. The drift check above
# only fails when a pinned value DISAPPEARS, so a stale number left alongside
# its replacement passes silently. Four such survivors were found by hand in one
# audit, which is how this list came to exist. A retired value may appear only
# on a line that says it is historical (retracted, earlier, previously, was,
# withdrawn) or inside a retraction blockquote.
RETIRED = [
    "factor of 5.0x",
    "0.24 to 0.88",
    "0.03 to 0.92",
    "28% narrower",
    "Only 7.7% of",
    "is exactly the ratio this repo measures",
]
HISTORICAL_MARKERS = ("retract", "earlier", "previous", "withdrawn", " was ",
                      "originally", "first version", "had been")


def main() -> int:
    text = {}
    for name in DOCS:
        path = ROOT / name
        if not path.exists():
            print(f"FAIL missing doc: {name}")
            return 1
        text[name] = path.read_text()
    # Prose gets rewrapped constantly, and a required phrase or a quoted figure
    # that straddles a line break is still present in the document. Matching on
    # whitespace-normalised text stops the guard from failing for a reason that
    # has nothing to do with the analysis, which is the failure mode that
    # teaches people to ignore it.
    blob = re.sub(r"\s+", " ", "\n".join(text.values()))

    m = _load_summaries()
    claims = build_claims(m)
    failures = []

    # the README states how many claims are pinned; keep that honest too
    if f"{len(claims)} claims are pinned" not in blob:
        failures.append(
            f"README claim count is stale: should say '{len(claims)} claims are pinned'"
        )

    for label, needle in claims:
        if re.sub(r"\s+", " ", needle) not in blob:
            failures.append(f"drifted claim [{label}]: docs do not contain {needle!r}")

    for label, needle in claims:
        if label not in MODELED:
            continue
        flat = re.sub(r"\s+", " ", needle)
        for name in CITABLE:
            if flat in re.sub(r"\s+", " ", text[name]):
                failures.append(
                    f"modeled claim in citable doc {name}: [{label}] {needle!r}"
                )

    for phrase in REQUIRED:
        if re.sub(r"\s+", " ", phrase) not in blob:
            failures.append(f"missing required caveat: {phrase!r}")

    for name, body in text.items():
        for i, line in enumerate(body.splitlines(), 1):
            if line.startswith(EXEMPT_PREFIX):
                continue
            low = line.lower()
            for value in RETIRED:
                if value.lower() in low and not any(m in low for m in HISTORICAL_MARKERS):
                    failures.append(
                        f"retired value in {name}:{i}: {value!r} stated as current"
                    )

    link = re.compile(r"\]\((?!https?://|#)([^)]+)\)")
    for name, body in text.items():
        for target in link.findall(body):
            if not (ROOT / target.split("#")[0]).exists():
                failures.append(f"dead link in {name}: {target}")

    for name, body in text.items():
        for i, line in enumerate(body.splitlines(), 1):
            if line.startswith(EXEMPT_PREFIX):
                continue
            for pattern in FORBIDDEN:
                if re.search(pattern, line, flags=re.I):
                    failures.append(f"overclaim in {name}:{i}: /{pattern}/ -> {line.strip()[:90]}")

    n = len(claims)
    if failures:
        for f in failures:
            print("FAIL", f)
        print(f"\n{len(failures)} problem(s); {n} claims checked")
        return 1
    print(f"OK {n} claims recomputed and matched, {len(REQUIRED)} caveats present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
