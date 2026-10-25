"""Trajectory and strategy comparison views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

from src.config import get_language
from src.i18n import t
from src.presentation.console import console
from src.presentation.views.common import MONTH_ABBR_EN, MONTH_ABBR_ES

if TYPE_CHECKING:
    from src.optimization.models import OptimizationResult


SPARK_BLOCKS = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")


def _coverage_sparkline(rate: float) -> str:
    """Render a 5-step visual sparkline block based on solar coverage rate."""
    if rate <= 0.0:
        return "[dim]░░░░░[/dim]"
    filled = min(5, max(1, round((rate / 100.0) * 5)))
    empty = 5 - filled
    block_idx = min(len(SPARK_BLOCKS) - 1, max(0, int((rate / 100.0) * len(SPARK_BLOCKS))))
    char = SPARK_BLOCKS[block_idx]
    if rate >= 50.0:
        return f"[bold bright_green]{char * filled}[/bold bright_green][dim]{'░' * empty}[/dim]"
    if rate >= 20.0:
        return f"[bright_yellow]{char * filled}[/bright_yellow][dim]{'░' * empty}[/dim]"
    return f"[cyan]{char * filled}[/cyan][dim]{'░' * empty}[/dim]"


def render_monthly_trajectory_table(
    opt_result: OptimizationResult,
    lang: str | None = None,
) -> None:
    """Render month-by-month trajectory table of community self-consumption and solar hours demand."""
    current_lang = lang or get_language()
    table = Table(
        title=f"[bold yellow]{t('title_monthly_trajectory', lang=lang)}[/bold yellow] [dim](kWh)[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 1),
        show_lines=False,
    )

    col_month = "Mes" if current_lang == "es" else "Month"
    col_gen = "Solar"
    col_dem = "Demanda" if current_lang == "es" else "Demand"
    col_soldem = "Dem.Sol" if current_lang == "es" else "Sol.Dem"
    col_sc = "Autocons" if current_lang == "es" else "Self-C"
    col_surplus = "Exced." if current_lang == "es" else "Surplus"
    col_sc_rate = "% Auto" if current_lang == "es" else "SC %"
    col_cov_rate = "% Cob" if current_lang == "es" else "Cov %"

    table.add_column(col_month, style="bold", no_wrap=True)
    table.add_column(col_gen, justify="right", style="yellow", no_wrap=True)
    table.add_column(col_dem, justify="right", style="white", no_wrap=True)
    table.add_column(col_soldem, justify="right", style="bright_cyan", no_wrap=True)
    table.add_column(col_sc, justify="right", style="bold green", no_wrap=True)
    table.add_column(col_surplus, justify="right", style="dim yellow", no_wrap=True)
    table.add_column(col_sc_rate, justify="right", style="bright_cyan", no_wrap=True)
    table.add_column(col_cov_rate, justify="right", style="bold magenta", no_wrap=True)

    abbr_map = MONTH_ABBR_ES if current_lang == "es" else MONTH_ABBR_EN
    for m in opt_result.monthly_results:
        m_name = abbr_map.get(m.month, m.month)
        if m.has_data:
            table.add_row(
                m_name,
                f"{m.total_generation_kwh:,.1f}",
                f"{m.total_consumption_kwh:,.1f}",
                f"{m.solar_hours_consumption_kwh:,.1f}",
                f"{m.total_self_consumed_kwh:,.1f}",
                f"{m.total_surplus_kwh:,.1f}",
                f"{m.self_consumption_rate:.1f}%",
                f"{m.solar_coverage_rate:.1f}%",
            )
        else:
            table.add_row(
                m_name,
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
            )

    tot = opt_result.total_summary
    table.add_section()
    table.add_row(
        f"[bold]{t('lbl_total', lang=lang)}[/bold]",
        f"[bold]{tot.total_generation_kwh:,.1f}[/bold]",
        f"[bold]{tot.total_consumption_kwh:,.1f}[/bold]",
        f"[bold bright_cyan]{tot.solar_hours_consumption_kwh:,.1f}[/bold bright_cyan]",
        f"[bold green]{tot.total_self_consumed_kwh:,.1f}[/bold green]",
        f"[bold yellow]{tot.total_surplus_kwh:,.1f}[/bold yellow]",
        f"[bold bright_cyan]{tot.self_consumption_rate:.1f}%[/bold bright_cyan]",
        f"[bold magenta]{tot.solar_coverage_rate:.1f}%[/bold magenta]",
    )

    console.print(table)
    console.print()


def render_strategy_comparison_table(
    opt_result: OptimizationResult,
    lang: str | None = None,
) -> None:
    """Render comparison of collective self-consumption between optimal and baseline allocations."""
    if not opt_result.baselines:
        return

    table = Table(
        title=f"[bold yellow]{t('title_strategy_comparison', lang=lang)}[/bold yellow] [dim](kWh)[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 1),
        show_lines=False,
    )

    table.add_column(t("col_strategy", lang=lang), style="bold", width=23, no_wrap=True)
    table.add_column(
        t("col_self_cons", lang=lang), justify="right", style="bold green", width=9, no_wrap=True
    )
    table.add_column(
        t("col_surplus", lang=lang), justify="right", style="yellow", width=9, no_wrap=True
    )
    table.add_column(
        t("col_sc_rate", lang=lang), justify="right", style="bright_cyan", width=7, no_wrap=True
    )
    table.add_column(
        t("col_gain_vs_equal", lang=lang),
        justify="right",
        style="bold magenta",
        width=19,
        no_wrap=True,
    )

    eq_sc = (
        opt_result.baselines["equal"].total_summary.total_self_consumed_kwh
        if "equal" in opt_result.baselines
        else opt_result.total_summary.total_self_consumed_kwh
    )

    opt_tot = opt_result.total_summary
    gain = opt_tot.total_self_consumed_kwh - eq_sc
    gain_str = f"+{gain:,.1f} (+{(gain / eq_sc * 100):.1f}%)" if eq_sc > 0 and gain > 0 else "—"

    table.add_row(
        t("lbl_optimal_strat", lang=lang),
        f"{opt_tot.total_self_consumed_kwh:,.1f}",
        f"{opt_tot.total_surplus_kwh:,.1f}",
        f"{opt_tot.self_consumption_rate:.1f}%",
        f"[bold green]{gain_str}[/bold green]",
    )

    for b_name, b_res in opt_result.baselines.items():
        b_tot = b_res.total_summary
        b_gain = b_tot.total_self_consumed_kwh - eq_sc
        b_gain_str = (
            f"+{b_gain:,.1f} (+{(b_gain / eq_sc * 100):.1f}%)"
            if eq_sc > 0 and b_gain > 0
            else (t("lbl_baseline", lang=lang) if b_gain == 0 else f"{b_gain:,.1f}")
        )
        table.add_row(
            f"  {b_name}",
            f"{b_tot.total_self_consumed_kwh:,.1f}",
            f"{b_tot.total_surplus_kwh:,.1f}",
            f"{b_tot.self_consumption_rate:.1f}%",
            f"[dim]{b_gain_str}[/dim]",
        )

    console.print(table)
    console.print()
