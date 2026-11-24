"""Rich terminal views for consumption-only community summaries and fair-share analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table

from src.i18n import t
from src.presentation.console import (
    console,
    format_cups_label,
    format_kwh,
    format_pct,
    make_percentage_bar,
)

if TYPE_CHECKING:
    from src.analytics.models import CommunityConsumptionSummary, CupsConsumptionShare
    from src.ingestion.schema import ValidationResult


def render_validation_warnings(
    validation_results: list[ValidationResult],
    lang: str | None = None,
) -> None:
    """Render a warning table if any consumption CSV files failed validation."""
    invalid_results = [r for r in validation_results if not r.is_valid]
    if not invalid_results:
        return

    table = Table(
        title=f"[warning]{t('summary_validation_title', lang=lang)}[/warning]",
        box=box.ROUNDED,
        header_style="warning",
        border_style="warning",
        padding=(0, 1),
    )
    table.add_column(t("summary_col_file", lang=lang), style="cups", no_wrap=True)
    table.add_column(t("summary_col_status", lang=lang), style="danger", no_wrap=True)
    table.add_column(t("summary_col_issue", lang=lang), style="dimmed")

    for res in invalid_results:
        table.add_row(
            res.file_path.name,
            "[danger]✗ SKIPPED[/danger]",
            res.error_message or "Unknown validation issue",
        )

    console.print(table)
    console.print()


def render_consumption_overview(
    summary: CommunityConsumptionSummary,
    file_count: int,
    lang: str | None = None,
) -> None:
    """Render a single unified overview card summarizing community consumption metrics."""
    overview_grid = Table.grid(expand=True, padding=(0, 2))
    overview_grid.add_column(ratio=1)
    overview_grid.add_column(ratio=1)
    overview_grid.add_column(ratio=1)

    overview_grid.add_row(
        f"[dimmed]{t('summary_total_consumption', lang=lang)}[/dimmed]\n"
        f"[metric]{format_kwh(summary.total_community_kwh)}[/metric]",
        f"[dimmed]{t('summary_active_cups', lang=lang)}[/dimmed]\n"
        f"[success]{t('summary_meters_count', lang=lang, count=summary.unique_cups_count)}[/success]",
        f"[dimmed]{t('summary_files_processed', lang=lang)}[/dimmed]\n"
        f"[warning]{t('summary_files_count', lang=lang, count=file_count)}[/warning]",
    )
    overview_grid.add_row(
        f"[dimmed]{t('summary_date_range', lang=lang)}[/dimmed]\n"
        f"[cups]{summary.date_min} ➔ {summary.date_max}[/cups]",
        f"[dimmed]{t('summary_peak_month', lang=lang)}[/dimmed]\n"
        f"[highlight]{summary.peak_month_label}[/highlight] ({format_kwh(summary.peak_month_kwh)})",
        f"[dimmed]{t('summary_total_readings', lang=lang)}[/dimmed]\n"
        f"[dimmed]{t('summary_hours_count', lang=lang, count=f'{summary.total_readings:,}')}[/dimmed]",
    )

    console.print()
    console.print(
        Panel(
            overview_grid,
            title=f"[title]{t('summary_overview_title', lang=lang)}[/title]",
            border_style="panel.border",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )
    console.print()


def _render_cups_shares_table(
    title: str,
    shares: list[CupsConsumptionShare],
    total_kwh: float,
    lang: str | None = None,
    legend: str | None = None,
) -> None:
    """Render an 80-column ranked CUPS share table with optional Use column and distribution bar."""
    include_use = any(item.use for item in shares)
    total_pct_footer = "100.00%" if total_kwh > 0.0 else "0.00%"

    table = Table(
        title=title,
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        padding=(0, 1),
        show_footer=True,
    )
    table.add_column(
        t("summary_col_rank", lang=lang), justify="right", style="dimmed", width=2, no_wrap=True
    )
    table.add_column(
        t("summary_col_cups", lang=lang),
        style="cups",
        footer=t("summary_col_total", lang=lang),
        no_wrap=True,
    )
    if include_use:
        table.add_column(
            t("summary_col_use", lang=lang),
            style="cups.use",
            min_width=8,
            max_width=12,
            overflow="ellipsis",
        )
    table.add_column(
        t("summary_col_consumption", lang=lang),
        justify="right",
        style="metric",
        footer=format_kwh(total_kwh),
        no_wrap=True,
    )
    table.add_column(
        t("summary_col_share", lang=lang),
        justify="right",
        style="badge.dominant",
        footer=total_pct_footer,
        no_wrap=True,
    )
    table.add_column(
        t("summary_col_distribution", lang=lang), justify="left", width=8, no_wrap=True
    )

    for idx, item in enumerate(shares, start=1):
        badge = ""
        if idx == 1 and item.share_pct > 30.0:
            badge = "★"
        elif item.consumption_kwh < 1.0:
            badge = "(0)"
        cups_label = format_cups_label(item.cups, badge=badge)

        row_cells = [str(idx), cups_label]
        if include_use:
            row_cells.append(item.use or "—")
        row_cells.extend(
            [
                format_kwh(item.consumption_kwh),
                format_pct(item.share_pct),
                make_percentage_bar(item.share_pct, width=8),
            ]
        )
        table.add_row(*row_cells)

    console.print(table)
    if legend:
        console.print(f"[dimmed]{legend}[/dimmed]\n")
    else:
        console.print()


def render_annual_consumption_tables(
    summary: CommunityConsumptionSummary,
    filter_cups: str | None = None,
    filter_year: int | None = None,
    lang: str | None = None,
) -> None:
    """Render formatted annual consumption tables with percentage share visual bars."""
    years_to_display = (
        [filter_year]
        if filter_year is not None and filter_year in summary.annual_summaries
        else sorted(summary.annual_summaries.keys())
    )
    legend = t("summary_annual_legend", lang=lang)

    for year in years_to_display:
        annual_data = summary.annual_summaries[year]
        shares = annual_data.cups_shares
        if filter_cups:
            shares = [s for s in shares if s.cups == filter_cups]

        title = (
            f"[title]{t('summary_annual_title', lang=lang, year=year)}[/title] "
            f"[dimmed]({t('summary_community_total_label', lang=lang, total=format_kwh(annual_data.community_total_kwh))})[/dimmed]"
        )
        _render_cups_shares_table(
            title=title,
            shares=shares,
            total_kwh=annual_data.community_total_kwh,
            lang=lang,
            legend=legend,
        )


def render_monthly_consumption_overview(
    summary: CommunityConsumptionSummary,
    filter_year: int | None = None,
    lang: str | None = None,
) -> None:
    """Render a monthly community timeline showing total consumption and top contributor."""
    filtered_months = summary.monthly_summaries
    if filter_year is not None:
        filtered_months = [m for m in filtered_months if m.year == filter_year]

    if not filtered_months:
        return

    table = Table(
        title=f"[title]{t('summary_monthly_timeline_title', lang=lang)}[/title]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        padding=(0, 1),
    )
    table.add_column(t("summary_col_period", lang=lang), style="cups", width=7, no_wrap=True)
    table.add_column(
        t("summary_col_community_total", lang=lang),
        justify="right",
        style="metric",
        no_wrap=True,
    )
    table.add_column(t("summary_col_top_cups", lang=lang), min_width=20)
    table.add_column(
        t("summary_col_top_share", lang=lang), justify="right", style="badge.dominant", no_wrap=True
    )
    table.add_column(
        t("summary_col_distribution", lang=lang), justify="left", width=10, no_wrap=True
    )

    for month_data in filtered_months:
        top = month_data.top_consumer
        top_label = format_cups_label(top.cups, use=top.use)
        table.add_row(
            month_data.period_label,
            format_kwh(month_data.community_total_kwh),
            top_label,
            format_pct(top.share_pct),
            make_percentage_bar(top.share_pct, width=10),
        )

    console.print(table)
    console.print()


def render_detailed_monthly_consumption(
    summary: CommunityConsumptionSummary,
    filter_cups: str | None = None,
    filter_year: int | None = None,
    lang: str | None = None,
) -> None:
    """Render full monthly CUPS share breakdown tables for each period."""
    filtered_months = summary.monthly_summaries
    if filter_year is not None:
        filtered_months = [m for m in filtered_months if m.year == filter_year]

    if not filtered_months:
        return

    for month_data in filtered_months:
        shares = month_data.cups_shares
        if filter_cups:
            shares = [s for s in shares if s.cups == filter_cups]

        title = (
            f"[title]{t('summary_period_title', lang=lang, period=month_data.period_label)}[/title] "
            f"[dimmed]({t('summary_community_total_label', lang=lang, total=format_kwh(month_data.community_total_kwh))})[/dimmed]"
        )
        _render_cups_shares_table(
            title=title,
            shares=shares,
            total_kwh=month_data.community_total_kwh,
            lang=lang,
        )


def render_cups_consumption_trajectory(
    summary: CommunityConsumptionSummary,
    target_cups: str,
    filter_year: int | None = None,
    lang: str | None = None,
) -> None:
    """Render a dedicated month-by-month consumption trajectory table for a single CUPS."""
    filtered_months = summary.monthly_summaries
    if filter_year is not None:
        filtered_months = [m for m in filtered_months if m.year == filter_year]

    use_label = summary.cups_uses.get(target_cups, "")
    title_cups = f"{target_cups} ({use_label})" if use_label else target_cups

    table = Table(
        title=f"[title]{t('summary_cups_trajectory_title', lang=lang, cups=title_cups)}[/title]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        padding=(0, 1),
        show_footer=True,
    )
    table.add_column(
        t("summary_col_period", lang=lang),
        style="cups",
        width=7,
        no_wrap=True,
        footer=t("summary_col_total", lang=lang),
    )
    table.add_column(
        t("summary_col_cups_kwh", lang=lang),
        justify="right",
        style="metric",
        no_wrap=True,
    )
    table.add_column(
        t("summary_col_community_kwh", lang=lang),
        justify="right",
        style="dimmed",
        no_wrap=True,
    )
    table.add_column(
        t("summary_col_share", lang=lang), justify="right", style="badge.dominant", no_wrap=True
    )
    table.add_column(
        t("summary_col_distribution", lang=lang), justify="left", width=10, no_wrap=True
    )

    total_cups_kwh = 0.0
    total_community_kwh = 0.0

    for month_data in filtered_months:
        match = next((s for s in month_data.cups_shares if s.cups == target_cups), None)
        if match:
            total_cups_kwh += match.consumption_kwh
            total_community_kwh += month_data.community_total_kwh
            table.add_row(
                month_data.period_label,
                format_kwh(match.consumption_kwh),
                format_kwh(month_data.community_total_kwh),
                format_pct(match.share_pct),
                make_percentage_bar(match.share_pct, width=10),
            )

    overall_share = (
        (total_cups_kwh / total_community_kwh * 100.0) if total_community_kwh > 0.0 else 0.0
    )
    table.columns[1].footer = format_kwh(total_cups_kwh)
    table.columns[2].footer = format_kwh(total_community_kwh)
    table.columns[3].footer = format_pct(overall_share)

    console.print(table)
    console.print()


def render_consumption_insights(
    summary: CommunityConsumptionSummary,
    lang: str | None = None,
) -> None:
    """Render an analytical insights panel highlighting dominant consumers, dormant meters, and seasonality."""
    top_overall = summary.overall_cups_shares[0] if summary.overall_cups_shares else None
    zero_consumers = [
        f"{s.cups} ({s.use})" if s.use else s.cups
        for s in summary.overall_cups_shares
        if s.consumption_kwh < 1.0
    ]

    insights: list[str] = []

    if top_overall and top_overall.share_pct > 50.0:
        top_label = (
            f"{top_overall.cups} ({top_overall.use})" if top_overall.use else top_overall.cups
        )
        insights.append(
            t(
                "summary_dominant_insight",
                lang=lang,
                cups=top_label,
                pct=f"{top_overall.share_pct:.2f}",
                kwh=format_kwh(top_overall.consumption_kwh),
            )
        )

    if zero_consumers:
        insights.append(
            t(
                "summary_zero_insight",
                lang=lang,
                count=len(zero_consumers),
                cups=", ".join(zero_consumers),
            )
        )

    insights.append(
        t(
            "summary_seasonality_insight",
            lang=lang,
            peak_month=summary.peak_month_label,
            peak_kwh=format_kwh(summary.peak_month_kwh),
            lowest_month=summary.lowest_month_label,
            lowest_kwh=format_kwh(summary.lowest_month_kwh),
        )
    )

    console.print(
        Panel(
            "\n\n".join(insights),
            title=f"[title]{t('summary_insights_title', lang=lang)}[/title]",
            border_style="warning",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
