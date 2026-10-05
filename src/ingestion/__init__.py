"""Ingestion package for DATADIS consumption and Huawei generation data."""

from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader
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
    "DatadisConsumptionLoader",
    "EsdError",
    "HuaweiGenerationLoader",
    "IngestionError",
    "IngestionSummary",
    "ParseError",
    "TimeSeriesAligner",
    "ValidationError",
]
