"""Pre-flight data doctor audit views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import get_language
from src.i18n import t
from src.presentation.console import console

if TYPE_CHECKING:
    from src.ingestion.doctor import DoctorReport, GapInterval


def _status_badge(status: str) -> str:
    """Return compact Rich status badge for diagnostic series rows."""
    if status == "ok":
        return "[green]✓ OK[/green]"
    if status == "warning":
        return "[yellow]⚠ WARN[/yellow]"
    return "[red]✗ FAIL[/red]"


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
            padding=(0, 2),
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
        c_table.add_column(t("col_cups_desc", lang=lang), style="bold cyan", min_width=22)
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

        for c in report.consumption_results:
            if c.use:
                pri_star = " [bold green]★[/bold green]" if c.is_primary else ""
                cups_cell = f"{c.identifier} [dim white]({c.use}{pri_star})[/dim white]"
            else:
                cups_cell = c.identifier

            c_table.add_row(
                cups_cell,
                f"{c.total_records:,}",
                f"{c.zero_ratio_pct:.1f}%",
                str(c.missing_hours),
                _status_badge(c.status),
            )

        console.print(c_table)
        console.print()

    # 3. Unified Data Sources Table (Generation + Weather)
    if report.generation_result or report.weather_result:
        s_table = Table(
            title=t("title_doctor_sources", lang=lang),
            box=box.ROUNDED,
            padding=(0, 1),
            show_lines=False,
        )
        s_table.add_column(
            t("lbl_doctor_source", lang=lang), style="bold yellow", width=22, no_wrap=True
        )
        s_table.add_column(
            t("lbl_doctor_files", lang=lang), justify="right", style="white", width=7, no_wrap=True
        )
        s_table.add_column(
            t("lbl_doctor_readings", lang=lang),
            justify="right",
            style="white",
            width=9,
            no_wrap=True,
        )
        s_table.add_column(
            t("lbl_doctor_gaps", lang=lang), justify="right", style="yellow", width=6, no_wrap=True
        )
        s_table.add_column(
            t("lbl_doctor_status", lang=lang), justify="center", width=7, no_wrap=True
        )

        if report.generation_result:
            g = report.generation_result
            s_table.add_row(
                t("doc_source_huawei", lang=lang),
                str(g.files_count),
                f"{g.total_records:,}",
                str(g.missing_hours),
                _status_badge(g.status),
            )
        if report.weather_result:
            w = report.weather_result
            s_table.add_row(
                t("doc_source_weather", lang=lang),
                str(w.files_count),
                f"{w.total_records:,}",
                str(w.missing_hours),
                _status_badge(w.status),
            )

        console.print(s_table)
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
        if c.duplicate_records > 0 or c.negative_records > 0 or c.null_records > 0:
            for note in c.notes:
                if any(kw in note for kw in ("duplicate", "negative", "null")):
                    advice_items.append(f"[yellow]• {escape(display_id)}:[/yellow] {escape(note)}")
    if report.generation_result:
        g_res = report.generation_result
        if g_res.missing_hours > 0:
            advice_items.append(t("doc_adv_gen_gaps", lang=lang, hours=g_res.missing_hours))
        for note in g_res.notes:
            if any(kw in note for kw in ("duplicate", "negative", "null", "telemetry outage")):
                advice_items.append(
                    f"[yellow]• {escape(t('doc_source_huawei', lang=lang))}:[/yellow] {escape(note)}"
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
        for note in w.notes:
            if any(kw in note for kw in ("duplicate", "null", "cloud cover")):
                advice_items.append(
                    f"[yellow]• {escape(t('doc_source_weather', lang=lang))}:[/yellow] {escape(note)}"
                )

    for msg in report.summary_messages:
        advice_items.append(f"[yellow]ℹ[/yellow] {escape(msg)}")

    advice_items = list(dict.fromkeys(advice_items))
    if not advice_items:
        advice_items.append(t("doc_adv_clean", lang=lang))

    advice_content = Text.from_markup("\n".join(f" {item}" for item in advice_items))

    console.print(
        Panel(
            advice_content,
            title=t("doc_title_advice", lang=lang),
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()
