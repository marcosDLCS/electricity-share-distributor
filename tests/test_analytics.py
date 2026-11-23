"""Automated unit, service, view, export, and CLI tests for consumption analytics (esd summary)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.analytics import ConsumptionAggregator
from src.cli import app
from src.domain.exceptions import EsdError, ValidationError
from src.presentation.console import console
from src.presentation.views.consumption import (
    render_annual_consumption_tables,
    render_consumption_insights,
    render_consumption_overview,
    render_cups_consumption_trajectory,
    render_detailed_monthly_consumption,
    render_monthly_consumption_overview,
    render_validation_warnings,
)
from src.services import SummaryRequest, SummaryService
from src.version import get_version


def _write_datadis_csv(
    path: Path,
    rows: list[tuple[str, str, str, str]],
    delimiter: str = ";",
) -> None:
    """Write a synthetic DATADIS consumption CSV with mock CUPS."""
    lines = [delimiter.join(["cups", "fecha", "hora", "consumo_kWh"])]
    for cups, fecha, hora, kwh in rows:
        lines.append(delimiter.join([cups, fecha, hora, kwh]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_aggregate_community_100_percent_invariant_and_metrics() -> None:
    """Verify 100.00% fair-share invariant across overall, annual, monthly, and pivot views."""
    df = pd.DataFrame(
        [
            {
                "cups": "ES0021000000000001AA",
                "timestamp": "2025-01-15 00:00:00",
                "consumption_kwh": 60.0,
            },
            {
                "cups": "ES0021000000000002BB",
                "timestamp": "2025-01-15 00:00:00",
                "consumption_kwh": 30.0,
            },
            {
                "cups": "ES0021000000000003CC",
                "timestamp": "2025-01-15 00:00:00",
                "consumption_kwh": 10.0,
            },
            {
                "cups": "ES0021000000000001AA",
                "timestamp": "2025-02-15 00:00:00",
                "consumption_kwh": 120.0,
            },
            {
                "cups": "ES0021000000000002BB",
                "timestamp": "2025-02-15 00:00:00",
                "consumption_kwh": 60.0,
            },
            {
                "cups": "ES0021000000000003CC",
                "timestamp": "2025-02-15 00:00:00",
                "consumption_kwh": 20.0,
            },
            {
                "cups": "ES0021000000000001AA",
                "timestamp": "2026-01-15 00:00:00",
                "consumption_kwh": 80.0,
            },
            {
                "cups": "ES0021000000000002BB",
                "timestamp": "2026-01-15 00:00:00",
                "consumption_kwh": 20.0,
            },
        ]
    )
    uses = {
        "ES0021000000000001AA": "Aerotermia",
        "ES0021000000000002BB": "Garaje",
        "ES0021000000000003CC": "Piscina",
    }

    summary = ConsumptionAggregator.aggregate_community(df, cups_uses=uses)
    assert summary.total_community_kwh == pytest.approx(400.0)
    assert summary.total_readings == 8
    assert summary.unique_cups_count == 3
    assert summary.date_min == "2025-01-15"
    assert summary.date_max == "2026-01-15"
    assert summary.peak_month_label == "2025-02"
    assert summary.peak_month_kwh == pytest.approx(200.0)
    assert summary.lowest_month_label in ("2025-01", "2026-01")
    assert summary.lowest_month_kwh == pytest.approx(100.0)

    # 100.00% overall, annual, and monthly invariants
    assert sum(s.share_pct for s in summary.overall_cups_shares) == pytest.approx(100.0)
    assert summary.overall_cups_shares[0].cups == "ES0021000000000001AA"
    assert summary.overall_cups_shares[0].use == "Aerotermia"

    for annual in summary.annual_summaries.values():
        assert sum(s.share_pct for s in annual.cups_shares) == pytest.approx(100.0)

    for monthly in summary.monthly_summaries:
        assert sum(s.share_pct for s in monthly.cups_shares) == pytest.approx(100.0)

    # Monthly pivot check
    pivot = ConsumptionAggregator.build_monthly_pivot(df, year=2025)
    assert list(pivot.index) == [
        "ES0021000000000001AA",
        "ES0021000000000002BB",
        "ES0021000000000003CC",
    ]
    assert pivot["Total_kWh"].sum() == pytest.approx(300.0)
    assert pivot["Share_%"].sum() == pytest.approx(100.0)
    assert ConsumptionAggregator.build_monthly_pivot(df, year=2099).empty


def test_aggregate_community_zero_consumption_and_errors() -> None:
    """Zero consumption yields 0.0% shares, and empty/malformed DataFrames raise EsdError."""
    zero_df = pd.DataFrame(
        [
            {
                "cups": "ES0021000000000001AA",
                "timestamp": "2025-01-01 00:00:00",
                "consumption_kwh": 0.0,
            },
            {
                "cups": "ES0021000000000002BB",
                "timestamp": "2025-01-01 00:00:00",
                "consumption_kwh": 0.0,
            },
        ]
    )
    summary = ConsumptionAggregator.aggregate_community(zero_df)
    assert summary.total_community_kwh == 0.0
    assert all(s.share_pct == 0.0 for s in summary.overall_cups_shares)

    with pytest.raises(EsdError, match="empty"):
        ConsumptionAggregator.aggregate_community(pd.DataFrame())

    with pytest.raises(EsdError, match="missing required"):
        ConsumptionAggregator.aggregate_community(pd.DataFrame({"cups": ["ES0021000000000001AA"]}))


def test_summary_service_consumption_only_and_validation_warnings(tmp_path: Path) -> None:
    """Run consumption-only summary without generation Excel or cups.json and capture warnings."""
    cons_dir = tmp_path / ".input" / "consumption"
    out_dir = tmp_path / ".output"

    _write_datadis_csv(
        cons_dir / "2025" / "ES0021000000000001AA.csv",
        [
            ("ES0021000000000001AA", "2025/05/01", "01:00", "70,0"),
            ("ES0021000000000002BB", "2025/05/01", "01:00", "30,0"),
        ],
    )
    # Invalid empty CSV should trigger a warning without aborting
    bad_csv = cons_dir / "2025" / "corrupt_empty.csv"
    bad_csv.write_text("", encoding="utf-8")

    result = SummaryService.execute(
        SummaryRequest(
            consumption_dir=cons_dir,
            output_dir=out_dir,
            export_markdown=True,
        )
    )

    assert result.valid_file_count == 1
    assert len(result.validation_results) == 2
    assert sum(1 for v in result.validation_results if not v.is_valid) == 1
    assert result.summary.total_community_kwh == pytest.approx(100.0)
    assert result.report_path is not None and result.report_path.is_file()
    assert result.report_path.name.endswith("_community_summary.md")

    md_text = result.report_path.read_text(encoding="utf-8")
    assert get_version() in md_text
    assert "ES0021000000000001AA" in md_text
    assert "[bold" not in md_text
    assert "[dim" not in md_text


def test_summary_service_with_cups_json_and_filters(tmp_path: Path) -> None:
    """Enrich CUPS with cups.json labels and enforce view/CUPS validation errors."""
    cons_dir = tmp_path / "consumption"
    out_dir = tmp_path / "output"
    cups_file = tmp_path / "cups.json"

    _write_datadis_csv(
        cons_dir / "data.csv",
        [
            ("ES0021000000000001AA", "2025/05/01", "01:00", "80,0"),
            ("ES0021000000000002BB", "2025/05/01", "01:00", "20,0"),
            ("ES0021000000000003CC", "2025/05/01", "01:00", "0,0"),
        ],
    )
    cups_file.write_text(
        json.dumps(
            [
                {"cups": "ES0021000000000001AA", "use": "Aerotermia", "primary": True},
                {"cups": "ES0021000000000002BB", "use": "Garaje", "primary": False},
            ]
        ),
        encoding="utf-8",
    )

    res = SummaryService.execute(
        SummaryRequest(
            consumption_dir=cons_dir,
            output_dir=out_dir,
            cups_config_path=cups_file,
            year=2025,
            cups="es0021000000000001aa",
            view="monthly",
            lang="es",
        )
    )
    assert res.summary.cups_uses["ES0021000000000001AA"] == "Aerotermia"
    # Does not filter out CUPS missing from cups.json in consumption-only summary
    assert len(res.summary.cups_list) == 3
    assert res.report_path is not None
    assert res.report_path.name.endswith("_summary_2025.md")
    md_text = res.report_path.read_text(encoding="utf-8")
    assert "Aerotermia" in md_text

    with pytest.raises(ValidationError, match="Invalid view mode"):
        SummaryService.execute(
            SummaryRequest(consumption_dir=cons_dir, output_dir=out_dir, view="invalid")
        )

    with pytest.raises(ValidationError, match="was not found"):
        SummaryService.execute(
            SummaryRequest(
                consumption_dir=cons_dir,
                output_dir=out_dir,
                cups="ES0021000000000099ZZ",
            )
        )


def test_consumption_rich_views_en_and_es(tmp_path: Path) -> None:
    """Verify Rich views render overview, badges (★/(0)), trajectory, warnings, and insights in EN/ES."""
    cons_dir = tmp_path / "consumption"
    out_dir = tmp_path / "output"
    cups_file = tmp_path / "cups.json"

    _write_datadis_csv(
        cons_dir / "valid.csv",
        [
            ("ES0021000000000001AA", "2025/05/01", "01:00", "85,0"),
            ("ES0021000000000002BB", "2025/05/01", "01:00", "14,5"),
            ("ES0021000000000003CC", "2025/05/01", "01:00", "0,5"),
        ],
    )
    (cons_dir / "bad.csv").write_text("", encoding="utf-8")
    cups_file.write_text(
        json.dumps([{"cups": "ES0021000000000001AA", "use": "Aerotermia", "primary": True}]),
        encoding="utf-8",
    )

    res = SummaryService.execute(
        SummaryRequest(
            consumption_dir=cons_dir,
            output_dir=out_dir,
            cups_config_path=cups_file,
            export_markdown=False,
        )
    )

    for lang in ("en", "es"):
        with console.capture() as capture:
            render_validation_warnings(res.validation_results, lang=lang)
            render_consumption_overview(res.summary, file_count=res.valid_file_count, lang=lang)
            render_annual_consumption_tables(res.summary, lang=lang)
            render_monthly_consumption_overview(res.summary, lang=lang)
            render_detailed_monthly_consumption(res.summary, lang=lang)
            render_cups_consumption_trajectory(
                res.summary, target_cups="ES0021000000000001AA", lang=lang
            )
            render_consumption_insights(res.summary, lang=lang)

        output = capture.get()
        assert "bad.csv" in output
        assert "ES0021000000000001AA" in output
        assert "★" in output
        assert "(0)" in output
        assert "Aerotermia" in output
        assert "100.00 kWh" in output


def test_cli_summary_command_workflows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise esd summary CLI workflows including filters, Spanish output, and error exits."""
    cons_dir = tmp_path / "consumption"
    out_dir = tmp_path / "output"
    cups_file = tmp_path / "cups.json"

    _write_datadis_csv(
        cons_dir / "2025" / "data.csv",
        [
            ("ES0021000000000001AA", "2025/05/01", "01:00", "75,0"),
            ("ES0021000000000002BB", "2025/05/01", "01:00", "25,0"),
        ],
    )
    cups_file.write_text(
        json.dumps([{"cups": "ES0021000000000001AA", "use": "Aerotermia", "primary": True}]),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.cli.is_initialized", lambda: True)
    runner = CliRunner()

    res_all = runner.invoke(
        app,
        [
            "summary",
            "-c",
            str(cons_dir),
            "-o",
            str(out_dir),
            "-C",
            str(cups_file),
        ],
    )
    assert res_all.exit_code == 0
    assert "ES0021000000000001AA" in res_all.output
    assert "Aerotermia" in res_all.output
    assert any(p.name.endswith("_community_summary.md") for p in out_dir.iterdir())

    res_es = runner.invoke(
        app,
        [
            "summary",
            "-c",
            str(cons_dir),
            "-o",
            str(out_dir),
            "-y",
            "2025",
            "-v",
            "monthly",
            "-l",
            "es",
        ],
    )
    assert res_es.exit_code == 0
    assert "Cronología Mensual" in res_es.output

    res_cups = runner.invoke(
        app,
        [
            "summary",
            "-c",
            str(cons_dir),
            "-o",
            str(out_dir),
            "--cups",
            "ES0021000000000001AA",
        ],
    )
    assert res_cups.exit_code == 0
    assert "Monthly Trajectory" in res_cups.output

    res_bad_view = runner.invoke(
        app,
        ["summary", "-c", str(cons_dir), "-o", str(out_dir), "--view", "badview"],
    )
    assert res_bad_view.exit_code == 1
    assert "Invalid view mode" in res_bad_view.output

    res_bad_cups = runner.invoke(
        app,
        ["summary", "-c", str(cons_dir), "-o", str(out_dir), "--cups", "ES0021000000000099ZZ"],
    )
    assert res_bad_cups.exit_code == 1
    assert "was not found" in res_bad_cups.output


def test_format_cups_label_and_custom_theme() -> None:
    """Verify semantic theme tokens in make_percentage_bar and CUPS label formatting."""
    from src.presentation.console import CUSTOM_THEME, format_cups_label, make_percentage_bar

    for key in (
        "title",
        "panel.border",
        "table.header",
        "cups",
        "cups.use",
        "delta.saving",
        "delta.increase",
        "delta.neutral",
        "badge.dominant",
        "badge.inactive",
    ):
        assert key in CUSTOM_THEME.styles

    assert "[metric]" in make_percentage_bar(75.0)
    assert "[warning]" in make_percentage_bar(25.0)
    assert "[highlight]" in make_percentage_bar(5.0)
    assert "[dimmed]" in make_percentage_bar(0.0)

    full_dom = format_cups_label("ES0021000000000001AA", use="Aerotermia", badge="★")
    assert "[cups]ES0021000000000001AA[/cups]" in full_dom
    assert "[cups.use](Aerotermia)[/cups.use]" in full_dom
    assert "[badge.dominant]★[/badge.dominant]" in full_dom

    masked_zero = format_cups_label("ES0021000000000004DD", mask=True, badge="(0)")
    assert "[cups]ES0021...04DD[/cups]" in masked_zero
    assert "[badge.inactive](0)[/badge.inactive]" in masked_zero


def test_consumption_views_render_cleanly_at_80_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure consumption summary Rich views use cohesive theme styling within 80 columns."""
    from io import StringIO

    from rich.console import Console

    from src.analytics.models import (
        AnnualConsumptionSummary,
        CommunityConsumptionSummary,
        CupsConsumptionShare,
        MonthlyConsumptionSummary,
    )
    from src.ingestion.schema import ValidationResult
    from src.presentation.console import CUSTOM_THEME
    from src.presentation.views import consumption as consumption_view

    buf = StringIO()
    test_console = Console(file=buf, width=80, force_terminal=False, theme=CUSTOM_THEME)
    monkeypatch.setattr(consumption_view, "console", test_console)

    summary = CommunityConsumptionSummary(
        total_community_kwh=1200.0,
        total_readings=744,
        unique_cups_count=2,
        cups_list=["ES0021000000000001AA", "ES0021000000000002BB"],
        date_min="2025-05-01",
        date_max="2025-05-31",
        annual_summaries={
            2025: AnnualConsumptionSummary(
                year=2025,
                period_label="2025",
                community_total_kwh=1200.0,
                cups_shares=[
                    CupsConsumptionShare(
                        "ES0021000000000001AA", 1200.0, 100.0, 744, 1.61, use="Aerotermia"
                    ),
                    CupsConsumptionShare("ES0021000000000002BB", 0.0, 0.0, 744, 0.0, use="Garage"),
                ],
                monthly_totals={5: 1200.0},
                top_consumer=CupsConsumptionShare(
                    "ES0021000000000001AA", 1200.0, 100.0, 744, 1.61, use="Aerotermia"
                ),
                lowest_consumer=CupsConsumptionShare(
                    "ES0021000000000002BB", 0.0, 0.0, 744, 0.0, use="Garage"
                ),
            )
        },
        monthly_summaries=[
            MonthlyConsumptionSummary(
                year=2025,
                month=5,
                period_label="2025-05",
                community_total_kwh=1200.0,
                cups_shares=[
                    CupsConsumptionShare(
                        "ES0021000000000001AA", 1200.0, 100.0, 744, 1.61, use="Aerotermia"
                    ),
                    CupsConsumptionShare("ES0021000000000002BB", 0.0, 0.0, 744, 0.0, use="Garage"),
                ],
                top_consumer=CupsConsumptionShare(
                    "ES0021000000000001AA", 1200.0, 100.0, 744, 1.61, use="Aerotermia"
                ),
            )
        ],
        overall_cups_shares=[
            CupsConsumptionShare(
                "ES0021000000000001AA", 1200.0, 100.0, 744, 1.61, use="Aerotermia"
            ),
            CupsConsumptionShare("ES0021000000000002BB", 0.0, 0.0, 744, 0.0, use="Garage"),
        ],
        peak_month_label="2025-05",
        peak_month_kwh=1200.0,
        lowest_month_label="2025-05",
        lowest_month_kwh=1200.0,
        cups_uses={"ES0021000000000001AA": "Aerotermia", "ES0021000000000002BB": "Garage"},
    )

    bad = [
        ValidationResult(
            file_path=tmp_path / "bad.csv",
            is_valid=False,
            error_message="Missing header",
        )
    ]

    consumption_view.render_validation_warnings(bad, lang="en")
    consumption_view.render_consumption_overview(summary, file_count=1, lang="en")
    consumption_view.render_annual_consumption_tables(summary, lang="en")
    consumption_view.render_monthly_consumption_overview(summary, lang="en")
    consumption_view.render_cups_consumption_trajectory(summary, "ES0021000000000001AA", lang="en")
    consumption_view.render_consumption_insights(summary, lang="en")

    rendered = buf.getvalue()
    assert "✗ SKIPPED" in rendered
    assert "ES0021000000000001AA" in rendered
    assert "Aerotermia" in rendered
    assert "★" in rendered
    assert "(0)" in rendered
    assert "100.00%" in rendered
    assert max(len(line) for line in rendered.splitlines()) <= 80
