"""Ingestion package for DATADIS consumption and Huawei generation data."""

from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader, DatadisValidator
from src.ingestion.csv_utils import (
    clean_numeric_series,
    detect_file_encoding,
    sniff_csv_delimiter,
)
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
    ValidationResult,
)
from src.ingestion.weather import (
    ALLOWED_WEATHER_HOST,
    MAX_RESPONSE_BYTES,
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
    "ALLOWED_WEATHER_HOST",
    "MAX_RESPONSE_BYTES",
    "WMO_WEATHER_CODES",
    "AlignedDataset",
    "AlignmentError",
    "DataDoctor",
    "DatadisConsumptionLoader",
    "DatadisValidator",
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
    "ValidationResult",
    "WeatherDownloadResult",
    "WeatherLoader",
    "clean_numeric_series",
    "detect_file_encoding",
    "extract_coordinates_from_cups_data",
    "extract_coordinates_from_cups_file",
    "format_weather_filename",
    "parse_coordinate_pair",
    "sniff_csv_delimiter",
]
