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
    solar_hours_gen = (
        tot.solar_hours_generation_kwh
        if tot.solar_hours_generation_kwh > 0
        else tot.total_generation_kwh
    )
    kpi_grid = Table.grid(expand=True, padding=(0, 2))
    kpi_grid.add_column(ratio=1)
    kpi_grid.add_column(ratio=1)
    kpi_grid.add_column(ratio=1)
    kpi_grid.add_row(
        f"[dimmed]🌞 {t('lbl_total_gen', lang=lang)}[/dimmed]\n"
        f"[solar]{format_kwh(tot.total_generation_kwh)}[/solar]\n"
        f"[dimmed]{t('lbl_solar_hours_gen', lang=lang)}: {format_kwh(solar_hours_gen)}[/dimmed]\n"
        f"[dimmed]{t('lbl_total_surplus', lang=lang)}: {format_kwh(tot.total_surplus_kwh)}[/dimmed]",
        f"[dimmed]⚡ {t('lbl_total_cons', lang=lang)}[/dimmed]\n"
        f"[metric]{format_kwh(tot.total_consumption_kwh)}[/metric]\n"
        f"[dimmed]{t('lbl_solar_hours_demand', lang=lang)}: {format_kwh(tot.solar_hours_consumption_kwh)}[/dimmed]\n"
        f"[dimmed]{t('col_cov_rate', lang=lang)}: {tot.solar_coverage_rate:.1f}%[/dimmed]",
        f"[dimmed]🏆 {t('lbl_total_sc', lang=lang)}[/dimmed]\n"
        f"[success]{format_kwh(tot.total_self_consumed_kwh)}[/success]\n"
        f"[dimmed]{t('col_sc_rate', lang=lang)}: {tot.self_consumption_rate:.1f}%[/dimmed]\n"
        f"[dimmed]{t('lbl_solar_hours_cov', lang=lang)}: {tot.solar_hours_coverage_rate:.1f}%[/dimmed]",
    )

    prog_table: Table | None = None
    if opt_result and (
        opt_result.monthly_share_self_consumed_kwh > 0
        or opt_result.current_self_consumed_kwh > 0
        or opt_result.hourly_share_self_consumed_kwh > 0
    ):
        prog_table = Table(
            title=f"[title]{t('title_sc_progression', lang=lang)}[/title] [dimmed](kWh)[/dimmed]",
            title_justify="left",
            box=box.ROUNDED,
            header_style="table.header",
            border_style="panel.border",
            padding=(0, 1),
            expand=True,
            show_edge=True,
        )
        prog_table.add_column(
            t("col_modality", lang=lang), style="value.strong", width=28, no_wrap=True
        )
        prog_table.add_column(
            t("col_self_cons", lang=lang),
            justify="right",
            style="success",
            width=11,
            no_wrap=True,
        )
        prog_table.add_column(
            t("col_sc_rate", lang=lang), justify="right", style="metric", width=8, no_wrap=True
        )
        prog_table.add_column(
            t("col_gain_vs_baseline", lang=lang),
            justify="right",
            style="highlight",
            width=18,
            no_wrap=True,
        )

        cur_kwh = opt_result.current_self_consumed_kwh
        cur_rate = opt_result.current_self_consumption_rate
        mon_kwh = opt_result.monthly_share_self_consumed_kwh or tot.total_self_consumed_kwh
        mon_rate = opt_result.monthly_share_self_consumption_rate or tot.self_consumption_rate
        hour_kwh = opt_result.hourly_share_self_consumed_kwh or mon_kwh
        hour_rate = opt_result.hourly_share_self_consumption_rate or mon_rate

        prog_table.add_row(
            t("lbl_sc_current", lang=lang),
            f"{cur_kwh:,.1f}",
            f"{cur_rate:.1f}%",
            f"[dimmed]{t('lbl_baseline', lang=lang)}[/dimmed]",
        )

        mon_gain = mon_kwh - cur_kwh
        mon_gain_pct = (mon_gain / max(cur_kwh, 1e-6)) * 100.0 if cur_kwh > 0 else 0.0
        mon_gain_str = (
            f"+{mon_gain:,.1f} (+{mon_gain_pct:.1f}%)" if mon_gain > 0 and cur_kwh > 0 else "—"
        )
        prog_table.add_row(
            t("lbl_sc_monthly", lang=lang),
            f"{mon_kwh:,.1f}",
            f"{mon_rate:.1f}%",
            f"[success]{mon_gain_str}[/success]" if mon_gain_str != "—" else "—",
        )

        if opt_result.fortnight_share_self_consumed_kwh > 0:
            fort_kwh = opt_result.fortnight_share_self_consumed_kwh
            fort_rate = opt_result.fortnight_share_self_consumption_rate
            fort_gain = fort_kwh - cur_kwh
            fort_gain_pct = (fort_gain / max(cur_kwh, 1e-6)) * 100.0 if cur_kwh > 0 else 0.0
            fort_gain_str = (
                f"+{fort_gain:,.1f} (+{fort_gain_pct:.1f}%)"
                if fort_gain > 0 and cur_kwh > 0
                else "—"
            )
            prog_table.add_row(
                t("lbl_sc_fortnight", lang=lang),
                f"{fort_kwh:,.1f}",
                f"{fort_rate:.1f}%",
                f"[success]{fort_gain_str}[/success]" if fort_gain_str != "—" else "—",
            )

        hour_gain = hour_kwh - cur_kwh
        hour_gain_pct = (hour_gain / max(cur_kwh, 1e-6)) * 100.0 if cur_kwh > 0 else 0.0
        hour_gain_str = (
            f"+{hour_gain:,.1f} (+{hour_gain_pct:.1f}%)" if hour_gain > 0 and cur_kwh > 0 else "—"
        )
        prog_table.add_row(
            f"★ {t('lbl_sc_hourly', lang=lang)}",
            f"{hour_kwh:,.1f}",
            f"{hour_rate:.1f}%",
            f"[heatmap.high]{hour_gain_str}[/heatmap.high]" if hour_gain_str != "—" else "—",
        )

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
            bylaw_str = (
                f" [dimmed]• Bylaws:[/dimmed] [heatmap.mid]{' | '.join(parts)}[/heatmap.mid]"
            )

    meta_grid.add_row(
        f"[dimmed]{t('lbl_supply_points', lang=lang)}:[/dimmed] [success]{summary.cups_count} CUPS[/success] "
        f"[dimmed]• {t('col_strategy', lang=lang)}:[/dimmed] [value]{strat_label}[/value]{bylaw_str}",
        f"[dimmed]{t('lbl_date_range', lang=lang)}:[/dimmed] [value]{summary.start_time[:10]} ➔ {summary.end_time[:10]}[/value]",
    )

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
            title=f"[panel.title]{t('title_community_summary', lang=lang)}[/panel.title]",
            border_style="panel.border",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
