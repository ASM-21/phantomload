"""Track tests. Every headline number is pinned tightly enough to fail on drift."""

from __future__ import annotations

import math

import pytest

from phantomload.tracks import t1_utilization as t1
from phantomload.tracks import t2_cost as t2
from phantomload.tracks import t3_behavioral as t3
from phantomload.tracks import t4_curtailment as t4
from phantomload.tracks import t5_double_count as t5
from phantomload.tracks import t6_overhead as t6
from phantomload.tracks import t7_crossval as t7
from phantomload.tracks import t8_falsification as t8


# --- track 1 ----------------------------------------------------------------
def test_t1_headline_utilization():
    s = t1.national_summary()
    assert s["mean_utilization"] == pytest.approx(0.3915, abs=5e-4)
    assert s["shortfall_share_mean"] == pytest.approx(0.6085, abs=5e-4)
    assert (s["min_year"], s["max_year"]) == (2016, 2022)


def test_t1_no_meaningful_trend():
    """The claim is that the ratio is structural, not sliding. If a future
    vintage puts a real trend in, this fails and the README has to change."""
    s = t1.national_summary()
    assert s["trend_r2"] < 0.05
    assert abs(s["trend_per_decade"]) < 0.05


def test_t1_residential_beats_industrial():
    sec = t1.sector_summary()
    assert sec.loc["residential", "mean_utilization"] > sec.loc["industrial", "mean_utilization"]


def test_t1_min_window_closed_form():
    for t in (2, 5, 10, 20):
        w = t1.min_window(t, alpha=0.05)
        assert t1.p_quiet(t, w) <= 0.05
        assert t1.p_quiet(t, w - 1) > 0.05


def test_t1_min_window_and_max_identifiable_are_inverses():
    for t in (3, 5, 10, 25):
        w = t1.min_window(t, 0.05)
        assert t1.max_identifiable_return_period(w, 0.05) >= t


def test_t1_panel_cannot_identify_decadal_reserve():
    assert t1.min_window(10) == 29
    assert t1.max_identifiable_return_period(t1.PANEL_YEARS) == pytest.approx(4.53, abs=0.02)
    assert t1.min_window(10) > t1.PANEL_YEARS


def test_t1_classifier_refuses_to_guess_on_short_windows():
    """The core guard. A naive one-year threshold is what produces the phantom
    headline this repo is testing, so the classifier must not reproduce it."""
    assert t1.classify([0.0], return_period=10) == "UNIDENTIFIED"
    assert t1.classify([0.0] * 5, return_period=10) == "UNIDENTIFIED"
    assert t1.classify([0.0] * 29, return_period=10) == "PHANTOM"
    assert t1.classify([0.0] * 5, return_period=2) == "PHANTOM"
    assert t1.classify([0.0, 0.0, 0.4], return_period=10) == "WORKING"


# --- track 2 ----------------------------------------------------------------
def test_t2_cost_identity_holds():
    """cost/delivered == (cost/enrolled) / utilization. Catches unit slips."""
    chk = t2.identity_check()
    assert chk.abs_err.max() < 1e-9


def test_t2_headline_costs():
    s = t2.summary()
    assert s["cost_per_kw_enrolled"] == pytest.approx(50.39, abs=0.01)
    assert s["cost_per_kw_delivered"] == pytest.approx(128.78, abs=0.01)
    assert s["basis_gap_ratio"] == pytest.approx(2.556, abs=0.005)


def test_t2_basis_flips_the_cheapest_sector():
    s = t2.summary()
    assert s["cheapest_sector_enrolled"] == "industrial"
    assert s["cheapest_sector_delivered"] == "residential"


def test_t2_framings_disagree_over_much_of_the_range():
    s = t2.summary()
    assert 0.4 < s["share_of_swept_comparators_where_framings_disagree"] < 0.7


def test_t2_cost_uses_only_years_with_published_costs():
    df = t2.cost_table()
    assert df.year.min() == 2015 and df.year.max() == 2024


# --- track 3 ----------------------------------------------------------------
def test_t3_inversion_is_reported_as_uninformative():
    s = t3.inversion_summary()
    assert s["informative"] is False
    assert s["implied_dlc_share_p95"] - s["implied_dlc_share_p05"] > 0.4


def test_t3_dominant_driver_is_unmeasured_peak_demand():
    """True of the fractional parameterisation, which is the point of the
    re-parameterisation below."""
    s = t3.inversion_summary()
    assert s["dominant_driver"] == "peak_kw"
    assert abs(s["driver_correlations"]["peak_kw"]) > abs(
        s["driver_correlations"]["dlc_frac"]
    )


def test_t3_units_choice_cost_a_quarter_of_the_band():
    """Fractional impacts import a scalar the data cannot constrain. Absolute
    impacts do not. If this reduction ever vanishes, the parameterisation lesson
    in FINDINGS is no longer supported."""
    c = t3.parameterization_cost()
    assert c["absolute_band_width"] < c["fractional_band_width"]
    assert c["width_reduction"] == pytest.approx(0.231, abs=0.01)
    assert c["dominant_driver"] == "dlc_kw_per_customer"
    assert c["still_uninformative"] is True


def test_t3_absolute_sweep_carries_no_peak_scalar():
    """The whole point: no column of the absolute sweep depends on customer peak
    demand. If one appears, the nuisance parameter has come back."""
    cols = set(t3.absolute_sweep().columns)
    assert not any("peak_kw" in c for c in cols)
    assert {"dlc_kw_per_customer", "tou_kw_per_customer"} <= cols


def test_t3_pure_price_based_fleet_is_ruled_out():
    """The bound the null was hiding, and it must hold across the whole range."""
    b = t3.pure_tou_ruled_out()
    assert b["tou_only_ruled_out_in_all_draws"] is True
    assert b["share_of_draws_needing_some_dlc"] == 1.0
    assert b["observed_over_tou_min"] > 1.5
    assert b["observed_kw_per_customer"] > b["tou_only_max_kw_per_customer"]


