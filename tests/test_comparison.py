"""Automated unit, chart, service, view, and CLI tests for multi-year comparison (esd compare)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.analytics import ConsumptionAggregator
from src.cli import app
from src.domain.exceptions import EsdError, ValidationError
from src.presentation.charts import generate_all_comparison_charts
from src.presentation.console import console
from src.presentation.views.comparison import (
    render_comparison_overview,
    render_cups_comparison_table,
    render_monthly_comparison_table,
)
from src.services import ComparisonRequest, ComparisonService, parse_years_option
from src.version import get_version


def _build_month_rows(
    cups: str,
    year: int,
    month: int,
    days: int,
    daily_kwh: float,
) -> list[dict[str, object]]:
    """Build synthetic daily consumption records for a calendar month."""
    return [
        {
            "cups": cups,
            "timestamp": f"{year:04d}-{month:02d}-{day:02d} 12:00:00",
            "consumption_kwh": daily_kwh,
        }
        for day in range(1, days + 1)
    ]


def _write_month_csv(
    path: Path,
    entries: list[tuple[str, int, int, int, float]],
) -> None:
    """Write synthetic DATADIS CSV files for multi-year comparison tests."""
    lines = ["cups;fecha;hora;consumo_kWh"]
    for cups, year, month, days, daily_kwh in entries:
        val_str = f"{daily_kwh:.2f}".replace(".", ",")
        for day in range(1, days + 1):
            lines.append(f"{cups};{year:04d}/{month:02d}/{day:02d};12:00;{val_str}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_compare_years_calendar_completeness_and_leap_year() -> None:
    """Enforce leap-year Feb completeness and apples-to-apples exclusion of incomplete months."""
    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"

    rows: list[dict[str, object]] = []
    # Jan: complete in both 2024 (31d) and 2025 (31d) -> c1 drops 310 -> 155, c2 rises 155 -> 217 (total 465 -> 372, -20%)
    rows.extend(_build_month_rows(c1, 2024, 1, 31, 10.0))
    rows.extend(_build_month_rows(c2, 2024, 1, 31, 5.0))
    rows.extend(_build_month_rows(c1, 2025, 1, 31, 5.0))
    rows.extend(_build_month_rows(c2, 2025, 1, 31, 7.0))

    # Feb: leap year 2024 (29d) and non-leap 2025 (28d) -> both complete! Total 290 -> 308 (+18 kWh)
    rows.extend(_build_month_rows(c1, 2024, 2, 29, 8.0))
    rows.extend(_build_month_rows(c2, 2024, 2, 29, 2.0))
    rows.extend(_build_month_rows(c1, 2025, 2, 28, 7.0))
    rows.extend(_build_month_rows(c2, 2025, 2, 28, 4.0))

    # Mar: 2024 complete (31d), 2025 incomplete (15d) -> excluded
    rows.extend(_build_month_rows(c1, 2024, 3, 31, 10.0))
    rows.extend(_build_month_rows(c1, 2025, 3, 15, 20.0))

    # Apr: only 2024 (30d), no_data in 2025 -> excluded
    rows.extend(_build_month_rows(c1, 2024, 4, 30, 10.0))

    df = pd.DataFrame(rows)
    uses = {c1: "Aerotermia", c2: "Garaje"}

    comp = ConsumptionAggregator.compare_years(df, cups_uses=uses)
    assert comp.years == [2024, 2025]
    assert comp.comparable_months == [1, 2]
    assert comp.excluded_months == [3, 4]

    # Comparable totals reflect strictly Jan + Feb: 2024 = 465 + 290 = 755; 2025 = 372 + 308 = 680
    assert comp.comparable_annual_totals[2024] == pytest.approx(755.0)
    assert comp.comparable_annual_totals[2025] == pytest.approx(680.0)
    assert comp.total_diff_kwh == pytest.approx(-75.0)
    assert comp.total_pct_change == pytest.approx(-75.0 / 755.0 * 100.0)

    # Raw annual totals include Mar/Apr
    assert comp.annual_totals[2024] == pytest.approx(755.0 + 310.0 + 300.0)
    assert comp.annual_totals[2025] == pytest.approx(680.0 + 300.0)

    month_by_num = {m.month: m for m in comp.monthly_comparisons}
    assert month_by_num[1].is_complete is True
    assert month_by_num[2].is_complete is True
    assert month_by_num[2].year_days == {2024: (29, 29), 2025: (28, 28)}
    assert month_by_num[3].is_complete is False
    assert month_by_num[3].year_status == {2024: "complete", 2025: "incomplete"}
    assert month_by_num[3].diff_kwh is None
    assert month_by_num[4].year_status == {2024: "complete", 2025: "no_data"}
    assert month_by_num[4].diff_kwh is None

    assert comp.max_decrease_month is not None and comp.max_decrease_month.month == 1
    assert comp.max_increase_month is not None and comp.max_increase_month.month == 2

    # CUPS shifts evaluated over Jan+Feb:
    # c1: 2024 = 310+232 = 542 -> 2025 = 155+196 = 351 (diff -191)
    # c2: 2024 = 155+58 = 213 -> 2025 = 217+112 = 329 (diff +116)
    assert comp.top_saving_cups is not None and comp.top_saving_cups.cups == c1
    assert comp.top_saving_cups.use == "Aerotermia"
    assert comp.top_saving_cups.diff_kwh == pytest.approx(-191.0)
    assert comp.top_increasing_cups is not None and comp.top_increasing_cups.cups == c2
    assert comp.top_increasing_cups.use == "Garaje"
    assert comp.top_increasing_cups.diff_kwh == pytest.approx(116.0)


def test_compare_years_validation_errors() -> None:
    """Validate single-year, missing-year, duplicate-year, and parse_years_option errors."""
    df_single = pd.DataFrame(
        [
            {
                "cups": "ES0021000000000001AA",
                "timestamp": "2024-01-01 00:00:00",
                "consumption_kwh": 5.0,
            }
        ]
    )
    with pytest.raises(EsdError, match="At least two years"):
        ConsumptionAggregator.compare_years(df_single)

    df_two = pd.DataFrame(
        [
            {
                "cups": "ES0021000000000001AA",
                "timestamp": "2024-01-01 00:00:00",
                "consumption_kwh": 5.0,
            },
            {
                "cups": "ES0021000000000001AA",
                "timestamp": "2025-01-01 00:00:00",
                "consumption_kwh": 6.0,
            },
        ]
    )
    with pytest.raises(EsdError, match="not found"):
        ConsumptionAggregator.compare_years(df_two, target_years=[2024, 2026])

    with pytest.raises(EsdError, match="two distinct years"):
        ConsumptionAggregator.compare_years(df_two, target_years=[2024, 2024])

    assert parse_years_option(None) is None
    assert parse_years_option(["2024,2025"]) == [2024, 2025]
    assert parse_years_option(["2024", "2025"]) == [2024, 2025]
    with pytest.raises(ValidationError, match="Invalid year"):
        parse_years_option(["2024,abc"])


def test_svg_comparison_charts_generation(tmp_path: Path) -> None:
    """Verify lightweight SVG grouped bar charts are generated with no matplotlib dependency."""
    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    rows = (
        _build_month_rows(c1, 2024, 1, 31, 10.0)
        + _build_month_rows(c2, 2024, 1, 31, 4.0)
        + _build_month_rows(c1, 2025, 1, 31, 8.0)
        + _build_month_rows(c2, 2025, 1, 31, 5.0)
    )
    comp = ConsumptionAggregator.compare_years(
        pd.DataFrame(rows), cups_uses={c1: "Aerotermia & Bomba"}
    )

    chart_paths = generate_all_comparison_charts(comp, output_dir=tmp_path, lang="en")
    assert len(chart_paths) == 3
    assert chart_paths[0].name == "community_monthly_2024_2025.svg"
    assert chart_paths[1].name == f"cups_{c1}_2024_2025.svg"
    assert chart_paths[2].name == f"cups_{c2}_2024_2025.svg"

    for p in chart_paths:
        assert p.is_file()
        svg = p.read_text(encoding="utf-8")
        assert svg.startswith("<svg ")
        assert svg.strip().endswith("</svg>")
        assert "2024" in svg and "2025" in svg

    c1_svg = chart_paths[1].read_text(encoding="utf-8")
    assert "Aerotermia &amp; Bomba" in c1_svg
    assert "matplotlib" not in sys.modules


def test_comparison_service_and_markdown_export(tmp_path: Path) -> None:
    """Run ComparisonService on annualized CSVs with invalid file, charts, and --no-charts."""
    cons_dir = tmp_path / ".input" / "consumption"
    out_dir = tmp_path / ".output"
    cups_file = tmp_path / "cups.json"

    _write_month_csv(
        cons_dir / "2024" / "data_2024.csv",
        [
            ("ES0021000000000001AA", 2024, 1, 31, 10.0),
            ("ES0021000000000002BB", 2024, 1, 31, 5.0),
            ("ES0021000000000001AA", 2024, 2, 29, 8.0),
        ],
    )
    _write_month_csv(
        cons_dir / "2025" / "data_2025.csv",
        [
            ("ES0021000000000001AA", 2025, 1, 31, 7.0),
            ("ES0021000000000002BB", 2025, 1, 31, 6.0),
            ("ES0021000000000001AA", 2025, 2, 10, 8.0),  # incomplete Feb 2025
        ],
    )
    (cons_dir / "2025" / "empty_bad.csv").write_text("", encoding="utf-8")
    cups_file.write_text(
        json.dumps([{"cups": "ES0021000000000001AA", "use": "Aerotermia", "primary": True}]),
        encoding="utf-8",
    )

    res = ComparisonService.execute(
        ComparisonRequest(
            consumption_dir=cons_dir,
            output_dir=out_dir,
            cups_config_path=cups_file,
            generate_charts=True,
            lang="en",
        )
    )
    assert res.valid_file_count == 2
    assert sum(1 for v in res.validation_results if not v.is_valid) == 1
    assert len(res.chart_paths) == 3
    assert res.report_path is not None and res.report_path.is_file()
    assert res.report_path.name.endswith("_comparison_2024_2025.md")

    md = res.report_path.read_text(encoding="utf-8")
    assert get_version() in md
    assert "charts/community_monthly_2024_2025.svg" in md
    assert "charts/cups_ES0021000000000001AA_2024_2025.svg" in md
    assert "Aerotermia" in md
    assert "*" in md  # incomplete month marker

    # --no-charts skips SVG generation cleanly
    no_charts_out = tmp_path / ".output_no_charts"
    res_no_charts = ComparisonService.execute(
        ComparisonRequest(
            consumption_dir=cons_dir,
            output_dir=no_charts_out,
            generate_charts=False,
        )
    )
    assert res_no_charts.chart_paths == []
    assert not (no_charts_out / "charts").exists()
    assert res_no_charts.report_path is not None
    md_nc = res_no_charts.report_path.read_text(encoding="utf-8")
    assert "charts/community_monthly" not in md_nc


def test_comparison_rich_views_en_and_es() -> None:
    """Capture 80-column comparison Rich views in English and Spanish."""
    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    rows = (
        _build_month_rows(c1, 2024, 1, 31, 10.0)
        + _build_month_rows(c2, 2024, 1, 31, 4.0)
        + _build_month_rows(c1, 2025, 1, 31, 8.0)
        + _build_month_rows(c2, 2025, 1, 31, 6.0)
        + _build_month_rows(c1, 2024, 2, 29, 9.0)
        + _build_month_rows(c1, 2025, 2, 10, 9.0)  # incomplete
    )
    comp = ConsumptionAggregator.compare_years(pd.DataFrame(rows), cups_uses={c1: "Aerotermia"})

    for lang in ("en", "es"):
        with console.capture() as capture:
            render_comparison_overview(comp, lang=lang)
            render_monthly_comparison_table(comp, lang=lang)
            render_cups_comparison_table(comp, lang=lang)

        output = capture.get()
        assert "2024 ➔ 2025" in output
        assert "*" in output
        assert "▼" in output or "▲" in output
        assert "Aerotermia" in output
        assert c1 in output


def test_cli_compare_command_workflows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise esd compare CLI flags (-y, --years, --no-charts, -l es) and errors."""
    cons_dir = tmp_path / "consumption"
    out_dir = tmp_path / "output"
    cups_file = tmp_path / "cups.json"

    _write_month_csv(
        cons_dir / "2024" / "d2024.csv",
        [("ES0021000000000001AA", 2024, 1, 31, 10.0)],
    )
    _write_month_csv(
        cons_dir / "2025" / "d2025.csv",
        [("ES0021000000000001AA", 2025, 1, 31, 8.0)],
    )
    cups_file.write_text(
        json.dumps([{"cups": "ES0021000000000001AA", "use": "Aerotermia", "primary": True}]),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.cli.is_initialized", lambda: True)
    runner = CliRunner()

    res_ok = runner.invoke(
        app,
        [
            "compare",
            "-c",
            str(cons_dir),
            "-o",
            str(out_dir),
            "-C",
            str(cups_file),
            "-y",
            "2024",
            "-y",
            "2025",
        ],
    )
    assert res_ok.exit_code == 0
    assert "2024 ➔ 2025" in res_ok.output
    assert "Aerotermia" in res_ok.output
    assert (out_dir / "charts" / "community_monthly_2024_2025.svg").is_file()
    assert any(p.name.endswith("_comparison_2024_2025.md") for p in out_dir.iterdir())

    out_nc = tmp_path / "output_nc"
    res_es_nc = runner.invoke(
        app,
        [
            "compare",
            "-c",
            str(cons_dir),
            "-o",
            str(out_nc),
            "--years",
            "2024,2025",
            "--no-charts",
            "-l",
            "es",
        ],
    )
    assert res_es_nc.exit_code == 0
    assert "Comparativa Energética Interanual" in res_es_nc.output
    assert not (out_nc / "charts").exists()

    res_bad_year = runner.invoke(
        app,
        ["compare", "-c", str(cons_dir), "-o", str(out_dir), "-y", "abc"],
    )
    assert res_bad_year.exit_code == 1
    assert "Invalid year" in res_bad_year.output

    single_dir = tmp_path / "single"
    _write_month_csv(
        single_dir / "2024" / "only2024.csv",
        [("ES0021000000000001AA", 2024, 1, 31, 10.0)],
    )
    res_single = runner.invoke(
        app,
        ["compare", "-c", str(single_dir), "-o", str(out_dir)],
    )
    assert res_single.exit_code == 1
    assert "At least two years" in res_single.output
