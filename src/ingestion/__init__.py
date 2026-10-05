"""Ingestion package for DATADIS consumption and Huawei generation data."""

from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.doctor import DataDoctor, DoctorReport, GapInterval, SeriesCheckResult
from src.ingestion.generation import HuaweiGenerationLoader
from src.ingestion.schema import (
    AlignedDataset,
    AlignmentError,
    EsdError,
    IngestionError,
    IngestionSummary,
    ParseError,
    ValidationError,
)

__all__ = [
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
    "ParseError",
    "SeriesCheckResult",
    "TimeSeriesAligner",
    "ValidationError",
]