def test_t3_bound_is_one_sided():
    """Price-based-only is excluded; control-based-only is not. Claiming both
    would be claiming identification the data does not support."""
    b = t3.pure_tou_ruled_out()
    assert b["dlc_only_ruled_out"] is False
    assert b["asymmetric"] is True


def test_t3_observed_delivery_per_customer_is_measured():
    s = t3.inversion_summary()
    assert s["observed_kw_per_customer_latest"] == pytest.approx(0.449, abs=0.002)


def test_t3_synthetic_registry_is_flagged_simulated():
    from phantomload.shared.dr_program import Provenance

    for p in t3.synthetic_registry():
        assert p.provenance is Provenance.SIMULATED
        assert p.verified_mw < p.enrolled_mw


# --- track 4 ----------------------------------------------------------------
def test_t4_regions_load_full_two_years():
    for region in t4.REGIONS:
        df = t4.load_region(region)
        assert len(df) == 17_544
        assert df.renewable_share.between(0, 1).all()


def test_t4_dr_window_misses_curtailment_risk():
    s = t4.summary()
    assert s["lift_ciso"] < 0.5
    assert s["lift_pjm"] < 0.5
    assert s["lift_erco"] == 0.0
    assert s["max_lift"] < 1.0


def test_t4_midday_window_would_work():
    ws = t4.window_sensitivity()
    ciso_mid = ws[(ws.region == "CISO") & (ws.window == "all_year_midday_10_15")]
    assert float(ciso_mid.lift.iloc[0]) > 2.0


def test_t4_ciso_oversupply_is_spring_midday():
    w = t4.when_is_risk()
    assert w.loc["CISO", "peak_risk_hour_local"] in (11, 12, 13)
    assert w.loc["CISO", "peak_risk_month"] in (3, 4, 5)


def test_t4_local_time_conversion_actually_applied():
    """If the tz conversion silently no-ops, CISO solar would peak at UTC noon
    which is 4am local. This pins that it does not."""
    df = t4.load_region("CISO")
    by_hour = df.groupby("local_hour").renewable_share.mean()
    assert 10 <= by_hour.idxmax() <= 15


# --- track 5 ----------------------------------------------------------------
def test_t5_attribution_components_sum_to_joint():
    rec = t5.attribute(0.045, 0.17)
    assert rec["shapley_tou"] + rec["credit_shapley"] == pytest.approx(rec["joint"])
    assert rec["tou_effect"] + rec["dr_effect"] - rec["interaction"] == pytest.approx(
        rec["joint"]
    )


def test_t5_overcredit_equals_tou_effect_under_pre_program_baseline():
    a, b = 0.045, 0.17
    rec = t5.attribute(a, b)
    assert rec["overcredit_vs_control"] == pytest.approx(a)


def test_t5_double_count_dominates_the_interaction():
    s = t5.summary()
    assert s["overcredit_exceeds_interaction_always"] is True
    assert s["overcredit_over_interaction_median"] > 3
    assert s["central_interaction_share"] < 0.05


def test_t5_is_scale_free_in_customer_peak():
    small = t5.attribute(0.045, 0.17)["overcredit_share_of_claim"]
    assert small == pytest.approx(
        t5.attribute(0.045, 0.17)["overcredit_share_of_claim"]
    )
    kw = t5.kw_view()
    ratio = kw.overcredit_kw / kw.joint_kw
    assert ratio.std() < 1e-12


# --- track 6 ----------------------------------------------------------------
def test_t6_compounding_hypothesis_rejected():
    s = t6.summary()
    assert s["compounding_supported"] is False
    assert s["pooled_r"] > 0


def test_t6_overhead_spread_by_sector():
    s = t6.summary()
    assert s["highest_overhead_share_sector"] == "residential"
    assert s["lowest_overhead_share_sector"] == "industrial"
    assert s["highest_overhead_share"] == pytest.approx(0.489, abs=0.002)
    assert s["overhead_per_kw_delivered_spread"] == pytest.approx(8.94, abs=0.05)


def test_t6_worst_overhead_sector_is_not_worst_utilization_sector():
    prof = t6.sector_profile().dropna()
    assert prof.overhead_share.idxmax() != prof.utilization.idxmin()


def test_t6_scale_threshold_identifies_best_sector():
    out = t6.scale_threshold()
    assert out["best_sector"] == "industrial"
    assert (out["table"]["multiple_of_current_kw_per_customer"] >= 1).all()


# --- track 7 ----------------------------------------------------------------
def test_t7_second_estimator_exists_and_retraction_is_recorded():
    """The first version of this track denied a second estimator existed. If
    that claim ever comes back, this fails."""
    s = t7.summary()
    assert s["second_estimator_exists"] is True
    assert "no genuine two-method cross-validation" in s["retracted_claim"]
    assert s["energy_column_is_independent"] is False


def test_t7_structural_break_hits_energy_not_peak():
    s = t7.summary()
    assert s["energy_change_at_break"] < -0.6
    assert abs(s["actual_peak_change_at_break"]) < 0.15
    assert abs(s["energy_change_at_break"]) > 5 * abs(s["actual_peak_change_at_break"])


def test_t7_implied_hours_are_implausible_as_event_records():
    s = t7.summary()
    assert s["residential_implied_hours_2022"] > 150
    assert s["industrial_implied_hours_2022"] < 40


# --- track 8 ----------------------------------------------------------------
def test_t8_attack_a_holds():
    a = t8.attack_a()
    assert a["shortfall_survives"] is True
    assert a["best_year_over_full_panel"] == pytest.approx(0.446, abs=0.002)
    assert a["best_year_over_full_panel"] < 0.6


def test_t8_attack_b_flips_only_on_basis():
    b = t8.attack_b()
    assert b["dr_wins_on_enrolled_basis_against_all_best_cases"] is True
    assert b["dr_wins_on_delivered_basis_against_any_best_case"] is False


def test_t8_attack_c_damages_the_headline_from_both_sides():
    c = t8.attack_c()
    assert c["headline_is_fragile"] is True
    assert c["no_reserve_credit_needed_at_gross"] is True
    assert c["reserve_share_needed_at_gross_cone"] < 0
    assert c["reserve_share_needed_at_net_cone"] == pytest.approx(0.568, abs=0.003)


