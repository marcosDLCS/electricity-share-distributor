"""Common terminal screens, dialogs, and general views rendered with Rich for esd."""

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
    from src.ingestion.weather import WeatherDownloadResult

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
    "2026-01": "Jan",
    "2026-02": "Feb",
    "2026-03": "Mar",
    "2026-04": "Apr",
    "2026-05": "May",
    "2026-06": "Jun",
    "2026-07": "Jul",
    "2026-08": "Aug",
    "2026-09": "Sep",
    "2026-10": "Oct",
    "2026-11": "Nov",
    "2026-12": "Dec",
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
    "2026-01": "Ene",
    "2026-02": "Feb",
    "2026-03": "Mar",
    "2026-04": "Abr",
    "2026-05": "May",
    "2026-06": "Jun",
    "2026-07": "Jul",
    "2026-08": "Ago",
    "2026-09": "Sep",
    "2026-10": "Oct",
    "2026-11": "Nov",
    "2026-12": "Dic",
}


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

    cmd_table.add_row("calculate", t("cmd_calculate_desc", lang=lang))
    cmd_table.add_row("curate", t("cmd_curate_desc", lang=lang))
    cmd_table.add_row("doctor", t("cmd_doctor_desc", lang=lang))
    cmd_table.add_row("init", t("cmd_init_desc", lang=lang))
    cmd_table.add_row("config", t("cmd_config_desc", lang=lang))
    cmd_table.add_row("cleanup", t("cmd_cleanup_desc", lang=lang))
    cmd_table.add_row("weather", t("cmd_weather_desc", lang=lang))
    cmd_table.add_row("help", t("cmd_help_desc", lang=lang))
    cmd_table.add_row("version", t("cmd_version_desc", lang=lang))

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
    table.add_row("weather_dir", str(cfg.weather_dir))
    table.add_row("output_dir", str(cfg.output_dir))
    coords_val = (
        f"{cfg.latitude}, {cfg.longitude}"
        if cfg.latitude is not None and cfg.longitude is not None
        else "—"
    )
    table.add_row("coordinates", coords_val)
    table.add_row("initialized_at", str(cfg.initialized_at or "—"))
    table.add_row("version", str(cfg.version or "—"))

    console.print()
    console.print(table)
    console.print()


def render_weather_result(
    result: WeatherDownloadResult,
    lang: str | None = None,
) -> None:
    """Render rich summary card for downloaded Open-Meteo hourly weather data."""
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    lat_str = f"{abs(result.latitude):.4f}°{'N' if result.latitude >= 0 else 'S'}"
    lon_str = f"{abs(result.longitude):.4f}°{'E' if result.longitude >= 0 else 'W'}"
    coords_text = f"{lat_str}, {lon_str}"

    grid.add_row(
        f"[dim]{t('weather_lbl_coords', lang=lang)}[/dim]\n[bold green]{coords_text}[/bold green]",
        f"[dim]{t('weather_lbl_year', lang=lang)}[/dim]\n[bold yellow]{result.year}[/bold yellow] [dim]({result.total_hours:,} hrs)[/dim]",
        f"[dim]{t('weather_lbl_period', lang=lang)}[/dim]\n[white]{result.start_date} ➔ {result.end_date}[/white]",
    )

    temp_summary = f"{result.avg_temperature:.1f}°C [dim]({result.min_temperature:.1f} / {result.max_temperature:.1f})[/dim]"
    cloud_summary = f"{result.avg_cloud_cover:.1f}%"
    dest_str = f"{result.file_path.name}"
    if result.overwritten:
        dest_str += f" {t('weather_overwritten', lang=lang)}"

    grid.add_row(
        f"[dim]{t('weather_lbl_temp', lang=lang)} (Avg / Min / Max)[/dim]\n[bold bright_cyan]{temp_summary}[/bold bright_cyan]",
        f"[dim]{t('weather_lbl_cloud', lang=lang)}[/dim]\n[bold white]{cloud_summary}[/bold white]",
        f"[dim]{t('weather_lbl_dest', lang=lang)}[/dim]\n[dim]{dest_str}[/dim]",
    )

    console.print()
    console.print(
        Panel(
            grid,
            title=f"[bold bright_cyan]{t('title_weather', lang=lang)}[/bold bright_cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
