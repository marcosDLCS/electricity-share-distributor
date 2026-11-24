"""Rich 80-column terminal views for multi-year consumption comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table

from src.i18n import get_month_name, t
from src.presentation.console import (
    console,
    format_cups_label,
    format_kwh,
    make_percentage_bar,
)

if TYPE_CHECKING:
    from src.analytics.models import ComparisonSummary


def render_comparison_overview(comparison: ComparisonSummary, lang: str | None = None) -> None:
    """Render executive overview panel comparing multiple calendar years."""
    years_str = " ➔ ".join(map(str, comparison.years))
    lines: list[str] = [
        f"[bold white]{t('compare_years_label', lang=lang)}[/bold white] [metric]{years_str}[/metric]"
    ]

    if comparison.comparable_months:
        first_m = get_month_name(min(comparison.comparable_months), lang=lang, short=True)
        last_m = get_month_name(max(comparison.comparable_months), lang=lang, short=True)
        period_str = f"{first_m} - {last_m}"
        lines.append(
            f"  [cups.use]{t('compare_comparable_period_note', lang=lang, period=period_str, months=len(comparison.comparable_months))}[/cups.use]"
        )

    max_comp_kwh = max(
        (
            comparison.comparable_annual_totals.get(y, comparison.annual_totals[y])
            for y in comparison.years
        ),
        default=0.0,
    )
    for year in comparison.years:
        raw_kwh = comparison.annual_totals[year]
        comp_kwh = comparison.comparable_annual_totals.get(year, raw_kwh)
        rel_pct = (comp_kwh / max_comp_kwh * 100.0) if max_comp_kwh > 0.0 else 0.0
        rel_bar = make_percentage_bar(rel_pct, width=10)
        if comparison.excluded_months and comp_kwh != raw_kwh:
            lines.append(
                f"  • [bold]{year}:[/bold] [metric]{format_kwh(comp_kwh)}[/metric] "
                f"{rel_bar} [dimmed]({format_kwh(raw_kwh)} total)[/dimmed]"
            )
        else:
            lines.append(
                f"  • [bold]{year}:[/bold] [metric]{format_kwh(raw_kwh)}[/metric] {rel_bar}"
            )

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
        lines.append(f"[warning]{t('compare_no_comparable_months', lang=lang)}[/warning]")

    highlights: list[str] = []
    if comparison.max_decrease_month and comparison.max_decrease_month.diff_kwh is not None:
        m_name = get_month_name(comparison.max_decrease_month.month, lang=lang)
        pct_val = abs(comparison.max_decrease_month.pct_change or 0.0)
        highlights.append(
            f"[delta.saving]▼[/delta.saving] {t('compare_max_decrease', lang=lang)} [bold]{m_name}[/bold] "
            f"([delta.saving]-{pct_val:.1f}%[/delta.saving] / [delta.saving]-{format_kwh(abs(comparison.max_decrease_month.diff_kwh))}[/delta.saving])"
        )

    if comparison.max_increase_month and comparison.max_increase_month.diff_kwh is not None:
        m_name = get_month_name(comparison.max_increase_month.month, lang=lang)
        pct_val = comparison.max_increase_month.pct_change or 0.0
        highlights.append(
            f"[delta.increase]▲[/delta.increase] {t('compare_max_increase', lang=lang)} [bold]{m_name}[/bold] "
            f"([delta.increase]+{pct_val:.1f}%[/delta.increase] / [delta.increase]+{format_kwh(comparison.max_increase_month.diff_kwh)}[/delta.increase])"
        )

    if comparison.top_saving_cups:
        saver = comparison.top_saving_cups
        saver_label = f"{saver.cups} ({saver.use})" if saver.use else saver.cups
        highlights.append(
            f"[delta.saving]🏆[/delta.saving] {t('compare_top_saver', lang=lang)} [cups]{saver_label}[/cups] "
            f"([delta.saving]-{format_kwh(abs(saver.diff_kwh))}[/delta.saving])"
        )

    if comparison.top_increasing_cups:
        inc = comparison.top_increasing_cups
        inc_label = f"{inc.cups} ({inc.use})" if inc.use else inc.cups
        highlights.append(
            f"[warning]⚡[/warning] {t('compare_top_increaser', lang=lang)} [cups]{inc_label}[/cups] "
            f"([delta.increase]+{format_kwh(inc.diff_kwh)}[/delta.increase])"
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
            f"  [badge.inactive]* {t('compare_excluded_months_note', lang=lang, count=len(comparison.excluded_months), months=ex_names)}[/badge.inactive]"
        )

    console.print()
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[table.header]{t('compare_overview_title', lang=lang)}[/table.header]",
            border_style="panel.border",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_monthly_comparison_table(comparison: ComparisonSummary, lang: str | None = None) -> None:
    """Render month-by-month comparative consumption and year-over-year variation table."""
    table = Table(
        title=f"[title]{t('compare_monthly_title', lang=lang)}[/title]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        padding=(0, 1),
        show_lines=False,
    )
    table.add_column(t("compare_month_col", lang=lang), style="cups", width=5, no_wrap=True)
    for year in comparison.years:
        table.add_column(f"{year}", justify="right", style="metric", no_wrap=True)
    table.add_column(t("compare_diff_col", lang=lang), justify="right", no_wrap=True)
    table.add_column(t("compare_var_col", lang=lang), justify="right", no_wrap=True)

    for m in comparison.monthly_comparisons:
        m_label = get_month_name(m.month, lang=lang, short=True)

        year_cells: list[str] = []
        for year in comparison.years:
            status = m.year_status.get(year, "complete")
            val = m.yearly_kwh.get(year)
            if status == "no_data" or val is None:
                year_cells.append(f"[dimmed]{t('compare_no_data', lang=lang)}[/dimmed]")
            elif status == "incomplete":
                year_cells.append(f"[warning]{format_kwh(val)}*[/warning]")
            else:
                year_cells.append(format_kwh(val))

        if m.diff_kwh is not None:
            if m.diff_kwh < 0.0:
                diff_cell = f"[delta.saving]-{format_kwh(abs(m.diff_kwh))}[/delta.saving]"
            elif m.diff_kwh > 0.0:
                diff_cell = f"[delta.increase]+{format_kwh(m.diff_kwh)}[/delta.increase]"
            else:
                diff_cell = "[delta.neutral]0.00 kWh[/delta.neutral]"
        else:
            diff_cell = "[dimmed]—[/dimmed]"

        if m.pct_change is not None:
            if m.pct_change < 0.0:
                var_cell = f"[delta.saving]▼ {m.pct_change:.1f}%[/delta.saving]"
            elif m.pct_change > 0.0:
                var_cell = f"[delta.increase]▲ +{m.pct_change:.1f}%[/delta.increase]"
            else:
                var_cell = "[delta.neutral]— 0.0%[/delta.neutral]"
        else:
            var_cell = "[dimmed]—[/dimmed]"

        table.add_row(m_label, *year_cells, diff_cell, var_cell)

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
                total_diff_cell = f"[delta.saving]-{format_kwh(abs(diff_tot))}[/delta.saving]"
            elif diff_tot > 0.0:
                total_diff_cell = f"[delta.increase]+{format_kwh(diff_tot)}[/delta.increase]"
            else:
                total_diff_cell = "[bold]0.00 kWh[/bold]"
        else:
            total_diff_cell = "[dimmed]—[/dimmed]"

        if pct_tot is not None:
            if pct_tot < 0.0:
                total_var_cell = f"[delta.saving]▼ {pct_tot:.1f}%[/delta.saving]"
            elif pct_tot > 0.0:
                total_var_cell = f"[delta.increase]▲ +{pct_tot:.1f}%[/delta.increase]"
            else:
                total_var_cell = "[delta.neutral]— 0.0%[/delta.neutral]"
        else:
            total_var_cell = "[dimmed]—[/dimmed]"

        table.add_row(
            f"[bold]{total_label}[/bold]",
            *total_year_cells,
            total_diff_cell,
            total_var_cell,
        )
    else:
        raw_year_cells = [format_kwh(comparison.annual_totals[y]) for y in comparison.years]
        table.add_row(
            "[bold]Total[/bold]",
            *raw_year_cells,
            "[dimmed]—[/dimmed]",
            "[dimmed]—[/dimmed]",
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
        title=f"[title]{t('compare_cups_title', lang=lang)} ({earliest_y} ➔ {latest_y}{sub_note})[/title]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        padding=(0, 1),
        show_lines=False,
    )
    table.add_column("#", justify="right", style="dimmed", width=2, no_wrap=True)
    table.add_column(t("compare_cups_col", lang=lang), style="cups", min_width=20)
    table.add_column(f"{earliest_y}", justify="right", style="metric", no_wrap=True)
    table.add_column(f"{latest_y}", justify="right", style="metric", no_wrap=True)
    table.add_column(t("compare_diff_col", lang=lang), justify="right", no_wrap=True)
    table.add_column(t("compare_var_col", lang=lang), justify="right", no_wrap=True)

    for idx, c in enumerate(comparison.cups_comparisons, start=1):
        c_kwh_base = c.yearly_kwh.get(earliest_y, 0.0)
        c_kwh_target = c.yearly_kwh.get(latest_y, 0.0)
        cups_cell = format_cups_label(c.cups, use=c.use)

        if c.diff_kwh < 0.0:
            diff_cell = f"[delta.saving]-{format_kwh(abs(c.diff_kwh))}[/delta.saving]"
        elif c.diff_kwh > 0.0:
            diff_cell = f"[delta.increase]+{format_kwh(c.diff_kwh)}[/delta.increase]"
        else:
            diff_cell = "[delta.neutral]0.00 kWh[/delta.neutral]"

        if c.pct_change is not None:
            if c.pct_change < 0.0:
                var_cell = f"[delta.saving]▼ {c.pct_change:.1f}%[/delta.saving]"
            elif c.pct_change > 0.0:
                var_cell = f"[delta.increase]▲ +{c.pct_change:.1f}%[/delta.increase]"
            else:
                var_cell = "[delta.neutral]— 0.0%[/delta.neutral]"
        else:
            var_cell = "[dimmed]N/A[/dimmed]"

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