def test_t8_reserve_breakeven_is_monotone_in_comparator_cost():
    grid = t8.attack_c()["grid"]
    shares = [g["reserve_share_of_shortfall_needed"] for g in grid]
    assert all(x >= y - 1e-12 for x, y in zip(shares, shares[1:]))


def test_t8_attack_c_uses_the_published_cone_values():
    from phantomload.shared.calibration import cone

    c = t8.attack_c()
    rto = cone("RTO", "2027/2028")
    assert c["gross_cone_per_kw_yr"] == pytest.approx(rto.gross_cone_per_kw_yr)
    assert c["net_cone_per_kw_yr"] == pytest.approx(rto.net_cone_per_kw_yr)


def test_t8_reserve_breakeven_matches_cost_table():
    """Recompute attack C by hand from the cost table, so a refactor of the
    solver cannot quietly change the number the README quotes."""
    cost = t2.cost_table()
    row = cost[cost.sector == "total"].sort_values("year").iloc[-1]
    c_alt = 115.0  # arbitrary probe value, the solver must not hard-code one
    shortfall = row.potential_peak_mw - row.actual_peak_mw
    expected = (row.total_cost_kusd / c_alt - row.actual_peak_mw) / shortfall
    assert t8.reserve_breakeven(c_alt)["reserve_share_of_shortfall_needed"] == pytest.approx(
        expected
    )


def test_all_tracks_run_and_tag_provenance():
    import pandas as pd

    for mod in (t1, t2, t3, t4, t5, t6, t7, t8):
        out = mod.run()
        assert out
        frames = [v for v in out.values() if isinstance(v, pd.DataFrame)]
        assert frames, f"{mod.__name__} produced no tables"
        assert any("provenance" in f.columns for f in frames), mod.__name__


# --- track 1 composition ----------------------------------------------------
def test_t1_shift_share_components_sum_to_the_change():
    ss = t1.shift_share()
    total = ss.within.sum() + ss["mix"].sum() + ss.interaction.sum()
    frozen = t1.frozen_mix_series()
    start = frozen[frozen.year == ss.attrs["start"]].actual.iloc[0]
    end = frozen[frozen.year == ss.attrs["end"]].actual.iloc[0]
    assert total == pytest.approx(end - start, abs=1e-9)


def test_t1_decline_is_within_sector_not_mix():
    c = t1.composition_summary()
    assert c["national_change"] < 0
    assert c["within_sector"] < c["national_change"]  # within overshoots, mix offsets
    assert c["mix"] > 0
    assert c["within_share_of_change"] > 1.0


def test_t1_frozen_mix_tracks_actual_closely():
    """If composition were doing the work, these two series would diverge."""
    f = t1.frozen_mix_series()
    assert (f.actual - f.frozen_mix).abs().max() < 0.02


def test_t1_weights_sum_to_one_each_year():
    ws = t1.weights_and_rates()
    sums = ws.groupby("year").weight.sum()
    assert sums.between(0.999, 1.001).all()


def test_t1_dispersion_range_excludes_immaterial_sectors():
    """Transportation swings wildly on a couple of hundred MW. It must not set
    the reported range, or the spread becomes a statement about rounding."""
    d = t1.dispersion_floor()
    assert (d.spread <= 0.45).all()
    assert (d.sectors_counted >= 3).all()
    assert d.between_sector_sd.max() < 0.15


def test_t1_dispersion_is_labelled_a_floor():
    assert t1.composition_summary()["dispersion_is_a_floor"] is True


# --- track 2, PJM comparator ------------------------------------------------
def test_pjm_cone_identity_gross_minus_eas_equals_net():
    """Transcription guard on PJM's own arithmetic."""
    from phantomload.shared.calibration import cone_table

    df = cone_table()
    err = (
        df.gross_cone_icap_usd_per_mw_yr
        - df.eas_offset_icap_usd_per_mw_yr
        - df.net_cone_icap_usd_per_mw_yr
    ).abs()
    assert err.max() <= 1  # PJM's own rounding
    assert len(df) == 30


def test_pjm_icap_to_ucap_factor_differs_between_auctions():
    """Ingest trap. Converting CONE bases with one factor is off by about 1%."""
    from phantomload.shared.calibration import cone_table

    df = cone_table()
    implied = (
        df.net_cone_icap_usd_per_mw_yr / 365 / df.net_cone_ucap_usd_per_mw_day
    )
    rto = df.location == "RTO"
    f26 = float(implied[rto & (df.delivery_year == "2026/2027")].iloc[0])
    f27 = float(implied[rto & (df.delivery_year == "2027/2028")].iloc[0])
    assert f26 == pytest.approx(0.7800, abs=0.0005)
    assert f27 == pytest.approx(0.7720, abs=0.0005)
    assert abs(f26 - f27) > 0.005


def test_t2_comparator_is_cited_not_assumed():
    from phantomload.shared.calibration import PEAKER_CONE
    from phantomload.shared.dr_program import Provenance

    assert PEAKER_CONE.provenance is Provenance.LITERATURE
    assert "PJM" in (PEAKER_CONE.citation or "")
    assert PEAKER_CONE.needs_citation is False


def test_t2_pjm_breakeven_utilizations():
    s = t2.summary()
    assert s["rto_gross_cone_per_kw_yr"] == pytest.approx(149.309)
    assert s["rto_net_cone_per_kw_yr"] == pytest.approx(68.347)
    assert s["breakeven_utilization_vs_rto_gross"] == pytest.approx(0.337, abs=0.002)
    assert s["breakeven_utilization_vs_rto_net"] == pytest.approx(0.737, abs=0.002)


def test_t2_dr_clears_gross_cone_but_not_net():
    s = t2.summary()
    assert s["dr_beats_rto_gross_on_delivered"] is True
    assert s["dr_beats_rto_net_on_delivered"] is False
    assert s["years_clearing_gross_cone"] == s["years_total"]
    assert s["ldas_where_dr_beats_net_cone"] == 0


