"""Data-layer tests. These guard the transcription and the registry schema."""

from __future__ import annotations

import pandas as pd
import pytest

from phantomload.shared.dr_program import (
    SECTORS,
    Provenance,
    ProgramType,
    load_eia_panel,
    registry,
    synthetic_program,
    to_frame,
)

# EIA aggregates its own published totals with rounding, so sector sums differ
# from the printed total by a few units in a handful of cells. Anything larger
# than this is a transcription error, not rounding.
SUM_TOLERANCE_ABS = 10
SUM_TOLERANCE_REL = 1e-5


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return load_eia_panel()


def test_panel_shape(panel):
    years = panel.index.get_level_values("year").unique()
    assert years.min() == 2013 and years.max() == 2024
    assert len(years) == 12
    assert set(panel.index.get_level_values("sector").unique()) == set(SECTORS) | {"total"}


def test_all_six_metrics_present(panel):
    expected = {
        "customers_enrolled",
        "energy_savings_mwh",
        "potential_peak_mw",
        "actual_peak_mw",
        "customer_incentives_kusd",
        "other_costs_kusd",
    }
    assert expected <= set(panel.columns)


def test_sector_values_sum_to_published_total(panel):
    """Ingest guard. Catches a mistyped digit anywhere in the transcription."""
    bad = []
    for metric in panel.columns:
        for year in panel.index.get_level_values("year").unique():
            block = panel.xs(year, level="year")[metric]
            total = block.get("total")
            if pd.isna(total):
                continue
            parts = block.reindex(list(SECTORS)).dropna().sum()
            gap = abs(parts - total)
            if gap > SUM_TOLERANCE_ABS and gap / total > SUM_TOLERANCE_REL:
                bad.append((metric, year, parts, total))
    assert not bad, f"sector sums off published totals: {bad}"


@pytest.mark.parametrize(
    "year,sector,metric,expected",
    [
        # spot pins straight off the published tables
        (2024, "total", "potential_peak_mw", 31_491),
        (2024, "total", "actual_peak_mw", 12_322),
        (2013, "total", "potential_peak_mw", 27_095),
        (2013, "total", "actual_peak_mw", 11_883),
        (2022, "industrial", "actual_peak_mw", 6_613),
        (2016, "commercial", "potential_peak_mw", 11_053),
        (2024, "residential", "other_costs_kusd", 262_017),
        (2024, "industrial", "customer_incentives_kusd", 602_656),
        (2023, "total", "energy_savings_mwh", 407_255),
        (2020, "total", "customers_enrolled", 11_665_663),
    ],
)
def test_transcription_pins(panel, year, sector, metric, expected):
    assert panel.loc[(year, sector), metric] == expected


def test_cost_years_are_2015_onwards(panel):
    """EIA publishes DR program costs only from 2015. 2013-14 must stay blank
    rather than being filled with a zero that would deflate cost per kW."""
    for year in (2013, 2014):
        assert pd.isna(panel.loc[(year, "total"), "customer_incentives_kusd"])
        assert pd.isna(panel.loc[(year, "total"), "other_costs_kusd"])


def test_double_dash_is_nan_not_zero(panel):
    """Transportation drops out of the table in several years. If those became
    zeros, sector shares and any per-sector mean would silently shift."""
    assert pd.isna(panel.loc[(2019, "transportation"), "potential_peak_mw"])
    assert panel.loc[(2015, "transportation"), "potential_peak_mw"] == 14


def test_no_negative_values(panel):
    numeric = panel.select_dtypes("number")
    assert (numeric.fillna(0) >= 0).all().all()


def test_actual_never_exceeds_potential(panel):
    both = panel[["potential_peak_mw", "actual_peak_mw"]].dropna()
    assert (both.actual_peak_mw <= both.potential_peak_mw).all()


def test_registry_excludes_totals_by_default():
    rows = registry()
    assert rows
    assert all(r.sector != "total" for r in rows)
    assert any(r.sector == "total" for r in registry(include_total=True))


def test_registry_rows_are_measured_and_lack_dispatch_data():
    """The absence of dispatch events is the repo's central data fact. If a
    loader ever starts filling it, track 1's argument has to change."""
    for row in registry():
        assert row.provenance is Provenance.MEASURED
        assert row.program_type is ProgramType.UNKNOWN
        assert row.dispatch_events is None
        assert row.event_hours is None
        assert row.granularity == "national_by_sector"


def test_program_year_derived_properties():
    row = next(r for r in registry() if r.sector == "residential" and r.year == 2024)
    assert row.utilization == pytest.approx(4785 / 9706)
    assert row.total_cost_kusd == pytest.approx(273_346 + 262_017)


def test_synthetic_program_cannot_claim_measured():
    p = synthetic_program(
        year=2024,
        sector="residential",
        program_type=ProgramType.DIRECT_LOAD_CONTROL,
        enrolled_mw=10.0,
        verified_mw=4.0,
        provenance=Provenance.MEASURED,  # ignored on purpose
    )
    assert p.provenance is Provenance.SIMULATED


def test_to_frame_serialises_enums():
    df = to_frame(registry())
    assert df.provenance.unique().tolist() == ["measured"]
    assert df.program_type.unique().tolist() == ["unknown"]
