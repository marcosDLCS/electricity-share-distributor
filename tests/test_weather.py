"""Tests for Open-Meteo weather downloading, loading, and CLI commands."""

from __future__ import annotations

import io
import json
import urllib.error
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.cli import app
from src.config import AppConfig, load_config, save_config
from src.ingestion.schema import IngestionError
from src.ingestion.weather import (
    WMO_WEATHER_CODES,
    OpenMeteoWeatherDownloader,
    WeatherLoader,
)

runner = CliRunner()


def _mock_open_meteo_response(
    start_date: str = "2024-01-01",
    hours_count: int = 24,
) -> bytes:
    """Generate mock Open-Meteo API JSON response payload."""
    times = [f"{start_date}T{h:02d}:00" for h in range(hours_count)]
    temps = [10.0 + (h % 5) for h in range(hours_count)]
    clouds = [20 + (h % 50) for h in range(hours_count)]
    codes = [1 if h % 2 == 0 else 2 for h in range(hours_count)]

    payload = {
        "latitude": 40.4168,
        "longitude": -3.7038,
        "generationtime_ms": 1.23,
        "utc_offset_seconds": 3600,
        "timezone": "Europe/Madrid",
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "cloud_cover": clouds,
            "weather_code": codes,
        },
    }
    return json.dumps(payload).encode("utf-8")


# =========================================================================
# Unit Tests: OpenMeteoWeatherDownloader validation
# =========================================================================


def test_validate_coordinates_valid() -> None:
    """Valid latitude and longitude should not raise exceptions."""
    OpenMeteoWeatherDownloader.validate_coordinates(40.4168, -3.7038)
    OpenMeteoWeatherDownloader.validate_coordinates(0.0, 0.0)
    OpenMeteoWeatherDownloader.validate_coordinates(-90.0, 180.0)
    OpenMeteoWeatherDownloader.validate_coordinates(90.0, -180.0)


def test_validate_coordinates_invalid_latitude() -> None:
    """Out of bound latitude should raise IngestionError."""
    with pytest.raises(IngestionError, match=r"Latitude must be between -90\.0 and 90\.0"):
        OpenMeteoWeatherDownloader.validate_coordinates(91.0, 0.0)

    with pytest.raises(IngestionError, match=r"Latitude must be between -90\.0 and 90\.0"):
        OpenMeteoWeatherDownloader.validate_coordinates(-90.1, 0.0)


def test_validate_coordinates_invalid_longitude() -> None:
    """Out of bound longitude should raise IngestionError."""
    with pytest.raises(IngestionError, match=r"Longitude must be between -180\.0 and 180\.0"):
        OpenMeteoWeatherDownloader.validate_coordinates(0.0, 180.1)

    with pytest.raises(IngestionError, match=r"Longitude must be between -180\.0 and 180\.0"):
        OpenMeteoWeatherDownloader.validate_coordinates(0.0, -181.0)


def test_validate_year_past() -> None:
    """Past year returns full calendar year range."""
    start_date, end_date = OpenMeteoWeatherDownloader.validate_year(2023)
    assert start_date == "2023-01-01"
    assert end_date == "2023-12-31"


def test_validate_year_current() -> None:
    """Current year bounds end_date to today."""
    today = date.today()
    start_date, end_date = OpenMeteoWeatherDownloader.validate_year(today.year)
    assert start_date == f"{today.year}-01-01"
    assert end_date == today.strftime("%Y-%m-%d")


def test_validate_year_too_early() -> None:
    """Year prior to 1940 raises IngestionError."""
    with pytest.raises(IngestionError, match="Year must be 1940 or later"):
        OpenMeteoWeatherDownloader.validate_year(1939)


def test_validate_year_future() -> None:
    """Future year raises IngestionError."""
    today = date.today()
    with pytest.raises(IngestionError, match="Cannot download historical weather for future year"):
        OpenMeteoWeatherDownloader.validate_year(today.year + 1)


# =========================================================================
# Unit Tests: OpenMeteoWeatherDownloader download_year
# =========================================================================


def test_download_year_success_and_overwrite(tmp_path: Path) -> None:
    """Downloading should write CSV, compute metrics, and overwrite when re-run."""
    weather_dir = tmp_path / "weather"
    downloader = OpenMeteoWeatherDownloader(weather_dir=weather_dir)

    mock_resp = MagicMock()
    mock_resp.read.return_value = _mock_open_meteo_response(hours_count=24)
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        out_file, df, result = downloader.download_year(
            year=2023,
            latitude=40.4168,
            longitude=-3.7038,
        )

    assert out_file.exists()
    assert out_file.name == "weather_2023.csv"
    assert len(df) == 24
    assert list(df.columns) == ["timestamp", "temperature", "cloud_cover", "weather_code"]
    assert result.overwritten is False
    assert result.total_hours == 24
    assert result.min_temperature == 10.0
    assert result.max_temperature == 14.0

    # Second run should overwrite existing file
    with patch("urllib.request.urlopen", return_value=mock_resp):
        out_file2, _df2, result2 = downloader.download_year(
            year=2023,
            latitude=40.4168,
            longitude=-3.7038,
        )

    assert out_file2 == out_file
    assert result2.overwritten is True