def test_t2_two_zones_are_unwinnable_against_net_cone():
    """Where net CONE is below DR's enrolled-basis cost, no utilization helps."""
    pjm = t2.pjm_comparison()
    latest = pjm[pjm.delivery_year == "2027/2028"]
    unwinnable = set(latest[latest.unwinnable_vs_net].location)
    assert unwinnable == {"BGE", "DOM"}


def test_t2_both_sides_have_comparable_basis_spreads():
    """If one denominator dominated, the other could be ignored. Neither does."""
    s = t2.summary()
    ratio = s["dr_basis_spread_ratio"] / s["cone_basis_spread_ratio"]
    assert 0.8 < ratio < 1.25


def test_t2_ppl_zone_present_and_distinct():
    pjm = t2.pjm_comparison()
    pl = pjm[(pjm.location == "PL") & (pjm.delivery_year == "2027/2028")].iloc[0]
    rto = pjm[(pjm.location == "RTO") & (pjm.delivery_year == "2027/2028")].iloc[0]
    assert pl.net_cone_per_kw_yr == pytest.approx(88.886)
    assert pl.net_cone_per_kw_yr > rto.net_cone_per_kw_yr
    older = pjm[(pjm.location == "PL") & (pjm.delivery_year == "2026/2027")].iloc[0]
    assert pl.net_cone_per_kw_yr < older.net_cone_per_kw_yr  # only zone that fell


# --- track 7, wholesale second measurement ----------------------------------
def test_t7_wholesale_totals_reconcile_with_the_source():
    w = t7.wholesale_table()
    for year in (2023, 2024):
        parts = w[(w.year == year) & (w.market != "All RTO/ISO")].dr_resources_mw.sum()
        total = float(
            w[(w.year == year) & (w.market == "All RTO/ISO")].dr_resources_mw.iloc[0]
        )
        assert abs(parts - total) <= 0.2, (year, parts, total)


def test_t7_wholesale_exceeds_retail_and_is_not_additive():
    s = t7.summary()
    assert s["wholesale_registered_mw_2024"] == pytest.approx(33_272.0)
    assert s["wholesale_over_retail_2023"] > 1.0
    assert s["totals_may_be_added"] is False
    assert t7.retail_vs_wholesale().populations_disjoint.eq(False).all()


def test_t7_pjm_event_realization_is_a_lower_bound_near_the_national_ratio():
    ev = t7.pjm_event_realization()
    assert ev["is_a_lower_bound"] is True
    assert ev["realization_at_least"] == pytest.approx(0.469, abs=0.002)
    assert ev["same_order_of_magnitude"] is True
    assert ev["identification_resolved"] is False


def test_t7_enforcement_scale_cannot_explain_the_shortfall():
    """Guard against the tempting overread. The prosecuted cases are real and
    far too small to account for a 19 GW gap."""
    enf = t7.enforcement_cases()
    assert len(enf) == 2
    assert enf.civil_penalty_usd.sum() == pytest.approx(38_419_457)
    assert enf.adjudicated.sum() == 1  # one adjudicated, one consent agreement


def test_t7_documented_double_registration_present():
    dr = t7.documented_double_registration()
    assert set(dr.market) == {"MISO", "PJM"}
    assert (dr.issue.str.len() > 40).all()


# --- track 1, regional ------------------------------------------------------
def test_t1_regional_weights_sum_to_one():
    mix = t1.regional_mix_floor()
    cols = [c for c in mix.columns if c.startswith("weight_")]
    assert mix[cols].sum(axis=1).between(0.999, 1.001).all()


def test_t1_regional_floor_is_narrower_than_the_truth_could_be():
    r = t1.regional_summary()
    assert r["regional_utilization_observable"] is False
    assert r["mix_floor_spread"] == pytest.approx(0.076, abs=0.002)
    assert r["mix_floor_min_division"] == "East South Central"
    assert r["mix_floor_max_division"] == "New England"


def test_t1_regional_enrolled_is_concentrated():
    r = t1.regional_summary()
    assert r["largest_division"] == "South Atlantic"
    assert r["top3_share"] > 0.5
    assert r["enrolled_hhi"] > 1 / 9  # above a perfectly even nine-way split


def test_ferc_regional_reproduces_the_eia_national_panel():
    """Cross-source ingest guard. Two agencies, two documents, one survey."""
    from phantomload.shared import ferc
    from phantomload.shared.dr_program import load_eia_panel

    panel = load_eia_panel()
    for year in (2022, 2023):
        div_sum = ferc.regional_metric("potential_peak_mw", year).sum()
        assert div_sum == pytest.approx(
            float(panel.loc[(year, "total"), "potential_peak_mw"]), abs=1.0
        )
        cust = ferc.regional_metric("dr_customers", year).sum()
        assert cust == pytest.approx(
            float(panel.loc[(year, "total"), "customers_enrolled"]), abs=1.0
        )
    for cls in ("residential", "commercial", "industrial"):
        assert ferc.regional_metric("potential_peak_mw", 2023, cls).sum() == pytest.approx(
            float(panel.loc[(2023, cls), "potential_peak_mw"]), abs=1.0
        )


# --- track 5, exposure ------------------------------------------------------
def test_t5_exposure_bounds_are_ordered_and_labelled():
    b = t5.exposure_bounds()
    assert b["overlap_lower_customers"] < b["overlap_upper_customers"]
    assert b["overlap_upper_share_of_dr"] == 1.0
    assert b["overlap_lower_share_of_dr"] == pytest.approx(0.109, abs=0.002)
    assert b["independence_is_a_lower_bound"] is True


def test_t5_exposed_mw_is_conditional_on_the_baseline_convention():
    mw = t5.exposed_mw()
    assert "pre-program baseline" in mw["conditional_on"]
    assert mw["double_counted_mw_low"] < mw["double_counted_mw_high"]
    assert mw["double_counted_share_of_residential_high"] == pytest.approx(
        mw["overcredit_share_of_claim"]
    )


