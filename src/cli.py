"""Command-line interface entry point for Electricity Share Distributor (esd)."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from src.config import (
    DEFAULT_SHARE_PRECISION,
    DEFAULT_WEATHER_DIR,
    clear_output_directory,
    ensure_directories,
    get_language,
    get_precision,
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
from src.ingestion import (
    OpenMeteoWeatherDownloader,
    WeatherDownloadResult,
    extract_coordinates_from_cups_file,
)
from src.optimization import OptimizationStrategy
from src.presentation.console import console
from src.presentation.views import (
    render_cleanup_result,
    render_coefficients_matrix_table,
    render_community_summary,
    render_config_view,
    render_curate_summary,
    render_doctor_report,
    render_export_success,
    render_help,
    render_hourly_profile_table,
    render_init_success,
    render_monthly_coefficients_table,
    render_monthly_trajectory_table,
    render_not_initialized_warning,
    render_strategy_comparison_table,
    render_version,
    render_weather_result,
)
from src.services import (
    CalculationRequest,
    CalculationService,
    CurationRequest,
    CurationService,
    DoctorRequest,
    DoctorService,
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
        help="Language preference: 'en' (English) or 'es' (Español). Defaults to 'en'.",
    ),
    precision: int | None = typer.Option(
        None,
        "--precision",
        "-p",
        help="Share percentage precision: 0 (e.g. 53%), 1 (e.g. 52.8%), or 2 (e.g. 52.86%). Defaults to 0.",
    ),
) -> None:
    """Initialize workspace: create dirs, clear .output, configure language and precision.

    Safe to call multiple times — always re-applies settings, clears .output, and creates
    missing directories. Defaults to English ('en') and zero precision (0) if omitted.
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
                default="en",
            )
        except typer.exceptions.Abort, EOFError:
            raw_lang = "en"
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
    consumption_dir: Path | None = typer.Option(
        None,
        "--consumption-dir",
        "-c",
        help="Path to folder containing DATADIS hourly consumption CSV files. Defaults to configured path.",
    ),
    generation_dir: Path | None = typer.Option(
        None,
        "--generation-dir",
        "-g",
        help="Path to folder containing Huawei FusionSolar generation Excel files. Defaults to configured path.",
    ),
    cups_file: Path | None = typer.Option(
        None,
        "--cups-file",
        "-C",
        help="Path to cups.json configuration file specifying CUPS uses and primary flags.",
    ),
    weather_dir: Path | None = typer.Option(
        None,
        "--weather-dir",
        "-w",
        help="Directory containing Open-Meteo hourly weather CSV files. Defaults to configured path.",
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
    cfg = load_config()
    target_consumption_dir = consumption_dir or Path(cfg.consumption_dir)
    target_generation_dir = generation_dir or Path(cfg.generation_dir)
    target_weather_dir = weather_dir or (
        Path(cfg.weather_dir) if cfg and cfg.weather_dir else DEFAULT_WEATHER_DIR
    )
    cups_path = resolve_cups_config_path(custom_path=cups_file, config=cfg)

    with console.status(f"[bold cyan]{t('status_doctor', lang=active_lang)}[/bold cyan]"):
        req = DoctorRequest(
            consumption_dir=target_consumption_dir,
            generation_dir=target_generation_dir,
            weather_dir=target_weather_dir,
            cups_config_path=cups_path,
        )
        report = DoctorService.execute(req)

    render_doctor_report(report, verbose=verbose, lang=active_lang)

    if not report.can_calculate:
        sys.exit(1)


@app.command(name="curate")
def curate_command(
    consumption_dir: Path | None = typer.Option(
        None,
        "--consumption-dir",
        "-c",
        help="Path to folder containing DATADIS hourly consumption CSV files. Defaults to configured path.",
    ),
    generation_dir: Path | None = typer.Option(
        None,
        "--generation-dir",
        "-g",
        help="Path to folder containing Huawei FusionSolar generation Excel files. Defaults to configured path.",
    ),
    cups_file: Path | None = typer.Option(
        None,
        "--cups-file",
        "-C",
        help="Path to cups.json configuration file specifying CUPS uses and primary flags.",
    ),
    curated_dir: Path | None = typer.Option(
        None,
        "--curated-dir",
        "-o",
        help="Path to directory where curated CSV files will be written. Defaults to configured path.",
    ),
    name: str = typer.Option(
        "curated",
        "--name",
        "-n",
        help="Base filename for generated curated export (e.g. 'curated' produces curated.csv).",
    ),
    delimiter: str = typer.Option(
        ";",
        "--delimiter",
        "-d",
        help="CSV delimiter character (';' or ','). Defaults to ';'.",
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
    weather_dir: Path | None = typer.Option(
        None,
        "--weather-dir",
        "-w",
        help="Directory containing Open-Meteo hourly weather CSV files. Defaults to configured path.",
    ),
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language override for messages ('en' or 'es').",
    ),
) -> None:
    """Reconcile DATADIS and Huawei time-series data and export curated CSV file."""
    active_lang = normalize_language_code(lang) if lang else get_language()
    cfg = load_config()

    if not is_initialized():
        render_not_initialized_warning(lang=active_lang)

    target_consumption_dir = consumption_dir or Path(cfg.consumption_dir)
    target_generation_dir = generation_dir or Path(cfg.generation_dir)
    target_curated_dir = curated_dir or Path(cfg.curated_dir)
    target_weather_dir = weather_dir or (
        Path(cfg.weather_dir) if cfg and cfg.weather_dir else DEFAULT_WEATHER_DIR
    )
    cups_path = resolve_cups_config_path(custom_path=cups_file, config=cfg)

    try:
        with console.status(f"[bold cyan]{t('status_curating', lang=active_lang)}[/bold cyan]"):
            req = CurationRequest(
                consumption_dir=target_consumption_dir,
                generation_dir=target_generation_dir,
                curated_dir=target_curated_dir,
                cups_config_path=cups_path,
                output_name=name,
                delimiter=delimiter,
                year=year,
                month=month,
                weather_dir=target_weather_dir,
            )
            cur_result = CurationService.execute(req)

        render_curate_summary(
            dataset=cur_result.dataset,
            csv_path=cur_result.csv_path,
            lang=active_lang,
        )

    except EsdError as err:
        console.print(f"\n[bold red]Error:[/bold red] {err}\n")
        sys.exit(1)
    except Exception as exc:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}\n")
        sys.exit(1)


