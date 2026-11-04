"""Command-line interface entry point for Electricity Share Distributor (esd)."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from src.config import (
    DEFAULT_CONSUMPTION_DIR,
    DEFAULT_CUPS_CONFIG_PATH,
    DEFAULT_CURATED_DIR,
    DEFAULT_SHARE_PRECISION,
    DEFAULT_WEATHER_DIR,
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
    render_init_success,
    render_monthly_trajectory_table,
    render_not_initialized_warning,
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
    WeatherRequest,
    WeatherService,
)
from src.version import get_version

app = typer.Typer(
    help="Electricity Share Distributor: Optimize collective PV self-consumption coefficients (RD 244/2019).",
    add_completion=False,
)


def _handle_cli_error(err: Exception | str, unexpected: bool = False) -> NoReturn:
    """Format domain or CLI errors cleanly and exit with code 1."""
    if isinstance(err, (typer.Exit, typer.Abort)):
        raise err
    prefix = (
        "[bold red]Unexpected error:[/bold red]" if unexpected else "[bold red]Error:[/bold red]"
    )
    console.print(f"\n{prefix} {err}\n")
    raise typer.Exit(code=1)


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
    try:
        cfg = load_config()
        was_already = is_initialized()

        # 1. Clear .output (always on init / re-init)
        cleared_count = clear_output_directory(Path(cfg.output_dir))

        # 2. Ask user for desired language if not explicitly provided
        if lang is None:
            try:
                raw_lang = typer.prompt(
                    t("prompt_lang", lang=cfg.language),
                    default="en",
                )
            except typer.exceptions.Abort, EOFError:
                raw_lang = "en"
        else:
            raw_lang = lang

        try:
            target_lang = normalize_language_code(raw_lang)
        except ValueError as err:
            _handle_cli_error(err)

        # 3. Ask user for desired precision if not explicitly provided
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
    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


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
    try:
        active_lang = normalize_language_code(lang) if lang else get_language()
        cfg = load_config()
        target_consumption_dir = consumption_dir or Path(cfg.consumption_dir)
        target_generation_dir = generation_dir or Path(cfg.generation_dir)
        target_weather_dir = weather_dir or (
            Path(cfg.weather_dir) if cfg and cfg.weather_dir else DEFAULT_WEATHER_DIR
        )
        cups_path = (
            resolve_cups_config_path(custom_path=cups_file, config=cfg)
            if (cups_file is not None or consumption_dir is None)
            else None
        )

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
            raise typer.Exit(code=1)
    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


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
        "-u",
        "-o",
        help="Path to directory where curated CSV files will be written. Defaults to configured path.",
    ),
    name: str = typer.Option(
        "esd",
        "--name",
        "-n",
        help="Base filename for generated master curated export (e.g. 'esd' produces esd.csv and esd.xlsx).",
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
    cups_path = (
        resolve_cups_config_path(custom_path=cups_file, config=cfg)
        if (cups_file is not None or consumption_dir is None)
        else None
    )

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
            excel_path=cur_result.excel_path,
            lang=active_lang,
            generation_csv_path=cur_result.generation_csv_path,
            generation_excel_path=cur_result.generation_excel_path,
            consumption_csv_path=cur_result.consumption_csv_path,
            consumption_excel_path=cur_result.consumption_excel_path,
        )

    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


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
    cups_path = resolve_cups_config_path(custom_path=cups_file, config=cfg)

    status_spinner = console.status(
        f"[bold cyan]{t('status_weather', lang=active_lang, year=year)}[/bold cyan]"
    )

    def on_progress(lat: float, lon: float, idx: int, total: int) -> None:
        coord_str = (
            f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
        )
        status_text = (
            f"[bold cyan]{t('status_weather_coord', lang=active_lang, year=year, coords=coord_str)}[/bold cyan]"
            if total > 1
            else f"[bold cyan]{t('status_weather', lang=active_lang, year=year)}[/bold cyan]"
        )
        status_spinner.update(status_text)

    try:
        req = WeatherRequest(
            year=year,
            latitude=latitude,
            longitude=longitude,
            cups_file=cups_path,
            weather_dir=weather_dir,
            timezone=timezone,
            config=cfg,
            lang=active_lang,
            resolve_cups=False,
        )
        with status_spinner:
            service_result = WeatherService.execute(req, progress_callback=on_progress)

        for result in service_result.results:
            render_weather_result(result, lang=active_lang)

    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


@app.command(name="calculate")
def calculate_command() -> None:
    """Calculate optimal electricity distribution coefficients (beta_i) for collective PV installation."""
    cfg = load_config()
    active_lang = cfg.language
    active_precision = cfg.share_precision

    if not is_initialized():
        render_not_initialized_warning(lang=active_lang)

    target_consumption_dir = Path(cfg.consumption_dir)
    target_generation_dir = Path(cfg.generation_dir)
    target_output_dir = Path(cfg.output_dir)
    target_curated_dir = Path(cfg.curated_dir)
    target_weather_dir = Path(cfg.weather_dir) if cfg and cfg.weather_dir else DEFAULT_WEATHER_DIR

    is_default_dirs = (
        target_consumption_dir == DEFAULT_CONSUMPTION_DIR
        and target_curated_dir == DEFAULT_CURATED_DIR
    )
    if cfg.cups_config_path != str(DEFAULT_CUPS_CONFIG_PATH):
        cups_path = resolve_cups_config_path(custom_path=cfg.cups_config_path, config=cfg)
    elif is_default_dirs:
        cups_path = resolve_cups_config_path(custom_path=None, config=cfg)
    else:
        cups_path = None

    try:
        req = CalculationRequest(
            consumption_dir=target_consumption_dir,
            generation_dir=target_generation_dir,
            curated_dir=target_curated_dir,
            output_dir=target_output_dir,
            weather_dir=target_weather_dir,
            cups_config_path=cups_path,
            force_curate=False,
            is_custom_input=False,
            is_custom_curated=False,
            year=None,
            month=None,
            strategy=OptimizationStrategy.OPTIMAL,
            precision=active_precision,
            compute_hourly=True,
            export_format="all",
            lang=active_lang,
            min_share=None,
            max_share=None,
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
        render_community_summary(
            metadata, opt_result.total_summary, lang=active_lang, opt_result=opt_result
        )
        render_monthly_trajectory_table(opt_result, lang=active_lang)
        render_coefficients_matrix_table(opt_result, lang=active_lang, precision=active_precision)

        # File Exports Feedback
        if calc_result.exported_paths:
            render_export_success(calc_result.exported_paths, lang=active_lang)

    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


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
    curated_dir: Path | None = typer.Option(
        None,
        "--curated-dir",
        "-u",
        help="Update default curated directory path.",
    ),
) -> None:
    """View or update persistent application configuration."""
    try:
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
                _handle_cli_error(t("err_lat_range", lang=active_lang, val=latitude))
            cfg.latitude = latitude
            modified = True
        if longitude is not None:
            if not (-180.0 <= longitude <= 180.0):
                _handle_cli_error(t("err_lon_range", lang=active_lang, val=longitude))
            cfg.longitude = longitude
            modified = True
        if output_dir is not None:
            cfg.output_dir = str(output_dir)
            modified = True
        if curated_dir is not None:
            cfg.curated_dir = str(curated_dir)
            modified = True

        if modified:
            save_config(cfg)
            console.print(f"[bold green]{t('msg_config_updated', lang=cfg.language)}[/bold green]")

        render_config_view(cfg, lang=cfg.language)
    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


@app.command(name="cleanup")
def cleanup_command(
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory to clean up. Defaults to configured output directory.",
    ),
    curated_dir: Path | None = typer.Option(
        None,
        "--curated-dir",
        "-u",
        help="Curated directory to clean up. Defaults to configured curated directory.",
    ),
    weather_dir: Path | None = typer.Option(
        None,
        "--weather-dir",
        "-w",
        help="Weather directory to clean up. Defaults to configured weather directory.",
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
    """Clean up generated files from .output, .curated, and .input/weather directories."""
    try:
        active_lang = normalize_language_code(lang) if lang else get_language()
        cfg = load_config()
        out_dir = output_dir or Path(cfg.output_dir)
        cur_dir = curated_dir or Path(cfg.curated_dir)
        wth_dir = weather_dir or (
            Path(cfg.weather_dir) if cfg and cfg.weather_dir else DEFAULT_WEATHER_DIR
        )

        target_dirs = [out_dir, cur_dir, wth_dir]
        dirs_display = ", ".join(str(d) for d in target_dirs)

        files: list[Path] = []
        for d in target_dirs:
            if d.exists() and d.is_dir():
                files.extend(f for f in d.iterdir() if f.is_file() and not f.name.startswith("."))

        if not files:
            render_cleanup_result(count=0, output_dir=dirs_display, lang=active_lang)
            return

        if not force:
            confirm = typer.confirm(
                t(
                    "prompt_cleanup_confirm",
                    lang=active_lang,
                    count=len(files),
                    dir=dirs_display,
                ),
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

        render_cleanup_result(count=count, output_dir=dirs_display, lang=active_lang)
    except typer.Exit, typer.Abort:
        raise
    except EsdError as err:
        _handle_cli_error(err)
    except Exception as exc:
        _handle_cli_error(exc, unexpected=True)


def main() -> None:
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
