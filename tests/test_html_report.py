"""Unit tests for standalone interactive HTML report generation."""

from __future__ import annotations

from pathlib import Path

from src.ingestion.schema import IngestionSummary
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    OptimizationResult,
    OptimizationStrategy,
)
from src.presentation.export import ReportExporter, export_interactive_html
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

    # Dynamic hourly shares distribution prevision box
    assert "section-hourly-prevision" in html_en
    assert "TED/1247/2021" in html_en
    assert "Prevision with Dynamic Hourly Coefficients" in html_en

    # Removed components: simulator and resolution annex
    assert "sim-slider" not in html_en
    assert "resolution-box" not in html_en

    # Bilingual language selector and JS engine
    assert "btn-lang-es" in html_en
    assert "btn-lang-en" in html_en
    assert "setLang" in html_en
    assert "showEffTooltip" in html_en

    # English titles & efficiency graphic
    assert "Executive Collective Solar Distribution Report" in html_en
    assert "Photovoltaic Solar Efficiency" in html_en
    assert "Total Solar Generation" in html_en

    # Bilingual Spanish generation
    html_es = generate_interactive_html_report(opt_result, summary, lang="es")
    assert "Informe Ejecutivo de Autoconsumo Colectivo" in html_es
    assert "Eficiencia Solar Fotovoltaica" in html_es
    assert "Producción Solar Total" in html_es
    assert "Previsión con Coeficientes Horarios Dinámicos" in html_es
    assert "sim-slider" not in html_es
    assert "resolution-box" not in html_es
    assert "Hare-Niemeyer" not in html_es


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

    # 4. Standalone export function
    p_standalone = export_interactive_html(
        opt_result, summary, output_dir=tmp_path, timestamp="20261025_150001"
    )
    assert p_standalone.exists()
