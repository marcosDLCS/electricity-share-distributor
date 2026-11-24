"""Command-line interface entry point for Electricity Share Distributor (esd)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import typer

from src.config import (
    DEFAULT_CUPS_CONFIG_PATH,
    DEFAULT_SHARE_PRECISION,
    DEFAULT_WEATHER_DIR,
    AppConfig,
    clear_output_directory,
    ensure_directories,
    get_language,
    is_initialized,
    load_config,
    mark_initialized,
    normalize_language_code,
    resolve_cups_config_path,
    save_config,
    set_language,
    set_precision,
    validate_share_precision,
)
from src.domain.exceptions import EsdError
from src.i18n import t
from src.presentation.console import console
from src.presentation.views.common import (
    render_cleanup_result,
    render_config_view,
    render_export_success,
    render_help,
    render_init_success,
    render_not_initialized_warning,
    render_version,
)
from src.presentation.views.curate import render_curate_summary
from src.version import get_version

app = typer.Typer(
    help="Electricity Share Distributor: collective PV analytics & optimization (RD 244/2019).",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@dataclass(frozen=True)
class _WorkspaceContext:
    """Resolved workspace settings, directories, and CUPS config from .esd_config.json."""

    config: AppConfig
    lang: str
    precision: int
    consumption_dir: Path
    generation_dir: Path
    weather_dir: Path
    curated_dir: Path
    output_dir: Path
    cups_path: Path | None


def _handle_cli_error(err: Exception | str, unexpected: bool = False) -> NoReturn:
    """Format domain or CLI errors cleanly and exit with code 1."""
    if isinstance(err, (typer.Exit, typer.Abort)):
        raise err
    prefix = "[danger]Unexpected error:[/danger]" if unexpected else "[danger]Error:[/danger]"
    console.print(f"\n{prefix} {err}\n")
    raise typer.Exit(code=1)


@contextmanager
def _cli_error_boundary() -> Iterator[None]:
    """Translate domain and unexpected errors into clean exit-code-1 CLI messages."""
    try:
        yield
    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


def _resolve_workspace_context(
    lang: str | None = None,
    check_initialized: bool = False,
) -> _WorkspaceContext:
    """Load persistent config, validate active language, and resolve workspace paths once."""
    from src.ingestion.consumption import resolve_effective_cups_path

    cfg = load_config()
    try:
        active_lang = normalize_language_code(lang) if lang else cfg.language
    except ValueError as err:
        _handle_cli_error(err)

    if check_initialized and not is_initialized():
        render_not_initialized_warning(lang=active_lang)

    consumption_dir = Path(cfg.consumption_dir)
    if cfg.cups_config_path and cfg.cups_config_path != str(DEFAULT_CUPS_CONFIG_PATH):
        cups_path = resolve_cups_config_path(custom_path=cfg.cups_config_path, config=cfg)
    else:
        cups_path = resolve_effective_cups_path(consumption_dir)

    return _WorkspaceContext(
        config=cfg,
        lang=active_lang,
        precision=cfg.share_precision,
        consumption_dir=consumption_dir,
        generation_dir=Path(cfg.generation_dir),
        weather_dir=Path(cfg.weather_dir) if cfg.weather_dir else DEFAULT_WEATHER_DIR,
        curated_dir=Path(cfg.curated_dir),
        output_dir=Path(cfg.output_dir),
        cups_path=cups_path,
    )


def _version_callback(value: bool) -> None:
    """Display active CalVer application version when --version / -V is passed."""
    if value:
        render_version(lang=get_language())
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def default_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show active CalVer application version and exit.",
    ),
) -> None:
    """Render formatted CLI help when no subcommand is passed."""
    if ctx.invoked_subcommand is None:
        render_help(lang=get_language())


@app.command(name="init")
def init_command(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: 'en' or 'es'."),
    precision: int | None = typer.Option(
        None, "--precision", "-p", help="Share decimals: 0, 1, or 2."
    ),
) -> None:
    """Initialize workspace dirs, clear .output, and save language and precision."""
    with _cli_error_boundary():
        cfg = load_config()
        was_already = is_initialized()
        cleared_count = clear_output_directory(Path(cfg.output_dir))

        if lang is None:
            try:
                raw_lang = typer.prompt(t("prompt_lang", lang=cfg.language), default="en")
            except typer.exceptions.Abort, EOFError:
                raw_lang = "en"
        else:
            raw_lang = lang

        try:
            target_lang = normalize_language_code(raw_lang)
        except ValueError as err:
            _handle_cli_error(err)

        if precision is None:
            try:
                raw_precision = typer.prompt(
                    t("prompt_precision", lang=target_lang),
                    default=DEFAULT_SHARE_PRECISION,
                    type=int,
                )
            except typer.exceptions.Abort, EOFError:
                raw_precision = DEFAULT_SHARE_PRECISION
        else:
            raw_precision = precision

        try:
            target_precision = validate_share_precision(raw_precision)
        except ValueError as err:
            _handle_cli_error(err)

        ensure_directories(config=cfg)
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all missing intervals."),
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language override ('en'|'es')."),
) -> None:
    """Audit configured DATADIS, generation, and weather data for gaps and overlap."""
    with _cli_error_boundary():
        from src.presentation.views.doctor import render_doctor_report
        from src.services.doctor_service import DoctorRequest, DoctorService

        ctx = _resolve_workspace_context(lang=lang)
        with console.status(f"[table.header]{t('status_doctor', lang=ctx.lang)}[/table.header]"):
            report = DoctorService.execute(
                DoctorRequest(
                    consumption_dir=ctx.consumption_dir,
                    generation_dir=ctx.generation_dir,
                    weather_dir=ctx.weather_dir,
                    cups_config_path=ctx.cups_path,
                )
            )
        render_doctor_report(report, verbose=verbose, lang=ctx.lang)
        if not report.can_calculate:
            raise typer.Exit(code=1)


@app.command(name="calculate")
def calculate_command(
    refresh: bool = typer.Option(
        False, "--refresh", "-r", help="Refresh cached weather and force re-curation."
    ),
    curate_only: bool = typer.Option(
        False, "--curate-only", help="Build CSV & styled Excel datasets in .curated/ only."
    ),
) -> None:
    """Calculate optimal PV distribution coefficients (beta_i) and export deliverables."""
    with _cli_error_boundary():
        from src.optimization import OptimizationStrategy
        from src.presentation.views.matrix import render_coefficients_matrix_table
        from src.presentation.views.summary import render_community_summary
        from src.presentation.views.trajectory import render_monthly_trajectory_table
        from src.services.calculation_service import CalculationRequest, CalculationService

        ctx = _resolve_workspace_context(check_initialized=True)
        req = CalculationRequest(
            consumption_dir=ctx.consumption_dir,
            generation_dir=ctx.generation_dir,
            curated_dir=ctx.curated_dir,
            output_dir=ctx.output_dir,
            weather_dir=ctx.weather_dir,
            cups_config_path=ctx.cups_path,
            strategy=OptimizationStrategy.OPTIMAL,
            precision=ctx.precision,
            compute_hourly=True,
            refresh=refresh,
            curate_only=curate_only,
            lang=ctx.lang,
        )

        initial_status = (
            f"[table.header]{t('status_curating', lang=ctx.lang)}[/table.header]"
            if curate_only
            else f"[table.header][1/4][/table.header] [value.strong]{t('status_step_1', lang=ctx.lang)}[/value.strong]"
        )
        with console.status(initial_status) as status:

            def _update_step(step_idx: int, message: str) -> None:
                if not curate_only:
                    status.update(
                        f"[table.header][{step_idx}/4][/table.header] [value.strong]{message}[/value.strong]"
                    )

            calc_result = CalculationService.execute(req, progress_callback=_update_step)

        if curate_only and calc_result.curation_result is not None:
            cur = calc_result.curation_result
            render_curate_summary(
                dataset=cur.dataset,
                csv_path=cur.csv_path,
                excel_path=cur.excel_path,
                lang=ctx.lang,
                generation_csv_path=cur.generation_csv_path,
                generation_excel_path=cur.generation_excel_path,
                consumption_csv_path=cur.consumption_csv_path,
                consumption_excel_path=cur.consumption_excel_path,
            )
            return

        opt_result = calc_result.opt_result
        assert opt_result is not None
        render_community_summary(
            calc_result.metadata, opt_result.total_summary, lang=ctx.lang, opt_result=opt_result
        )
        render_monthly_trajectory_table(opt_result, lang=ctx.lang)
        render_coefficients_matrix_table(opt_result, lang=ctx.lang, precision=ctx.precision)

        if calc_result.exported_paths:
            render_export_success(calc_result.exported_paths, lang=ctx.lang)


@app.command(name="summary")
def summary_command(
    year: int | None = typer.Option(None, "--year", "-y", help="Filter to a calendar year."),
    view: str = typer.Option("all", "--view", "-v", help="Mode: 'all', 'annual', or 'monthly'."),
    cups: str | None = typer.Option(None, "--cups", help="Filter to a single CUPS trajectory."),
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language override ('en'|'es')."),
) -> None:
    """Aggregate community consumption by year and month, show fair shares, and export Markdown."""
    with _cli_error_boundary():
        from src.presentation.views.consumption import (
            render_annual_consumption_tables,
            render_consumption_insights,
            render_consumption_overview,
            render_cups_consumption_trajectory,
            render_detailed_monthly_consumption,
            render_monthly_consumption_overview,
            render_validation_warnings,
        )
        from src.services.summary_service import SummaryRequest, SummaryService

        ctx = _resolve_workspace_context(lang=lang, check_initialized=True)
        with console.status(
            f"[table.header]{t('status_summarizing', lang=ctx.lang)}[/table.header]"
        ):
            result = SummaryService.execute(
                SummaryRequest(
                    consumption_dir=ctx.consumption_dir,
                    output_dir=ctx.output_dir,
                    cups_config_path=ctx.cups_path,
                    year=year,
                    cups=cups,
                    view=view,
                    lang=ctx.lang,
                    export_markdown=True,
                )
            )

        render_validation_warnings(result.validation_results, lang=ctx.lang)
        render_consumption_overview(
            result.summary, file_count=result.valid_file_count, lang=ctx.lang
        )

        if cups and cups.strip():
            render_cups_consumption_trajectory(
                result.summary, target_cups=cups.strip().upper(), filter_year=year, lang=ctx.lang
            )
        else:
            view_clean = view.lower().strip()
            if view_clean in ("all", "annual"):
                render_annual_consumption_tables(result.summary, filter_year=year, lang=ctx.lang)
            if view_clean in ("all", "monthly"):
                render_monthly_consumption_overview(result.summary, filter_year=year, lang=ctx.lang)
            if view_clean == "monthly":
                render_detailed_monthly_consumption(result.summary, filter_year=year, lang=ctx.lang)
        render_consumption_insights(result.summary, lang=ctx.lang)

        if result.report_path is not None:
            render_export_success([result.report_path], lang=ctx.lang)


@app.command(name="compare")
def compare_command(
    years: list[str] | None = typer.Option(
        None, "--years", "-y", help="Years to compare (e.g. -y 2024 -y 2025 or 2024,2025)."
    ),
    charts: bool = typer.Option(
        True, "--charts/--no-charts", help="Generate SVG bar charts in .output/charts/."
    ),
    html: bool = typer.Option(
        False, "--html", help="Export standalone interactive HTML dashboard."
    ),
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language override ('en'|'es')."),
) -> None:
    """Compare community consumption across multiple years with apples-to-apples completeness."""
    with _cli_error_boundary():
        from src.presentation.views.comparison import (
            render_comparison_overview,
            render_cups_comparison_table,
            render_monthly_comparison_table,
        )
        from src.presentation.views.consumption import render_validation_warnings
        from src.services.comparison_service import (
            ComparisonRequest,
            ComparisonService,
            parse_years_option,
        )

        ctx = _resolve_workspace_context(lang=lang, check_initialized=True)
        target_years = parse_years_option(years)

        with console.status(f"[table.header]{t('status_comparing', lang=ctx.lang)}[/table.header]"):
            result = ComparisonService.execute(
                ComparisonRequest(
                    consumption_dir=ctx.consumption_dir,
                    output_dir=ctx.output_dir,
                    cups_config_path=ctx.cups_path,
                    years=target_years,
                    generate_charts=charts,
                    lang=ctx.lang,
                    export_markdown=True,
                    export_html=html,
                )
            )

        render_validation_warnings(result.validation_results, lang=ctx.lang)
        render_comparison_overview(result.comparison, lang=ctx.lang)
        render_monthly_comparison_table(result.comparison, lang=ctx.lang)
        render_cups_comparison_table(result.comparison, lang=ctx.lang)

        exported = [p for p in (result.report_path, result.html_report_path) if p is not None]
        charts_note = (
            t(
                "compare_charts_generated",
                lang=ctx.lang,
                count=len(result.chart_paths),
                path=str(ctx.output_dir / "charts"),
            )
            if result.chart_paths
            else None
        )
        if exported or charts_note:
            render_export_success(exported, lang=ctx.lang, extra_note=charts_note)


@app.command(name="config")
def config_command(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Set default language ('en'|'es')."),
    precision: int | None = typer.Option(
        None, "--precision", "-p", help="Set share percentage decimals (0, 1, or 2)."
    ),
    consumption_dir: Path | None = typer.Option(
        None, "--consumption-dir", "-c", help="Set default DATADIS consumption directory."
    ),
    generation_dir: Path | None = typer.Option(
        None, "--generation-dir", "-g", help="Set default PV generation directory."
    ),
    weather_dir: Path | None = typer.Option(
        None, "--weather-dir", "-w", help="Set default Open-Meteo weather directory."
    ),
    curated_dir: Path | None = typer.Option(
        None, "--curated-dir", "-u", help="Set default curated dataset directory."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Set default output directory."
    ),
    cups_file: Path | None = typer.Option(
        None, "--cups-file", "-C", help="Set default path to cups.json configuration file."
    ),
    latitude: float | None = typer.Option(
        None, "--latitude", "--lat", help="Set default latitude (-90..90)."
    ),
    longitude: float | None = typer.Option(
        None, "--longitude", "--lon", help="Set default longitude (-180..180)."
    ),
) -> None:
    """View or update persistent application configuration in .esd_config.json."""
    with _cli_error_boundary():
        cfg = load_config()
        modified = False
        active_lang = cfg.language

        if lang is not None:
            try:
                active_lang = normalize_language_code(lang)
                cfg.language = active_lang
                modified = True
            except ValueError as err:
                _handle_cli_error(err)
        if precision is not None:
            try:
                cfg.share_precision = validate_share_precision(precision)
                modified = True
            except ValueError as err:
                _handle_cli_error(err)
        if latitude is not None:
            if not (-90.0 <= latitude <= 90.0):
                _handle_cli_error(t("err_lat_range", lang=active_lang, val=latitude))
            cfg.latitude = latitude
            modified = True
        if longitude is not None:
            if not (-180.0 <= longitude <= 180.0):
                _handle_cli_error(t("err_lon_range", lang=active_lang, val=longitude))
            cfg.longitude = longitude
            modified = True

        for attr, val in (
            ("consumption_dir", consumption_dir),
            ("generation_dir", generation_dir),
            ("weather_dir", weather_dir),
            ("curated_dir", curated_dir),
            ("output_dir", output_dir),
            ("cups_config_path", cups_file),
        ):
            if val is not None:
                setattr(cfg, attr, str(val))
                modified = True

        if modified:
            save_config(cfg)
            console.print(f"[success]{t('msg_config_updated', lang=cfg.language)}[/success]")

        render_config_view(cfg, lang=cfg.language)


@app.command(name="clean")
def clean_command(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt."),
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language override ('en'|'es')."),
) -> None:
    """Clean generated files in configured .output, .curated, and .input/weather dirs."""
    with _cli_error_boundary():
        ctx = _resolve_workspace_context(lang=lang)
        target_dirs = [ctx.output_dir, ctx.curated_dir, ctx.weather_dir]
        dirs_display = ", ".join(str(d) for d in target_dirs)

        items = [
            item
            for d in target_dirs
            if d.exists() and d.is_dir()
            for item in d.iterdir()
            if (not item.name.startswith(".") or item.name == ".esd_manifest.json")
            and (item.is_file() or item.is_symlink() or item.is_dir())
        ]
        if not items:
            render_cleanup_result(count=0, output_dir=dirs_display, lang=ctx.lang)
            return

        if not force and not typer.confirm(
            t("prompt_cleanup_confirm", lang=ctx.lang, count=len(items), dir=dirs_display),
            default=False,
        ):
            console.print(f"[warning]{t('cleanup_aborted', lang=ctx.lang)}[/warning]")
            return

        count = sum(clear_output_directory(d) for d in target_dirs)
        render_cleanup_result(count=count, output_dir=dirs_display, lang=ctx.lang)


def main() -> None:
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
