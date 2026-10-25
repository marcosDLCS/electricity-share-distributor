"""Application service for time-series curation and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.curation.curator import DataCurator
from src.curation.models import CuratedDataset


@dataclass(frozen=True)
class CurationRequest:
    """Request DTO for curating and reconciling time-series data."""

    consumption_dir: Path
    generation_dir: Path
    curated_dir: Path
    cups_config_path: Path | None = None
    output_name: str = "curated"
    delimiter: str = ";"
    year: int | None = None
    month: int | None = None
    weather_dir: Path | None = None
    force: bool = False


@dataclass(frozen=True)
class CurationResult:
    """Result DTO returned by CurationService."""

    dataset: CuratedDataset
    csv_path: Path


class CurationService:
    """Orchestrates fake-zero load reconciliation, metadata enrichment, and curated CSV generation."""

    @staticmethod
    def execute(request: CurationRequest) -> CurationResult:
        """Run curation workflow and return curated dataset with exported CSV path."""
        curator = DataCurator(
            consumption_dir=request.consumption_dir,
            generation_dir=request.generation_dir,
            cups_config_path=request.cups_config_path,
            curated_dir=request.curated_dir,
            weather_dir=request.weather_dir or Path(".input/weather"),
        )

        dataset = curator.curate(
            year=request.year,
            month=request.month,
        )
        csv_path = curator.export_csv(
            dataset,
            curated_dir=request.curated_dir,
            base_name=request.output_name,
            delimiter=request.delimiter,
        )
        return CurationResult(dataset=dataset, csv_path=csv_path)
