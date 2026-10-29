"""Curation summary and reconciliation views rendered with Rich."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.i18n import t
from src.presentation.console import console

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

    # 1. Summary Metrics Panel
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    grid.add_row(
        f"[bold]{t('lbl_supply_points', lang=lang)}:[/bold] {s.cups_count} supply points",
        f"[bold]{t('lbl_total_hours', lang=lang)}:[/bold] {s.total_hours:,} h",
    )
    grid.add_row(
        f"[bold]{t('lbl_date_range', lang=lang)}:[/bold] {start_dt} ➔ {end_dt}",
        f"[bold]{t('lbl_total_gen', lang=lang)}:[/bold] {s.total_generation_kwh:,.1f} kWh",
    )
    grid.add_row(
        f"[bold]{t('lbl_total_cons', lang=lang)}:[/bold] {s.total_consumption_kwh:,.1f} kWh",
        f"[bold]{t('lbl_reconciled_hours', lang=lang)}:[/bold] [bold yellow]{s.reconciled_hours_count:,} h[/bold yellow]",
    )
    if s.recovered_kwh > 0:
        grid.add_row(
            f"[bold]{t('lbl_recovered_kwh', lang=lang)}:[/bold] [bold green]+{s.recovered_kwh:,.1f} kWh[/bold green]",
            "",
        )

    console.print()
    console.print(
        Panel(
            grid,
            title=f"[bold yellow]{t('title_curate_summary', lang=lang)}[/bold yellow]",
            box=box.ROUNDED,
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # 2. Per-CUPS Reconciliation Table
    table = Table(
        title=f"[bold cyan]{t('lbl_supply_points', lang=lang)}[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column(t("col_cups", lang=lang), style="bold cyan", no_wrap=True)
    table.add_column(t("col_use", lang=lang), style="white")
    table.add_column(t("col_primary", lang=lang), justify="center", no_wrap=True)
    table.add_column(t("col_reconciled_hours", lang=lang), justify="right", no_wrap=True)
    table.add_column(t("col_curated_cons", lang=lang), justify="right", no_wrap=True)

    sorted_cups = sorted(s.cups_total_consumption.keys())
    for cups in sorted_cups:
        cfg = dataset.cups_configs.get(cups)
        use_str = cfg.use if cfg and cfg.use else "—"
        is_pri = cfg.primary if cfg else False
        pri_str = "[bold green]★ Primary[/bold green]" if is_pri else "—"
        rec_count = s.cups_reconciled_hours.get(cups, 0)
        rec_str = f"[bold yellow]{rec_count:,} h[/bold yellow]" if rec_count > 0 else "0 h"
        cons_str = f"{s.cups_total_consumption.get(cups, 0.0):,.1f} kWh"

        table.add_row(cups, use_str, pri_str, rec_str, cons_str)

    table.add_section()
    table.add_row(
        t("lbl_total", lang=lang),
        "",
        "",
        f"[bold yellow]{s.reconciled_hours_count:,} h[/bold yellow]",
        f"[bold green]{s.total_consumption_kwh:,.1f} kWh[/bold green]",
    )

    console.print(table)
    console.print()

    # 3. Export Artifacts Panel
    export_text = Text()

    def _append_artifact(label: str, path: Path | None, always_show: bool = False) -> None:
        if path and (path.exists() or always_show):
            size_str = f"{path.stat().st_size / 1024:.1f} KB" if path.exists() else "—"
            export_text.append(f"{label:<18}", style="bold green")
            export_text.append(f"{path} ", style="white")
            export_text.append(f"({size_str})\n", style="dim")

    _append_artifact("☀️ Gen CSV:", generation_csv_path)
    _append_artifact("☀️ Gen Excel:", generation_excel_path)
    _append_artifact("📥 Cons CSV:", consumption_csv_path)
    _append_artifact("📥 Cons Excel:", consumption_excel_path)
    _append_artifact("📊 ESD CSV:", csv_path, always_show=True)
    _append_artifact("📑 ESD Excel:", excel_path)

    console.print(
        Panel(
            export_text,
            title=f"[bold green]{t('curate_success_title', lang=lang)}[/bold green]",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