def test_download_year_http_error(tmp_path: Path) -> None:
    """HTTP errors from Open-Meteo should be caught and raised as IngestionError."""
    downloader = OpenMeteoWeatherDownloader(weather_dir=tmp_path)

    err = urllib.error.HTTPError(
        url="https://archive-api.open-meteo.com/v1/archive",
        code=400,
        msg="Bad Request",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error": true, "reason": "Location invalid"}'),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(IngestionError, match="Open-Meteo API HTTP Error 400: Location invalid"):
            downloader.download_year(year=2023, latitude=40.0, longitude=-3.0)


def test_download_year_url_error(tmp_path: Path) -> None:
    """Network connection errors should be caught and raised as IngestionError."""
    downloader = OpenMeteoWeatherDownloader(weather_dir=tmp_path)
    err = urllib.error.URLError(reason="Name resolution failed")

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(IngestionError, match="Failed to connect to Open-Meteo API"):
            downloader.download_year(year=2023, latitude=40.0, longitude=-3.0)


def test_download_year_malformed_response(tmp_path: Path) -> None:
    """Malformed JSON response without hourly times should raise IngestionError."""
    downloader = OpenMeteoWeatherDownloader(weather_dir=tmp_path)
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"hourly": {}}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(IngestionError, match="Malformed Open-Meteo response"):
            downloader.download_year(year=2023, latitude=40.0, longitude=-3.0)


# =========================================================================
# Unit Tests: WeatherLoader
# =========================================================================


def test_weather_loader_discover_and_load(tmp_path: Path) -> None:
    """WeatherLoader should discover CSVs and parse them into structured DataFrames."""
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()

    csv_path = weather_dir / "weather_2024.csv"
    csv_path.write_text(
        "timestamp,temperature,cloud_cover,weather_code\n"
        "2024-01-01 00:00:00,5.2,80,3\n"
        "2024-01-01 01:00:00,4.8,90,45\n",
        encoding="utf-8",
    )

    loader = WeatherLoader(weather_dir=weather_dir)
    discovered = loader.discover_files()
    assert discovered == [csv_path]

    df = loader.load_year(2024)
    assert len(df) == 2
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert df["temperature"].iloc[0] == 5.2
    assert df["cloud_cover"].iloc[0] == 80
    assert df["weather_code"].iloc[0] == 3


def test_weather_loader_missing_year(tmp_path: Path) -> None:
    """Loading an unrecorded year raises IngestionError with download guidance."""
    loader = WeatherLoader(weather_dir=tmp_path)
    with pytest.raises(IngestionError, match="No weather CSV found for year 2020"):
        loader.load_year(2020)


def test_weather_loader_missing_column(tmp_path: Path) -> None:
    """CSV missing required weather column raises IngestionError."""
    csv_path = tmp_path / "weather_2024.csv"
    csv_path.write_text(
        "timestamp,temperature,cloud_cover\n2024-01-01 00:00:00,5.2,80\n",
        encoding="utf-8",
    )
    loader = WeatherLoader(weather_dir=tmp_path)
    with pytest.raises(IngestionError, match="missing required column: 'weather_code'"):
        loader.load_year(2024)


def test_weather_loader_load_all(tmp_path: Path) -> None:
    """load_all combines multiple yearly CSV files and sorts by timestamp."""
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()

    f1 = weather_dir / "weather_2023.csv"
    f1.write_text(
        "timestamp,temperature,cloud_cover,weather_code\n2023-12-31 23:00:00,3.0,10,0\n",
        encoding="utf-8",
    )

    f2 = weather_dir / "weather_2024.csv"
    f2.write_text(
        "timestamp,temperature,cloud_cover,weather_code\n2024-01-01 00:00:00,2.5,20,1\n",
        encoding="utf-8",
    )

    loader = WeatherLoader(weather_dir=weather_dir)
    combined = loader.load_all()
    assert len(combined) == 2
    assert combined["timestamp"].iloc[0] == pd.Timestamp("2023-12-31 23:00:00")
    assert combined["timestamp"].iloc[1] == pd.Timestamp("2024-01-01 00:00:00")


