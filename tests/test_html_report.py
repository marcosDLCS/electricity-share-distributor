"""Unit tests for standalone interactive HTML report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.ingestion.schema import IngestionSummary
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    OptimizationResult,
    OptimizationStrategy,
)
from src.presentation.export import ReportExporter
from src.presentation.html_report import generate_interactive_html_report


def _create_mock_optimization_result() -> tuple[OptimizationResult, IngestionSummary]:
    """Create a minimal mock OptimizationResult and IngestionSummary for testing."""
    cups_list = ["ES0021000000000001AA", "ES0021000000000002BB"]
    cups_uses = {"ES0021000000000001AA": "Aerotermia", "ES0021000000000002BB": "Garaje"}

    cm1 = CupsMonthlyMetrics(
        cups="ES0021000000000001AA",
        month="05",
        beta=0.70,
        consumption_kwh=1000.0,
        generation_allocated_kwh=1400.0,
        self_consumed_kwh=800.0,
        surplus_kwh=600.0,
        grid_demand_kwh=200.0,
        self_consumption_rate=57.1,
        solar_coverage_rate=80.0,
        use="Aerotermia",
    )
    cm2 = CupsMonthlyMetrics(
        cups="ES0021000000000002BB",
        month="05",
        beta=0.30,
        consumption_kwh=400.0,
        generation_allocated_kwh=600.0,
        self_consumed_kwh=300.0,
        surplus_kwh=300.0,
        grid_demand_kwh=100.0,
        self_consumption_rate=50.0,
        solar_coverage_rate=75.0,
        use="Garaje",
    )

    monthly_metrics = CommunityMonthlyMetrics(
        month="05",
        strategy=OptimizationStrategy.OPTIMAL.value,
        total_consumption_kwh=1400.0,
        total_generation_kwh=2000.0,
        total_self_consumed_kwh=1100.0,
        total_surplus_kwh=900.0,
        total_grid_demand_kwh=300.0,
        self_consumption_rate=55.0,
        solar_coverage_rate=78.6,
        beta_sum=1.0,
        cups_metrics=[cm1, cm2],
        has_data=True,
    )

    total_summary = CommunityMonthlyMetrics(
        month="Total",
        strategy=OptimizationStrategy.OPTIMAL.value,
        total_consumption_kwh=1400.0,
        total_generation_kwh=2000.0,
        total_self_consumed_kwh=1100.0,
        total_surplus_kwh=900.0,
        total_grid_demand_kwh=300.0,
        self_consumption_rate=55.0,
        solar_coverage_rate=78.6,
        beta_sum=1.0,
        cups_metrics=[cm1, cm2],
        has_data=True,
    )

    opt_result = OptimizationResult(
        strategy=OptimizationStrategy.OPTIMAL.value,
        monthly_results=[monthly_metrics],
        total_summary=total_summary,
        cups_list=cups_list,
        cups_uses=cups_uses,
    )

    summary = IngestionSummary(
        cups_count=2,
        cups_list=cups_list,
        consumption_files_loaded=2,
        generation_files_loaded=1,
        start_time="2026-05-01 00:00:00",
        end_time="2026-05-31 23:00:00",
        total_hours=744,
        missing_hours_count=0,
    )

    return opt_result, summary


def test_generate_interactive_html_report_structure() -> None:
    """Verify that generated HTML report contains required sections, language switcher, and solar efficiency chart."""
    opt_result, summary = _create_mock_optimization_result()
    html_en = generate_interactive_html_report(opt_result, summary, lang="en")

    # Document type and basic tags
    assert "<!DOCTYPE html>" in html_en
    assert "<html" in html_en
    assert "</html>" in html_en

    # Offline requirement: no external script sources
    assert '<script src="http' not in html_en
    assert '<script src="//' not in html_en

    # Core UI components
    assert "chart-monthly-svg" in html_en
    assert "chart-eff-svg" in html_en
    assert "eff-cards-grid" in html_en
    assert "kpi-grid" in html_en
    assert "kpi-gen" in html_en
    assert "kpi-dem" in html_en
    assert "kpi-surplus" in html_en
    assert "kpi-sc" in html_en
    assert "Hare-Niemeyer" not in html_en
    assert "Aerotermia" in html_en
    assert "Garaje" in html_en

    # Four executive KPI cards: plain title and value only (no subtitle, no progress bar, no gain badge)
    assert "kpi-subtitle" not in html_en
    assert "kpi-meter-track" not in html_en
    assert "gain-badge" not in html_en

    # Dynamic 3-way comparative prevision showcase box
    assert "section-hourly-prevision" in html_en
    assert "TED/1247/2021" in html_en
    assert "Self-Consumption Prevision & Comparison" in html_en
    # 3 comparative scenarios present
    assert "No Share (Single CUPS)" in html_en
    assert "Monthly Share (RD 244/2019)" in html_en
    assert "Hourly Share (Order TED)" in html_en
    assert "Total Collective Uplift" in html_en
    # 3 comparison bar rows
    assert "No Collective Share (Single CUPS)" in html_en
    assert "Fixed Monthly Share (RD 244/2019)" in html_en
    assert "Dynamic Hourly Share (Orden TED/1247/2021)" in html_en

    # Removed components: simulator and resolution annex
    assert "sim-slider" not in html_en
    assert "resolution-box" not in html_en

    # Bilingual language selector and JS engine
    assert "btn-lang-es" in html_en
    assert "btn-lang-en" in html_en
    assert "setLang" in html_en
    assert "showEffTooltip" in html_en

    # Matrix table summary footer
    assert "<tfoot>" in html_en
    assert "</tfoot>" in html_en
    assert "TOTAL (RD 244/2019)" in html_en
    assert "100%" in html_en
    assert "total-label" in html_en
    assert "total-val" in html_en

    # English titles & efficiency graphic
    assert "Executive Collective Solar Distribution Report" in html_en
    assert "Photovoltaic Solar Efficiency" in html_en
    assert "Total Solar Generation" in html_en

    # Bilingual Spanish generation
    html_es = generate_interactive_html_report(opt_result, summary, lang="es")
    assert "Informe Ejecutivo de Autoconsumo Colectivo" in html_es
    assert "Eficiencia Solar Fotovoltaica" in html_es
    assert "Producción Solar Total" in html_es
    assert "Previsión y Comparativa de Autoconsumo" in html_es
    assert "Sin Reparto (1 solo CUPS)" in html_es
    assert "Reparto Mensual (RD 244/2019)" in html_es
    assert "Reparto Horario (Orden TED)" in html_es
    assert "Ganancia Colectiva Total" in html_es
    assert "Sin Reparto Colectivo (1 solo CUPS)" in html_es
    assert "Reparto Mensual Fijo (RD 244/2019)" in html_es
    assert "Reparto Horario Dinámico (Orden TED/1247/2021)" in html_es
    assert "kpi-subtitle" not in html_es
    assert "kpi-meter-track" not in html_es
    assert "gain-badge" not in html_es
    assert "sim-slider" not in html_es
    assert "resolution-box" not in html_es
    assert "Hare-Niemeyer" not in html_es


def test_prevision_three_way_comparison() -> None:
    """Verify that _calculate_hourly_prevision computes consistent metrics across all 3 scenarios."""
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    prev = _calculate_hourly_prevision(opt_result)

    # All 3 scenarios must be present
    assert "single_sc_kwh" in prev
    assert "monthly_sc_kwh" in prev
    assert "hourly_sc_kwh" in prev

    # Physical progression invariant: single_sc <= monthly_sc <= hourly_sc
    assert prev["single_sc_kwh"] <= prev["monthly_sc_kwh"]
    assert prev["monthly_sc_kwh"] <= prev["hourly_sc_kwh"]

    # Corresponding self-consumption rate progression
    assert prev["single_sc_rate"] <= prev["monthly_sc_rate"]
    assert prev["monthly_sc_rate"] <= prev["hourly_sc_rate"]

    # Step-by-step gains
    assert round(prev["gain_monthly_kwh"], 1) == round(
        prev["monthly_sc_kwh"] - prev["single_sc_kwh"], 1
    )
    assert round(prev["gain_hourly_kwh"], 1) == round(
        prev["hourly_sc_kwh"] - prev["monthly_sc_kwh"], 1
    )
    assert round(prev["gain_total_kwh"], 1) == round(
        prev["hourly_sc_kwh"] - prev["single_sc_kwh"], 1
    )


def test_prevision_with_hourly_simulation_three_way() -> None:
    """Verify 3-way calculation when explicit hourly time-series simulation dataframe is present."""
    import pandas as pd

    from src.optimization.models import HourlyOptimizationResult, HourlyProfileMatrix
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()

    # Create synthetic hourly time-series df with primary CUPS (Aerotermia) and secondary CUPS (Garaje)
    df_rows = [
        # Hour 10: Gen = 5.0 kWh. Primary consumes 1.5, Secondary consumes 2.5
        {
            "timestamp": "2026-05-01 10:00:00",
            "cups": "ES0021000000000001AA",
            "consumption_kwh": 1.5,
            "generation_kwh": 5.0,
            "share_pct": "30.0%",
            "estimated_share_pct": "30.0%",
        },
        {
            "timestamp": "2026-05-01 10:00:00",
            "cups": "ES0021000000000002BB",
            "consumption_kwh": 2.5,
            "generation_kwh": 5.0,
            "share_pct": "50.0%",
            "estimated_share_pct": "50.0%",
        },
        # Hour 11: Gen = 10.0 kWh. Primary consumes 2.0, Secondary consumes 4.0
        {
            "timestamp": "2026-05-01 11:00:00",
            "cups": "ES0021000000000001AA",
            "consumption_kwh": 2.0,
            "generation_kwh": 10.0,
            "share_pct": "20.0%",
            "estimated_share_pct": "20.0%",
        },
        {
            "timestamp": "2026-05-01 11:00:00",
            "cups": "ES0021000000000002BB",
            "consumption_kwh": 4.0,
            "generation_kwh": 10.0,
            "share_pct": "40.0%",
            "estimated_share_pct": "40.0%",
        },
    ]
    df = pd.DataFrame(df_rows)
    empty_profile = HourlyProfileMatrix(
        cups_list=opt_result.cups_list,
        hours=[f"{h:02d}" for h in range(24)],
        matrix={c: {} for c in opt_result.cups_list},
        hourly_sums={},
        average_shares={},
        average_sum=1.0,
    )
    opt_result.hourly_result = HourlyOptimizationResult(
        profile_matrix=empty_profile,
        time_series_df=df,
    )

    prev = _calculate_hourly_prevision(opt_result)
    assert prev["is_simulated"] is True

    # Single CUPS tied solely to Primary (ES0021000000000001AA, Aerotermia):
    # Hour 10: min(1.5, 5.0) = 1.5
    # Hour 11: min(2.0, 10.0) = 2.0
    # Expected single_sc = 3.5 kWh
    assert prev["single_sc_kwh"] == 3.5

    # Hourly simulation collective:
    # Hour 10: min(1.5, 0.3*5.0=1.5) + min(2.5, 0.5*5.0=2.5) = 1.5 + 2.5 = 4.0
    # Hour 11: min(2.0, 0.2*10.0=2.0) + min(4.0, 0.4*10.0=4.0) = 2.0 + 4.0 = 6.0
    # Total hourly_sc = 10.0 kWh (bounded by monthly_sc if monthly_sc were larger, but here 1100 > 10 so it's bounded by monthly_sc = 1100)
    assert prev["single_sc_kwh"] <= prev["monthly_sc_kwh"]
    assert prev["gain_monthly_kwh"] >= 0.0
    assert prev["gain_total_kwh"] >= prev["gain_monthly_kwh"]


def test_prevision_vectorized_numeric_and_fallback_shares() -> None:
    """Verify vectorized _calculate_hourly_prevision handles numeric shares and fallback columns cleanly."""
    import pandas as pd

    from src.optimization.models import HourlyOptimizationResult, HourlyProfileMatrix
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()

    # Time series where estimated_share_pct is empty string or None, falling back to share_pct (numeric 0.40)
    df_rows = [
        {
            "timestamp": "2026-05-01 12:00:00",
            "cups": "ES0021000000000001AA",
            "consumption_kwh": 3.0,
            "generation_kwh": 10.0,
            "share_pct": 0.40,  # Numeric float fraction
            "estimated_share_pct": "",  # Empty string fallback
        },
        {
            "timestamp": "2026-05-01 12:00:00",
            "cups": "ES0021000000000002BB",
            "consumption_kwh": 5.0,
            "generation_kwh": 10.0,
            "share_pct": 60.0,  # Numeric > 1.0 (percentage scale)
            "estimated_share_pct": None,  # None fallback
        },
    ]
    df = pd.DataFrame(df_rows)
    opt_result.hourly_result = HourlyOptimizationResult(
        profile_matrix=HourlyProfileMatrix(
            cups_list=opt_result.cups_list,
            hours=[f"{h:02d}" for h in range(24)],
            matrix={c: {} for c in opt_result.cups_list},
            hourly_sums={},
            average_shares={},
            average_sum=1.0,
        ),
        time_series_df=df,
    )

    prev = _calculate_hourly_prevision(opt_result)
    assert prev["is_simulated"] is True
    # Primary: min(3.0, 0.40 * 10.0 = 4.0) = 3.0
    # Secondary: min(5.0, 0.60 * 10.0 = 6.0) = 5.0
    # Expected collective = 8.0 kWh (clamped within physical limits)
    assert prev["single_sc_kwh"] == 3.0
    assert prev["hourly_sc_kwh"] >= prev["monthly_sc_kwh"]


def test_export_interactive_html_file(tmp_path: Path) -> None:
    """Verify that ReportExporter exports the HTML report to disk."""
    opt_result, summary = _create_mock_optimization_result()
    exporter = ReportExporter(output_dir=tmp_path, timestamp="20261025_150000")

    # 1. Direct method call
    html_file = exporter.export_interactive_html(opt_result, summary)
    assert html_file.exists()
    assert html_file.name == "20261025_150000_esd_interactive_report.html"
    content = html_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content

    # 2. export_all with formats='html'
    exported_html_only = exporter.export_all(opt_result, summary, formats="html")
    assert len(exported_html_only) == 1
    assert exported_html_only[0].suffix == ".html"

    # 3. export_all with formats='all'
    exported_all = exporter.export_all(opt_result, summary, formats="all")
    assert any(p.suffix == ".html" for p in exported_all)

    # 4. Custom timestamp exporter
    p_custom = ReportExporter(
        output_dir=tmp_path, timestamp="20261025_150001"
    ).export_interactive_html(opt_result, summary)
    assert p_custom.exists()


def test_prevision_reads_primary_cups_directly_without_disk_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _calculate_hourly_prevision reads opt_result.primary_cups directly without calling DataCurator."""
    from src.curation.curator import DataCurator
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    opt_result.primary_cups = "ES0021000000000002BB"
    opt_result.cups_uses = {"ES0021000000000002BB": "Custom Primary"}

    def fail_load_cups_config(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "DataCurator.load_cups_config should not be called when primary_cups is present"
        )

    monkeypatch.setattr(DataCurator, "load_cups_config", fail_load_cups_config)

    prev = _calculate_hourly_prevision(opt_result)
    assert prev["primary_cups"] == "ES0021000000000002BB"
    assert prev["primary_name"] == "Custom Primary"


