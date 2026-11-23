"""Application service for consumption-only community summaries and fair-share analytics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from src.analytics.aggregator import ConsumptionAggregator
from src.analytics.models import CommunityConsumptionSummary
from src.curation.curator import DataCurator
from src.domain.exceptions import EsdError, ValidationError
from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.schema import ValidationResult
from src.presentation.export import ReportExporter

VALID_SUMMARY_VIEWS: Final[tuple[str, ...]] = ("all", "annual", "monthly")


@dataclass(frozen=True)
class SummaryRequest:
    """Request DTO for generating consumption-only community fair-share summaries."""

    consumption_dir: Path
    output_dir: Path
    cups_config_path: Path | None = None
    year: int | None = None
    cups: str | None = None
    view: str = "all"
    lang: str = "en"
    export_markdown: bool = True


@dataclass(frozen=True)
class SummaryResult:
    """Result DTO returned by SummaryService."""

    summary: CommunityConsumptionSummary
    validation_results: list[ValidationResult]
    valid_file_count: int
    report_path: Path | None


class SummaryService:
    """Orchestrates DATADIS consumption ingestion, fair-share aggregation, and Markdown export."""

    @staticmethod
    def execute(request: SummaryRequest) -> SummaryResult:
        """Execute the consumption summary pipeline."""
        view_clean = request.view.lower().strip()
        if view_clean not in VALID_SUMMARY_VIEWS:
            raise ValidationError(
                f"Invalid view mode '{request.view}'. Expected one of: 'all', 'annual', 'monthly'."
            )

        cups_uses: dict[str, str] = {}
        if request.cups_config_path is not None and request.cups_config_path.is_file():
            try:
                cfg = DataCurator(cups_config_path=request.cups_config_path).load_cups_config()
                cups_uses = {cid: sp.use for cid, sp in cfg.items()}
            except Exception:
                cups_uses = {}

        loader = DatadisConsumptionLoader(request.consumption_dir)
        df, validation_results = loader.load_all_with_validation(year=request.year)

        if df.empty:
            msg = (
                f"No consumption records found for year {request.year}."
                if request.year is not None
                else "No consumption records found."
            )
            raise EsdError(msg)

        summary = ConsumptionAggregator.aggregate_community(df, cups_uses=cups_uses)

        target_cups: str | None = None
        if request.cups is not None and request.cups.strip():
            target_cups = request.cups.strip().upper()
            if target_cups not in summary.cups_list:
                raise ValidationError(
                    f"CUPS '{request.cups}' was not found in the loaded dataset. "
                    f"Available CUPS: {', '.join(summary.cups_list)}"
                )

        valid_file_count = sum(1 for v in validation_results if v.is_valid)

        report_path: Path | None = None
        if request.export_markdown:
            exporter = ReportExporter(output_dir=request.output_dir)
            report_path = exporter.export_consumption_summary_markdown(
                summary=summary,
                lang=request.lang,
                year_filter=request.year,
                cups_filter=target_cups,
                view_mode=view_clean,
            )

        return SummaryResult(
            summary=summary,
            validation_results=validation_results,
            valid_file_count=valid_file_count,
            report_path=report_path,
        )
