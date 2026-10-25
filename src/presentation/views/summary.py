"""Executive community summary and KPI dashboard views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table

from src.i18n import t
from src.presentation.console import console, format_kwh

if TYPE_CHECKING:
    from src.ingestion.schema import IngestionSummary
    from src.optimization.models import CommunityMonthlyMetrics, OptimizationResult


def render_community_summary(
    summary: IngestionSummary,
    tot: CommunityMonthlyMetrics,
    lang: str | None = None,
    opt_result: OptimizationResult | None = None,
) -> None:
    """Render executive dashboard with high-contrast KPI cards and community energy balance."""
    # 1. KPI Cards Row
    solar_card = Panel(
        f"[bold yellow]{format_kwh(tot.total_generation_kwh)}[/bold yellow]\n"
        f"[dim]{t('lbl_total_surplus', lang=lang)}: {format_kwh(tot.total_surplus_kwh)}[/dim]",
        title=f"🌞 {t('lbl_total_gen', lang=lang)}",
        title_align="left",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    demand_card = Panel(
        f"[bold bright_cyan]{format_kwh(tot.total_consumption_kwh)}[/bold bright_cyan]\n"
        f"[dim]{t('col_cov_rate', lang=lang)}: {tot.solar_coverage_rate:.1f}%[/dim]",
        title=f"⚡ {t('lbl_total_cons', lang=lang)}",
        title_align="left",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    gain_str = ""
    if opt_result and "equal" in opt_result.baselines:
        eq_sc = opt_result.baselines["equal"].total_summary.total_self_consumed_kwh
        if eq_sc > 0:
            diff_pct = ((tot.total_self_consumed_kwh - eq_sc) / eq_sc) * 100.0
            if diff_pct > 0.05:
                gain_str = f" [bold bright_green](+{diff_pct:.1f}% vs base)[/bold bright_green]"

    sc_card = Panel(
        f"[bold green]{format_kwh(tot.total_self_consumed_kwh)}[/bold green]{gain_str}\n"
        f"[dim]{t('col_sc_rate', lang=lang)}: {tot.self_consumption_rate:.1f}%[/dim]",
        title=f"🏆 {t('lbl_total_sc', lang=lang)}",
        title_align="left",
        border_style="green",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    kpi_cards = Columns([solar_card, demand_card, sc_card], equal=True, expand=True)

    # 2. Scope & Timeline Metadata Grid
    meta_grid = Table.grid(expand=True, padding=(0, 2))
    meta_grid.add_column(ratio=1)
    meta_grid.add_column(ratio=1)

    strat_label = tot.strategy.upper()
    bylaw_str = ""
    if opt_result and opt_result.constraints and opt_result.constraints.is_active:
        parts: list[str] = []
        if opt_result.constraints.min_share is not None:
            parts.append(f"Min: {opt_result.constraints.min_share * 100:.1f}%")
        if opt_result.constraints.max_share is not None:
            parts.append(f"Max: {opt_result.constraints.max_share * 100:.1f}%")
        if parts:
            bylaw_str = f" [dim]• Bylaws:[/dim] [bright_yellow]{' | '.join(parts)}[/bright_yellow]"

    meta_grid.add_row(
        f"[dim]{t('lbl_supply_points', lang=lang)}:[/dim] [bold green]{summary.cups_count} CUPS[/bold green] [dim]• {t('col_strategy', lang=lang)}:[/dim] [white]{strat_label}[/white]{bylaw_str}",
        f"[dim]{t('lbl_date_range', lang=lang)}:[/dim] [white]{summary.start_time[:10]} ➔ {summary.end_time[:10]}[/white]",
    )

    # 3. Consolidated Container Table
    container = Table.grid(expand=True, padding=(0, 0))
    container.add_column()
    container.add_row(kpi_cards)
    container.add_row("")
    container.add_row(meta_grid)

    console.print()
    console.print(
        Panel(
            container,
            title=f"[bold bright_cyan]{t('title_community_summary', lang=lang)}[/bold bright_cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