@app.command(name="weather")
def weather_command(
    year: int = typer.Option(
        ...,
        "--year",
        "-y",
        help="Calendar year to download hourly weather data for (e.g. 2024).",
    ),
    latitude: float | None = typer.Option(
        None,
        "--latitude",
        "--lat",
        help="Geographical latitude coordinate (e.g. 40.4168). Overrides cups.json and config.",
    ),
    longitude: float | None = typer.Option(
        None,
        "--longitude",
        "--lon",
        help="Geographical longitude coordinate (e.g. -3.7038). Overrides cups.json and config.",
    ),
    cups_file: Path | None = typer.Option(
        None,
        "--cups-file",
        "-C",
        help="Path to cups.json configuration file to extract coordinates from when not provided on CLI.",
    ),
    weather_dir: Path | None = typer.Option(
        None,
        "--weather-dir",
        "-w",
        help="Directory to store downloaded weather CSV files. Defaults to configured path.",
    ),
    timezone: str = typer.Option(
        "auto",
        "--timezone",
        "-tz",
        help="Timezone for hourly timestamps (default: 'auto').",
    ),
    lang: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language override for messages ('en' or 'es').",
    ),
) -> None:
    """Download hourly weather data (temperature, cloud cover, weather code) from Open-Meteo into .input/weather."""
    active_lang = normalize_language_code(lang) if lang else get_language()
    cfg = load_config()

    # 1. Resolve coordinates to download
    coords_to_download: list[tuple[float, float]] = []

    if latitude is not None and longitude is not None:
        coords_to_download = [(latitude, longitude)]
    elif latitude is not None or longitude is not None:
        console.print(
            "[bold red]Error:[/bold red] Both --latitude and --longitude must be provided when specifying manual coordinates."
        )
        sys.exit(1)
    else:
        # Check cups.json configuration file
        cups_path = resolve_cups_config_path(custom_path=cups_file, config=cfg)
        if cups_path:
            coords_to_download = extract_coordinates_from_cups_file(cups_path)

        # Fallback to persistent configuration if cups.json didn't yield any coordinates
        if not coords_to_download and cfg.latitude is not None and cfg.longitude is not None:
            coords_to_download = [(cfg.latitude, cfg.longitude)]

    if not coords_to_download:
        console.print(f"[bold red]Error:[/bold red] {t('err_coords_required', lang=active_lang)}")
        sys.exit(1)

    target_weather_dir = weather_dir or Path(cfg.weather_dir)
    downloader = OpenMeteoWeatherDownloader(weather_dir=target_weather_dir)

    try:
        results: list[WeatherDownloadResult] = []
        for lat, lon in coords_to_download:
            coord_str = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
            status_text = (
                f"[bold cyan]{t('status_weather_coord', lang=active_lang, year=year, coords=coord_str)}[/bold cyan]"
                if len(coords_to_download) > 1
                else f"[bold cyan]{t('status_weather', lang=active_lang, year=year)}[/bold cyan]"
            )
            with console.status(status_text):
                _, _, result = downloader.download_year(
                    year=year,
                    latitude=lat,
                    longitude=lon,
                    timezone=timezone,
                )
                results.append(result)

        for result in results:
            render_weather_result(result, lang=active_lang)

    except EsdError as err:
        console.print(f"\n[bold red]Error:[/bold red] {err}\n")
        sys.exit(1)
    except Exception as exc:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}\n")
        sys.exit(1)


