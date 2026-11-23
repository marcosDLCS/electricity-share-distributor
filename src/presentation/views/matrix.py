"""Matrix and coefficient tabular views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

from src.config import get_language, get_precision
from src.i18n import t
from src.presentation.console import console
from src.presentation.views.common import MONTH_ABBR_EN, MONTH_ABBR_ES

if TYPE_CHECKING:
    from src.optimization.models import OptimizationResult


def _format_heatmap_cell(val: float | None, formatted: str) -> str:
    """Format table cell with visual heatmap styling based on share magnitude."""
    if val is None or formatted.strip() == "—":
        return "[dim]—[/dim]"
    if val <= 0.05:
        return f"[dim white]{formatted}[/dim white]"
    if val <= 0.20:
        return f"[bright_cyan]{formatted}[/bright_cyan]"
    if val <= 0.50:
        return f"[bright_yellow]{formatted}[/bright_yellow]"
    return f"[bold bright_green]{formatted}[/bold bright_green]"


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