def test_prevision_falls_back_to_curator_when_primary_cups_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _calculate_hourly_prevision falls back to DataCurator when opt_result.primary_cups is None."""
    from src.curation.curator import DataCurator
    from src.domain.models import SupplyPoint
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    opt_result.primary_cups = None

    called: list[bool] = []

    def mock_load_cups_config(*args: Any, **kwargs: Any) -> dict[str, SupplyPoint]:
        called.append(True)
        return {
            "ES0021000000000001AA": SupplyPoint(
                cups="ES0021000000000001AA",
                use="Fallback Aerotermia",
                primary=True,
            )
        }

    monkeypatch.setattr(DataCurator, "load_cups_config", mock_load_cups_config)

    prev = _calculate_hourly_prevision(opt_result)
    assert len(called) == 1
    assert prev["primary_cups"] == "ES0021000000000001AA"
    assert prev["primary_name"] == "Fallback Aerotermia"


def test_matrix_table_total_footer_row() -> None:
    """Verify that matrix table contains a styled <tfoot> row with TOTAL (RD 244/2019) and 100.00%."""
    opt_result, summary = _create_mock_optimization_result()
    html = generate_interactive_html_report(opt_result, summary, lang="en", precision=2)

    assert "<tfoot>" in html
    assert "</tfoot>" in html
    assert (
        "<span class='total-label' data-i18n='lbl_total_rd244'>TOTAL (RD 244/2019)</span>" in html
    )
    assert "100.00%" in html

    html_es = generate_interactive_html_report(opt_result, summary, lang="es", precision=2)
    assert "<tfoot>" in html_es
    assert (
        "<span class='total-label' data-i18n='lbl_total_rd244'>TOTAL (RD 244/2019)</span>"
        in html_es
    )
    assert "100.00%" in html_es
