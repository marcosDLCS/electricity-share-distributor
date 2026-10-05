"""Command-line interface entry point for Electricity Share Distributor (esd)."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from src.config import (
    DEFAULT_CONSUMPTION_DIR,
    DEFAULT_GENERATION_DIR,
    DEFAULT_OUTPUT_DIR,
    ensure_directories,
    get_language,
    is_initialized,
    load_config,
    mark_initialized,
    normalize_language_code,
    set_language,
)
from src.presentation.console import console
from src.presentation.views import (
    render_cleanup_result,
    render_help,
    render_init_success,
    render_not_initialized_warning,
    render_version,
)
from src.version import get_version

app = typer.Typer(
    help="Electricity Share Distributor: Optimize collective PV self-consumption coefficients (RD 244/2019).",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def default_callback(ctx: typer.Context) -> None:
    """Default entrypoint. Renders custom formatted help if no subcommand is passed."""
    if ctx.invoked_subcommand is None:
        render_help(lang=get_language())


@app.command(name="help")
def help_command(
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language code ('en' or 'es').",
    ),
) -> None:
    """Display comprehensive command reference and user guide."""
    target_lang = normalize_language_code(lang) if lang else get_language()
    render_help(lang=target_lang)


@app.command(name="version")
def version_command() -> None:
    """Display active CalVer application version and system info."""
    render_version()


@app.command(name="init")
def init_command(
    lang: str = typer.Option(
        "en",
        "--lang",
        "-l",
        help="Language preference: 'en' (English) or 'es' (Español).",
    ),
) -> None:
    """Initialize workspace directories, configure language preference, and save settings."""
    try:
        norm_lang = normalize_language_code(lang)
    except ValueError as err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        sys.exit(1)

    cfg = load_config()
    was_already = is_initialized()
    old_ts = cfg.initialized_at

    set_language(norm_lang)
    ensure_directories()
    ts = mark_initialized(version=get_version())

    render_init_success(lang=norm_lang, initialized_at=old_ts or ts, was_already=was_already)


@app.command(name="calculate")
def calculate_command(
    consumption_dir: Path = typer.Option(
        DEFAULT_CONSUMPTION_DIR,
        "--consumption-dir",
        "-c",
        help="Path to folder containing DATADIS hourly consumption CSV files.",
    ),
    generation_dir: Path = typer.Option(
        DEFAULT_GENERATION_DIR,
        "--generation-dir",
        "-g",
        help="Path to folder containing Huawei FusionSolar generation Excel files.",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--output-dir",
        "-o",
        help="Path to folder where summary reports and exports will be written.",
    ),
    year: int | None = typer.Option(
        None,
        "--year",
        "-y",
        help="Optional calendar year filter (e.g. 2026).",
    ),
    month: int | None = typer.Option(
        None,
        "--month",
        "-m",
        help="Optional month filter (1-12).",
    ),
    export_format: str = typer.Option(
        "all",
        "--format",
        "-f",
        help="Export format: 'table', 'csv', 'json', 'markdown', or 'all'.",
    ),
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language override for outputs ('en' or 'es').",
    ),
) -> None:
    """Calculate optimal electricity distribution coefficients (beta_i) for collective PV installation."""
    active_lang = normalize_language_code(lang) if lang else get_language()

    if not is_initialized():
        render_not_initialized_warning(lang=active_lang)

    console.print(
        f"[bold cyan]esd calculate[/bold cyan] [dim](v{get_version()})[/dim]\n"
        f"Consumption dir: [yellow]{consumption_dir}[/yellow]\n"
        f"Generation dir:  [yellow]{generation_dir}[/yellow]\n"
        f"Output dir:      [yellow]{output_dir}[/yellow]\n"
    )
    console.print(
        "[dim]Data ingestion and optimization engine will run here in Phases 2-4.[/dim]\n"
    )


@app.command(name="cleanup")
def cleanup_command(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force deletion without interactive confirmation.",
    ),
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language override for messages ('en' or 'es').",
    ),
) -> None:
    """Clean up generated reports and files from the output directory."""
    active_lang = normalize_language_code(lang) if lang else get_language()
    cfg = load_config()
    out_dir = Path(cfg.output_dir)

    if not out_dir.exists():
        render_cleanup_result(count=0, output_dir=str(out_dir), lang=active_lang)
        return

    files = [f for f in out_dir.iterdir() if f.is_file() and not f.name.startswith(".")]

    if not files:
        render_cleanup_result(count=0, output_dir=str(out_dir), lang=active_lang)
        return

    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to delete {len(files)} files in {out_dir}?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Cleanup aborted by user.[/yellow]")
            return

    count = 0
    for f in files:
        try:
            f.unlink()
            count += 1
        except Exception as err:
            console.print(f"[red]Error deleting {f.name}: {err}[/red]")

    render_cleanup_result(count=count, output_dir=str(out_dir), lang=active_lang)


def main() -> None:
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