def test_t5_regional_exposure_is_lopsided():
    r = t5.regional_exposure()
    assert r.index[0] == "Pacific"
    assert r.dp_per_dr_customer.iloc[0] > 5
    assert int(r.overlap_can_cover_all_dr.sum()) == 7
    assert "South Atlantic" in r[~r.overlap_can_cover_all_dr].index


# --- track 1, persistence attack on the closed form -------------------------
def test_t1_markov_collapses_to_independent_when_memoryless():
    """At persistence = p the chain has no memory and must reproduce p_quiet."""
    for t in (5, 10, 20):
        p = 1 / t
        for w in (1, 5, 12, 30):
            assert t1.p_quiet_markov(t, w, p) == pytest.approx(t1.p_quiet(t, w))
    assert t1.min_window_markov(10, 0.1) == t1.min_window(10)


def test_t1_persistence_only_lengthens_the_requirement():
    sweep = t1.persistence_sweep()
    assert sweep.min_window_years.is_monotonic_increasing
    assert (sweep[~sweep.memoryless].vs_independent > 1).all()
    s = t1.persistence_summary()
    assert s["closed_form_is_a_lower_bound_under_persistence"] is True
    assert s["min_window_at_max_persistence"] == 65


def test_t1_markov_closed_form_matches_monte_carlo():
    """Simulation checks the algebra, not the world."""
    for q in (0.1, 0.3, 0.5):
        closed = t1.p_quiet_markov(10, 12, q)
        mc = t1.simulate_quiet_runs(10, 12, q, n=60_000, seed=11)
        assert abs(closed - mc) < 0.01, (q, closed, mc)


def test_t1_markov_rejects_invalid_persistence():
    with pytest.raises(ValueError):
        t1.p_quiet_markov(10, 5, 1.0)


# --- track 2, netting bound -------------------------------------------------
def test_t2_netting_cannot_close_the_gap():
    s = t2.netting_summary()
    assert s["share_of_grid_that_clears"] == 0.0
    assert s["max_credit_covers_gap"] is False
    assert s["gap_to_net_cone_per_kw_yr"] == pytest.approx(60.43, abs=0.02)
    assert s["still_over_net_cone_by"] > 1.0


def test_t2_netting_credit_is_hours_times_price():
    grid = t2.netting_bound()
    expected = grid.implied_event_hours * grid.energy_price_usd_per_kwh
    assert (grid.avoided_energy_credit_per_kw_yr - expected).abs().max() < 1e-9


def test_t2_netting_uses_both_sides_of_the_reclassification():
    grid = t2.netting_bound()
    assert grid.hours_basis.nunique() == 2
    assert grid.implied_event_hours.max() / grid.implied_event_hours.min() > 2


# --- track 4, proxy robustness ----------------------------------------------
def test_t4_conclusion_survives_every_proxy_definition():
    s = t4.robustness_summary()
    assert s["combinations_tested"] == 24
    assert s["all_below_one"] is True
    assert s["share_below_half"] == 1.0
    assert s["max_lift_across_all"] < 0.5


def test_t4_two_proxy_definitions_rank_regions_alike():
    s = t4.robustness_summary()
    assert s["definitions_correlate"] > 0.8


# --- synthesis --------------------------------------------------------------
def test_synthesis_accreditation_recovered_not_assumed():
    from phantomload import synthesis
    from phantomload.shared.calibration import cone

    factor = synthesis.accreditation_factor()
    row = cone("RTO", "2027/2028")
    assert factor == pytest.approx(
        row.net_cone_icap_usd_per_mw_yr / 365 / row.net_cone_ucap_usd_per_mw_day
    )
    assert 0.75 < factor < 0.80


def test_synthesis_grid_shape_and_verdicts():
    from phantomload import synthesis

    s = synthesis.summary()
    assert s["cells"] == 8
    assert s["dr_wins_cells"] == 6
    assert s["dr_loses_cells"] == 2
    assert s["internally_consistent_cells"] == 2
    assert s["dr_wins_among_consistent"] == 2


def test_synthesis_both_losses_are_the_same_pairing():
    from phantomload import synthesis

    v = synthesis.verdict_table()
    losses = v[~v.dr_wins]
    assert set(losses.dr_basis) == {"per kW delivered"}
    assert set(losses.comparator) == {"net CONE"}
    assert (losses.n_inconsistencies >= 1).all()


def test_synthesis_consistent_cells_carry_no_mismatch():
    from phantomload import synthesis

    v = synthesis.verdict_table()
    clean = v[v.n_inconsistencies == 0]
    assert (clean.inconsistencies == "none").all()
    assert clean.dr_wins.all()


def test_synthesis_aligned_cell_turns_on_the_unpublished_number():
    from phantomload import synthesis

    be = synthesis.breakeven_energy_price()
    assert be["credit_needed_per_kw_yr"] == pytest.approx(40.26, abs=0.05)
    assert be["breakeven_price_at_high_hours"] == pytest.approx(0.430, abs=0.005)
    assert be["breakeven_price_at_low_hours"] > be["breakeven_price_at_high_hours"]
    aligned = synthesis.aligned_comparison()
    assert 0 < aligned.clears_aligned.sum() < len(aligned)


def test_synthesis_ratio_spread_is_larger_than_any_single_axis():
    """The three basis choices compound. If any one axis explained the spread,
    the others could be ignored."""
    from phantomload import synthesis

    s = synthesis.summary()
    assert s["ratio_spread"] > 5
    assert s["ratio_spread"] > s["accreditation_factor"] ** -1


# --- track 8, attack D ------------------------------------------------------
def test_t8_intensity_index_is_pure_redistribution():
    """Built from national per-class intensities, so the aggregate index must be
    1.0 by construction. If it is not, the class mapping has drifted."""
    d = t8.attack_d()
    assert d["index_is_pure_redistribution"] is True
    assert d["aggregate_intensity_index"] == pytest.approx(1.0, abs=0.01)


