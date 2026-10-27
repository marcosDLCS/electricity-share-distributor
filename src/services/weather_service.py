"""Application service for orchestrating weather data downloads."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.config import DEFAULT_WEATHER_DIR, AppConfig, load_config, resolve_cups_config_path
from src.domain.exceptions import ValidationError
from src.i18n import t
from src.ingestion.weather import (
    OpenMeteoWeatherDownloader,
    WeatherDownloadResult,
    extract_coordinates_from_cups_file,
)


@dataclass(frozen=True)
class WeatherRequest:
    """Request DTO for downloading hourly weather data."""

    year: int
    latitude: float | None = None
    longitude: float | None = None
    cups_file: Path | None = None
    weather_dir: Path | None = None
    timezone: str = "auto"
    config: AppConfig | None = None
    lang: str = "en"
    resolve_cups: bool = True


@dataclass(frozen=True)
class WeatherServiceResult:
    """Result DTO returned by WeatherService."""

    results: list[WeatherDownloadResult]


class WeatherService:
    """Orchestrates coordinate resolution and Open-Meteo weather downloads."""

    @staticmethod
    def resolve_coordinates(
        latitude: float | None = None,
        longitude: float | None = None,
        cups_file: Path | None = None,
        config: AppConfig | None = None,
        lang: str = "en",
        resolve_cups: bool = True,
    ) -> list[tuple[float, float]]:
        """Resolve geographical coordinates following the fallback chain:

        1. Explicit manual coordinates (both lat and lon required).
        2. cups.json configuration file.
        3. Persistent AppConfig settings.

        Raises:
            ValidationError: If coordinates are incomplete or cannot be resolved.
        """
        cfg = config or load_config()

        if latitude is not None and longitude is not None:
            return [(latitude, longitude)]

        if latitude is not None or longitude is not None:
            raise ValidationError(
                "Both --latitude and --longitude must be provided when specifying manual coordinates."
            )

        # Check cups.json configuration file
        if cups_file is not None:
            if cups_file.exists() and cups_file.is_file():
                coords = extract_coordinates_from_cups_file(cups_file)
                if coords:
                    return coords
        elif resolve_cups:
            cups_path = resolve_cups_config_path(config=cfg)
            if cups_path:
                coords = extract_coordinates_from_cups_file(cups_path)
                if coords:
                    return coords

        # Fallback to persistent configuration if cups.json didn't yield any coordinates
        if cfg.latitude is not None and cfg.longitude is not None:
            return [(cfg.latitude, cfg.longitude)]

        raise ValidationError(t("err_coords_required", lang=lang))

    @staticmethod
    def execute(
        request: WeatherRequest,
        progress_callback: Callable[[float, float, int, int], None] | None = None,
    ) -> WeatherServiceResult:
        """Download hourly weather datasets for all resolved coordinates.

        Args:
            request: Weather download request parameters.
            progress_callback: Optional hook called before downloading each location:
                callback(latitude, longitude, current_index, total_locations).

        Returns:
            WeatherServiceResult containing summary metrics for each download.
        """
        cfg = request.config or load_config()
        coords = WeatherService.resolve_coordinates(
            latitude=request.latitude,
            longitude=request.longitude,
            cups_file=request.cups_file,
            config=cfg,
            lang=request.lang,
            resolve_cups=request.resolve_cups,
        )

        target_weather_dir = request.weather_dir or (
            Path(cfg.weather_dir) if cfg and cfg.weather_dir else DEFAULT_WEATHER_DIR
        )
        downloader = OpenMeteoWeatherDownloader(weather_dir=target_weather_dir)

        results: list[WeatherDownloadResult] = []
        total = len(coords)
        for idx, (lat, lon) in enumerate(coords):
            if progress_callback:
                progress_callback(lat, lon, idx + 1, total)
            _, _, result = downloader.download_year(
                year=request.year,
                latitude=lat,
                longitude=lon,
                timezone=request.timezone,
            )
            results.append(result)

        return WeatherServiceResult(results=results)
