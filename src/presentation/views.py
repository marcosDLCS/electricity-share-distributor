"""Terminal views, tables, cards, and help screens rendered with Rich for esd."""

from __future__ import annotations

import sys

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
        "init",
        t("cmd_init_desc", lang=lang),
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


def render_init_success(lang: str, initialized_at: str, was_already: bool = False) -> None:
    """Render initialization result card."""
    title = (
        "[bold green]✓ Initialized Successfully[/bold green]"
        if not was_already
        else "[bold cyan]ℹ Already Initialized[/bold cyan]"
    )
    lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
    msg = (
        t("init_already", lang=lang, timestamp=initialized_at)
        if was_already
        else t("init_success", lang=lang, language=lang_name)
    )

    console.print()
    console.print(
        Panel(
            f"{msg}\n[dim]Timestamp: {initialized_at}[/dim]",
            title=title,
            border_style="green" if not was_already else "cyan",
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
