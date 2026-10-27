"""Ingestion package for DATADIS consumption and Huawei generation data."""

from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.doctor import DataDoctor, DoctorReport, GapInterval, SeriesCheckResult
from src.ingestion.generation import HuaweiGenerationLoader, SolarGenerationLoader
from src.ingestion.schema import (
    AlignedDataset,
    AlignmentError,
    EsdError,
    IngestionError,
    IngestionSummary,
    ParseError,
    ValidationError,
)
from src.ingestion.weather import (
    WMO_WEATHER_CODES,
    OpenMeteoWeatherDownloader,
    WeatherDownloadResult,
    WeatherLoader,
    extract_coordinates_from_cups_data,
    extract_coordinates_from_cups_file,
    format_weather_filename,
    parse_coordinate_pair,
)

__all__ = [
    "WMO_WEATHER_CODES",
    "AlignedDataset",
    "AlignmentError",
    "DataDoctor",
    "DatadisConsumptionLoader",
    "DoctorReport",
    "EsdError",
    "GapInterval",
    "HuaweiGenerationLoader",
    "IngestionError",
    "IngestionSummary",
    "OpenMeteoWeatherDownloader",
    "ParseError",
    "SeriesCheckResult",
    "SolarGenerationLoader",
    "TimeSeriesAligner",
    "ValidationError",
    "WeatherDownloadResult",
    "WeatherLoader",
    "extract_coordinates_from_cups_data",
    "extract_coordinates_from_cups_file",
    "format_weather_filename",
    "parse_coordinate_pair",
]
