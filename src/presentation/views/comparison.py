"""Rich 80-column terminal views for multi-year consumption comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table

from src.i18n import get_month_name, t
from src.presentation.console import console, format_kwh

if TYPE_CHECKING:
    from src.analytics.models import ComparisonSummary


def render_comparison_overview(comparison: ComparisonSummary, lang: str | None = None) -> None:
    """Render executive overview panel comparing multiple calendar years."""
    years_str = " ➔ ".join(map(str, comparison.years))
    lines: list[str] = [
        f"[bold white]{t('compare_years_label', lang=lang)}[/bold white] [bold cyan]{years_str}[/bold cyan]"
    ]

    if comparison.comparable_months:
        first_m = get_month_name(min(comparison.comparable_months), lang=lang, short=True)
        last_m = get_month_name(max(comparison.comparable_months), lang=lang, short=True)
        period_str = f"{first_m} - {last_m}"
        lines.append(
            f"  [dim cyan]{t('compare_comparable_period_note', lang=lang, period=period_str, months=len(comparison.comparable_months))}[/dim cyan]"
        )

    for year in comparison.years:
        raw_kwh = comparison.annual_totals[year]
        comp_kwh = comparison.comparable_annual_totals.get(year, raw_kwh)
        if comparison.excluded_months and comp_kwh != raw_kwh:
            lines.append(
                f"  • [bold]{year}:[/bold] [yellow]{format_kwh(comp_kwh)}[/yellow] "
                f"[dim]({format_kwh(raw_kwh)} total)[/dim]"
            )
        else:
            lines.append(f"  • [bold]{year}:[/bold] [yellow]{format_kwh(raw_kwh)}[/yellow]")

    lines.append("")
    diff = comparison.total_diff_kwh
    pct = comparison.total_pct_change
    if diff is not None and pct is not None:
        if diff < 0.0:
            status_text = t(
                "compare_status_saving",
                lang=lang,
                diff_kwh=format_kwh(abs(diff)),
                pct=f"{abs(pct):.2f}",
            )
        elif diff > 0.0:
            status_text = t(
                "compare_status_increase",
                lang=lang,
                diff_kwh=format_kwh(diff),
                pct=f"{pct:.2f}",
            )
        else:
            status_text = t("compare_status_stable", lang=lang, diff_kwh=format_kwh(diff))
        lines.append(f"[bold]{t('compare_overall_change', lang=lang)}[/bold] {status_text}")
    elif comparison.excluded_months and not comparison.comparable_months:
        lines.append(f"[yellow]{t('compare_no_comparable_months', lang=lang)}[/yellow]")

    highlights: list[str] = []
    if comparison.max_decrease_month and comparison.max_decrease_month.diff_kwh is not None:
        m_name = get_month_name(comparison.max_decrease_month.month, lang=lang)
        pct_val = abs(comparison.max_decrease_month.pct_change or 0.0)
        highlights.append(
            f"[green]▼[/green] {t('compare_max_decrease', lang=lang)} [bold]{m_name}[/bold] "
            f"([green]-{pct_val:.1f}%[/green] / [green]-{format_kwh(abs(comparison.max_decrease_month.diff_kwh))}[/green])"
        )

    if comparison.max_increase_month and comparison.max_increase_month.diff_kwh is not None:
        m_name = get_month_name(comparison.max_increase_month.month, lang=lang)
        pct_val = comparison.max_increase_month.pct_change or 0.0
        highlights.append(
            f"[red]▲[/red] {t('compare_max_increase', lang=lang)} [bold]{m_name}[/bold] "
            f"([red]+{pct_val:.1f}%[/red] / [red]+{format_kwh(comparison.max_increase_month.diff_kwh)}[/red])"
        )

    if comparison.top_saving_cups:
        saver = comparison.top_saving_cups
        saver_label = f"{saver.cups} ({saver.use})" if saver.use else saver.cups
        highlights.append(
            f"[green]🏆[/green] {t('compare_top_saver', lang=lang)} [cyan]{saver_label}[/cyan] "
            f"([green]-{format_kwh(abs(saver.diff_kwh))}[/green])"
        )

    if comparison.top_increasing_cups:
        inc = comparison.top_increasing_cups
        inc_label = f"{inc.cups} ({inc.use})" if inc.use else inc.cups
        highlights.append(
            f"[yellow]⚡[/yellow] {t('compare_top_increaser', lang=lang)} [cyan]{inc_label}[/cyan] "
            f"([red]+{format_kwh(inc.diff_kwh)}[/red])"
        )

    if highlights:
        lines.append("")
        lines.extend(f"  {h}" for h in highlights)

    if comparison.excluded_months:
        lines.append("")
        ex_names = ", ".join(
            get_month_name(m, lang=lang, short=True) for m in comparison.excluded_months
        )
        lines.append(
            f"  [dim yellow]* {t('compare_excluded_months_note', lang=lang, count=len(comparison.excluded_months), months=ex_names)}[/dim yellow]"
        )

    console.print()
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold cyan]{t('compare_overview_title', lang=lang)}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_monthly_comparison_table(comparison: ComparisonSummary, lang: str | None = None) -> None:
    """Render month-by-month comparative consumption and year-over-year variation table."""
    table = Table(
        title=f"[bold yellow]{t('compare_monthly_title', lang=lang)}[/bold yellow]",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column(t("compare_month_col", lang=lang), style="bold white", width=5, no_wrap=True)
    for year in comparison.years:
        table.add_column(f"{year}", justify="right", style="cyan", no_wrap=True)
    table.add_column(t("compare_diff_col", lang=lang), justify="right", no_wrap=True)
    table.add_column(t("compare_var_col", lang=lang), justify="right", no_wrap=True)
    table.add_column(t("compare_trend_col", lang=lang), justify="center", no_wrap=True)

    for m in comparison.monthly_comparisons:
        m_label = get_month_name(m.month, lang=lang, short=True)

        year_cells: list[str] = []
        for year in comparison.years:
            status = m.year_status.get(year, "complete")
            val = m.yearly_kwh.get(year)
            if status == "no_data" or val is None:
                year_cells.append(f"[dim]{t('compare_no_data', lang=lang)}[/dim]")
            elif status == "incomplete":
                year_cells.append(f"[yellow]{format_kwh(val)}*[/yellow]")
            else:
                year_cells.append(format_kwh(val))

        if m.diff_kwh is not None:
            if m.diff_kwh < 0.0:
                diff_cell = f"[green]-{format_kwh(abs(m.diff_kwh))}[/green]"
            elif m.diff_kwh > 0.0:
                diff_cell = f"[red]+{format_kwh(m.diff_kwh)}[/red]"
            else:
                diff_cell = "[dim]0.00 kWh[/dim]"
        else:
            diff_cell = "[dim]—[/dim]"

        if m.pct_change is not None:
            if m.pct_change < 0.0:
                var_cell = f"[bold green]▼ {m.pct_change:.1f}%[/bold green]"
                trend_cell = f"[green]{t('compare_trend_reduced', lang=lang)}[/green]"
            elif m.pct_change > 0.0:
                var_cell = f"[bold red]▲ +{m.pct_change:.1f}%[/bold red]"
                trend_cell = f"[red]{t('compare_trend_increased', lang=lang)}[/red]"
            else:
                var_cell = "[dim]— 0.0%[/dim]"
                trend_cell = f"[dim]{t('compare_trend_equal', lang=lang)}[/dim]"
        else:
            var_cell = "[dim]—[/dim]"
            trend_cell = (
                f"[dim]{t('compare_no_data', lang=lang)}[/dim]"
                if not m.is_complete
                else "[dim]—[/dim]"
            )

        table.add_row(m_label, *year_cells, diff_cell, var_cell, trend_cell)

    table.add_section()
    if comparison.comparable_months:
        first_m = get_month_name(min(comparison.comparable_months), lang=lang, short=True)
        last_m = get_month_name(max(comparison.comparable_months), lang=lang, short=True)
        total_label = (
            f"Total ({first_m}-{last_m})" if len(comparison.comparable_months) < 12 else "Total"
        )
        total_year_cells = [
            format_kwh(comparison.comparable_annual_totals[y]) for y in comparison.years
        ]
        diff_tot = comparison.total_diff_kwh
        pct_tot = comparison.total_pct_change

        if diff_tot is not None:
            if diff_tot < 0.0:
                total_diff_cell = f"[bold green]-{format_kwh(abs(diff_tot))}[/bold green]"
            elif diff_tot > 0.0:
                total_diff_cell = f"[bold red]+{format_kwh(diff_tot)}[/bold red]"
            else:
                total_diff_cell = "[bold]0.00 kWh[/bold]"
        else:
            total_diff_cell = "[dim]—[/dim]"

        if pct_tot is not None:
            if pct_tot < 0.0:
                total_var_cell = f"[bold green]▼ {pct_tot:.1f}%[/bold green]"
                total_trend_cell = (
                    f"[bold green]{t('compare_trend_reduced', lang=lang)}[/bold green]"
                )
            elif pct_tot > 0.0:
                total_var_cell = f"[bold red]▲ +{pct_tot:.1f}%[/bold red]"
                total_trend_cell = f"[bold red]{t('compare_trend_increased', lang=lang)}[/bold red]"
            else:
                total_var_cell = "[bold dim]— 0.0%[/bold dim]"
                total_trend_cell = f"[bold dim]{t('compare_trend_equal', lang=lang)}[/bold dim]"
        else:
            total_var_cell = "[dim]—[/dim]"
            total_trend_cell = "[dim]—[/dim]"

        table.add_row(
            f"[bold]{total_label}[/bold]",
            *total_year_cells,
            total_diff_cell,
            total_var_cell,
            total_trend_cell,
        )
    else:
        raw_year_cells = [format_kwh(comparison.annual_totals[y]) for y in comparison.years]
        table.add_row(
            "[bold]Total[/bold]", *raw_year_cells, "[dim]—[/dim]", "[dim]—[/dim]", "[dim]—[/dim]"
        )

    console.print(table)
    console.print()


def render_cups_comparison_table(comparison: ComparisonSummary, lang: str | None = None) -> None:
    """Render comparison table showing individual CUPS shifts between earliest and latest years."""
    if not comparison.cups_comparisons:
        return

    earliest_y = comparison.years[0]
    latest_y = comparison.years[-1]

    sub_note = ""
    if comparison.comparable_months and len(comparison.comparable_months) < 12:
        first_m = get_month_name(min(comparison.comparable_months), lang=lang, short=True)
        last_m = get_month_name(max(comparison.comparable_months), lang=lang, short=True)
        sub_note = f" [{first_m}-{last_m}]"

    table = Table(
        title=f"[bold yellow]{t('compare_cups_title', lang=lang)} ({earliest_y} ➔ {latest_y}{sub_note})[/bold yellow]",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("#", justify="right", style="dim", width=2, no_wrap=True)
    table.add_column(t("compare_cups_col", lang=lang), style="bold white", min_width=20)
    table.add_column(f"{earliest_y}", justify="right", style="cyan", no_wrap=True)
    table.add_column(f"{latest_y}", justify="right", style="cyan", no_wrap=True)
    table.add_column(t("compare_diff_col", lang=lang), justify="right", no_wrap=True)
    table.add_column(t("compare_var_col", lang=lang), justify="right", no_wrap=True)

    for idx, c in enumerate(comparison.cups_comparisons, start=1):
        c_kwh_base = c.yearly_kwh.get(earliest_y, 0.0)
        c_kwh_target = c.yearly_kwh.get(latest_y, 0.0)
        cups_cell = f"{c.cups}\n[dim cyan]{c.use}[/dim cyan]" if c.use else c.cups

        if c.diff_kwh < 0.0:
            diff_cell = f"[green]-{format_kwh(abs(c.diff_kwh))}[/green]"
        elif c.diff_kwh > 0.0:
            diff_cell = f"[red]+{format_kwh(c.diff_kwh)}[/red]"
        else:
            diff_cell = "[dim]0.00 kWh[/dim]"

        if c.pct_change is not None:
            if c.pct_change < 0.0:
                var_cell = f"[bold green]▼ {c.pct_change:.1f}%[/bold green]"
            elif c.pct_change > 0.0:
                var_cell = f"[bold red]▲ +{c.pct_change:.1f}%[/bold red]"
            else:
                var_cell = "[dim]— 0.0%[/dim]"
        else:
            var_cell = "[dim]N/A[/dim]"

        table.add_row(
            str(idx),
            cups_cell,
            format_kwh(c_kwh_base),
            format_kwh(c_kwh_target),
            diff_cell,
            var_cell,
        )

    console.print(table)
    console.print()
