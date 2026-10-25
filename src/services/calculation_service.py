"""Application service for calculating optimal distribution coefficients and generating deliverables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.curation.curator import DataCurator
from src.ingestion.schema import IngestionSummary
from src.optimization.engine import DistributionOptimizer
from src.optimization.models import OptimizationResult, OptimizationStrategy
from src.presentation.export import export_all


@dataclass(frozen=True)
class CalculationRequest:
    """Request DTO for running collective solar distribution optimization."""

    consumption_dir: Path
    generation_dir: Path
    curated_dir: Path
    output_dir: Path
    cups_config_path: Path | None = None
    force_curate: bool = False
    is_custom_input: bool = False
    is_custom_curated: bool = False
    year: int | None = None
    month: int | None = None
    strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL
    precision: int = 0
    compute_hourly: bool = False
    export_format: str = "all"
    lang: str = "en"


@dataclass(frozen=True)
class CalculationResult:
    """Result DTO returned by CalculationService."""

    opt_result: OptimizationResult
    metadata: IngestionSummary
    curated_csv: Path
    exported_paths: list[Path]


class CalculationService:
    """Orchestrates curation verification, LP optimization, and artifact exports."""

    @staticmethod
    def execute(request: CalculationRequest) -> CalculationResult:
        """Run complete calculation pipeline and return results and exported artifacts."""
        curator = DataCurator(
            consumption_dir=request.consumption_dir,
            generation_dir=request.generation_dir,
            cups_config_path=request.cups_config_path,
            curated_dir=request.curated_dir,
        )

        curated_csv = (
            request.curated_dir / "curated.csv"
            if request.curated_dir.is_dir()
            else request.curated_dir
        )
        needs_curation = (
            request.force_curate
            or not curated_csv.exists()
            or (request.is_custom_input and not request.is_custom_curated)
        )

        if needs_curation:
            curated_csv = curator.ensure_curated(force=True)

        aligned = curator.load_aligned_dataset(
            curated_csv,
            year=request.year,
            month=request.month,
        )

        opt_result = DistributionOptimizer.optimize_dataset(
            aligned,
            strategy=request.strategy,
            include_baselines=True,
            precision=request.precision,
            compute_hourly=request.compute_hourly,
        )

        exported_paths: list[Path] = []
        fmt_clean = request.export_format.lower().strip()
        if fmt_clean not in ("table", "none"):
            exported_paths = export_all(
                opt_result,
                aligned.metadata,
                output_dir=request.output_dir,
                formats=fmt_clean,
                lang=request.lang,
                precision=request.precision,
            )

        return CalculationResult(
            opt_result=opt_result,
            metadata=aligned.metadata,
            curated_csv=curated_csv,
            exported_paths=exported_paths,
        )
