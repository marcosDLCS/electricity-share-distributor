"""Application service for multi-year consumption comparison and SVG chart generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.analytics.aggregator import ConsumptionAggregator
from src.analytics.models import ComparisonSummary
from src.domain.exceptions import ValidationError
from src.ingestion.consumption import DatadisConsumptionLoader, load_cups_uses
from src.ingestion.schema import ValidationResult
from src.presentation.charts import generate_all_comparison_charts
from src.presentation.export import ReportExporter


def parse_years_option(years: list[str] | None) -> list[int] | None:
    """Parse repeatable (-y 2024 -y 2025) or comma-separated (--years 2024,2025) year flags."""
    if not years:
        return None

    parsed: list[int] = []
    for item in years:
        for part in item.split(","):
            clean = part.strip()
            if not clean:
                continue
            if not clean.isdigit():
                raise ValidationError(
                    f"Invalid year '{clean}'. Expected integer calendar year (e.g. 2025)."
                )
            parsed.append(int(clean))
    return parsed or None


@dataclass(frozen=True)
class ComparisonRequest:
    """Request DTO for running multi-year consumption comparison."""

    consumption_dir: Path
    output_dir: Path
    cups_config_path: Path | None = None
    years: list[int] | None = None
    generate_charts: bool = True
    lang: str = "en"
    export_markdown: bool = True
    export_html: bool = False


@dataclass(frozen=True)
class ComparisonResult:
    """Result DTO returned by ComparisonService."""

    comparison: ComparisonSummary
    validation_results: list[ValidationResult]
    valid_file_count: int
    chart_paths: list[Path]
    report_path: Path | None
    html_report_path: Path | None = None


class ComparisonService:
    """Orchestrates multi-year DATADIS ingestion, calendar-complete comparison, charts, and Markdown."""

    @staticmethod
    def execute(request: ComparisonRequest) -> ComparisonResult:
        """Execute the multi-year consumption comparison pipeline."""
        cups_uses = load_cups_uses(request.cups_config_path)

        loader = DatadisConsumptionLoader(request.consumption_dir)
        df, validation_results = loader.load_all_with_validation()

        comparison = ConsumptionAggregator.compare_years(
            df,
            target_years=request.years,
            cups_uses=cups_uses,
        )

        chart_paths: list[Path] = []
        if request.generate_charts:
            chart_paths = generate_all_comparison_charts(
                comparison=comparison,
                output_dir=request.output_dir,
                lang=request.lang,
            )

        report_path: Path | None = None
        html_report_path: Path | None = None
        if request.export_markdown or request.export_html:
            exporter = ReportExporter(output_dir=request.output_dir)
            if request.export_markdown:
                report_path = exporter.export_comparison_markdown(
                    comparison=comparison,
                    lang=request.lang,
                    chart_paths=chart_paths,
                )
            if request.export_html:
                html_report_path = exporter.export_comparison_html(
                    comparison=comparison,
                    lang=request.lang,
                )

        valid_file_count = sum(1 for v in validation_results if v.is_valid)
        return ComparisonResult(
            comparison=comparison,
            validation_results=validation_results,
            valid_file_count=valid_file_count,
            chart_paths=chart_paths,
            report_path=report_path,
            html_report_path=html_report_path,
        )
