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


def render_monthly_trajectory_table(
    opt_result: OptimizationResult,
    lang: str | None = None,
) -> None:
    """Render month-by-month trajectory table of community self-consumption and solar hours demand."""
    current_lang = lang or get_language()
    table = Table(
        title=f"[title]{t('title_monthly_trajectory', lang=lang)}[/title] [dimmed](kWh)[/dimmed]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
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

    table.add_column(col_month, style="value.strong", no_wrap=True)
    table.add_column(col_gen, justify="right", style="solar.muted", no_wrap=True)
    table.add_column(col_dem, justify="right", style="value", no_wrap=True)
    table.add_column(col_soldem, justify="right", style="metric", no_wrap=True)
    table.add_column(col_sc, justify="right", style="success", no_wrap=True)
    table.add_column(col_surplus, justify="right", style="solar.surplus", no_wrap=True)
    table.add_column(col_sc_rate, justify="right", style="metric", no_wrap=True)
    table.add_column(col_cov_rate, justify="right", style="highlight", no_wrap=True)

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
            table.add_row(m_name, "—", "—", "—", "—", "—", "—", "—")

    tot = opt_result.total_summary
    table.add_section()
    table.add_row(
        f"[value.strong]{t('lbl_total', lang=lang)}[/value.strong]",
        f"[value.strong]{tot.total_generation_kwh:,.1f}[/value.strong]",
        f"[value.strong]{tot.total_consumption_kwh:,.1f}[/value.strong]",
        f"[metric]{tot.solar_hours_consumption_kwh:,.1f}[/metric]",
        f"[success]{tot.total_self_consumed_kwh:,.1f}[/success]",
        f"[solar]{tot.total_surplus_kwh:,.1f}[/solar]",
        f"[metric]{tot.self_consumption_rate:.1f}%[/metric]",
        f"[highlight]{tot.solar_coverage_rate:.1f}%[/highlight]",
    )

    console.print(table)
    console.print()
