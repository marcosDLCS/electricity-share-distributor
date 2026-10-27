"""Unit tests for presentation layer, formatting, and terminal view helpers."""

from __future__ import annotations

from src.presentation.views.matrix import _format_heatmap_cell
from src.presentation.views.trajectory import SPARK_BLOCKS, _coverage_sparkline


def test_format_heatmap_cell_styling() -> None:
    """Verify that _format_heatmap_cell applies proper color intensities."""
    # None or dash
    assert _format_heatmap_cell(None, "—") == "[dim]—[/dim]"

    # 0% to 5% -> dim white
    res_zero = _format_heatmap_cell(0.0, "0.0%")
    assert "[dim white]0.0%[/dim white]" in res_zero

    res_five = _format_heatmap_cell(0.05, "5.0%")
    assert "[dim white]5.0%[/dim white]" in res_five

    # 6% to 20% -> bright_cyan
    res_ten = _format_heatmap_cell(0.10, "10.0%")
    assert "[bright_cyan]10.0%[/bright_cyan]" in res_ten

    # 21% to 50% -> bright_yellow
    res_thirty = _format_heatmap_cell(0.35, "35.0%")
    assert "[bright_yellow]35.0%[/bright_yellow]" in res_thirty

    # > 50% -> bold bright_green
    res_seventy = _format_heatmap_cell(0.75, "75.0%")
    assert "[bold bright_green]75.0%[/bold bright_green]" in res_seventy


def test_coverage_sparkline_rendering() -> None:
    """Verify that _coverage_sparkline generates correct block sparklines."""
    # Zero or negative coverage
    assert _coverage_sparkline(0.0) == "[dim]░░░░░[/dim]"
    assert _coverage_sparkline(-5.0) == "[dim]░░░░░[/dim]"

    # Low coverage (< 20%) -> cyan
    spark_low = _coverage_sparkline(15.0)
    assert "[cyan]" in spark_low
    assert "░" in spark_low

    # Medium coverage (20% - 49%) -> bright_yellow
    spark_mid = _coverage_sparkline(30.0)
    assert "[bright_yellow]" in spark_mid

    # High coverage (>= 50%) -> bold bright_green
    spark_high = _coverage_sparkline(80.0)
    assert "[bold bright_green]" in spark_high

    # Ensure SPARK_BLOCKS are valid unicode
    assert len(SPARK_BLOCKS) == 8


def test_render_community_summary_output() -> None:
    """Verify that render_community_summary renders 6 energy KPIs and 3-way progression."""
    from src.ingestion.schema import IngestionSummary
    from src.optimization.models import CommunityMonthlyMetrics, OptimizationResult
    from src.presentation.console import console
    from src.presentation.views.summary import render_community_summary

    summary = IngestionSummary(
        cups_count=2,
        cups_list=["ES0021000000000001AA", "ES0021000000000002BB"],
        consumption_files_loaded=2,
        generation_files_loaded=1,
        start_time="2026-05-01 00:00:00",
        end_time="2026-05-31 23:00:00",
        total_hours=744,
        missing_hours_count=0,
    )

    tot = CommunityMonthlyMetrics(
        month="Total",
        strategy="optimal",
        total_consumption_kwh=1500.0,
        total_generation_kwh=2000.0,
        solar_hours_generation_kwh=2000.0,
        solar_hours_consumption_kwh=1200.0,
        total_self_consumed_kwh=1100.0,
        total_surplus_kwh=900.0,
        total_grid_demand_kwh=400.0,
        self_consumption_rate=55.0,
        solar_coverage_rate=73.3,
        solar_hours_coverage_rate=91.7,
        beta_sum=1.0,
        cups_metrics=[],
        has_data=True,
    )

    opt_result = OptimizationResult(
        strategy="optimal",
        monthly_results=[tot],
        total_summary=tot,
        cups_list=summary.cups_list,
        cups_uses={"ES0021000000000001AA": "Aerotermia", "ES0021000000000002BB": "Garaje"},
        current_self_consumed_kwh=800.0,
        monthly_share_self_consumed_kwh=1100.0,
        hourly_share_self_consumed_kwh=1250.0,
    )

    with console.capture() as capture:
        render_community_summary(summary, tot, lang="en", opt_result=opt_result)

    output = capture.get()
    # Check 6 core energy KPIs
    assert "2,000.00 kWh" in output
    assert "1,500.00 kWh" in output
    assert "1,200.00 kWh" in output
    assert "1,100.00 kWh" in output
    assert "900.00 kWh" in output
    # Check 3-way progression table
    assert "Current (No Share)" in output
    assert "Monthly Share (RD 244/2019)" in output
    assert "Hourly Share (Order TED)" in output
    assert "800.0" in output
    assert "1,100.0" in output
    assert "1,250.0" in output
