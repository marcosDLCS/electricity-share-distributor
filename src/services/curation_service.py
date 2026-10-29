"""Application service for multi-stage time-series aggregation, curation, and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.curation.curator import DataCurator
from src.curation.models import ConsumptionDataset, CuratedDataset, GenerationDataset


@dataclass(frozen=True)
class CurationRequest:
    """Request DTO for aggregating, curating, and reconciling time-series data."""

    consumption_dir: Path
    generation_dir: Path
    curated_dir: Path
    cups_config_path: Path | None = None
    output_name: str = "esd"
    delimiter: str = ";"
    year: int | None = None
    month: int | None = None
    weather_dir: Path | None = None
    force: bool = False


@dataclass(frozen=True)
class CurationResult:
    """Result DTO returned by CurationService containing all 3 pipeline stage artifacts."""

    dataset: CuratedDataset
    csv_path: Path
    excel_path: Path | None = None
    generation_dataset: GenerationDataset | None = None
    generation_csv_path: Path | None = None
    generation_excel_path: Path | None = None
    consumption_dataset: ConsumptionDataset | None = None
    consumption_csv_path: Path | None = None
    consumption_excel_path: Path | None = None


class CurationService:
    """Orchestrates the 3-stage curation pipeline: aggregate generation, aggregate consumption, and build ESD master files."""

    @staticmethod
    def execute(request: CurationRequest) -> CurationResult:
        """Run multi-stage curation workflow and return datasets with exported CSV and Excel paths."""
        curator = DataCurator(
            consumption_dir=request.consumption_dir,
            generation_dir=request.generation_dir,
            cups_config_path=request.cups_config_path,
            curated_dir=request.curated_dir,
            weather_dir=request.weather_dir or Path(".input/weather"),
        )

        # Stage 1: Aggregate generation files into canonical GenerationDataset (generation.csv + generation.xlsx)
        gen_dataset = curator.aggregate_generation(year=request.year, month=request.month)
        gen_csv_path, gen_excel_path = curator.export_generation(
            gen_dataset,
            curated_dir=request.curated_dir,
            delimiter=request.delimiter,
        )

        # Stage 2: Aggregate consumption files into canonical ConsumptionDataset (consumption.csv + consumption.xlsx)
        cups_configs = curator.load_cups_config()
        cons_dataset = curator.aggregate_consumption(
            cups_configs=cups_configs,
            year=request.year,
            month=request.month,
        )
        cons_csv_path, cons_excel_path = curator.export_consumption(
            cons_dataset,
            curated_dir=request.curated_dir,
            delimiter=request.delimiter,
        )

        # Stage 3: Build master ESD curated dataset from aggregated generation & consumption (esd.csv + esd.xlsx)
        dataset = curator.curate(
            year=request.year,
            month=request.month,
            generation_dataset=gen_dataset,
            consumption_dataset=cons_dataset,
        )
        csv_path = curator.export_csv(
            dataset,
            curated_dir=request.curated_dir,
            base_name=request.output_name,
            delimiter=request.delimiter,
        )
        excel_path = request.curated_dir / f"{request.output_name}.xlsx"

        return CurationResult(
            dataset=dataset,
            csv_path=csv_path,
            excel_path=excel_path,
            generation_dataset=gen_dataset,
            generation_csv_path=gen_csv_path,
            generation_excel_path=gen_excel_path,
            consumption_dataset=cons_dataset,
            consumption_csv_path=cons_csv_path,
            consumption_excel_path=cons_excel_path,
        )