def test_wmo_weather_codes() -> None:
    """Check that WMO weather codes dictionary contains expected standard keys."""
    assert 0 in WMO_WEATHER_CODES
    assert WMO_WEATHER_CODES[0] == "Clear sky"
    assert 61 in WMO_WEATHER_CODES
    assert "rain" in WMO_WEATHER_CODES[61].lower()


# =========================================================================
# CLI Integration Tests: esd weather & esd config
# =========================================================================


def test_cli_weather_missing_coordinates(tmp_path: Path) -> None:
    """Running weather command without coordinates or config coordinates fails gracefully."""
    config_file = tmp_path / ".esd_config.json"
    save_config(AppConfig(latitude=None, longitude=None), path=config_file)

    with patch("src.cli.load_config", return_value=load_config(config_file)):
        result = runner.invoke(app, ["weather", "--year", "2023"])

    assert result.exit_code != 0
    assert "Coordinates are required" in result.output


def test_cli_weather_success_with_cli_coords(tmp_path: Path) -> None:
    """Running weather command with explicit --lat and --lon downloads and renders results."""
    weather_dir = tmp_path / "weather"
    config_file = tmp_path / ".esd_config.json"
    save_config(AppConfig(weather_dir=str(weather_dir)), path=config_file)

    mock_resp = MagicMock()
    mock_resp.read.return_value = _mock_open_meteo_response(hours_count=24)
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with (
        patch("src.cli.load_config", return_value=load_config(config_file)),
        patch("urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(
            app,
            [
                "weather",
                "--year",
                "2023",
                "--latitude",
                "40.4168",
                "--longitude",
                "-3.7038",
                "--weather-dir",
                str(weather_dir),
            ],
        )

    assert result.exit_code == 0
    assert "OPEN-METEO HOURLY WEATHER INGESTION" in result.output
    assert "40.4168°N, 3.7038°W" in result.output
    assert "2023" in result.output
    assert (weather_dir / "weather_2023.csv").exists()


def test_cli_weather_uses_configured_coordinates(tmp_path: Path) -> None:
    """Running weather command without CLI coords uses persisted coordinates from config."""
    weather_dir = tmp_path / "weather"
    config_file = tmp_path / ".esd_config.json"
    save_config(
        AppConfig(
            latitude=37.3891,
            longitude=-5.9845,
            weather_dir=str(weather_dir),
        ),
        path=config_file,
    )

    mock_resp = MagicMock()
    mock_resp.read.return_value = _mock_open_meteo_response(hours_count=24)
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with (
        patch("src.cli.load_config", return_value=load_config(config_file)),
        patch("urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["weather", "--year", "2023"])

    assert result.exit_code == 0
    assert "37.3891°N, 5.9845°W" in result.output
    assert (weather_dir / "weather_2023.csv").exists()


def test_cli_weather_spanish_output(tmp_path: Path) -> None:
    """Running weather command with --lang es renders Spanish localized headers."""
    weather_dir = tmp_path / "weather"
    mock_resp = MagicMock()
    mock_resp.read.return_value = _mock_open_meteo_response(hours_count=24)
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = runner.invoke(
            app,
            [
                "weather",
                "--year",
                "2023",
                "--lat",
                "40.4168",
                "--lon",
                "-3.7038",
                "-w",
                str(weather_dir),
                "--lang",
                "es",
            ],
        )

    assert result.exit_code == 0
    assert "INGESTA METEOROLÓGICA HORARIA OPEN-METEO" in result.output
    assert "Coordenadas" in result.output


def test_cli_config_update_weather_and_coords(tmp_path: Path) -> None:
    """Updating weather_dir, latitude, and longitude via esd config persists properly."""
    config_file = tmp_path / ".esd_config.json"
    save_config(AppConfig(), path=config_file)

    with patch("src.config.CONFIG_FILE_PATH", config_file):
        result = runner.invoke(
            app,
            [
                "config",
                "--weather-dir",
                ".input/custom_weather",
                "--latitude",
                "41.3851",
                "--longitude",
                "2.1734",
            ],
        )

    assert result.exit_code == 0
    cfg = load_config(config_file)
    assert cfg.weather_dir == ".input/custom_weather"
    assert cfg.latitude == 41.3851
    assert cfg.longitude == 2.1734


def test_cli_config_invalid_coordinates() -> None:
    """Invalid latitude or longitude passed to esd config fails with exit code 1."""
    res_lat = runner.invoke(app, ["config", "--latitude", "100.0"])
    assert res_lat.exit_code != 0
    assert "Latitude must be between -90.0 and 90.0" in res_lat.output

    res_lon = runner.invoke(app, ["config", "--longitude", "200.0"])
    assert res_lon.exit_code != 0
    assert "Longitude must be between -180.0 and 180.0" in res_lon.output
