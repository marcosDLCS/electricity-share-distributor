"""Terminal views, tables, cards, and help screens rendered with Rich for esd."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import SUPPORTED_LANGUAGES
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


def render_version() -> None:
    """Render a rich, formatted version panel for 'esd version'."""
    version = get_version()
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold cyan", no_wrap=True)
    info_table.add_column(style="white")

    info_table.add_row("☀️ Version", f"[bold cyan]{version}[/bold cyan]")
    info_table.add_row("🐍 Python", f"[dim]{py_version}[/dim]")
    info_table.add_row("📜 License", "[dim]MIT[/dim]")
    info_table.add_row(
        "🌐 Source",
        "[dim]github.com/marcosDLCS/electricity-share-distributor[/dim]",
    )

    title_text = Text()
    title_text.append("Electricity Share Distributor ", style="bold yellow")
    title_text.append("(esd)", style="bold white")

    subtitle = Text(
        "\nCollective PV self-consumption coefficient optimization CLI (RD 244/2019)\n",
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
    title = (
        "[bold green]✓ Initialized Successfully[/bold green]"
        if not was_already
        else "[bold green]✓ Re-initialized Successfully[/bold green]"
    )
    lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
    prec_example = "53%" if precision == 0 else ("52.8%" if precision == 1 else "52.86%")
    msg_key = "init_reinit" if was_already else "init_success"
    msg = t(msg_key, lang=lang, language=lang_name)

    lines = [
        msg,
        f"[dim]• Language: [cyan]{lang_name}[/cyan] ({lang})[/dim]",
        f"[dim]• Share Precision: [cyan]{precision} decimal(s)[/cyan] (e.g. {prec_example}, sums to 100%)[/dim]",
        f"[dim]• Timestamp: {initialized_at}[/dim]",
    ]
    if cleared_files > 0:
        lines.append(
            f"[dim]• Output Directory: [yellow]Cleared {cleared_files} file(s) from .output[/yellow][/dim]"
        )
    else:
        lines.append("[dim]• Output Directory: [cyan]Ready & clean[/cyan][/dim]")

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
            f"{msg}\n[dim]Directory: {output_dir}[/dim]",
            title="[bold yellow]🧹 Cleanup Summary[/bold yellow]",
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


def render_monthly_trajectory_table(
    opt_result: OptimizationResult,
    lang: str | None = None,
) -> None:
    """Render month-by-month trajectory table of community self-consumption."""
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

    for m in opt_result.monthly_results:
        table.add_row(
            m.month,
            f"{m.total_generation_kwh:,.1f}",
            f"{m.total_consumption_kwh:,.1f}",
            f"{m.total_self_consumed_kwh:,.1f}",
            f"{m.total_surplus_kwh:,.1f}",
            f"{m.self_consumption_rate:.1f}%",
            f"{m.solar_coverage_rate:.1f}%",
        )

    tot = opt_result.total_summary
    table.add_section()
    table.add_row(
        "[bold]Total[/bold]",
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
        "★ Optimal (RD 244/2019)",
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
            else ("Baseline" if b_gain == 0 else f"{b_gain:,.1f}")
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
        title="⚙️ Active Configuration",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="green")

    table.add_row("language", cfg.language)
    table.add_row("share_precision", f"{cfg.share_precision} decimal(s)")
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
        badge = "[bold green]✓ ALL DATA HEALTHY & SYNCHRONIZED[/bold green]"
        border_col = "green"
    elif report.overall_status == "warning":
        badge = "[bold yellow]⚠ DATA USABLE WITH DIAGNOSTIC WARNINGS[/bold yellow]"
        border_col = "yellow"
    else:
        badge = "[bold red]✗ CRITICAL DATA ISSUES DETECTED[/bold red]"
        border_col = "red"

    ov = report.overlap
    banner_grid = Table.grid(padding=(0, 2))
    banner_grid.add_column(style="bold white", width=22)
    banner_grid.add_column(style="cyan", width=20)
    banner_grid.add_column(style="bold white", width=18)
    banner_grid.add_column(style="green", width=16)

    banner_grid.add_row(
        "Participating CUPS:",
        f"{ov.cups_count} supply points",
        "Common Hours:",
        f"{ov.common_hours:,} hours",
    )
    banner_grid.add_row(
        "Overlap Date Range:",
        f"{ov.common_start[:10] if ov.common_start else '—'} ➔ {ov.common_end[:10] if ov.common_end else '—'}",
        "Ready to Calculate:",
        "[bold green]Yes[/bold green]" if report.can_calculate else "[bold red]No[/bold red]",
    )

    console.print()
    console.print(
        Panel(
            banner_grid,
            title=f"🩺 ESD DATA DOCTOR DIAGNOSTIC REPORT — {badge}",
            border_style=border_col,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )

    # 2. Consumption Files & CUPS Health Table
    if report.consumption_results:
        c_table = Table(
            title="📥 Consumption Data Health per CUPS (DATADIS)",
            box=box.ROUNDED,
            padding=(0, 1),
            show_lines=False,
        )
        c_table.add_column("CUPS", style="bold cyan", width=22, no_wrap=True)
        c_table.add_column("Readings", justify="right", style="white", width=9, no_wrap=True)
        c_table.add_column("Zero %", justify="right", style="dim", width=7, no_wrap=True)
        c_table.add_column("Gaps", justify="right", style="yellow", width=5, no_wrap=True)
        c_table.add_column("Status", justify="center", width=9, no_wrap=True)
        c_table.add_column("Diagnosis Notes", style="dim", width=22, no_wrap=True)

        for c in report.consumption_results:
            if c.status == "ok":
                st_badge = "[green]✓ OK[/green]"
            elif c.status == "warning":
                st_badge = "[yellow]⚠ WARN[/yellow]"
            else:
                st_badge = "[red]✗ FAIL[/red]"

            note_str = c.notes[0] if c.notes else "Healthy"
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
            title="☀️ Solar PV Generation Health (Huawei FusionSolar)",
            box=box.ROUNDED,
            padding=(0, 1),
            show_lines=False,
        )
        g_table.add_column("Source", style="bold yellow", width=24, no_wrap=True)
        g_table.add_column("Files", justify="right", style="white", width=7, no_wrap=True)
        g_table.add_column("Readings", justify="right", style="white", width=9, no_wrap=True)
        g_table.add_column("Gaps", justify="right", style="yellow", width=5, no_wrap=True)
        g_table.add_column("Status", justify="center", width=9, no_wrap=True)
        g_table.add_column("Diagnosis Notes", style="dim", width=20, no_wrap=True)

        g_badge = "[green]✓ OK[/green]" if g.status == "ok" else "[yellow]⚠ WARN[/yellow]"
        g_note = g.notes[0] if g.notes else "Healthy"
        if len(g_note) > 20:
            g_note = g_note[:18] + "…"

        g_table.add_row(
            "Huawei PV Generation",
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
            title="⚠️ Detected Missing Interval Gaps",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        gap_table.add_column("Series", style="bold cyan", width=22, no_wrap=True)
        gap_table.add_column("Gap Start", style="yellow", width=17, no_wrap=True)
        gap_table.add_column("Gap End", style="yellow", width=17, no_wrap=True)
        gap_table.add_column("Missing", justify="right", style="bold red", width=9, no_wrap=True)

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
                f"+{len(all_gaps) - 10} more gaps",
                "Use --verbose to view all",
                "",
            )

        console.print(gap_table)
        console.print()

    # 5. Diagnostic Findings & Actionable Advice
    advice_items: list[str] = []
    for c in report.consumption_results:
        if c.zero_ratio_pct >= 99.0:
            advice_items.append(
                f"[yellow]• Inactive Meter:[/yellow] {c.identifier} has {c.zero_ratio_pct}% zero readings. In optimization, its β coefficient will be 0.00% to protect community solar energy."
            )
        if c.missing_hours > 0:
            advice_items.append(
                f"[yellow]• Consumption Gaps:[/yellow] {c.identifier} has {c.missing_hours} missing hours. Download updated DATADIS CSV for complete billing periods."
            )
    if report.generation_result and report.generation_result.missing_hours > 0:
        advice_items.append(
            f"[yellow]• Generation Gaps:[/yellow] Huawei solar series has {report.generation_result.missing_hours} missing hours. Check inverter log exports."
        )

    if not advice_items:
        advice_items.append(
            "[green]• Dataset is clean and ready. You can safely run 'esd calculate'.[/green]"
        )

    advice_text = Text()
    for item in advice_items:
        advice_text.append(f" {item}\n")

    console.print(
        Panel(
            advice_text,
            title="💡 Doctor Findings & Recommendations",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