def test_t8_attack_d_opens_a_third_explanation():
    d = t8.attack_d()
    assert d["mix_adjusted_intensity_spread"] == pytest.approx(5.54, abs=0.05)
    assert d["least_intense_division"] == "Pacific"
    assert d["most_intense_division"] == "Mountain"
    assert d["reporting_could_explain_whole_shortfall"] is True
    assert d["test_can_attribute_cause"] is False


def test_t8_restating_can_cut_either_way():
    """The counterfactual is a bound, not a correction. Restating to the median
    standard makes utilization worse, which is the tell that this is not an
    estimate of the artefact."""
    lo = t8.restate_to_standard(standard="min")
    med = t8.restate_to_standard(standard="median")
    assert lo["restated_utilization"] > lo["reported_utilization"]
    assert med["restated_utilization"] < med["reported_utilization"]


def test_t8_reporting_intensity_covers_all_divisions():
    from phantomload.shared import ferc

    r = t8.reporting_intensity()
    assert set(r.index) == set(ferc.DIVISIONS)
    assert (r.intensity_index > 0).all()


def test_t8_persistence_separates_the_two_mechanisms():
    """Most of the cross-sectional spread is stable across years, which favours
    genuine program differences; the exceptions are the reporting story."""
    d = t8.attack_d()
    assert d["divisions_stable_year_over_year"] == 7
    assert d["divisions_tested_for_stability"] == 9
    assert d["spread_is_mostly_persistent"] is True
    assert d["discontinuity_divisions"] == ["Mountain", "Pacific"]


def test_t8_discontinuities_move_capacity_and_headcount_oppositely():
    """That is the signature a real fleet cannot produce, and it is what the
    discontinuity flag is testing for."""
    st = t8.reporting_stability()
    flagged = st[st.discontinuity]
    assert (flagged.customers_change * flagged.potential_mw_change < 0).all()
    assert (flagged.kw_per_customer_change.abs() > 0.4).all()
    stable = st[~st.discontinuity]
    assert (stable.kw_per_customer_change.abs() < 0.3).all()


def test_t8_mw_weighting_does_not_rescue_the_norm():
    d = t8.attack_d()
    assert d["share_of_mw_within_25pct_of_norm"] < 0.4
    assert d["mw_weighted_intensity_index"] > d["aggregate_intensity_index"]


# --- track 4, scarcity targeting --------------------------------------------
def test_t4_window_hits_scarcity_and_misses_surplus():
    """The two results must have opposite signs. If they ever agree, the window
    definition or the net-load construction has drifted."""
    s = t4.summary()
    assert s["target_scarcity_lift_min"] > 10
    assert s["target_oversupply_lift_max"] < 0.2
    assert s["target_window_is_built_for_scarcity_not_surplus"] is True
    assert s["target_targeting_asymmetry"] > 50


def test_t4_event_hour_depths_match_the_measured_fleet():
    """Depths are not arbitrary: they come from track 7's implied event hours."""
    from phantomload.tracks import t7_crossval as t7

    hours = t7.summary()
    assert min(t4.EVENT_HOUR_DEPTHS) <= hours["implied_hours_latest_total"] + 1
    assert max(t4.EVENT_HOUR_DEPTHS) >= hours["implied_hours_2022_total"]
    st = t4.scarcity_targeting()
    assert st.depth_share_of_year.max() < 0.02


def test_t4_scarcity_hours_carry_higher_net_load():
    st = t4.scarcity_targeting()
    assert (st.net_load_vs_annual_mean > 1.5).all()
    # deeper tails must dilute, never concentrate
    for region, grp in st.groupby("region"):
        g = grp.sort_values("depth_hours")
        assert g.net_load_vs_annual_mean.is_monotonic_decreasing


def test_t4_winter_blind_spot_is_reported_as_a_floor():
    s = t4.summary()
    bs = t4.seasonal_blind_spot()
    assert s["target_regions_with_winter_scarcity"] == ["ERCO"]
    assert s["target_winter_hours_erco_top200"] == 6
    assert s["target_winter_counts_are_a_floor"] is True
    erco = bs[(bs.region == "ERCO") & (bs.depth_hours == 200)].iloc[0]
    assert "2021-02" in erco.dates
    assert "understates" in erco.provenance


def test_t4_winter_shoulder_is_structural_not_one_storm():
    """If this only reflected February 2021, CISO would look like ERCO. It does
    not: the eastern markets carry a high winter shoulder in ordinary months."""
    w = t4.winter_shoulder().set_index("region")
    assert w.loc["ERCO", "winter_peak_share_of_annual"] > 0.85
    assert w.loc["PJM", "winter_peak_share_of_annual"] > 0.80
    assert w.loc["CISO", "winter_peak_share_of_annual"] < 0.70
    assert (w.summer_window_peak_share == 1.0).all()


def test_t4_seasonal_finding_is_scoped_to_retail():
    """The winter result must not be presented as unnoticed. PJM addressed it by
    rule years earlier, and this repo measures a different population."""
    r = t4.rule_scoping()
    assert r["wholesale_already_addressed"] is True
    assert r["finding_scope"].startswith("EIA retail")
    assert r["eia_publishes_seasonal_availability"] is False
    assert r["verify_before_citing"] is True
    assert "tariff not read" in r["source_quality"]


# --- the priced anchor ------------------------------------------------------
def test_lmp_anchor_is_labelled_as_an_annual_average():
    """It is the wrong price for called hours and must never be used as one.
    The file itself has to say so, because the warning is the whole safeguard."""
    from phantomload.shared.calibration import lmp_table

    df = lmp_table()
    assert len(df) == 3
    assert (df.basis.str.contains("NOT called-hour price")).all()
    assert df.rt_load_weighted_avg_lmp_usd_per_mwh.between(20, 100).all()


def test_lmp_unit_conversion_is_consistent():
    from phantomload.shared.calibration import annual_avg_lmp, lmp_table

    df = lmp_table()
    assert (
        (df.rt_load_weighted_avg_lmp_usd_per_mwh / 1_000
         - df.rt_load_weighted_avg_lmp_usd_per_kwh).abs().max() < 1e-9
    )
    assert annual_avg_lmp() == pytest.approx(
        float(df.loc[df.year.idxmax(), "rt_load_weighted_avg_lmp_usd_per_kwh"])
    )


