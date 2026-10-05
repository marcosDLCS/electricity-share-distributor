"""Command-line interface entry point for Electricity Share Distributor (esd)."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from src.config import (
    DEFAULT_CONSUMPTION_DIR,
    DEFAULT_GENERATION_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SHARE_PRECISION,
    clear_output_directory,
    ensure_directories,
    get_language,
    get_precision,
    is_initialized,
    load_config,
    mark_initialized,
    normalize_language_code,
    save_config,
    set_language,
    set_precision,
    validate_share_precision,
)
from src.i18n import t
from src.ingestion import (
    DatadisConsumptionLoader,
    DataDoctor,
    EsdError,
    HuaweiGenerationLoader,
    TimeSeriesAligner,
)
from src.optimization import DistributionOptimizer, OptimizationStrategy
from src.presentation.console import console
from src.presentation.export import export_all
from src.presentation.views import (
    render_cleanup_result,
    render_community_summary,
    render_config_view,
    render_doctor_report,
    render_export_success,
    render_help,
    render_init_success,
    render_monthly_coefficients_table,
    render_monthly_trajectory_table,
    render_not_initialized_warning,
    render_strategy_comparison_table,
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
    render_version(lang=get_language())


@app.command(name="init")
def init_command(
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language preference: 'en' (English) or 'es' (Español). Defaults to current setting or 'en'.",
    ),
    precision: int | None = typer.Option(
        None,
        "--precision",
        "-p",
        help="Share percentage precision: 0 (e.g. 53%), 1 (e.g. 52.8%), or 2 (e.g. 52.86%). Defaults to current setting or 0.",
    ),
) -> None:
    """Initialize workspace: create dirs, clear .output, configure language and precision.

    Safe to call multiple times — always re-applies settings, clears .output, and creates
    missing directories. Language and precision default to already-configured values if omitted.
    """
    cfg = load_config()
    was_already = is_initialized()

    # 1. Clear .output (always on init / re-init)
    cleared_count = clear_output_directory(Path(cfg.output_dir))

    # 2. Ask user for desired language if not explicitly provided
    if lang is None:
        try:
            raw_lang = typer.prompt(
                "Select desired language ('en' for English, 'es' for Spanish)",
                default=cfg.language or "en",
            )
        except (typer.exceptions.Abort, EOFError):
            raw_lang = cfg.language or "en"
    else:
        raw_lang = lang

    try:
        target_lang = normalize_language_code(raw_lang)
    except ValueError as err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        sys.exit(1)

    # 3. Ask user for desired precision if not explicitly provided
    if precision is None:
        try:
            raw_precision = typer.prompt(
                "Select desired share precision (0, 1, or 2 decimal places)",
                default=cfg.share_precision
                if cfg.share_precision is not None
                else DEFAULT_SHARE_PRECISION,
                type=int,
            )
        except (typer.exceptions.Abort, EOFError):
            raw_precision = (
                cfg.share_precision if cfg.share_precision is not None else DEFAULT_SHARE_PRECISION
            )
    else:
        raw_precision = precision

    try:
        target_precision = validate_share_precision(raw_precision)
    except ValueError as err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        sys.exit(1)

    # 4. Ensure all workspace directories exist
    ensure_directories(config=cfg)

    # 5. Persist settings and record initialization timestamp
    set_language(target_lang)
    set_precision(target_precision)
    ts = mark_initialized(version=get_version())

    render_init_success(
        lang=target_lang,
        initialized_at=ts,
        precision=target_precision,
        was_already=was_already,
        cleared_files=cleared_count,
    )


@app.command(name="doctor")
def doctor_command(
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
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show complete list of all detected missing intervals and timestamps.",
    ),
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language override for messages ('en' or 'es').",
    ),
) -> None:
    """Audit input data files to detect gaps, missing hourly intervals, and inconsistencies."""
    active_lang = normalize_language_code(lang) if lang else get_language()

    with console.status(f"[bold cyan]{t('status_doctor', lang=active_lang)}[/bold cyan]"):
        doc = DataDoctor(consumption_dir=consumption_dir, generation_dir=generation_dir)
        report = doc.diagnose()

    render_doctor_report(report, verbose=verbose, lang=active_lang)

    if not report.can_calculate:
        sys.exit(1)


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
    strategy: str = typer.Option(
        "optimal",
        "--strategy",
        "-s",
        help="Allocation strategy: 'optimal' (RD 244/2019 LP), 'consumption_share', or 'equal'.",
    ),
    view: str = typer.Option(
        "summary",
        "--view",
        "-v",
        help="Display view mode: 'summary' (overview + comparison + coefficients), 'trajectory', or 'all'.",
    ),
    export_format: str = typer.Option(
        "all",
        "--format",
        "-f",
        help="Export format: 'all', 'table' (no file export), 'csv', 'json', or 'markdown'.",
    ),
    precision: int | None = typer.Option(
        None,
        "--precision",
        "-p",
        help="Share percentage precision: 0 (e.g. 53%), 1 (e.g. 52.8%), or 2 (e.g. 52.86%).",
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

    try:
        active_precision = (
            get_precision() if precision is None else validate_share_precision(precision)
        )
    except ValueError as err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        sys.exit(1)

    if not is_initialized():
        render_not_initialized_warning(lang=active_lang)

    # Normalize strategy
    strat_key = strategy.lower().strip()
    try:
        opt_strat = OptimizationStrategy(strat_key)
    except ValueError:
        valid_strats = ", ".join(f"'{s.value}'" for s in OptimizationStrategy)
        console.print(
            f"[bold red]Error:[/bold red] Invalid strategy '{strategy}'. Valid options: {valid_strats}"
        )
        sys.exit(1)

    try:
        with console.status(
            f"[bold cyan]{t('status_ingesting', lang=active_lang, consumption_dir=consumption_dir, generation_dir=generation_dir)}[/bold cyan]"
        ):
            c_loader = DatadisConsumptionLoader(consumption_dir)
            g_loader = HuaweiGenerationLoader(generation_dir)

            c_df = c_loader.load_all()
            g_df = g_loader.load_all()

            c_files_count = len(c_loader.discover_files())
            g_files_count = len(g_loader.discover_files())

            aligner = TimeSeriesAligner(
                c_df,
                g_df,
                consumption_files_loaded=c_files_count,
                generation_files_loaded=g_files_count,
            )
            aligned = aligner.align(year=year, month=month)

        with console.status(f"[bold green]{t('status_optimizing', lang=active_lang)}[/bold green]"):
            opt_result = DistributionOptimizer.optimize_dataset(
                aligned,
                strategy=opt_strat,
                include_baselines=True,
                precision=active_precision,
            )

        # Presentation Views
        view_mode = view.lower().strip()

        if view_mode in ("summary", "all"):
            render_community_summary(aligned.metadata, opt_result.total_summary, lang=active_lang)
            render_monthly_trajectory_table(opt_result, lang=active_lang)
            render_strategy_comparison_table(opt_result, lang=active_lang)
            if month is not None or view_mode == "all":
                for m in opt_result.monthly_results:
                    render_monthly_coefficients_table(
                        m, lang=active_lang, precision=active_precision
                    )
            else:
                latest_month = opt_result.monthly_results[-1]
                render_monthly_coefficients_table(
                    latest_month, lang=active_lang, precision=active_precision
                )
        elif view_mode == "trajectory":
            render_monthly_trajectory_table(opt_result, lang=active_lang)
        elif view_mode == "coefficients":
            for m in opt_result.monthly_results:
                render_monthly_coefficients_table(m, lang=active_lang, precision=active_precision)
        elif view_mode == "comparison":
            render_strategy_comparison_table(opt_result, lang=active_lang)

        # File Exports
        fmt_clean = export_format.lower().strip()
        if fmt_clean not in ("table", "none"):
            exported_paths = export_all(
                opt_result,
                aligned.metadata,
                output_dir=output_dir,
                formats=fmt_clean,
                lang=active_lang,
                precision=active_precision,
            )
            render_export_success(exported_paths, lang=active_lang)

    except EsdError as err:
        console.print(f"\n[bold red]Error:[/bold red] {err}\n")
        sys.exit(1)
    except Exception as exc:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}\n")
        sys.exit(1)


@app.command(name="config")
def config_command(
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Update default language ('en' or 'es').",
    ),
    precision: int | None = typer.Option(
        None,
        "--precision",
        "-p",
        help="Update share percentage precision (0, 1, or 2 decimals).",
    ),
    consumption_dir: Path | None = typer.Option(
        None,
        "--consumption-dir",
        "-c",
        help="Update default consumption directory path.",
    ),
    generation_dir: Path | None = typer.Option(
        None,
        "--generation-dir",
        "-g",
        help="Update default generation directory path.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Update default output directory path.",
    ),
) -> None:
    """View or update persistent application configuration."""
    cfg = load_config()
    modified = False

    if lang is not None:
        try:
            cfg.language = normalize_language_code(lang)
            modified = True
        except ValueError as err:
            console.print(f"[bold red]Error:[/bold red] {err}")
            sys.exit(1)
    if precision is not None:
        try:
            cfg.share_precision = validate_share_precision(precision)
            modified = True
        except ValueError as err:
            console.print(f"[bold red]Error:[/bold red] {err}")
            sys.exit(1)
    if consumption_dir is not None:
        cfg.consumption_dir = str(consumption_dir)
        modified = True
    if generation_dir is not None:
        cfg.generation_dir = str(generation_dir)
        modified = True
    if output_dir is not None:
        cfg.output_dir = str(output_dir)
        modified = True

    if modified:
        save_config(cfg)
        console.print(f"[bold green]{t('msg_config_updated', lang=cfg.language)}[/bold green]")

    render_config_view(cfg, lang=cfg.language)


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
            t("prompt_cleanup_confirm", lang=active_lang, count=len(files), dir=str(out_dir)),
            default=False,
        )
        if not confirm:
            console.print(f"[yellow]{t('cleanup_aborted', lang=active_lang)}[/yellow]")
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
