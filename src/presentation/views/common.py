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


def format_month_abbr(month: str | int, lang: str = "en") -> str:
    """Format month identifier ('01'..'12', '2026-05', or int 1..12) as localized abbreviation."""
    m_clean = str(month).split("-")[-1].zfill(2)
    abbr_map = MONTH_ABBR_ES if lang == "es" else MONTH_ABBR_EN
    return abbr_map.get(m_clean, str(month))


def render_help(lang: str | None = None) -> None:
    """Render a comprehensive, formatted help screen for the esd CLI tool."""
    title_text = Text()
    title_text.append(f"{t('app_title', lang=lang)} ", style="solar")
    title_text.append(f"(esd v{get_version()})", style="table.header")
    title_text.append(f"\n{t('app_subtitle', lang=lang)}", style="subtitle")

    console.print()
    console.print(
        Panel(
            Align.center(title_text),
            box=box.ROUNDED,
            border_style="panel.border",
            padding=(1, 2),
        )
    )

    console.print(
        f"[table.header]{t('overview_heading', lang=lang)}[/table.header]\n"
        f"{t('overview_text', lang=lang)}\n"
    )

    cmd_table = Table(
        title=f"[solar]{t('available_commands', lang=lang)}[/solar]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        show_lines=False,
    )
    cmd_table.add_column(t("cmd_name", lang=lang), style="success", no_wrap=True)
    cmd_table.add_column(t("cmd_desc", lang=lang), style="value")

    cmd_table.add_row("init", t("cmd_init_desc", lang=lang))
    cmd_table.add_row("doctor", t("cmd_doctor_desc", lang=lang))
    cmd_table.add_row("summary", t("cmd_summary_desc", lang=lang))
    cmd_table.add_row("compare", t("cmd_compare_desc", lang=lang))
    cmd_table.add_row("calculate", t("cmd_calculate_desc", lang=lang))
    cmd_table.add_row("config", t("cmd_config_desc", lang=lang))
    cmd_table.add_row("clean", t("cmd_clean_desc", lang=lang))

    console.print(cmd_table)
    console.print()
    console.print(
        f"[table.header]{t('help_workflow_heading', lang=lang)}[/table.header]\n"
        f"{t('help_workflow_body', lang=lang)}\n"
    )


