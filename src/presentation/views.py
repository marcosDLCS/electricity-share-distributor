"""Terminal views, tables, cards, and help screens rendered with Rich for esd."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import SUPPORTED_LANGUAGES, get_language
from src.i18n import t
from src.presentation.console import console
from src.version import get_version

if TYPE_CHECKING:
    from pathlib import Path

    from src.config import AppConfig
    from src.ingestion.doctor import DoctorReport, GapInterval
    from src.ingestion.schema import IngestionSummary
    from src.optimization.models import CommunityMonthlyMetrics, OptimizationResult


def render_help(lang: str | None = None) -> None:
    """Render a comprehensive, formatted help screen for the esd CLI tool."""
    title_text = Text()
    title_text.append(f"{t('app_title', lang=lang)} ", style="bold yellow")
    title_text.append(f"(esd v{get_version()})", style="bold cyan")
    title_text.append(f"\n{t('app_subtitle', lang=lang)}", style="dim italic")

    console.print()
    console.print(
        Panel(
            Align.center(title_text),
            box=box.DOUBLE,
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Overview
    console.print(
        f"[bold cyan]{t('overview_heading', lang=lang)}[/bold cyan]\n{t('overview_text', lang=lang)}\n"
    )

    # Commands Table
    cmd_table = Table(
        title=f"[bold yellow]{t('available_commands', lang=lang)}[/bold yellow]",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    cmd_table.add_column(t("cmd_name", lang=lang), style="bold green", no_wrap=True)
    cmd_table.add_column(t("cmd_desc", lang=lang), style="white")

    cmd_table.add_row(
        "calculate",
        t("cmd_calculate_desc", lang=lang),
    )
    cmd_table.add_row(
        "doctor",
        t("cmd_doctor_desc", lang=lang),
    )
    cmd_table.add_row(
        "init",
        t("cmd_init_desc", lang=lang),
    )
    cmd_table.add_row(
        "config",
        t("cmd_config_desc", lang=lang),
    )
    cmd_table.add_row(
        "cleanup",
        t("cmd_cleanup_desc", lang=lang),
    )
    cmd_table.add_row(
        "help",
        t("cmd_help_desc", lang=lang),
    )
    cmd_table.add_row(
        "version",
        t("cmd_version_desc", lang=lang),
    )

    console.print(cmd_table)
    console.print()


def render_version(lang: str | None = None) -> None:
    """Render a rich, formatted version panel for 'esd version'."""
    version = get_version()
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold cyan", no_wrap=True)
    info_table.add_column(style="white")

    info_table.add_row(f"☀️ {t('lbl_version', lang=lang)}", f"[bold cyan]{version}[/bold cyan]")
    info_table.add_row("🐍 Python", f"[dim]{py_version}[/dim]")
    info_table.add_row(f"📜 {t('lbl_license', lang=lang)}", "[dim]MIT[/dim]")
    info_table.add_row(
        f"🌐 {t('lbl_source', lang=lang)}",
        "[dim]github.com/marcosDLCS/electricity-share-distributor[/dim]",
    )

    title_text = Text()
    title_text.append("Electricity Share Distributor ", style="bold yellow")
    title_text.append("(esd)", style="bold white")

    subtitle = Text(
        f"\n{t('app_subtitle', lang=lang)}\n",
        style="dim italic",
    )

    body = Text.assemble(title_text, subtitle)
    panel_content = Columns([body, info_table], equal=False, expand=True)

    console.print()
    console.print(
        Panel(
            panel_content,
            title="[bold cyan]esd[/bold cyan]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_init_success(
    lang: str,
    initialized_at: str,
    precision: int = 0,
    was_already: bool = False,
    cleared_files: int = 0,
) -> None:
    """Render initialization result card."""
    title_key = "init_title_reinit" if was_already else "init_title_success"
    title = f"[bold green]{t(title_key, lang=lang)}[/bold green]"
    lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
    prec_example = "53%" if precision == 0 else ("52.8%" if precision == 1 else "52.86%")
    msg_key = "init_reinit" if was_already else "init_success"
    msg = t(msg_key, lang=lang, language=lang_name)
    prec_desc = t("init_prec_desc", lang=lang, precision=precision, example=prec_example)

    lines = [
        msg,
        f"[dim]• {t('init_lbl_lang', lang=lang)}: [cyan]{lang_name}[/cyan] ({lang})[/dim]",
        f"[dim]• {t('init_lbl_precision', lang=lang)}: [cyan]{prec_desc}[/cyan][/dim]",
        f"[dim]• {t('init_lbl_timestamp', lang=lang)}: {initialized_at}[/dim]",
    ]
    if cleared_files > 0:
        clean_text = t("init_clean_cleared", lang=lang, count=cleared_files)
        lines.append(
            f"[dim]• {t('init_lbl_output', lang=lang)}: [yellow]{clean_text}[/yellow][/dim]"
        )
    else:
        clean_text = t("init_clean_ready", lang=lang)
        lines.append(f"[dim]• {t('init_lbl_output', lang=lang)}: [cyan]{clean_text}[/cyan][/dim]")

    console.print()
    console.print(
        Panel(
            "\n".join(lines),
            title=title,
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_not_initialized_warning(lang: str | None = None) -> None:
    """Render warning if workspace has not been initialized."""
    console.print(t("not_initialized_warning", lang=lang))


def render_cleanup_result(count: int, output_dir: str, lang: str | None = None) -> None:
    """Render cleanup result card."""
    if count > 0:
        msg = t("cleaned_files", lang=lang, count=count)
        border = "green"
    else:
        msg = t("no_files_cleaned", lang=lang)
        border = "yellow"

    console.print()
    console.print(
        Panel(
            f"{msg}\n[dim]{t('lbl_directory', lang=lang)}: {output_dir}[/dim]",
            title=f"[bold yellow]{t('title_cleanup', lang=lang)}[/bold yellow]",
            border_style=border,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_community_summary(
    summary: IngestionSummary,
    tot: CommunityMonthlyMetrics,
    lang: str | None = None,
) -> None:
    """Render community aggregate summary banner with key energy and efficiency metrics."""
    from src.presentation.console import format_kwh

    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    grid.add_row(
        f"[dim]{t('lbl_supply_points', lang=lang)}[/dim]\n[bold green]{summary.cups_count} CUPS[/bold green]",
        f"[dim]{t('lbl_total_gen', lang=lang)}[/dim]\n[bold yellow]{format_kwh(tot.total_generation_kwh)}[/bold yellow]",
        f"[dim]{t('lbl_total_cons', lang=lang)}[/dim]\n[bold bright_cyan]{format_kwh(tot.total_consumption_kwh)}[/bold bright_cyan]",
    )
    grid.add_row(
        f"[dim]{t('lbl_date_range', lang=lang)}[/dim]\n[white]{summary.start_time[:10]} ➔ {summary.end_time[:10]}[/white]",
        f"[dim]{t('lbl_total_sc', lang=lang)}[/dim]\n[bold green]{format_kwh(tot.total_self_consumed_kwh)}[/bold green] [dim]({tot.self_consumption_rate:.1f}%)[/dim]",
        f"[dim]{t('lbl_total_surplus', lang=lang)}[/dim]\n[yellow]{format_kwh(tot.total_surplus_kwh)}[/yellow]",
    )

    console.print()
    console.print(
        Panel(
            grid,
            title=f"[bold bright_cyan]{t('title_community_summary', lang=lang)}[/bold bright_cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_monthly_coefficients_table(
    month_metrics: CommunityMonthlyMetrics,
    lang: str | None = None,
    precision: int | None = None,
) -> None:
    """Render 80-column compliant tabular view of monthly coefficient proposals per CUPS."""
    from src.presentation.console import make_percentage_bar

    table = Table(
        title=f"[bold yellow]{t('title_monthly_coefficients', lang=lang, month=month_metrics.month)}[/bold yellow] "
        f"[dim](Gen: {month_metrics.total_generation_kwh:,.1f} kWh, Dem: {month_metrics.total_consumption_kwh:,.1f} kWh)[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 1),
        show_lines=False,
    )

    table.add_column(t("col_rank", lang=lang), justify="right", style="dim", width=2, no_wrap=True)
    table.add_column(t("col_cups", lang=lang), style="bold white", width=20, no_wrap=True)
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

    from src.config import get_precision

    prec = get_precision() if precision is None else precision
    sorted_cups = sorted(month_metrics.cups_metrics, key=lambda c: c.beta, reverse=True)
    for rank, cm in enumerate(sorted_cups, 1):
        pct = cm.beta * 100.0
        bar = make_percentage_bar(pct, width=8)
        table.add_row(
            str(rank),
            cm.cups,
            f"{pct:.{prec}f}%",
            bar,
            f"{cm.consumption_kwh:,.1f}",
            f"{cm.self_consumed_kwh:,.1f}",
            f"{cm.surplus_kwh:,.1f}",
        )

    console.print(table)
    console.print()


MONTH_ABBR_EN: Final[dict[str, str]] = {
    "01": "Jan",
    "02": "Feb",
    "03": "Mar",
    "04": "Apr",
    "05": "May",
    "06": "Jun",
    "07": "Jul",
    "08": "Aug",
    "09": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dec",
}
MONTH_ABBR_ES: Final[dict[str, str]] = {
    "01": "Ene",
    "02": "Feb",
    "03": "Mar",
    "04": "Abr",
    "05": "May",
    "06": "Jun",
    "07": "Jul",
    "08": "Ago",
    "09": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dic",
}


def render_coefficients_matrix_table(
    opt_result: OptimizationResult,
    lang: str | None = None,
    precision: int | None = None,
) -> None:
    """Render consolidated matrix table of monthly distribution shares (CUPS in Y, Months in X)."""
    from src.config import get_language, get_precision

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

    cups_width = 12 if compact_mode else 20
    table.add_column(t("col_cups", lang=lang), style="bold cyan", width=cups_width, no_wrap=True)

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
        display_cups = f"…{cups[-10:]}" if compact_mode and len(cups) > 12 else cups
        row = [display_cups]
        for m in matrix.months:
            row.append(matrix.format_cell(cups, m, precision=prec))
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


def render_monthly_trajectory_table(
    opt_result: OptimizationResult,
    lang: str | None = None,
) -> None:
    """Render month-by-month trajectory table of community self-consumption."""
    from src.config import get_language

    current_lang = lang or get_language()
    table = Table(
        title=f"[bold yellow]{t('title_monthly_trajectory', lang=lang)}[/bold yellow] [dim](kWh)[/dim]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 1),
        show_lines=False,
    )

    table.add_column(t("col_month", lang=lang), style="bold", width=7, no_wrap=True)
    table.add_column(
        t("col_generation", lang=lang), justify="right", style="yellow", width=9, no_wrap=True
    )
    table.add_column(
        t("col_consumption", lang=lang), justify="right", style="white", width=9, no_wrap=True
    )
    table.add_column(
        t("col_self_cons", lang=lang), justify="right", style="bold green", width=9, no_wrap=True
    )
    table.add_column(
        t("col_surplus", lang=lang), justify="right", style="dim yellow", width=9, no_wrap=True
    )
    table.add_column(
        t("col_sc_rate", lang=lang), justify="right", style="bright_cyan", width=7, no_wrap=True
    )
    table.add_column(
        t("col_cov_rate", lang=lang), justify="right", style="bold magenta", width=7, no_wrap=True
    )

    abbr_map = MONTH_ABBR_ES if current_lang == "es" else MONTH_ABBR_EN
    for m in opt_result.monthly_results:
        m_name = abbr_map.get(m.month, m.month)
        if m.has_data:
            table.add_row(
                m_name,
                f"{m.total_generation_kwh:,.1f}",
                f"{m.total_consumption_kwh:,.1f}",
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
            )

    tot = opt_result.total_summary
    table.add_section()
    table.add_row(
        f"[bold]{t('lbl_total', lang=lang)}[/bold]",
        f"[bold]{tot.total_generation_kwh:,.1f}[/bold]",
        f"[bold]{tot.total_consumption_kwh:,.1f}[/bold]",
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


def render_export_success(exported_paths: list[Path], lang: str | None = None) -> None:
    """Render list of generated report files."""
    if not exported_paths:
        return

    text = Text()
    for p in exported_paths:
        text.append(f"  • {p}\n", style="bold green")

    console.print(
        Panel(
            text,
            title=f"[bold green]{t('export_success_title', lang=lang)}[/bold green]",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_config_view(cfg: AppConfig, lang: str | None = None) -> None:
    """Render active configuration parameters table."""
    table = Table(
        title=f"⚙️ {t('title_config', lang=lang)}",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    table.add_column(t("col_setting", lang=lang), style="bold cyan")
    table.add_column(t("col_value", lang=lang), style="green")

    table.add_row("language", cfg.language)
    prec_unit = "decimal(es)" if (lang or get_language()) == "es" else "decimal(s)"
    table.add_row("share_precision", f"{cfg.share_precision} {prec_unit}")
    table.add_row("consumption_dir", str(cfg.consumption_dir))
    table.add_row("generation_dir", str(cfg.generation_dir))
    table.add_row("output_dir", str(cfg.output_dir))
    table.add_row("initialized_at", str(cfg.initialized_at or "—"))
    table.add_row("version", str(cfg.version or "—"))

    console.print()
    console.print(table)
    console.print()


def render_doctor_report(
    report: DoctorReport,
    verbose: bool = False,
    lang: str | None = None,
) -> None:
    """Render comprehensive diagnostic health report for the doctor command."""
    # 1. Overall Status Banner
    if report.overall_status == "ok":
        badge = f"[bold green]{t('doc_status_ok', lang=lang)}[/bold green]"
        border_col = "green"
    elif report.overall_status == "warning":
        badge = f"[bold yellow]{t('doc_status_warning', lang=lang)}[/bold yellow]"
        border_col = "yellow"
    else:
        badge = f"[bold red]{t('doc_status_error', lang=lang)}[/bold red]"
        border_col = "red"

    ov = report.overlap
    banner_grid = Table.grid(padding=(0, 2))
    banner_grid.add_column(style="bold white", width=25)
    banner_grid.add_column(style="cyan", width=22)
    banner_grid.add_column(style="bold white", width=22)
    banner_grid.add_column(style="green", width=16)

    cups_suffix = "puntos" if (lang or get_language()) == "es" else "supply points"
    hours_suffix = "h"
    ready_yes = f"[bold green]{t('doc_yes', lang=lang)}[/bold green]"
    ready_no = f"[bold red]{t('doc_no', lang=lang)}[/bold red]"

    banner_grid.add_row(
        t("doc_lbl_participating_cups", lang=lang),
        f"{ov.cups_count} {cups_suffix}",
        t("doc_lbl_common_hours", lang=lang),
        f"{ov.common_hours:,} {hours_suffix}",
    )
    banner_grid.add_row(
        t("doc_lbl_overlap_range", lang=lang),
        f"{ov.common_start[:10] if ov.common_start else '—'} ➔ {ov.common_end[:10] if ov.common_end else '—'}",
        t("doc_lbl_ready_calc", lang=lang),
        ready_yes if report.can_calculate else ready_no,
    )

    console.print()
    console.print(
        Panel(
            banner_grid,
            title=f"{t('doc_title_banner', lang=lang)} — {badge}",
            border_style=border_col,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )

    # 2. Consumption Files & CUPS Health Table
    if report.consumption_results:
        c_table = Table(
            title=t("doc_title_consumption", lang=lang),
            box=box.ROUNDED,
            padding=(0, 1),
            show_lines=False,
        )
        c_table.add_column("CUPS", style="bold cyan", width=22, no_wrap=True)
        c_table.add_column(
            t("lbl_doctor_readings", lang=lang),
            justify="right",
            style="white",
            width=9,
            no_wrap=True,
        )
        c_table.add_column(
            t("doc_lbl_zero_pct", lang=lang), justify="right", style="dim", width=7, no_wrap=True
        )
        c_table.add_column(
            t("lbl_doctor_gaps", lang=lang), justify="right", style="yellow", width=5, no_wrap=True
        )
        c_table.add_column(
            t("lbl_doctor_status", lang=lang), justify="center", width=9, no_wrap=True
        )
        c_table.add_column(
            t("lbl_doctor_diagnosis", lang=lang), style="dim", width=22, no_wrap=True
        )

        for c in report.consumption_results:
            if c.status == "ok":
                st_badge = "[green]✓ OK[/green]"
            elif c.status == "warning":
                st_badge = "[yellow]⚠ WARN[/yellow]"
            else:
                st_badge = "[red]✗ FAIL[/red]"

            note_str = c.notes[0] if c.notes else t("doc_lbl_healthy", lang=lang)
            if len(note_str) > 22:
                note_str = note_str[:20] + "…"

            c_table.add_row(
                c.identifier,
                f"{c.total_records:,}",
                f"{c.zero_ratio_pct:.1f}%",
                str(c.missing_hours),
                st_badge,
                note_str,
            )

        console.print(c_table)
        console.print()

    # 3. Generation File Health Table
    if report.generation_result:
        g = report.generation_result
        g_table = Table(
            title=t("title_doctor_gen", lang=lang),
            box=box.ROUNDED,
            padding=(0, 1),
            show_lines=False,
        )
        g_table.add_column(
            t("lbl_doctor_source", lang=lang), style="bold yellow", width=24, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_files", lang=lang), justify="right", style="white", width=7, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_readings", lang=lang),
            justify="right",
            style="white",
            width=9,
            no_wrap=True,
        )
        g_table.add_column(
            t("lbl_doctor_gaps", lang=lang), justify="right", style="yellow", width=5, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_status", lang=lang), justify="center", width=9, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_diagnosis", lang=lang), style="dim", width=20, no_wrap=True
        )

        g_badge = "[green]✓ OK[/green]" if g.status == "ok" else "[yellow]⚠ WARN[/yellow]"
        g_note = g.notes[0] if g.notes else t("doc_lbl_healthy", lang=lang)
        if len(g_note) > 20:
            g_note = g_note[:18] + "…"

        g_table.add_row(
            t("doc_source_huawei", lang=lang),
            str(g.files_count),
            f"{g.total_records:,}",
            str(g.missing_hours),
            g_badge,
            g_note,
        )
        console.print(g_table)
        console.print()

    # 4. Detailed Gap Breakdown (if gaps exist or verbose)
    all_gaps: list[tuple[str, GapInterval]] = []
    for c in report.consumption_results:
        for gap in c.gaps:
            all_gaps.append((c.identifier, gap))
    if report.generation_result:
        for gap in report.generation_result.gaps:
            all_gaps.append(("Huawei Generation", gap))

    if all_gaps:
        gap_table = Table(
            title=t("title_doctor_gaps", lang=lang),
            box=box.ROUNDED,
            padding=(0, 1),
        )
        gap_table.add_column(
            t("lbl_doctor_series", lang=lang), style="bold cyan", width=22, no_wrap=True
        )
        gap_table.add_column(
            t("lbl_doctor_gap_start", lang=lang), style="yellow", width=17, no_wrap=True
        )
        gap_table.add_column(
            t("lbl_doctor_gap_end", lang=lang), style="yellow", width=17, no_wrap=True
        )
        gap_table.add_column(
            t("lbl_doctor_missing", lang=lang),
            justify="right",
            style="bold red",
            width=9,
            no_wrap=True,
        )

        show_gaps = all_gaps if verbose else all_gaps[:10]
        for series_id, gap in show_gaps:
            gap_table.add_row(
                series_id,
                gap.start_time,
                gap.end_time,
                f"{gap.missing_hours} h",
            )
        if len(all_gaps) > 10 and not verbose:
            gap_table.add_row(
                "...",
                t("doc_more_gaps", lang=lang, count=len(all_gaps) - 10),
                t("doc_verbose_hint", lang=lang),
                "",
            )

        console.print(gap_table)
        console.print()

    # 5. Diagnostic Findings & Actionable Advice
    advice_items: list[str] = []
    for c in report.consumption_results:
        if c.zero_ratio_pct >= 99.0:
            advice_items.append(
                t("doc_adv_inactive", lang=lang, id=c.identifier, pct=f"{c.zero_ratio_pct:.1f}")
            )
        if c.missing_hours > 0:
            advice_items.append(
                t("doc_adv_cons_gaps", lang=lang, id=c.identifier, hours=c.missing_hours)
            )
    if report.generation_result and report.generation_result.missing_hours > 0:
        advice_items.append(
            t("doc_adv_gen_gaps", lang=lang, hours=report.generation_result.missing_hours)
        )

    if not advice_items:
        advice_items.append(t("doc_adv_clean", lang=lang))

    advice_text = Text()
    for item in advice_items:
        advice_text.append(f" {item}\n")

    console.print(
        Panel(
            advice_text,
            title=t("doc_title_advice", lang=lang),
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
