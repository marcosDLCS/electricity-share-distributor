"""Open-Meteo hourly weather data downloader and ingestion loader for esd."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

import pandas as pd

from src.ingestion.schema import IngestionError

# Official WMO weather code descriptions
WMO_WEATHER_CODES: Final[dict[int, str]] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass
class WeatherDownloadResult:
    """Outcome and summary metrics of an Open-Meteo weather download operation.

    Attributes:
        year: Downloaded calendar year.
        latitude: Geographical latitude coordinate.
        longitude: Geographical longitude coordinate.
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        total_hours: Total number of hourly intervals retrieved.
        file_path: Destination path of the saved CSV file.
        avg_temperature: Mean temperature (°C) across the period.
        min_temperature: Minimum recorded temperature (°C).
        max_temperature: Maximum recorded temperature (°C).
        avg_cloud_cover: Mean cloud cover percentage (0-100%).
        overwritten: Whether an existing file was overwritten.
    """

    year: int
    latitude: float
    longitude: float
    start_date: str
    end_date: str
    total_hours: int
    file_path: Path
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    avg_cloud_cover: float
    overwritten: bool


class OpenMeteoWeatherDownloader:
    """Downloads hourly historical weather data from the Open-Meteo Archive API."""

    DEFAULT_BASE_URL: Final[str] = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(
        self,
        weather_dir: Path | str,
        base_url: str | None = None,
    ) -> None:
        self.weather_dir = Path(weather_dir)
        self.base_url = base_url or self.DEFAULT_BASE_URL

    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> None:
        """Validate latitude and longitude ranges.

        Raises:
            IngestionError: If coordinates are out of standard bounds.
        """
        if not (-90.0 <= latitude <= 90.0):
            raise IngestionError(f"Latitude must be between -90.0 and 90.0 (got {latitude}).")
        if not (-180.0 <= longitude <= 180.0):
            raise IngestionError(f"Longitude must be between -180.0 and 180.0 (got {longitude}).")

    @staticmethod
    def validate_year(year: int) -> tuple[str, str]:
        """Validate requested calendar year and calculate start and end dates.

        Raises:
            IngestionError: If the year is before 1940 or completely in the future.
        """
        if year < 1940:
            raise IngestionError(
                f"Year must be 1940 or later. Open-Meteo historical archive begins in 1940 (got {year})."
            )

        today = date.today()
        current_year = today.year

        if year > current_year:
            raise IngestionError(
                f"Cannot download historical weather for future year {year}. "
                f"Open-Meteo historical archive only covers past dates up to the present."
            )

        start_date = f"{year}-01-01"
        if year == current_year:
            end_date = min(date(year, 12, 31), today).strftime("%Y-%m-%d")
        else:
            end_date = f"{year}-12-31"

        return start_date, end_date

    def download_year(
        self,
        year: int,
        latitude: float,
        longitude: float,
        timezone: str = "auto",
        timeout_seconds: int = 30,
    ) -> tuple[Path, pd.DataFrame, WeatherDownloadResult]:
        """Fetch hourly weather records from Open-Meteo for an entire year and save to CSV.

        If a file already exists for that year, it is automatically overwritten.

        Args:
            year: Calendar year to query (e.g. 2024).
            latitude: Geographical latitude.
            longitude: Geographical longitude.
            timezone: Timezone for timestamps (default: 'auto').
            timeout_seconds: Network request timeout in seconds.

        Returns:
            Tuple of (saved_file_path, weather_dataframe, download_result).

        Raises:
            IngestionError: On invalid parameters, network failures, or API errors.
        """
        self.validate_coordinates(latitude, longitude)
        start_date, end_date = self.validate_year(year)

        url = (
            f"{self.base_url}"
            f"?latitude={latitude}&longitude={longitude}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&hourly=temperature_2m,cloud_cover,weather_code"
            f"&timezone={timezone}"
        )

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "esd/1.0 (electricity-share-distributor)"},
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                raw_bytes = response.read()
                data = json.loads(raw_bytes.decode("utf-8"))
        except urllib.error.HTTPError as err:
            error_body = ""
            try:
                error_body = err.read().decode("utf-8")
                parsed_err = json.loads(error_body)
                reason = parsed_err.get("reason", error_body)
            except Exception:
                reason = error_body or str(err)
            raise IngestionError(f"Open-Meteo API HTTP Error {err.code}: {reason}") from err
        except urllib.error.URLError as err:
            raise IngestionError(f"Failed to connect to Open-Meteo API: {err.reason}") from err
        except TimeoutError as err:
            raise IngestionError(
                f"Connection to Open-Meteo timed out after {timeout_seconds} seconds."
            ) from err
        except Exception as err:
            raise IngestionError(f"Unexpected error retrieving Open-Meteo data: {err}") from err

        hourly = data.get("hourly")
        if not hourly or "time" not in hourly:
            raise IngestionError(
                f"Malformed Open-Meteo response: 'hourly' field missing or empty for year {year}."
            )

        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        clouds = hourly.get("cloud_cover", [])
        codes = hourly.get("weather_code", [])

        if not times or len(times) != len(temps):
            raise IngestionError(
                f"No hourly weather records returned by Open-Meteo for year {year}."
            )

        # Standardize timestamp to YYYY-MM-DD HH:MM:SS
        formatted_timestamps = (
            pd.to_datetime(times, errors="coerce").strftime("%Y-%m-%d %H:%M:%S").tolist()
        )

        df = pd.DataFrame(
            {
                "timestamp": formatted_timestamps,
                "temperature": [float(t) if t is not None else float("nan") for t in temps],
                "cloud_cover": [int(c) if c is not None else 0 for c in clouds],
                "weather_code": [int(w) if w is not None else 0 for w in codes],
            }
        )

        # Ensure weather directory exists
        self.weather_dir.mkdir(parents=True, exist_ok=True)
        out_file = self.weather_dir / f"weather_{year}.csv"
        overwritten = out_file.exists()

        # Save to CSV (overwriting if it already exists)
        df.to_csv(out_file, index=False)

        valid_temps = df["temperature"].dropna()
        avg_temp = float(valid_temps.mean()) if not valid_temps.empty else 0.0
        min_temp = float(valid_temps.min()) if not valid_temps.empty else 0.0
        max_temp = float(valid_temps.max()) if not valid_temps.empty else 0.0
        avg_cloud = float(df["cloud_cover"].mean()) if not df.empty else 0.0

        result = WeatherDownloadResult(
            year=year,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            total_hours=len(df),
            file_path=out_file,
            avg_temperature=avg_temp,
            min_temperature=min_temp,
            max_temperature=max_temp,
            avg_cloud_cover=avg_cloud,
            overwritten=overwritten,
        )

        return out_file, df, result


class WeatherLoader:
    """Discovers, validates, and loads local weather CSV files from .input/weather."""

    REQUIRED_COLUMNS: Final[list[str]] = [
        "timestamp",
        "temperature",
        "cloud_cover",
        "weather_code",
    ]

    def __init__(self, weather_dir: Path | str) -> None:
        self.weather_dir = Path(weather_dir)

    def discover_files(self) -> list[Path]:
        """Find all weather CSV files in the weather directory."""
        if not self.weather_dir.exists():
            return []

        return sorted(
            [
                f
                for f in self.weather_dir.iterdir()
                if f.is_file() and f.suffix.lower() == ".csv" and not f.name.startswith(".")
            ]
        )

    def load_year(self, year: int) -> pd.DataFrame:
        """Load weather data for a specific calendar year.

        Looks for weather_{year}.csv or {year}.csv.
        """
        candidate1 = self.weather_dir / f"weather_{year}.csv"
        candidate2 = self.weather_dir / f"{year}.csv"

        target_file: Path | None = None
        if candidate1.exists():
            target_file = candidate1
        elif candidate2.exists():
            target_file = candidate2

        if target_file is None:
            raise IngestionError(
                f"No weather CSV found for year {year} in {self.weather_dir}. "
                f"Run 'esd weather --year {year}' to download it."
            )

        return self.parse_file(target_file)

    def parse_file(self, file_path: Path) -> pd.DataFrame:
        """Parse and validate a single weather CSV file."""
        try:
            df = pd.read_csv(file_path)
        except Exception as err:
            raise IngestionError(f"Failed to read weather CSV '{file_path}': {err}") from err

        # Normalize column names to lowercase
        df.columns = df.columns.str.strip().str.lower()

        # Check required columns
        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                raise IngestionError(
                    f"Weather CSV '{file_path.name}' is missing required column: '{col}'. "
                    f"Expected columns: {self.REQUIRED_COLUMNS}"
                )

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
        df["cloud_cover"] = pd.to_numeric(df["cloud_cover"], errors="coerce")
        df["weather_code"] = pd.to_numeric(df["weather_code"], errors="coerce")

        return df.sort_values("timestamp").reset_index(drop=True)

    def load_all(self) -> pd.DataFrame:
        """Load and concatenate all weather CSV files discovered in weather_dir."""
        files = self.discover_files()
        if not files:
            raise IngestionError(f"No weather CSV files found in {self.weather_dir}")

        dfs = [self.parse_file(f) for f in files]
        combined = pd.concat(dfs, ignore_index=True)
        return (
            combined.drop_duplicates(subset=["timestamp"], keep="last")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