def test_t2_price_requirement_expressed_as_a_multiple():
    s = t2.netting_summary()
    assert s["price_multiple_needed_vs_annual_avg"] == pytest.approx(12.7, abs=0.2)
    assert s["credit_at_annual_avg_covers_share_of_gap"] < 0.10
    assert s["annual_avg_is_a_floor_on_called_hour_price"] is True


def test_synthesis_multiple_is_lower_than_the_unaligned_one():
    """Aligning the bases shrinks the requirement. If aligning ever made it
    harder, the accreditation term has the wrong sign."""
    from phantomload import synthesis

    be = synthesis.breakeven_energy_price()
    assert be["multiple_of_annual_avg_needed"] == pytest.approx(8.5, abs=0.2)
    assert (
        be["multiple_of_annual_avg_needed"]
        < t2.netting_summary()["price_multiple_needed_vs_annual_avg"]
    )


# --- track 1, utility level -------------------------------------------------
def test_aceee_national_footer_reproduces_the_panel():
    """ACEEE's own all-utility totals for 2015 must match the vendored national
    panel. Third independent source agreeing on the same transcription."""
    from phantomload.shared.dr_program import load_eia_panel

    panel = load_eia_panel()
    assert t1.ACEEE_NATIONAL_2015["potential_mw"] == panel.loc[(2015, "total"), "potential_peak_mw"]
    assert t1.ACEEE_NATIONAL_2015["actual_mw"] == panel.loc[(2015, "total"), "actual_peak_mw"]


def test_t1_utility_sample_covers_most_of_national_potential():
    d = t1.utility_dispersion()
    assert d["utilities"] == 28
    assert d["utilities_with_actual"] == 25
    assert 0.60 < d["coverage_share_of_national_potential"] < 0.70


def test_t1_zero_mass_is_the_discriminating_evidence():
    z = t1.zero_mass_test()
    assert z["zero_mass_utilities"] == 5
    assert z["favours_uncalled_for_the_zero_mass"] is True
    assert z["discriminates_above_zero"] is False
    assert z["spread_is_continuous"] is True


def test_t1_missing_actuals_are_not_zeros():
    """Three utilities reported potential and no actual. Treating those as zero
    would inflate the zero mass, which is the evidence this rests on."""
    df = t1.utility_table()
    assert (~df.reported_actual).sum() == 3
    assert df[~df.reported_actual].actual_peak_mw.isna().all()
    assert (df[df.reported_actual].actual_peak_mw == 0).sum() == 5


def test_t1_utility_distribution_is_left_skewed():
    d = t1.utility_dispersion()
    assert d["median_realisation"] < d["mean_realisation"]
    assert d["mw_weighted_realisation"] < 0.40
    assert d["min_realisation"] == 0.0
    assert d["max_realisation"] == 1.0


def test_t3_dlc_impact_is_now_cited():
    """Moved from ASSUMPTION to LITERATURE once the evaluations were read. If it
    reverts, the tension result below is resting on a guess again."""
    from phantomload.shared.calibration import DLC_KW_PER_CUSTOMER
    from phantomload.shared.dr_program import Provenance

    assert DLC_KW_PER_CUSTOMER.provenance is Provenance.LITERATURE
    assert DLC_KW_PER_CUSTOMER.citation
    assert "SDG&E" in DLC_KW_PER_CUSTOMER.citation
    assert DLC_KW_PER_CUSTOMER.central == 0.5
    assert "UNIT WARNING" in DLC_KW_PER_CUSTOMER.note


def test_t3_infeasibility_tension_is_reported_not_resolved():
    t = t3.infeasible_share()
    assert t["observed_exceeds_central_pure_dlc"] is True
    assert t["observed_over_central_pure_dlc"] == pytest.approx(1.28, abs=0.02)
    assert 0.3 < t["share_of_draws_infeasible"] < 0.6
    assert t["repo_can_choose"] is False
    assert set(t["explanations"]) == {"units", "composition", "reporting"}


def test_t3_dlc_floor_survives_the_new_parameters():
    """The one-sided bound must not depend on the old assumed impact range."""
    t = t3.infeasible_share()
    assert t["min_implied_share"] > 0.15


# --- synthesis, accreditation the way the field does it ---------------------
def test_synthesis_elcc_is_cited_and_distinct_from_realisation():
    """ELCC and the realisation rate measure different things. Conflating them
    is the error this correction exists to undo."""
    from phantomload import synthesis
    from phantomload.shared.calibration import DR_ELCC
    from phantomload.shared.dr_program import Provenance

    assert DR_ELCC.provenance is Provenance.LITERATURE
    assert "E3" in DR_ELCC.citation and "SPP" in DR_ELCC.citation
    s = synthesis.elcc_summary()
    assert s["dr_elcc_central"] > s["realisation_ratio_used_elsewhere"]
    assert s["elcc_over_realisation"] == pytest.approx(2.12, abs=0.03)


def test_synthesis_elcc_basis_moves_the_cost_materially():
    from phantomload import synthesis

    s = synthesis.elcc_summary()
    assert s["dr_cost_per_accredited_kw_central"] == pytest.approx(60.71, abs=0.1)
    assert s["accreditation_choice_moves_cost_by"] == pytest.approx(2.12, abs=0.03)
    assert s["dr_cost_per_accredited_kw_central"] < s["dr_cost_per_delivered_kw"]


def test_synthesis_elcc_loses_only_the_winter_case():
    """The one failing cell is track 4's seasonal finding arriving by a third
    route. If it ever stops being the winter case, that convergence is gone."""
    from phantomload import synthesis

    s = synthesis.elcc_summary()
    assert s["dr_wins_cells"] == 5 and s["cells"] == 6
    assert s["worst_case"] == "winter four-hour"
    assert s["dr_wins_all_gross"] is True
    assert s["dr_wins_all_net"] is False


