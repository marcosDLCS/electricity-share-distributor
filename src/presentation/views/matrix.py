"""Matrix and coefficient tabular views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

from src.config import get_language, get_precision
from src.i18n import t
from src.presentation.console import console, make_percentage_bar
from src.presentation.views.common import MONTH_ABBR_EN, MONTH_ABBR_ES

if TYPE_CHECKING:
    from src.optimization.models import (
        CommunityMonthlyMetrics,
        HourlyOptimizationResult,
        HourlyProfileMatrix,
        OptimizationResult,
    )


def _format_heatmap_cell(val: float | None, formatted: str) -> str:
    """Format table cell with visual heatmap styling based on share magnitude."""
    if val is None or formatted.strip() == "—":
        return "[dim]—[/dim]"
    if val <= 0.0001:
        return f"[dim white]{formatted}[/dim white]"
    if val <= 0.05:
        return f"[white]{formatted}[/white]"
    if val <= 0.20:
        return f"[bright_cyan]{formatted}[/bright_cyan]"
    if val <= 0.50:
        return f"[bright_yellow]{formatted}[/bright_yellow]"
    return f"[bold bright_green]{formatted}[/bold bright_green]"


def render_monthly_coefficients_table(
    month_metrics: CommunityMonthlyMetrics,
    lang: str | None = None,
    precision: int | None = None,
) -> None:
    """Render 80-column compliant tabular view of monthly coefficient proposals per CUPS."""
    table = Table(
        title=f"[bold yellow]{t('title_monthly_coefficients', lang=lang, month=month_metrics.month)}[/bold yellow] "
        f"[dim](Gen: {month_metrics.total_generation_kwh:,.1f} kWh, Dem: {month_metrics.total_consumption_kwh:,.1f} kWh)[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 1),
        show_lines=False,
    )

    table.add_column(t("col_rank", lang=lang), justify="right", style="dim", width=2, no_wrap=True)
    table.add_column(t("col_cups_desc", lang=lang), style="bold white", width=20, no_wrap=True)
    table.add_column(
        t("col_beta", lang=lang), justify="right", style="bold green", width=7, no_wrap=True
    )
    table.add_column(t("col_share_bar", lang=lang), justify="left", width=8, no_wrap=True)
    table.add_column(
        t("col_demand", lang=lang), justify="right", style="white", width=8, no_wrap=True
    )
    table.add_column(
        t("col_self_cons", lang=lang),
        justify="right",
        style="bold bright_cyan",
        width=8,
        no_wrap=True,
    )
    table.add_column(
        t("col_surplus", lang=lang), justify="right", style="dim yellow", width=8, no_wrap=True
    )

    prec = get_precision() if precision is None else precision
    sorted_cups = sorted(month_metrics.cups_metrics, key=lambda c: c.beta, reverse=True)
    for rank, cm in enumerate(sorted_cups, 1):
        pct = cm.beta * 100.0
        bar = make_percentage_bar(pct, width=8)
        cups_label = f"{cm.use[:11]} (…{cm.cups[-6:]})" if cm.use else cm.cups
        table.add_row(
            str(rank),
            cups_label,
            f"{pct:.{prec}f}%",
            bar,
            f"{cm.consumption_kwh:,.1f}",
            f"{cm.self_consumed_kwh:,.1f}",
            f"{cm.surplus_kwh:,.1f}",
        )

    console.print(table)
    console.print()


def render_coefficients_matrix_table(
    opt_result: OptimizationResult,
    lang: str | None = None,
    precision: int | None = None,
) -> None:
    """Render consolidated matrix table of monthly distribution shares (CUPS in Y, Months in X) with two-tone heatmap."""
    matrix = opt_result.build_matrix()
    if not matrix.cups_list or not matrix.months:
        return

    prec = get_precision() if precision is None else precision
    current_lang = lang or get_language()

    # Determine if compact layout is needed to guarantee 80-column terminal compliance
    compact_mode = len(matrix.months) > 5 and (console.width or 80) < 115
    tbl_padding = (0, 0) if compact_mode else (0, 1)

    table = Table(
        title=f"[bold yellow]{t('title_coefficients_matrix', lang=lang)}[/bold yellow]",
        caption=f"[dim]{t('desc_coefficients_matrix', lang=lang)}[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=tbl_padding,
        show_lines=False,
    )

    cups_width = 12 if compact_mode else 22
    col_cups_title = t("col_cups", lang=lang) if compact_mode else t("col_cups_desc", lang=lang)
    table.add_column(col_cups_title, style="bold cyan", width=cups_width, no_wrap=True)

    abbr_map = MONTH_ABBR_ES if current_lang == "es" else MONTH_ABBR_EN
    for m in matrix.months:
        header_name = abbr_map.get(m, m)
        col_width = 4 if compact_mode else None
        table.add_column(
            header_name, justify="right", style="yellow", width=col_width, no_wrap=True
        )

    annual_col = t("col_annual_avg", lang=lang)
    if compact_mode and len(annual_col) > 6:
        annual_col = "Media" if current_lang == "es" else "Avg"

    table.add_column(
        annual_col,
        justify="right",
        style="bold green",
        width=4 if compact_mode else None,
        no_wrap=True,
    )

    for cups in matrix.cups_list:
        use_val = matrix.cups_uses.get(cups, "") if hasattr(matrix, "cups_uses") else ""
        if compact_mode:
            display_cups = f"…{cups[-10:]}" if len(cups) > 12 else cups
        else:
            display_cups = f"{use_val[:11]} (…{cups[-6:]})" if use_val else cups
        row = [display_cups]
        for m in matrix.months:
            raw_val = matrix.matrix.get(cups, {}).get(m)
            cell_txt = matrix.format_cell(cups, m, precision=prec)
            row.append(_format_heatmap_cell(raw_val, cell_txt))
        row.append(f"[bold green]{matrix.format_annual(cups, precision=prec)}[/bold green]")
        table.add_row(*row)

    table.add_section()
    total_lbl = "TOTAL" if compact_mode else t("lbl_total_rd244", lang=lang)
    total_row = [f"[bold]{total_lbl}[/bold]"]
    total_prec = 0 if compact_mode else prec
    for m in matrix.months:
        total_row.append(
            f"[bold green]{matrix.format_month_sum(m, precision=total_prec)}[/bold green]"
        )
    total_row.append(f"[bold green]{matrix.format_annual_sum(precision=total_prec)}[/bold green]")
    table.add_row(*total_row)

    console.print(table)
    console.print()


def render_hourly_profile_table(
    hourly_result: HourlyOptimizationResult,
    lang: str | None = None,
    precision: int | None = None,
) -> None:
    """Render diurnal hourly distribution share profile tables formatted for 80-column terminals."""
    matrix = hourly_result.profile_matrix
    if not matrix.cups_list or not matrix.hours:
        return

    prec = get_precision() if precision is None else precision
    current_lang = lang or get_language()
    term_width = console.width or 80

    if term_width >= 125:
        _render_single_hourly_table(matrix, current_lang, prec)
    else:
        _render_split_hourly_tables(matrix, current_lang, prec)


def _render_single_hourly_table(
    matrix: HourlyProfileMatrix,
    current_lang: str,
    prec: int,
) -> None:
    """Render all 24 hours in a single wide table when terminal width allows."""
    table = Table(
        title=f"[bold yellow]{t('title_hourly_profile', lang=current_lang)}[/bold yellow]",
        caption=f"[dim]{t('desc_hourly_profile', lang=current_lang)}[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 0),
        show_lines=False,
    )

    table.add_column(t("col_cups", lang=current_lang), style="bold cyan", width=12, no_wrap=True)

    for h_str in matrix.hours:
        table.add_column(f"{h_str}h", justify="right", style="yellow", width=4, no_wrap=True)

    table.add_column(
        t("col_hourly_avg", lang=current_lang),
        justify="right",
        style="bold green",
        width=5,
        no_wrap=True,
    )

    for cups in matrix.cups_list:
        use_val = matrix.cups_uses.get(cups, "") if hasattr(matrix, "cups_uses") else ""
        display_cups = (
            f"{use_val[:11]} (…{cups[-6:]})"
            if use_val
            else (f"…{cups[-10:]}" if len(cups) > 12 else cups)
        )
        row = [display_cups]
        for h_str in matrix.hours:
            raw_val = matrix.matrix.get(cups, {}).get(h_str)
            cell_txt = matrix.format_cell(cups, h_str, precision=prec)
            row.append(_format_heatmap_cell(raw_val, cell_txt))
        row.append(f"[bold green]{matrix.format_average(cups, precision=prec)}[/bold green]")
        table.add_row(*row)

    table.add_section()
    total_row = ["[bold]TOTAL[/bold]"]
    for h_str in matrix.hours:
        total_row.append(
            f"[bold green]{matrix.format_hour_sum(h_str, precision=prec)}[/bold green]"
        )
    total_row.append(f"[bold green]{matrix.format_average_sum(precision=prec)}[/bold green]")
    table.add_row(*total_row)

    console.print(table)
    console.print()


def _render_split_hourly_tables(
    matrix: HourlyProfileMatrix,
    current_lang: str,
    prec: int,
) -> None:
    """Render two compact 12-hour tables (00-11 and 12-23) to guarantee 80-column terminal compliance."""
    # Table 1: Hours 00:00 to 11:00
    table_am = Table(
        title=f"[bold yellow]{t('title_hourly_profile_am', lang=current_lang)}[/bold yellow]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 0),
        show_lines=False,
    )
    table_am.add_column(t("col_cups", lang=current_lang), style="bold cyan", width=12, no_wrap=True)

    hours_am = [f"{h:02d}" for h in range(12)]
    for h_str in hours_am:
        table_am.add_column(f"{h_str}h", justify="right", style="yellow", width=4, no_wrap=True)

    for cups in matrix.cups_list:
        display_cups = f"…{cups[-10:]}" if len(cups) > 12 else cups
        row = [display_cups]
        for h_str in hours_am:
            raw_val = matrix.matrix.get(cups, {}).get(h_str)
            cell_txt = matrix.format_cell(cups, h_str, precision=prec)
            row.append(_format_heatmap_cell(raw_val, cell_txt))
        table_am.add_row(*row)

    table_am.add_section()
    total_am = ["[bold]TOTAL[/bold]"]
    for h_str in hours_am:
        total_am.append(f"[bold green]{matrix.format_hour_sum(h_str, precision=prec)}[/bold green]")
    table_am.add_row(*total_am)

    console.print(table_am)

    # Table 2: Hours 12:00 to 23:00 + Avg
    table_pm = Table(
        title=f"[bold yellow]{t('title_hourly_profile_pm', lang=current_lang)}[/bold yellow]",
        caption=f"[dim]{t('desc_hourly_profile', lang=current_lang)}[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 0),
        show_lines=False,
    )
    table_pm.add_column(t("col_cups", lang=current_lang), style="bold cyan", width=12, no_wrap=True)

    hours_pm = [f"{h:02d}" for h in range(12, 24)]
    for h_str in hours_pm:
        table_pm.add_column(f"{h_str}h", justify="right", style="yellow", width=4, no_wrap=True)

    table_pm.add_column(
        t("col_hourly_avg", lang=current_lang),
        justify="right",
        style="bold green",
        width=4,
        no_wrap=True,
    )

    for cups in matrix.cups_list:
        display_cups = f"…{cups[-10:]}" if len(cups) > 12 else cups
        row = [display_cups]
        for h_str in hours_pm:
            raw_val = matrix.matrix.get(cups, {}).get(h_str)
            cell_txt = matrix.format_cell(cups, h_str, precision=prec)
            row.append(_format_heatmap_cell(raw_val, cell_txt))
        row.append(f"[bold green]{matrix.format_average(cups, precision=prec)}[/bold green]")
        table_pm.add_row(*row)

    table_pm.add_section()
    total_pm = ["[bold]TOTAL[/bold]"]
    for h_str in hours_pm:
        total_pm.append(f"[bold green]{matrix.format_hour_sum(h_str, precision=prec)}[/bold green]")
    total_pm.append(f"[bold green]{matrix.format_average_sum(precision=prec)}[/bold green]")
    table_pm.add_row(*total_pm)

    console.print(table_pm)
    console.print()