def render_version(lang: str | None = None) -> None:
    """Render a rich, formatted version panel for 'esd --version'."""
    version = get_version()
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="table.header", no_wrap=True)
    info_table.add_column(style="value")

    info_table.add_row(
        f"☀️ {t('lbl_version', lang=lang)}", f"[table.header]{version}[/table.header]"
    )
    info_table.add_row("🐍 Python", f"[dimmed]{py_version}[/dimmed]")
    info_table.add_row(f"📜 {t('lbl_license', lang=lang)}", "[dimmed]MIT[/dimmed]")
    info_table.add_row(
        f"🌐 {t('lbl_source', lang=lang)}",
        "[dimmed]github.com/marcosDLCS/electricity-share-distributor[/dimmed]",
    )

    title_text = Text()
    title_text.append("Electricity Share Distributor ", style="solar")
    title_text.append("(esd)", style="value.strong")

    subtitle = Text(f"\n{t('app_subtitle', lang=lang)}\n", style="subtitle")

    body = Text.assemble(title_text, subtitle)
    panel_content = Columns([body, info_table], equal=False, expand=True)

    console.print()
    console.print(
        Panel(
            panel_content,
            title="[table.header]esd[/table.header]",
            border_style="panel.border",
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
    title = f"[success]{t(title_key, lang=lang)}[/success]"
    lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
    prec_example = "53%" if precision == 0 else ("52.8%" if precision == 1 else "52.86%")
    msg_key = "init_reinit" if was_already else "init_success"
    msg = t(msg_key, lang=lang, language=lang_name)
    prec_desc = t("init_prec_desc", lang=lang, precision=precision, example=prec_example)

    lines = [
        msg,
        f"[dimmed]• {t('init_lbl_lang', lang=lang)}: [info]{lang_name}[/info] ({lang})[/dimmed]",
        f"[dimmed]• {t('init_lbl_precision', lang=lang)}: [info]{prec_desc}[/info][/dimmed]",
        f"[dimmed]• {t('init_lbl_timestamp', lang=lang)}: {initialized_at}[/dimmed]",
    ]
    if cleared_files > 0:
        clean_text = t("init_clean_cleared", lang=lang, count=cleared_files)
        lines.append(
            f"[dimmed]• {t('init_lbl_output', lang=lang)}: [warning]{clean_text}[/warning][/dimmed]"
        )
    else:
        clean_text = t("init_clean_ready", lang=lang)
        lines.append(
            f"[dimmed]• {t('init_lbl_output', lang=lang)}: [info]{clean_text}[/info][/dimmed]"
        )

    console.print()
    console.print(
        Panel(
            "\n".join(lines),
            title=title,
            border_style="panel.border.success",
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
        border = "panel.border.success"
    else:
        msg = t("no_files_cleaned", lang=lang)
        border = "panel.border.warning"

    console.print()
    console.print(
        Panel(
            f"{msg}\n[dimmed]{t('lbl_directory', lang=lang)}: {output_dir}[/dimmed]",
            title=f"[solar]{t('title_cleanup', lang=lang)}[/solar]",
            border_style=border,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def render_export_success(
    exported_paths: list[Path],
    lang: str | None = None,
    extra_note: str | None = None,
) -> None:
    """Render a compact 1-2 line export footer listing generated deliverables."""
    if not exported_paths and not extra_note:
        return

    label = t("export_footer_label", lang=lang)
    parts: list[str] = []
    if len(exported_paths) == 1:
        parts.append(f"[dimmed]{exported_paths[0]}[/dimmed]")
    elif exported_paths:
        parent_dirs = {p.parent for p in exported_paths}
        if len(parent_dirs) == 1:
            parent = exported_paths[0].parent
            names = ", ".join(p.name for p in exported_paths)
            parts.append(f"[table.header]{parent}[/table.header]: [dimmed]{names}[/dimmed]")
        else:
            parts.append(f"[dimmed]{' · '.join(str(p) for p in exported_paths)}[/dimmed]")

    if extra_note:
        parts.append(f"[dimmed]{extra_note}[/dimmed]")

    console.print(f"[success]✔[/success] {label}: {' · '.join(parts)}\n")


def render_config_view(cfg: AppConfig, lang: str | None = None) -> None:
    """Render active configuration parameters table."""
    table = Table(
        title=f"⚙️ [title]{t('title_config', lang=lang)}[/title]",
        box=box.ROUNDED,
        header_style="table.header",
        border_style="panel.border",
        padding=(0, 1),
    )
    table.add_column(t("col_setting", lang=lang), style="table.header")
    table.add_column(t("col_value", lang=lang), style="status.ok")

    table.add_row("language", cfg.language)
    prec_unit = "decimal(es)" if (lang or get_language()) == "es" else "decimal(s)"
    table.add_row("share_precision", f"{cfg.share_precision} {prec_unit}")
    table.add_row("consumption_dir", str(cfg.consumption_dir))
    table.add_row("generation_dir", str(cfg.generation_dir))
    table.add_row("weather_dir", str(cfg.weather_dir))
    table.add_row("curated_dir", str(cfg.curated_dir))
    table.add_row("output_dir", str(cfg.output_dir))
    table.add_row("cups_config_path", str(cfg.cups_config_path))
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
        f"[dimmed]{t('weather_lbl_coords', lang=lang)}[/dimmed]\n[success]{coords_text}[/success]",
        f"[dimmed]{t('weather_lbl_year', lang=lang)}[/dimmed]\n[solar]{result.year}[/solar] [dimmed]({result.total_hours:,} hrs)[/dimmed]",
        f"[dimmed]{t('weather_lbl_period', lang=lang)}[/dimmed]\n[value]{result.start_date} ➔ {result.end_date}[/value]",
    )

    temp_summary = f"{result.avg_temperature:.1f}°C [dimmed]({result.min_temperature:.1f} / {result.max_temperature:.1f})[/dimmed]"
    cloud_summary = f"{result.avg_cloud_cover:.1f}%"
    dest_str = f"{result.file_path.name}"
    if result.overwritten:
        dest_str += f" {t('weather_overwritten', lang=lang)}"

    grid.add_row(
        f"[dimmed]{t('weather_lbl_temp', lang=lang)} (Avg / Min / Max)[/dimmed]\n[metric]{temp_summary}[/metric]",
        f"[dimmed]{t('weather_lbl_cloud', lang=lang)}[/dimmed]\n[value.strong]{cloud_summary}[/value.strong]",
        f"[dimmed]{t('weather_lbl_dest', lang=lang)}[/dimmed]\n[dimmed]{dest_str}[/dimmed]",
    )

    console.print()
    console.print(
        Panel(
            grid,
            title=f"[panel.title]{t('title_weather', lang=lang)}[/panel.title]",
            border_style="panel.border",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()