def test_synthesis_elcc_splices_are_declared():
    from phantomload import synthesis
    from phantomload.shared.calibration import DR_ELCC

    assert len(synthesis.elcc_summary()["splices"]) == 2
    assert "SPP-specific" in DR_ELCC.note


def test_t1_bound_matches_the_textbook_rule_of_three():
    """min_window is the exact form of a 1983 result, not a new derivation.
    The textbook 3T approximation must sit within a year of it."""
    for t in (5, 10, 20, 50):
        exact = t1.min_window(t)
        approx = t1.rule_of_three_window(t)
        assert abs(exact - approx) <= 1, (t, exact, approx)
    assert "Hanley" in t1.RULE_OF_THREE_CITATION


# --- the full utility population, 2016 to 2018 ------------------------------
def test_utility_panel_reconciles_to_the_national_panel():
    """Fourth independent source on the same series, first at utility grain.
    Summed utility values must match the national panel to the megawatt."""
    from phantomload.shared.dr_program import load_eia_panel

    panel = load_eia_panel()
    up = t1.utility_panel()
    for year, g in up.groupby("year"):
        assert g.potential_peak_mw.sum() == pytest.approx(
            float(panel.loc[(year, "total"), "potential_peak_mw"]), abs=0.5
        )
        assert g.actual_peak_mw.sum() == pytest.approx(
            float(panel.loc[(year, "total"), "actual_peak_mw"]), abs=0.5
        )


def test_utility_panel_keeps_not_reported_apart_from_zero():
    """The central result depends on this distinction. A blank must never
    become a zero."""
    up = t1.utility_panel()
    assert (up.status == "not_reported").sum() > 0
    assert (up.status == "exact_zero").sum() > 0
    assert up[up.status == "not_reported"].actual_peak_mw.isna().all()
    assert (up[up.status == "exact_zero"].actual_peak_mw == 0).all()


def test_zero_mass_rotates_rather_than_persists():
    s = t1.utility_panel_summary()
    assert s["persist_utilities_reporting_every_year"] == 304
    assert s["persist_zero_every_year"] == 9
    assert s["persist_rotating_share_of_ever_zero_mw"] == pytest.approx(0.787, abs=0.01)
    assert s["persist_favours_uncalled_for_most_zeros"] is True
    assert s["persist_largest_persistent_key"] == "1167_MD"


def test_zero_mass_analysis_refuses_a_degenerate_slice(monkeypatch):
    """The standard: refuse to run rather than produce a degenerate answer."""
    import pandas as pd

    tiny = t1.utility_panel().head(10)
    monkeypatch.setattr(t1, "utility_panel", lambda: tiny)
    with pytest.raises(t1.InsufficientData):
        t1.zero_mass_by_year()


# --- synthesis, headline sweep ----------------------------------------------
def test_headline_survives_its_analyst_choices():
    from phantomload import synthesis

    s = synthesis.headline_sweep_summary()
    assert s["configurations"] == 300
    assert s["headline_6_of_8_holds_every_cost_year"] is True
    assert s["share_of_configurations_where_dr_wins_majority"] > 0.95
    assert s["dr_wins_min"] == 4
    assert "BGE" in s["worst_configuration"]
    assert s["delivery_year_sweep_vacuous"] is False


# --- track 2 cross-check and track 3 denominator ----------------------------
def test_t2_brattle_cross_check_implies_a_modest_premium():
    """Independent route to the netting conclusion. If the implied premium ever
    reached the requirement, the netting bound would no longer hold."""
    x = t2.netting_cross_check()
    assert x["implied_event_hour_price_multiple"] == pytest.approx(2.5, abs=0.1)
    assert x["netting_can_close_the_gap"] is False
    assert x["shortfall_factor"] > 4


def test_t3_denominator_explanation_is_sufficient():
    d = t3.denominator_reconciliation()
    assert d["below_mixed_denominator_benchmark"] is True
    assert d["units_explanation_sufficient"] is True
    assert d["devices_per_customer_at_central"] == pytest.approx(1.28, abs=0.02)


def test_t1_persistence_is_an_effective_sample_size_correction():
    s = t1.persistence_summary()
    assert s["is_an_effective_sample_size_correction"] is True
    assert s["design_effect_at_max_persistence"] == pytest.approx(2.24, abs=0.02)
    assert t1.ar1_effective_size(12, 0.5) == pytest.approx(4.0)


# --- the stranger's single command ------------------------------------------
def test_cli_reproduces_track_one_on_the_repos_own_data(tmp_path):
    """The CLI must give the same answer as the track it packages, or a stranger
    running it on their data is testing something else."""
    import pandas as pd
    from phantomload.__main__ import zero_mass

    up = t1.utility_panel()
    df = up.rename(
        columns={"potential_peak_mw": "potential_mw", "actual_peak_mw": "actual_mw"}
    )[["key", "year", "potential_mw", "actual_mw"]]
    r = zero_mass(df)
    s = t1.utility_panel_summary()
    assert r["entities_reporting_every_year"] == s["persist_utilities_reporting_every_year"]
    assert r["zero_every_year"] == s["persist_zero_every_year"]
    assert r["rotating_share_of_zero_capacity"] == pytest.approx(
        s["persist_rotating_share_of_ever_zero_mw"]
    )


def test_cli_refuses_degenerate_input():
    import pandas as pd
    from phantomload.__main__ import zero_mass

    tiny = pd.DataFrame({"potential_mw": [10, 20, 30], "actual_mw": [0, 5, None]})
    with pytest.raises(SystemExit):
        zero_mass(tiny)


def test_cli_keeps_blank_apart_from_zero():
    import pandas as pd
    from phantomload.__main__ import zero_mass

    n = 30
    df = pd.DataFrame(
        {
            "potential_mw": [10.0] * n,
            "actual_mw": [0.0] * 10 + [None] * 10 + [5.0] * 10,
        }
    )
    r = zero_mass(df)
    assert r["exact_zero_entities"] == 10
    assert r["not_reported_entities"] == 10
