"""Pre-flight data doctor audit views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import get_language
from src.i18n import t
from src.presentation.console import console

if TYPE_CHECKING:
    from src.ingestion.doctor import DoctorReport, GapInterval


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
            title=t("doc_title_banner", lang=lang),
            subtitle=badge,
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
        c_table.add_column(t("col_cups_desc", lang=lang), style="bold cyan", width=22, no_wrap=True)
        c_table.add_column(
            t("lbl_doctor_readings", lang=lang),
            justify="right",
            style="white",
            width=8,
            no_wrap=True,
        )
        c_table.add_column(
            t("doc_lbl_zero_pct", lang=lang), justify="right", style="dim", width=7, no_wrap=True
        )
        c_table.add_column(
            t("lbl_doctor_gaps", lang=lang), justify="right", style="yellow", width=6, no_wrap=True
        )
        c_table.add_column(
            t("lbl_doctor_status", lang=lang), justify="center", width=7, no_wrap=True
        )
        c_table.add_column(
            t("lbl_doctor_diagnosis", lang=lang), style="dim", width=12, no_wrap=True
        )

        for c in report.consumption_results:
            if c.status == "ok":
                st_badge = "[green]✓ OK[/green]"
            elif c.status == "warning":
                st_badge = "[yellow]⚠ WARN[/yellow]"
            else:
                st_badge = "[red]✗ FAIL[/red]"

            note_str = c.notes[0] if c.notes else t("doc_lbl_healthy", lang=lang)
            if len(note_str) > 12:
                note_str = note_str[:11] + "…"

            if c.use:
                pri_star = " [bold green]★[/bold green]" if c.is_primary else ""
                cups_cell = f"{c.identifier}\n[dim white]{c.use}{pri_star}[/dim white]"
            else:
                cups_cell = c.identifier

            c_table.add_row(
                cups_cell,
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
            t("lbl_doctor_source", lang=lang), style="bold yellow", width=20, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_files", lang=lang), justify="right", style="white", width=8, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_readings", lang=lang),
            justify="right",
            style="white",
            width=8,
            no_wrap=True,
        )
        g_table.add_column(
            t("lbl_doctor_gaps", lang=lang), justify="right", style="yellow", width=6, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_status", lang=lang), justify="center", width=7, no_wrap=True
        )
        g_table.add_column(
            t("lbl_doctor_diagnosis", lang=lang), style="dim", width=12, no_wrap=True
        )

        g_badge = "[green]✓ OK[/green]" if g.status == "ok" else "[yellow]⚠ WARN[/yellow]"
        g_note = g.notes[0] if g.notes else t("doc_lbl_healthy", lang=lang)
        if len(g_note) > 12:
            g_note = g_note[:11] + "…"

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

    # 4. Weather Ingestion Health Table
    if report.weather_result:
        w = report.weather_result
        w_table = Table(
            title=t("title_doctor_weather", lang=lang),
            box=box.ROUNDED,
            padding=(0, 1),
            show_lines=False,
        )
        w_table.add_column(
            t("lbl_doctor_source", lang=lang), style="bold bright_cyan", width=20, no_wrap=True
        )
        w_table.add_column(
            t("lbl_doctor_files", lang=lang), justify="right", style="white", width=8, no_wrap=True
        )
        w_table.add_column(
            t("lbl_doctor_readings", lang=lang),
            justify="right",
            style="white",
            width=8,
            no_wrap=True,
        )
        w_table.add_column(
            t("lbl_doctor_gaps", lang=lang), justify="right", style="yellow", width=6, no_wrap=True
        )
        w_table.add_column(
            t("lbl_doctor_status", lang=lang), justify="center", width=7, no_wrap=True
        )
        w_table.add_column(
            t("lbl_doctor_diagnosis", lang=lang), style="dim", width=12, no_wrap=True
        )

        if w.status == "ok":
            w_badge = "[green]✓ OK[/green]"
        elif w.status == "warning":
            w_badge = "[yellow]⚠ WARN[/yellow]"
        else:
            w_badge = "[red]✗ FAIL[/red]"

        w_note = w.notes[0] if w.notes else t("doc_lbl_healthy", lang=lang)
        if len(w_note) > 12:
            w_note = w_note[:11] + "…"

        w_table.add_row(
            t("doc_source_weather", lang=lang),
            str(w.files_count),
            f"{w.total_records:,}",
            str(w.missing_hours),
            w_badge,
            w_note,
        )
        console.print(w_table)
        console.print()

    # 5. Detailed Gap Breakdown (if gaps exist or verbose)
    all_gaps: list[tuple[str, GapInterval]] = []
    for c in report.consumption_results:
        display_id = f"{c.identifier} ({c.use})" if c.use else c.identifier
        for gap in c.gaps:
            all_gaps.append((display_id, gap))
    if report.generation_result:
        for gap in report.generation_result.gaps:
            all_gaps.append((t("doc_source_huawei", lang=lang), gap))
    if report.weather_result:
        for gap in report.weather_result.gaps:
            all_gaps.append((t("doc_source_weather", lang=lang), gap))

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

    # 6. Diagnostic Findings & Actionable Advice
    advice_items: list[str] = []
    for c in report.consumption_results:
        display_id = f"{c.identifier} ({c.use})" if c.use else c.identifier
        if c.zero_ratio_pct >= 99.0:
            advice_items.append(
                t("doc_adv_inactive", lang=lang, id=display_id, pct=f"{c.zero_ratio_pct:.1f}")
            )
        if c.missing_hours > 0:
            advice_items.append(
                t("doc_adv_cons_gaps", lang=lang, id=display_id, hours=c.missing_hours)
            )
    if report.generation_result and report.generation_result.missing_hours > 0:
        advice_items.append(
            t("doc_adv_gen_gaps", lang=lang, hours=report.generation_result.missing_hours)
        )
    if report.weather_result:
        w = report.weather_result
        if w.files_count == 0:
            advice_items.append(t("doc_adv_weather_missing", lang=lang, dir=".input/weather"))
        elif w.missing_hours > 0:
            advice_items.append(t("doc_adv_weather_gaps", lang=lang, hours=w.missing_hours))
        elif any("does not fully cover" in note for note in w.notes):
            period_str = (
                f"{ov.common_start[:10]} ➔ {ov.common_end[:10]}"
                if ov.common_start and ov.common_end
                else ""
            )
            advice_items.append(t("doc_adv_weather_coverage", lang=lang, period=period_str))

    if not advice_items:
        advice_items.append(t("doc_adv_clean", lang=lang))

    advice_content = Text.from_markup("\n".join(f" {item}" for item in advice_items))

    console.print(
        Panel(
            advice_content,
            title=t("doc_title_advice", lang=lang),
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
