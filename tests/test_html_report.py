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

    # Dynamic 4-way comparative prevision showcase box
    assert "section-hourly-prevision" in html_en
    assert "TED/1247/2021" in html_en
    assert "Self-Consumption Prevision & Comparison" in html_en
    # All 4 comparative scenarios + uplift card present
    assert "No Share (Single CUPS)" in html_en
    assert "Monthly Share (RD 244/2019)" in html_en
    assert "Fortnight Share (24 Periods)" in html_en
    assert "Hourly Share (Order TED)" in html_en
    assert "Total Collective Uplift" in html_en
    # 4 comparison bar rows
    assert "No Collective Share (Single CUPS)" in html_en
    assert "Fixed Monthly Share (RD 244/2019)" in html_en
    assert "Fortnight Share (24 Half-Month Periods)" in html_en
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
    assert "Reparto Quincenal (24 Quincenas)" in html_es
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


def test_prevision_four_way_progression_fallback_and_ordering() -> None:
    """Verify _calculate_hourly_prevision computes monotonic 4-way fallback metrics when optional fields are 0."""
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    prev = _calculate_hourly_prevision(opt_result)

    assert prev["single_sc_kwh"] == 800.0
    assert prev["monthly_sc_kwh"] == 1100.0
    assert prev["fortnight_sc_kwh"] == 1100.0
    assert prev["hourly_sc_kwh"] == 1100.0
    assert prev["has_fortnight"] is False
    assert prev["is_simulated"] is False

    # Physical progression invariant: single <= monthly <= fortnight <= hourly
    assert prev["single_sc_kwh"] <= prev["monthly_sc_kwh"]
    assert prev["monthly_sc_kwh"] <= prev["fortnight_sc_kwh"]
    assert prev["fortnight_sc_kwh"] <= prev["hourly_sc_kwh"]

    assert prev["single_sc_rate"] <= prev["monthly_sc_rate"]
    assert prev["monthly_sc_rate"] <= prev["fortnight_sc_rate"]
    assert prev["fortnight_sc_rate"] <= prev["hourly_sc_rate"]

    # Step-by-step and cumulative gains
    assert round(prev["gain_monthly_kwh"], 1) == round(
        prev["monthly_sc_kwh"] - prev["single_sc_kwh"], 1
    )
    assert round(prev["gain_fortnight_kwh"], 1) == round(
        prev["fortnight_sc_kwh"] - prev["single_sc_kwh"], 1
    )
    assert round(prev["gain_hourly_kwh"], 1) == round(
        prev["hourly_sc_kwh"] - prev["monthly_sc_kwh"], 1
    )
    assert round(prev["gain_total_kwh"], 1) == round(
        prev["hourly_sc_kwh"] - prev["single_sc_kwh"], 1
    )


def test_prevision_reads_four_way_metrics_directly_from_opt_result() -> None:
    """Verify _calculate_hourly_prevision reads 4-way kWh directly without re-parsing time_series_df strings."""
    import pandas as pd

    from src.optimization.models import HourlyOptimizationResult, HourlyProfileMatrix
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    opt_result.current_self_consumed_kwh = 720.0
    opt_result.monthly_share_self_consumed_kwh = 1100.0
    opt_result.fortnight_share_self_consumed_kwh = 1240.0
    opt_result.hourly_share_self_consumed_kwh = 1360.0

    # Inject deliberately conflicting formatted strings in time_series_df to verify they are NOT re-parsed
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-05-01 12:00:00",
                "cups": "ES0021000000000001AA",
                "consumption_kwh": "1,0",
                "generation_kwh": "10,0",
                "share_pct": "1.0%",
                "estimated_share_pct": "1.0%",
            }
        ]
    )
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
    assert prev["has_fortnight"] is True
    assert prev["is_simulated"] is True
    assert prev["single_sc_kwh"] == 720.0
    assert prev["monthly_sc_kwh"] == 1100.0
    assert prev["fortnight_sc_kwh"] == 1240.0
    assert prev["hourly_sc_kwh"] == 1360.0

    # Exact self-consumption rates against 2,000 kWh generation: 36%, 55%, 62%, 68%
    assert prev["single_sc_rate"] == 36.0
    assert prev["monthly_sc_rate"] == 55.0
    assert prev["fortnight_sc_rate"] == 62.0
    assert prev["hourly_sc_rate"] == 68.0

    # Step gains
    assert prev["gain_monthly_kwh"] == 380.0
    assert prev["gain_fortnight_kwh"] == 520.0
    assert prev["gain_fortnight_vs_monthly_kwh"] == 140.0
    assert prev["gain_hourly_kwh"] == 260.0
    assert prev["gain_total_kwh"] == 640.0


def test_html_i18n_dictionary_parity() -> None:
    """Verify unified EN/ES HTML report dictionary has complete top-level and month key parity."""
    from src.presentation.html_report import _build_html_i18n

    catalog = _build_html_i18n(version="2026.11.018")
    assert set(catalog.keys()) == {"es", "en"}
    assert set(catalog["es"].keys()) == set(catalog["en"].keys())
    assert set(catalog["es"]["months"].keys()) == set(catalog["en"]["months"].keys())
    assert set(catalog["es"]["months_full"].keys()) == set(catalog["en"]["months_full"].keys())
    assert "2026.11.018" in catalog["es"]["footer_text"]
    assert "2026.11.018" in catalog["en"]["footer_text"]


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


def test_prevision_no_disk_read_or_keyword_heuristic_when_primary_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _calculate_hourly_prevision never reads cups.json or uses keyword heuristics when primary_cups is None."""
    from src.curation.curator import DataCurator
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    opt_result.primary_cups = None
    # Put keyword-like name on the second CUPS to prove keyword heuristics are absent
    opt_result.cups_uses = {
        "ES0021000000000001AA": "Garaje",
        "ES0021000000000002BB": "Aerotermia Principal",
    }

    def fail_load_cups_config(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("DataCurator.load_cups_config must not be called by html_report")

    monkeypatch.setattr(DataCurator, "load_cups_config", fail_load_cups_config)

    prev = _calculate_hourly_prevision(opt_result)
    assert prev["primary_cups"] == "ES0021000000000001AA"
    assert prev["primary_name"] == "Garaje"


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
