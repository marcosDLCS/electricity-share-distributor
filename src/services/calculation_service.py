"""Application service for calculating optimal distribution coefficients and generating deliverables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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
    min_share: float | None = None
    max_share: float | None = None


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

        if progress_callback:
            progress_callback(2, t("status_step_2", lang=request.lang))

        aligned = curator.load_aligned_dataset(
            curated_csv,
            year=request.year,
            month=request.month,
        )

        if progress_callback:
            progress_callback(3, t("status_step_3", lang=request.lang))

        # Resolve bylaw constraints from request parameters and CUPS config
        cups_cfg = curator.load_cups_config()
        cups_min: dict[str, float] = {
            c.cups: c.min_share
            for c in cups_cfg.values()
            if getattr(c, "min_share", None) is not None
        }
        cups_max: dict[str, float] = {
            c.cups: c.max_share
            for c in cups_cfg.values()
            if getattr(c, "max_share", None) is not None
        }
        constraints = BylawConstraints(
            min_share=request.min_share,
            max_share=request.max_share,
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

        exported_paths: list[Path] = []
        fmt_clean = request.export_format.lower().strip()
        if fmt_clean not in ("table", "none"):
            exporter = ReportExporter(output_dir=request.output_dir)
            exported_paths = exporter.export_all(
                opt_result,
                aligned.metadata,
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