@app.command(name="calculate")
def calculate_command(
    consumption_dir: Path | None = typer.Option(
        None,
        "--consumption-dir",
        "-c",
        help="Path to folder containing DATADIS hourly consumption CSV files. Defaults to configured path.",
    ),
    generation_dir: Path | None = typer.Option(
        None,
        "--generation-dir",
        "-g",
        help="Path to folder containing Huawei FusionSolar generation Excel files. Defaults to configured path.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Path to folder where summary reports and exports will be written. Defaults to configured path.",
    ),
    curated_dir: Path | None = typer.Option(
        None,
        "--curated-dir",
        "-u",
        help="Path to folder containing curated time-series CSV file. Defaults to configured path.",
    ),
    cups_file: Path | None = typer.Option(
        None,
        "--cups-file",
        "-C",
        help="Path to cups.json configuration file specifying CUPS uses and primary flags. Defaults to configured path.",
    ),
    force_curate: bool = typer.Option(
        False,
        "--force-curate",
        help="Force re-running curation before calculating, even if curated CSV exists.",
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
        help="Display view mode: 'summary' (overview + matrix), 'matrix' (CUPS/months share matrix), 'trajectory', 'hourly', 'coefficients', 'comparison', or 'all'.",
    ),
    hourly: bool = typer.Option(
        False,
        "--hourly",
        "-H",
        help="Calculate and export distribution shares per hour (24-hour diurnal profile and hourly time-series).",
    ),
    export_format: str = typer.Option(
        "all",
        "--format",
        "-f",
        help="Export format: 'all', 'table' (no file export), 'csv', 'json', 'markdown', or 'html'.",
    ),
    precision: int | None = typer.Option(
        None,
        "--precision",
        "-p",
        help="Share percentage precision: 0 (e.g. 53%), 1 (e.g. 52.8%), or 2 (e.g. 52.86%).",
    ),
    min_share: float | None = typer.Option(
        None,
        "--min-share",
        help="Regulatory or bylaw minimum share floor per CUPS (e.g. 0.05 or 5%).",
    ),
    max_share: float | None = typer.Option(
        None,
        "--max-share",
        help="Regulatory or bylaw maximum share cap per CUPS (e.g. 0.70 or 70%).",
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

    cfg = load_config()
    target_consumption_dir = consumption_dir or Path(cfg.consumption_dir)
    target_generation_dir = generation_dir or Path(cfg.generation_dir)
    target_output_dir = output_dir or Path(cfg.output_dir)
    target_curated_dir = curated_dir or Path(cfg.curated_dir)
    cups_path = resolve_cups_config_path(custom_path=cups_file, config=cfg)

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

    def _parse_share(val: float | None, name: str) -> float | None:
        if val is None:
            return None
        if val < 0.0 or val > 100.0:
            console.print(
                f"[bold red]Error:[/bold red] {name} must be between 0% and 100%. Got {val}."
            )
            sys.exit(1)
        return val / 100.0 if val > 1.0 else val

    parsed_min_share = _parse_share(min_share, "--min-share")
    parsed_max_share = _parse_share(max_share, "--max-share")

    view_mode = view.lower().strip()
    is_hourly = hourly or (view_mode == "hourly")

    try:
        req = CalculationRequest(
            consumption_dir=target_consumption_dir,
            generation_dir=target_generation_dir,
            curated_dir=target_curated_dir,
            output_dir=target_output_dir,
            cups_config_path=cups_path,
            force_curate=force_curate,
            is_custom_input=(consumption_dir is not None or generation_dir is not None),
            is_custom_curated=(curated_dir is not None),
            year=year,
            month=month,
            strategy=opt_strat,
            precision=active_precision,
            compute_hourly=is_hourly,
            export_format=export_format,
            lang=active_lang,
            min_share=parsed_min_share,
            max_share=parsed_max_share,
        )

        with console.status(
            f"[bold cyan][1/4][/bold cyan] [bold white]{t('status_step_1', lang=active_lang)}[/bold white]"
        ) as status:

            def _update_step(step_idx: int, message: str) -> None:
                status.update(
                    f"[bold cyan][{step_idx}/4][/bold cyan] [bold white]{message}[/bold white]"
                )

            calc_result = CalculationService.execute(req, progress_callback=_update_step)

        opt_result = calc_result.opt_result
        metadata = calc_result.metadata

        # Presentation Views
        if view_mode in ("summary", "all"):
            render_community_summary(
                metadata, opt_result.total_summary, lang=active_lang, opt_result=opt_result
            )
            render_monthly_trajectory_table(opt_result, lang=active_lang)
            render_coefficients_matrix_table(
                opt_result, lang=active_lang, precision=active_precision
            )
        elif view_mode == "hourly":
            if opt_result.hourly_result is not None:
                render_hourly_profile_table(
                    opt_result.hourly_result, lang=active_lang, precision=active_precision
                )
        elif view_mode == "matrix":
            render_coefficients_matrix_table(
                opt_result, lang=active_lang, precision=active_precision
            )
        elif view_mode == "trajectory":
            render_monthly_trajectory_table(opt_result, lang=active_lang)
        elif view_mode == "coefficients":
            for m in opt_result.monthly_results:
                if m.has_data:
                    render_monthly_coefficients_table(
                        m, lang=active_lang, precision=active_precision
                    )
        elif view_mode == "comparison":
            render_strategy_comparison_table(opt_result, lang=active_lang)

        # File Exports Feedback
        if calc_result.exported_paths:
            render_export_success(calc_result.exported_paths, lang=active_lang)

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
    weather_dir: Path | None = typer.Option(
        None,
        "--weather-dir",
        "-w",
        help="Update default weather directory path.",
    ),
    latitude: float | None = typer.Option(
        None,
        "--latitude",
        "--lat",
        help="Update default latitude coordinate.",
    ),
    longitude: float | None = typer.Option(
        None,
        "--longitude",
        "--lon",
        help="Update default longitude coordinate.",
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
    if weather_dir is not None:
        cfg.weather_dir = str(weather_dir)
        modified = True
    if latitude is not None:
        if not (-90.0 <= latitude <= 90.0):
            console.print(
                f"[bold red]Error:[/bold red] Latitude must be between -90.0 and 90.0 (got {latitude})."
            )
            sys.exit(1)
        cfg.latitude = latitude
        modified = True
    if longitude is not None:
        if not (-180.0 <= longitude <= 180.0):
            console.print(
                f"[bold red]Error:[/bold red] Longitude must be between -180.0 and 180.0 (got {longitude})."
            )
            sys.exit(1)
        cfg.longitude = longitude
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
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to clean up. Defaults to configured output directory.",
    ),
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
    out_dir = output_dir or Path(cfg.output_dir)

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
