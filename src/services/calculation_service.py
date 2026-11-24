"""Application service for calculating optimal distribution coefficients and generating deliverables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import DEFAULT_WEATHER_DIR
from src.curation.curator import DataCurator, dataframe_to_aligned_dataset, read_curated_csv
from src.domain.models import BylawConstraints
from src.i18n import t
from src.ingestion.schema import IngestionSummary
from src.ingestion.weather import WeatherLoader, resolve_community_coordinates
from src.optimization.engine import DistributionOptimizer
from src.optimization.models import OptimizationResult, OptimizationStrategy
from src.presentation.export import ReportExporter
from src.presentation.story_data import build_story_context

if TYPE_CHECKING:
    import pandas as pd

    from src.services.curation_service import CurationResult


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
    include_baselines: bool = False
    refresh: bool = False
    curate_only: bool = False
    lang: str = "en"


@dataclass(frozen=True)
class CalculationResult:
    """Result DTO returned by CalculationService."""

    opt_result: OptimizationResult | None
    metadata: IngestionSummary
    curated_csv: Path
    exported_paths: list[Path]
    curation_result: CurationResult | None = None


class CalculationService:
    """Orchestrates curation verification, LP optimization, and artifact exports."""

    @staticmethod
    def _refresh_cached_weather(request: CalculationRequest) -> None:
        """Re-download any cached weather archive years when --refresh is requested."""
        if not request.weather_dir.exists():
            return
        cached_years = sorted(
            {
                int(path.name[:4])
                for path in request.weather_dir.glob("*_*_weather.csv")
                if len(path.name) >= 4 and path.name[:4].isdigit()
            }
        )
        if not cached_years:
            return
        coords = resolve_community_coordinates(
            cups_file=request.cups_config_path,
            allow_config_fallback=True,
            resolve_default_cups=(request.cups_config_path is None),
        )
        if not coords:
            return
        from src.services.weather_service import WeatherRequest, WeatherService

        for yr in cached_years:
            WeatherService.execute(
                WeatherRequest(
                    year=yr,
                    cups_file=request.cups_config_path,
                    weather_dir=request.weather_dir,
                    lang=request.lang,
                    resolve_cups=(request.cups_config_path is None),
                )
            )

    @staticmethod
    def execute(
        request: CalculationRequest,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> CalculationResult:
        """Run complete calculation pipeline and return results and exported artifacts."""
        if progress_callback:
            progress_callback(1, t("status_step_1", lang=request.lang))

        if request.refresh:
            CalculationService._refresh_cached_weather(request)

        if request.curate_only:
            from src.services.curation_service import CurationRequest, CurationService

            cur_res = CurationService.execute(
                CurationRequest(
                    consumption_dir=request.consumption_dir,
                    generation_dir=request.generation_dir,
                    curated_dir=request.curated_dir,
                    cups_config_path=request.cups_config_path,
                    weather_dir=request.weather_dir,
                )
            )
            ds = cur_res.dataset
            summary = IngestionSummary(
                cups_count=ds.summary.cups_count,
                cups_list=list(ds.cups_configs.keys())
                if ds.cups_configs
                else sorted({c.id for r in ds.records for c in r.cups}),
                consumption_files_loaded=0,
                generation_files_loaded=0,
                start_time=ds.summary.start_time,
                end_time=ds.summary.end_time,
                total_hours=ds.summary.total_hours,
                missing_hours_count=0,
            )
            exported = [
                p
                for p in (
                    cur_res.csv_path,
                    cur_res.excel_path,
                    cur_res.generation_csv_path,
                    cur_res.generation_excel_path,
                    cur_res.consumption_csv_path,
                    cur_res.consumption_excel_path,
                )
                if p is not None
            ]
            return CalculationResult(
                opt_result=None,
                metadata=summary,
                curated_csv=cur_res.csv_path,
                exported_paths=exported,
                curation_result=cur_res,
            )

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

        if request.refresh or not curated_csv.exists():
            curated_csv = curator.ensure_curated(force=True, export_excel=False)
        elif request.consumption_dir.exists() and request.generation_dir.exists():
            curated_csv = curator.ensure_curated(force=False, export_excel=False)

        if progress_callback:
            progress_callback(2, t("status_step_2", lang=request.lang))

        resolved_cups_path = curator._resolve_cups_path()
        if curator._last_curated_df is not None:
            last_ds = curator._last_curated_dataset
            primary = last_ds.summary.primary_cups if last_ds is not None else None
            if not primary and last_ds is not None and last_ds.cups_configs:
                primary = next((c.cups for c in last_ds.cups_configs.values() if c.primary), None)
            aligned = dataframe_to_aligned_dataset(
                curator._last_curated_df,
                primary_cups=primary,
                cups_config_path=resolved_cups_path,
            )
        else:
            aligned = curator.load_aligned_dataset(
                curated_csv,
                cups_config_path=resolved_cups_path,
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
            include_baselines=request.include_baselines,
            precision=request.precision,
            compute_hourly=request.compute_hourly,
            constraints=constraints,
        )

        if progress_callback:
            progress_callback(4, t("status_step_4", lang=request.lang))

        curated_base_dir = curated_csv.parent
        consumption_df: pd.DataFrame | None = curator._last_consumption_df
        if consumption_df is None:
            cons_csv = curated_base_dir / "consumption.csv"
            if cons_csv.is_file():
                try:
                    consumption_df = read_curated_csv(
                        cons_csv,
                        dtype={"cups_id": str, "timestamp": str},
                        dataset_label="consumption",
                    )
                except Exception:
                    consumption_df = None

        generation_df: pd.DataFrame | None = curator._last_generation_df
        if generation_df is None:
            gen_csv = curated_base_dir / "generation.csv"
            if gen_csv.is_file():
                try:
                    generation_df = read_curated_csv(
                        gen_csv,
                        dtype={"timestamp": str},
                        dataset_label="generation",
                    )
                except Exception:
                    generation_df = None

        analyzed_years: set[int] = {
            int(str(ts)[:4])
            for ts in aligned.data.index
            if len(str(ts)) >= 4 and str(ts)[:4].isdigit()
        }
        for ts_df in (consumption_df, generation_df):
            if ts_df is not None and not ts_df.empty and "timestamp" in ts_df.columns:
                for yr_str in ts_df["timestamp"].astype(str).str.strip().str.slice(0, 4).unique():
                    if len(yr_str) == 4 and yr_str.isdigit():
                        analyzed_years.add(int(yr_str))

        weather_df: pd.DataFrame | None = None
        if analyzed_years and request.weather_dir.exists():
            coords = curator.get_default_location(cups_cfg)
            lat_val = coords[0] if coords else None
            lon_val = coords[1] if coords else None
            weather_loader = WeatherLoader(request.weather_dir)
            weather_frames: list[pd.DataFrame] = []
            for yr in sorted(analyzed_years):
                try:
                    w_yr = weather_loader.load_year(year=yr, latitude=lat_val, longitude=lon_val)
                    if not w_yr.empty:
                        weather_frames.append(w_yr)
                except Exception:
                    continue
            if len(weather_frames) == 1:
                weather_df = weather_frames[0]
            elif len(weather_frames) > 1:
                import pandas as pd

                weather_df = pd.concat(weather_frames, ignore_index=True)

        story_context = build_story_context(
            opt_result=opt_result,
            ingestion_summary=aligned.metadata,
            cups_configs=cups_cfg or None,
            consumption_df=consumption_df,
            generation_df=generation_df,
            aligned_dataset=aligned,
            weather_df=weather_df,
        )

        exporter = ReportExporter(output_dir=request.output_dir)
        exported_paths = exporter.export_all(
            opt_result,
            aligned.metadata,
            formats="all",
            lang=request.lang,
            precision=request.precision,
            aligned_dataset=aligned,
            story_context=story_context,
        )

        return CalculationResult(
            opt_result=opt_result,
            metadata=aligned.metadata,
            curated_csv=curated_csv,
            exported_paths=exported_paths,
        )
