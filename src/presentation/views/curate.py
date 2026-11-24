"""Curation summary and reconciliation views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.i18n import t
from src.presentation.console import console, format_cups_label, format_kwh

if TYPE_CHECKING:
    from pathlib import Path

    from src.curation.models import CuratedDataset


def render_curate_summary(
    dataset: CuratedDataset,
    csv_path: Path,
    excel_path: Path | None = None,
    lang: str = "en",
    generation_csv_path: Path | None = None,
    generation_excel_path: Path | None = None,
    consumption_csv_path: Path | None = None,
    consumption_excel_path: Path | None = None,
) -> None:
    """Render a comprehensive, 80-column rich summary of curated data reconciliation."""
    s = dataset.summary
    start_dt = s.start_time.split(" ")[0] if s.start_time else "—"
    end_dt = s.end_time.split(" ")[0] if s.end_time else "—"

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    grid.add_row(
        f"[value.strong]{t('lbl_supply_points', lang=lang)}:[/value.strong] {s.cups_count} CUPS",
        f"[value.strong]{t('lbl_total_hours', lang=lang)}:[/value.strong] {s.total_hours:,} h",
    )
    grid.add_row(
        f"[value.strong]{t('lbl_date_range', lang=lang)}:[/value.strong] {start_dt} ➔ {end_dt}",
        f"[value.strong]{t('lbl_total_gen', lang=lang)}:[/value.strong] {format_kwh(s.total_generation_kwh)}",
    )
    grid.add_row(
        f"[value.strong]{t('lbl_total_cons', lang=lang)}:[/value.strong] {format_kwh(s.total_consumption_kwh)}",
        f"[value.strong]{t('lbl_reconciled_hours', lang=lang)}:[/value.strong] [solar]{s.reconciled_hours_count:,} h[/solar]",
    )
    if s.recovered_kwh > 0:
        grid.add_row(
            f"[value.strong]{t('lbl_recovered_kwh', lang=lang)}:[/value.strong] [success]+{format_kwh(s.recovered_kwh)}[/success]",
            "",
        )

    console.print()
    console.print(
        Panel(
            grid,
            title=f"[title]{t('title_curate_summary', lang=lang)}[/title]",
            box=box.ROUNDED,
            border_style="panel.border",
            padding=(1, 2),
        )
    )

    table = Table(
        title=f"[table.header]{t('lbl_supply_points', lang=lang)}[/table.header]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        show_lines=False,
    )
    table.add_column(t("col_cups", lang=lang), style="cups", no_wrap=True)
    table.add_column(t("col_use", lang=lang), style="value")
    table.add_column(t("col_primary", lang=lang), justify="center", no_wrap=True)
    table.add_column(t("col_reconciled_hours", lang=lang), justify="right", no_wrap=True)
    table.add_column(t("col_curated_cons", lang=lang), justify="right", no_wrap=True)

    sorted_cups = sorted(s.cups_total_consumption.keys())
    for cups in sorted_cups:
        cfg = dataset.cups_configs.get(cups)
        use_str = cfg.use if cfg and cfg.use else "—"
        is_pri = cfg.primary if cfg else False
        pri_str = "[success]★ Primary[/success]" if is_pri else "—"
        rec_count = s.cups_reconciled_hours.get(cups, 0)
        rec_str = f"[solar]{rec_count:,} h[/solar]" if rec_count > 0 else "0 h"
        cons_str = format_kwh(s.cups_total_consumption.get(cups, 0.0))

        table.add_row(format_cups_label(cups), use_str, pri_str, rec_str, cons_str)

    table.add_section()
    table.add_row(
        t("lbl_total", lang=lang),
        "",
        "",
        f"[solar]{s.reconciled_hours_count:,} h[/solar]",
        f"[success]{format_kwh(s.total_consumption_kwh)}[/success]",
    )

    console.print(table)
    console.print()

    export_text = Text()

    def _append_artifact(label: str, path: Path | None, always_show: bool = False) -> None:
        if path and (path.exists() or always_show):
            size_str = f"{path.stat().st_size / 1024:.1f} KB" if path.exists() else "—"
            export_text.append(f"{label:<18}", style="success")
            export_text.append(f"{path} ", style="value")
            export_text.append(f"({size_str})\n", style="dimmed")

    _append_artifact("☀️ Gen CSV:", generation_csv_path)
    _append_artifact("☀️ Gen Excel:", generation_excel_path)
    _append_artifact("📥 Cons CSV:", consumption_csv_path)
    _append_artifact("📥 Cons Excel:", consumption_excel_path)
    _append_artifact("📊 ESD CSV:", csv_path, always_show=True)
    _append_artifact("📑 ESD Excel:", excel_path)

    console.print(
        Panel(
            export_text,
            title=f"[success]{t('curate_success_title', lang=lang)}[/success]",
            border_style="panel.border.success",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
