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
