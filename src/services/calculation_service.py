"""Application service for calculating optimal distribution coefficients and generating deliverables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.config import DEFAULT_WEATHER_DIR
from src.curation.curator import DataCurator
from src.domain.models import BylawConstraints
from src.i18n import t
from src.ingestion.schema import IngestionSummary
from src.optimization.engine import DistributionOptimizer
from src.optimization.models import OptimizationResult, OptimizationStrategy
from src.presentation.export import ReportExporter


@dataclass(frozen=True)
class CalculationRequest:
    """Request DTO for running collective solar distribution optimization."""

    consumption_dir: Path
    generation_dir: Path
    curated_dir: Path
    output_dir: Path
    weather_dir: Path = DEFAULT_WEATHER_DIR
    cups_config_path: Path | None = None
    strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL
    precision: int = 0
    compute_hourly: bool = True
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
    def execute(
        request: CalculationRequest,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> CalculationResult:
        """Run complete calculation pipeline and return results and exported artifacts."""
        if progress_callback:
            progress_callback(1, t("status_step_1", lang=request.lang))

        curator = DataCurator(
            consumption_dir=request.consumption_dir,
            generation_dir=request.generation_dir,
            cups_config_path=request.cups_config_path,
            curated_dir=request.curated_dir,
            weather_dir=request.weather_dir,
        )

        curated_csv = (
            request.curated_dir / "esd.csv"
            if request.curated_dir.is_dir() or request.curated_dir.suffix.lower() != ".csv"
            else request.curated_dir
        )

        if not curated_csv.exists():
            curated_csv = curator.ensure_curated(force=True)
        elif request.consumption_dir.exists() and request.generation_dir.exists():
            curated_csv = curator.ensure_curated(force=False)

        if progress_callback:
            progress_callback(2, t("status_step_2", lang=request.lang))

        aligned = curator.load_aligned_dataset(
            curated_csv,
            cups_config_path=curator._resolve_cups_path(),
        )

        if progress_callback:
            progress_callback(3, t("status_step_3", lang=request.lang))

        # Resolve bylaw constraints from CUPS config (with 1% minimum floor)
        cups_cfg = curator.load_cups_config()
        cups_min: dict[str, float] = {
            c.cups: max(0.01, c.min_share)
            for c in cups_cfg.values()
            if getattr(c, "min_share", None) is not None
        }
        cups_max: dict[str, float] = {
            c.cups: c.max_share
            for c in cups_cfg.values()
            if getattr(c, "max_share", None) is not None
        }
        constraints = BylawConstraints(
            min_share=0.01,
            cups_min_shares=cups_min,
            cups_max_shares=cups_max,
        )
        if constraints.is_active:
            constraints.validate_feasibility(aligned.cups_list)

        opt_result = DistributionOptimizer.optimize_dataset(
            aligned,
            strategy=request.strategy,
            include_baselines=True,
            precision=request.precision,
            compute_hourly=request.compute_hourly,
            constraints=constraints,
        )

        if progress_callback:
            progress_callback(4, t("status_step_4", lang=request.lang))

        exporter = ReportExporter(output_dir=request.output_dir)
        exported_paths = exporter.export_all(
            opt_result,
            aligned.metadata,
            formats="all",
            lang=request.lang,
            precision=request.precision,
            aligned_dataset=aligned,
        )

        return CalculationResult(
            opt_result=opt_result,
            metadata=aligned.metadata,
            curated_csv=curated_csv,
            exported_paths=exported_paths,
        )
