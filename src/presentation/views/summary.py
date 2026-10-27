"""Executive community summary and KPI dashboard views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
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
    # 1. Energy Balance KPI Cards Row
    solar_hours_gen = (
        tot.solar_hours_generation_kwh
        if tot.solar_hours_generation_kwh > 0
        else tot.total_generation_kwh
    )
    solar_card = Panel(
        f"[bold yellow]{format_kwh(tot.total_generation_kwh)}[/bold yellow]\n"
        f"[dim]{t('lbl_solar_hours_gen', lang=lang)}: {format_kwh(solar_hours_gen)}[/dim]\n"
        f"[dim]{t('lbl_total_surplus', lang=lang)}: {format_kwh(tot.total_surplus_kwh)}[/dim]",
        title=f"🌞 {t('lbl_total_gen', lang=lang)}",
        title_align="left",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    demand_card = Panel(
        f"[bold bright_cyan]{format_kwh(tot.total_consumption_kwh)}[/bold bright_cyan]\n"
        f"[dim]{t('lbl_solar_hours_demand', lang=lang)}: {format_kwh(tot.solar_hours_consumption_kwh)}[/dim]\n"
        f"[dim]{t('col_cov_rate', lang=lang)}: {tot.solar_coverage_rate:.1f}%[/dim]",
        title=f"⚡ {t('lbl_total_cons', lang=lang)}",
        title_align="left",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    sc_card = Panel(
        f"[bold green]{format_kwh(tot.total_self_consumed_kwh)}[/bold green]\n"
        f"[dim]{t('col_sc_rate', lang=lang)}: {tot.self_consumption_rate:.1f}%[/dim]\n"
        f"[dim]{t('lbl_solar_hours_cov', lang=lang)}: {tot.solar_hours_coverage_rate:.1f}%[/dim]",
        title=f"🏆 {t('lbl_total_sc', lang=lang)}",
        title_align="left",
        border_style="green",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    kpi_grid = Table.grid(expand=True, padding=(0, 1))
    kpi_grid.add_column(ratio=1)
    kpi_grid.add_column(ratio=1)
    kpi_grid.add_column(ratio=1)
    kpi_grid.add_row(solar_card, demand_card, sc_card)

    # 2. 3-Way Self-Consumption Modality Progression Table
    prog_table: Table | None = None
    if opt_result and (
        opt_result.monthly_share_self_consumed_kwh > 0
        or opt_result.current_self_consumed_kwh > 0
        or opt_result.hourly_share_self_consumed_kwh > 0
    ):
        prog_table = Table(
            title=f"[bold bright_yellow]{t('title_sc_progression', lang=lang)}[/bold bright_yellow] [dim](kWh)[/dim]",
            title_justify="left",
            box=box.ROUNDED,
            header_style="bold cyan",
            padding=(0, 1),
            expand=True,
            show_edge=True,
        )
        prog_table.add_column(t("col_modality", lang=lang), style="bold", width=28, no_wrap=True)
        prog_table.add_column(
            t("col_self_cons", lang=lang),
            justify="right",
            style="bold green",
            width=11,
            no_wrap=True,
        )
        prog_table.add_column(
            t("col_sc_rate", lang=lang), justify="right", style="bright_cyan", width=8, no_wrap=True
        )
        prog_table.add_column(
            t("col_gain_vs_baseline", lang=lang),
            justify="right",
            style="bold magenta",
            width=18,
            no_wrap=True,
        )

        cur_kwh = opt_result.current_self_consumed_kwh
        cur_rate = opt_result.current_self_consumption_rate
        mon_kwh = opt_result.monthly_share_self_consumed_kwh or tot.total_self_consumed_kwh
        mon_rate = opt_result.monthly_share_self_consumption_rate or tot.self_consumption_rate
        hour_kwh = opt_result.hourly_share_self_consumed_kwh or mon_kwh
        hour_rate = opt_result.hourly_share_self_consumption_rate or mon_rate

        # 1. Baseline: Current (Sin Reparto)
        prog_table.add_row(
            t("lbl_sc_current", lang=lang),
            f"{cur_kwh:,.1f}",
            f"{cur_rate:.1f}%",
            f"[dim]{t('lbl_baseline', lang=lang)}[/dim]",
        )

        # 2. Monthly Share (RD 244/2019)
        mon_gain = mon_kwh - cur_kwh
        mon_gain_pct = (mon_gain / max(cur_kwh, 1e-6)) * 100.0 if cur_kwh > 0 else 0.0
        mon_gain_str = (
            f"+{mon_gain:,.1f} (+{mon_gain_pct:.1f}%)" if mon_gain > 0 and cur_kwh > 0 else "—"
        )
        prog_table.add_row(
            t("lbl_sc_monthly", lang=lang),
            f"{mon_kwh:,.1f}",
            f"{mon_rate:.1f}%",
            f"[bold green]{mon_gain_str}[/bold green]" if mon_gain_str != "—" else "—",
        )

        # 3. Dynamic Hourly Share (Orden TED/1247/2021)
        hour_gain = hour_kwh - cur_kwh
        hour_gain_pct = (hour_gain / max(cur_kwh, 1e-6)) * 100.0 if cur_kwh > 0 else 0.0
        hour_gain_str = (
            f"+{hour_gain:,.1f} (+{hour_gain_pct:.1f}%)" if hour_gain > 0 and cur_kwh > 0 else "—"
        )
        prog_table.add_row(
            f"★ {t('lbl_sc_hourly', lang=lang)}",
            f"{hour_kwh:,.1f}",
            f"{hour_rate:.1f}%",
            f"[bold bright_green]{hour_gain_str}[/bold bright_green]"
            if hour_gain_str != "—"
            else "—",
        )

    # 3. Scope & Timeline Metadata Grid
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

    # 4. Consolidated Container Table
    container = Table.grid(expand=True, padding=(0, 0))
    container.add_column()
    container.add_row(kpi_grid)
    if prog_table is not None:
        container.add_row("")
        container.add_row(prog_table)
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
