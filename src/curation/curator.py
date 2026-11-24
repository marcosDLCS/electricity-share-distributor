"""Engine and logic for aggregating, curating, reconciling, and exporting time-series datasets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from src.config import (
    DEFAULT_CONSUMPTION_DIR,
    DEFAULT_CURATED_DIR,
    DEFAULT_GENERATION_DIR,
    DEFAULT_WEATHER_DIR,
    load_config,
    resolve_cups_config_path,
)
from src.curation.models import (
    ConsumptionDataset,
    CuratedCupsReading,
    CuratedDataset,
    CuratedHourRecord,
    CuratedSummary,
    CurationError,
    GenerationDataset,
    GenerationRecord,
)
from src.domain.exceptions import EsdError
from src.domain.models import SupplyPoint
from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import (
    DatadisConsumptionLoader,
    filter_consumption_by_cups,
    load_cups_config_file,
    resolve_effective_cups_path,
)
from src.ingestion.csv_utils import clean_numeric_series, sniff_csv_delimiter
from src.ingestion.generation import HuaweiGenerationLoader
from src.ingestion.schema import (
    AlignedDataset,
    AlignmentError,
    IngestionSummary,
)
from src.ingestion.weather import (
    OpenMeteoWeatherDownloader,
    WeatherLoader,
    resolve_community_coordinates,
)

MANIFEST_FILENAME: Final[str] = ".esd_manifest.json"
CURATED_SCHEMA_VERSION: Final[int] = 1


def read_curated_csv(
    path: Path,
    delimiter: str | None = None,
    dtype: dict[str, object] | None = None,
    dataset_label: str = "curated",
) -> pd.DataFrame:
    """Read a curated CSV file with delimiter/decimal sniffing and CurationError wrapping."""
    sep = delimiter or sniff_csv_delimiter(path, encoding="utf-8", default=",")
    decimal_char = "," if sep == ";" else "."
    try:
        return pd.read_csv(
            path,
            sep=sep,
            decimal=decimal_char,
            dtype=dtype,
        )
    except Exception as err:
        raise CurationError(f"Failed to read {dataset_label} CSV '{path}': {err}") from err


def dataframe_to_aligned_dataset(
    df: pd.DataFrame,
    year: int | None = None,
    month: int | None = None,
    primary_cups: str | None = None,
    cups_config_path: Path | str | None = None,
) -> AlignedDataset:
    """Convert a curated ESD DataFrame into an AlignedDataset for calculation.

    Args:
        df: Curated ESD DataFrame containing timestamp, cups_id, consumption, and generation.
        year: Optional calendar year filter.
        month: Optional calendar month filter (1-12).
        primary_cups: Optional pre-resolved primary CUPS identifier.
        cups_config_path: Optional path to cups.json configuration file.

    Returns:
        AlignedDataset with pivoted consumption and generation series.

    Raises:
        CurationError: If required columns are missing or DataFrame is empty.
        AlignmentError: If no data points match the year/month filter.
    """
    if df.empty:
        raise AlignmentError("Curated dataset is empty.")

    required_cols = {"timestamp", "generation", "cups_id", "consumption"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise CurationError(f"Curated dataset is missing required columns: {sorted(missing_cols)}")

    df_clean = df.copy()
    for num_col in (
        "consumption",
        "generation",
        "community_demand",
        "self_consumption",
        "exported_energy",
        "imported_energy",
    ):
        if num_col in df_clean.columns:
            df_clean[num_col] = clean_numeric_series(df_clean[num_col], fill_na=0.0)

    # Filter to CUPS present in cups.json if configured and non-empty
    cups_cfg: dict[str, SupplyPoint] = {}
    if cups_config_path is not None:
        try:
            cups_cfg = DataCurator(cups_config_path=cups_config_path).load_cups_config()
        except Exception:
            cups_cfg = {}

    if cups_cfg:
        all_cups_before = set(df_clean["cups_id"].astype(str).str.strip().unique())
        df_clean, _ = filter_consumption_by_cups(df_clean, cups_cfg, cups_col="cups_id")
        if df_clean.empty:
            raise AlignmentError("No curated data points match the CUPS present in cups.json.")
        if "community_demand" in df_clean.columns and all_cups_before != set(cups_cfg.keys()):
            df_clean["community_demand"] = df_clean.groupby("timestamp")["consumption"].transform(
                "sum"
            )

    # Apply year / month filters if specified
    if year is not None:
        prefix = f"{year:04d}"
        if month is not None:
            prefix = f"{year:04d}-{month:02d}"
        df_clean = df_clean[df_clean["timestamp"].str.startswith(prefix)]
        if df_clean.empty:
            raise AlignmentError(
                f"No aligned data points found for specified filter (year={year}, month={month})."
            )
    elif month is not None:
        m_str = f"-{month:02d}-"
        df_clean = df_clean[df_clean["timestamp"].str.contains(m_str)]
        if df_clean.empty:
            raise AlignmentError(f"No aligned data points found for month={month}.")

    # Pivot consumption: index=timestamp, columns=cups_id, values=consumption
    pivot_cons = df_clean.pivot(index="timestamp", columns="cups_id", values="consumption")
    cups_list = sorted(pivot_cons.columns.tolist())
    missing_count = int(pivot_cons.isna().sum().sum())
    pivot_cons = pivot_cons.fillna(0.0)

    # Combine temporal metrics into a single groupby pass and align with pivoted consumption
    agg_spec: dict[str, str] = {"generation": "first"}
    if "community_demand" in df_clean.columns:
        agg_spec["community_demand"] = "first"
    for add_col in ("self_consumption", "exported_energy", "imported_energy"):
        if add_col in df_clean.columns:
            agg_spec[add_col] = "sum"
    for weather_col in ("temperature", "cloud_cover"):
        if weather_col in df_clean.columns:
            agg_spec[weather_col] = "first"

    ts_meta = df_clean.groupby("timestamp", sort=False).agg(agg_spec).reindex(pivot_cons.index)

    aligned_df = pivot_cons.copy()
    aligned_df["generation_kwh"] = ts_meta["generation"]
    for col in (
        "community_demand",
        "self_consumption",
        "exported_energy",
        "imported_energy",
        "temperature",
        "cloud_cover",
    ):
        if col in ts_meta.columns:
            aligned_df[col] = ts_meta[col]
    aligned_df = aligned_df.sort_index()

    # Extract CUPS functional uses if available (vectorized deduplication preserving last value)
    cups_uses: dict[str, str] = {}
    if "use" in df_clean.columns:
        use_clean = df_clean["use"].astype("string").str.strip()
        valid_uses = df_clean.loc[
            df_clean["cups_id"].notna() & use_clean.notna() & (use_clean != ""),
            ["cups_id", "use"],
        ].drop_duplicates(subset=["cups_id"], keep="last")
        for cups, use_val in zip(valid_uses["cups_id"], valid_uses["use"], strict=False):
            cups_uses[str(cups)] = str(use_val).strip()
    for cid, c_point in cups_cfg.items():
        if cid in cups_list and c_point.use and cid not in cups_uses:
            cups_uses[cid] = c_point.use

    # Extract primary CUPS if available
    resolved_primary = primary_cups
    if not resolved_primary and "primary" in df_clean.columns:
        pri_vals = df_clean["primary"]
        pri_mask = (
            pri_vals
            if pd.api.types.is_bool_dtype(pri_vals)
            else pri_vals.astype(str).str.lower().isin(["true", "1"])
        )
        pri_rows = df_clean.loc[pri_mask, "cups_id"]
        if not pri_rows.empty:
            cand = str(pri_rows.iloc[0])
            if cand in cups_list:
                resolved_primary = cand

    if not resolved_primary and cups_cfg:
        cand = next((c.cups for c in cups_cfg.values() if c.primary), None)
        if cand and cand in cups_list:
            resolved_primary = cand

    # Summary metadata
    summary = IngestionSummary(
        cups_count=len(cups_list),
        cups_list=cups_list,
        consumption_files_loaded=len(cups_list),
        generation_files_loaded=1,
        start_time=str(aligned_df.index[0]),
        end_time=str(aligned_df.index[-1]),
        total_hours=len(aligned_df),
        missing_hours_count=missing_count,
    )

    # Monthly groups
    monthly_groups: dict[str, pd.DataFrame] = {}
    for ym, group in aligned_df.groupby(aligned_df.index.str.slice(0, 7)):
        monthly_groups[str(ym)] = group

    return AlignedDataset(
        data=aligned_df,
        cups_list=cups_list,
        metadata=summary,
        monthly_groups=monthly_groups,
        cups_uses=cups_uses,
        primary_cups=resolved_primary,
    )


def format_energy_value(val: float) -> float | int:
    """Format energy values into clean integer if exact whole number, else rounded float.

    Args:
        val: Energy reading in kWh.

    Returns:
        Exact integer if val is a whole number (e.g. 500), otherwise float rounded to 3 decimals.
    """
    rounded = round(float(val), 3)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


class DataCurator:
    """Coordinates multi-stage aggregation, CUPS metadata enrichment, primary meter reconciliation, and export."""

    def __init__(
        self,
        consumption_dir: Path | str = DEFAULT_CONSUMPTION_DIR,
        generation_dir: Path | str = DEFAULT_GENERATION_DIR,
        cups_config_path: Path | str | None = None,
        curated_dir: Path | str = DEFAULT_CURATED_DIR,
        weather_dir: Path | str = DEFAULT_WEATHER_DIR,
    ) -> None:
        self.consumption_dir = Path(consumption_dir)
        self.generation_dir = Path(generation_dir)
        self.cups_config_path = Path(cups_config_path) if cups_config_path else None
        self.curated_dir = Path(curated_dir)
        self.weather_dir = Path(weather_dir)
        self._last_curated_dataset: CuratedDataset | None = None
        self._last_curated_df: pd.DataFrame | None = None

    def _resolve_cups_path(self) -> Path | None:
        """Resolve cups.json path, isolating custom test directories from global workspace config."""
        return resolve_effective_cups_path(self.consumption_dir, self.cups_config_path)

    def load_cups_config(self) -> dict[str, SupplyPoint]:
        """Discover and parse CUPS configuration file containing uses, primary flags, and coordinates.

        Returns:
            Dictionary mapping CUPS string identifiers to SupplyPoint instances.
        """
        try:
            return load_cups_config_file(self._resolve_cups_path())
        except EsdError as err:
            raise CurationError(str(err)) from err

    def get_default_location(
        self,
        cups_configs: dict[str, SupplyPoint] | None = None,
    ) -> tuple[float, float] | None:
        """Resolve the default geographical location (latitude, longitude) for the community.

        Resolution order:
        1. Primary CUPS coordinates from cups.json.
        2. First available CUPS coordinates from cups.json.
        3. Coordinates extracted directly from cups_config_path file.
        4. Global persistent configuration coordinates (cfg.latitude, cfg.longitude).

        Returns:
            Tuple of (latitude, longitude) rounded to 4 decimals, or None if not configured.
        """
        configs = cups_configs if cups_configs is not None else self.load_cups_config()
        found_path = self._resolve_cups_path()
        app_cfg = load_config()
        default_cons_dirs = {
            DEFAULT_CONSUMPTION_DIR.resolve(),
            Path(app_cfg.consumption_dir).resolve(),
        }
        allow_cfg = (
            self.cups_config_path is None and self.consumption_dir.resolve() in default_cons_dirs
        )
        coords = resolve_community_coordinates(
            cups_configs=configs,
            cups_file=found_path,
            config=app_cfg,
            allow_config_fallback=allow_cfg,
            resolve_default_cups=False,
        )
        return coords[0] if coords else None

    @staticmethod
    def _filter_df_by_period(
        df: pd.DataFrame,
        year: int | None = None,
        month: int | None = None,
    ) -> pd.DataFrame:
        """Filter a DataFrame with a 'timestamp' column by optional calendar year and/or month."""
        if df.empty or (year is None and month is None):
            return df
        ts_col = df["timestamp"].astype(str)
        if year is not None:
            prefix = f"{year:04d}-{month:02d}" if month is not None else f"{year:04d}"
            return df[ts_col.str.startswith(prefix)].reset_index(drop=True)
        m_str = f"-{month:02d}-"
        return df[ts_col.str.contains(m_str)].reset_index(drop=True)

    def aggregate_generation(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> GenerationDataset:
        """Stage 1: Ingest raw solar inverter files and aggregate into canonical GenerationDataset.

        Args:
            year: Optional calendar year filter.
            month: Optional calendar month filter (1-12).

        Returns:
            GenerationDataset decoupled from vendor-specific column names.

        Raises:
            CurationError: If raw generation ingestion fails.
        """
        try:
            g_loader = HuaweiGenerationLoader(self.generation_dir)
            g_files_count = len(g_loader.discover_files())
            g_df = self._filter_df_by_period(g_loader.load_all(), year=year, month=month)
            return GenerationDataset.from_dataframe(g_df, source_files_count=g_files_count)
        except Exception as err:
            raise CurationError(f"Generation aggregation failed: {err}") from err

    @classmethod
    def export_generation(
        cls,
        dataset: GenerationDataset,
        curated_dir: Path | str,
        base_name: str = "generation",
        delimiter: str = ";",
        export_excel: bool = True,
    ) -> tuple[Path, Path]:
        """Export canonical GenerationDataset to CSV and optionally styled Excel (.xlsx) in curated_dir."""
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(
            output_dir=curated_dir,
            delimiter=delimiter,
            decimal_char="," if delimiter == ";" else ".",
        )
        gen_df = dataset.to_dataframe()
        csv_path = exporter.export_generation_dataset(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
            df=gen_df,
        )
        if export_excel:
            excel_path = exporter.export_generation_excel(
                dataset=dataset,
                curated_dir=curated_dir,
                base_name=base_name,
                df=gen_df,
            )
        else:
            excel_path = Path(curated_dir) / f"{base_name}.xlsx"
        return csv_path, excel_path

    @classmethod
    def load_generation_dataset(
        cls,
        generation_path: Path | str,
        delimiter: str | None = None,
    ) -> GenerationDataset:
        """Load canonical generation.csv from disk into a GenerationDataset instance."""
        path = Path(generation_path)
        if path.is_dir():
            path = path / "generation.csv"
        if not path.exists() or not path.is_file():
            raise CurationError(f"Aggregated generation file '{path}' does not exist.")

        df = read_curated_csv(
            path,
            delimiter=delimiter,
            dtype={"timestamp": str},
            dataset_label="generation",
        )

        return GenerationDataset.from_dataframe(df)

    def aggregate_consumption(
        self,
        cups_configs: dict[str, SupplyPoint] | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> ConsumptionDataset:
        """Stage 2: Ingest raw DSO/DATADIS files and aggregate into canonical ConsumptionDataset.

        Args:
            cups_configs: Optional pre-loaded SupplyPoint metadata mapping.
            year: Optional calendar year filter.
            month: Optional calendar month filter (1-12).

        Returns:
            ConsumptionDataset decoupled from source DSO column names.

        Raises:
            CurationError: If raw consumption ingestion fails.
        """
        configs = cups_configs if cups_configs is not None else self.load_cups_config()
        cups_uses = {cid: cfg.use for cid, cfg in configs.items()}
        try:
            c_loader = DatadisConsumptionLoader(self.consumption_dir)
            c_files_count = len(c_loader.discover_files())
            c_df = self._filter_df_by_period(c_loader.load_all(), year=year, month=month)
            if configs and not c_df.empty and "cups" in c_df.columns:
                c_df, _ = filter_consumption_by_cups(c_df, configs, cups_col="cups")
                if c_df.empty:
                    raise CurationError(
                        "No consumption records found matching the CUPS defined in cups.json."
                    )
            return ConsumptionDataset.from_dataframe(
                c_df,
                source_files_count=c_files_count,
                cups_uses=cups_uses,
            )
        except CurationError:
            raise
        except Exception as err:
            raise CurationError(f"Consumption aggregation failed: {err}") from err

    @classmethod
    def export_consumption(
        cls,
        dataset: ConsumptionDataset,
        curated_dir: Path | str,
        base_name: str = "consumption",
        delimiter: str = ";",
        export_excel: bool = True,
    ) -> tuple[Path, Path]:
        """Export canonical ConsumptionDataset to CSV and optionally styled Excel (.xlsx) in curated_dir."""
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(
            output_dir=curated_dir,
            delimiter=delimiter,
            decimal_char="," if delimiter == ";" else ".",
        )
        cons_df = dataset.to_dataframe()
        csv_path = exporter.export_consumption_dataset(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
            df=cons_df,
        )
        if export_excel:
            excel_path = exporter.export_consumption_excel(
                dataset=dataset,
                curated_dir=curated_dir,
                base_name=base_name,
                df=cons_df,
            )
        else:
            excel_path = Path(curated_dir) / f"{base_name}.xlsx"
        return csv_path, excel_path

    @classmethod
    def load_consumption_dataset(
        cls,
        consumption_path: Path | str,
        delimiter: str | None = None,
        cups_config_path: Path | str | None = None,
    ) -> ConsumptionDataset:
        """Load canonical consumption.csv from disk into a ConsumptionDataset instance."""
        path = Path(consumption_path)
        if path.is_dir():
            path = path / "consumption.csv"
        if not path.exists() or not path.is_file():
            raise CurationError(f"Aggregated consumption file '{path}' does not exist.")

        df = read_curated_csv(
            path,
            delimiter=delimiter,
            dtype={"cups_id": str, "timestamp": str},
            dataset_label="consumption",
        )

        cups_uses: dict[str, str] = {}
        try:
            cfg = (
                load_cups_config_file(resolve_effective_cups_path(Path.cwd(), cups_config_path))
                if cups_config_path is not None
                else {}
            )
            if cfg and not df.empty and "cups_id" in df.columns:
                df, _ = filter_consumption_by_cups(df, cfg, cups_col="cups_id")
            cups_uses = {cid: c.use for cid, c in cfg.items()}
        except Exception:
            pass

        return ConsumptionDataset.from_dataframe(df, cups_uses=cups_uses)

    def curate(
        self,
        year: int | None = None,
        month: int | None = None,
        generation_dataset: GenerationDataset | None = None,
        consumption_dataset: ConsumptionDataset | None = None,
    ) -> CuratedDataset:
        """Stage 3: Build master ESD CuratedDataset from aggregated GenerationDataset and ConsumptionDataset.

        Pipeline algorithm:
        1. Obtain canonical aggregated GenerationDataset and ConsumptionDataset.
        2. Align datasets on common hourly timestamps, respecting any year/month filters.
        3. For each participating CUPS:
           - Retrieve the human-readable 'use' from cups.json config.
           - If marked as 'primary' and the canonical generation dataset records an active plant
             consumption reading, reconcile by adopting the inverter consumption to correct
             fake-zero readings caused by direct behind-the-meter PV self-consumption.
           - Otherwise, use the canonical aggregated consumption reading.
        4. Calculate hourly community totals, solar surplus, and residual grid demand, and enrich
           with Open-Meteo hourly weather context (temperature, cloud_cover).
        5. Return structured CuratedDataset (master ESD dataset) with full metadata and summary metrics.

        Args:
            year: Optional calendar year filter.
            month: Optional calendar month filter (1-12).
            generation_dataset: Optional pre-aggregated canonical GenerationDataset.
            consumption_dataset: Optional pre-aggregated canonical ConsumptionDataset.

        Returns:
            CuratedDataset containing aligned hourly records and summary metrics.

        Raises:
            CurationError: If aggregation or alignment fails.
        """
        cups_configs = self.load_cups_config()

        try:
            gen_ds = (
                generation_dataset
                if generation_dataset is not None
                else self.aggregate_generation()
            )
            cons_ds = (
                consumption_dataset
                if consumption_dataset is not None
                else self.aggregate_consumption(cups_configs=cups_configs)
            )

            allowed_cups = set(cups_configs.keys()) if cups_configs else None
            filtered_records = (
                [r for r in cons_ds.records if str(r.cups_id).strip() in allowed_cups]
                if allowed_cups is not None
                else cons_ds.records
            )
            if allowed_cups is not None and not filtered_records:
                raise CurationError(
                    "No consumption records found matching the CUPS defined in cups.json."
                )

            c_df = pd.DataFrame(
                {
                    "cups": [r.cups_id for r in filtered_records],
                    "timestamp": [r.timestamp for r in filtered_records],
                    "consumption_kwh": [float(r.consumption) for r in filtered_records],
                },
                columns=["cups", "timestamp", "consumption_kwh"],
            )
            g_df = pd.DataFrame(
                {
                    "timestamp": [r.timestamp for r in gen_ds.records],
                    "generation_kwh": [float(r.generation) for r in gen_ds.records],
                },
                columns=["timestamp", "generation_kwh"],
            )

            aligner = TimeSeriesAligner(
                c_df,
                g_df,
                consumption_files_loaded=cons_ds.summary.source_files_count,
                generation_files_loaded=gen_ds.summary.source_files_count,
            )
            aligned = aligner.align(year=year, month=month)
        except CurationError:
            raise
        except Exception as err:
            raise CurationError(f"Curation pre-flight ingestion failed: {err}") from err

        primary_cups: str | None = next(
            (c.cups for c in cups_configs.values() if c.primary),
            None,
        )

        # Index canonical GenerationRecord by timestamp for O(1) lookup
        gen_record_map: dict[str, GenerationRecord] = {r.timestamp: r for r in gen_ds.records}

        # Determine all calendar years present in the aligned dataset
        years_present = sorted({int(str(ts)[:4]) for ts in aligned.data.index})

        # Resolve cups default location (latitude, longitude)
        default_coords = self.get_default_location(cups_configs)

        # Build hourly weather lookup mapping: timestamp_str -> (temperature, cloud_cover)
        weather_map: dict[str, tuple[float | None, int | None]] = {}
        weather_loader = WeatherLoader(self.weather_dir)
        weather_downloader = OpenMeteoWeatherDownloader(self.weather_dir)

        for yr in years_present:
            yr_df: pd.DataFrame | None = None
            lat = default_coords[0] if default_coords else None
            lon = default_coords[1] if default_coords else None

            # 1. Try loading existing weather data from disk
            try:
                yr_df = weather_loader.load_year(year=yr, latitude=lat, longitude=lon)
            except Exception:
                yr_df = None

            # 2. If weather data is not available, execute the weather fetch automatically
            if yr_df is None and default_coords is not None:
                try:
                    _, yr_df, _ = weather_downloader.download_year(
                        year=yr,
                        latitude=default_coords[0],
                        longitude=default_coords[1],
                    )
                except Exception:
                    yr_df = None

            # 3. Map hourly weather readings by standard timestamp string
            if yr_df is not None and not yr_df.empty:
                ts_series = pd.to_datetime(yr_df["timestamp"], errors="coerce").dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                for ts_fmt, temp, cloud in zip(
                    ts_series, yr_df["temperature"], yr_df["cloud_cover"], strict=False
                ):
                    if pd.isna(ts_fmt):
                        continue
                    temp_val = round(float(temp), 1) if pd.notna(temp) else None
                    cloud_val = round(float(cloud)) if pd.notna(cloud) else None
                    weather_map[str(ts_fmt)] = (temp_val, cloud_val)

        # Pre-sort CUPS metadata once so every hour emits CUPS in deterministic alphabetical (use, id) order
        cups_entries = [
            (cid, cups_configs.get(cid, SupplyPoint(cups=cid, use="", primary=False)))
            for cid in aligned.cups_list
        ]
        cups_entries.sort(
            key=lambda item: (str(item[1].use or "").strip().lower(), str(item[0]).lower())
        )
        sorted_cups = [cid for cid, _ in cups_entries]
        sorted_cfgs = [cfg for _, cfg in cups_entries]

        timestamps = aligned.data.index.astype(str).tolist()
        t_steps = len(timestamps)
        n_cups = len(sorted_cups)

        if t_steps == 0:
            summary = CuratedSummary(
                total_hours=0,
                reconciled_hours_count=0,
                recovered_kwh=0.0,
                total_generation_kwh=0.0,
                total_consumption_kwh=0.0,
                start_time="",
                end_time="",
                cups_count=len(aligned.cups_list),
                primary_cups=primary_cups,
                cups_reconciled_hours=dict.fromkeys(aligned.cups_list, 0),
                cups_total_consumption=dict.fromkeys(aligned.cups_list, 0.0),
            )
            return CuratedDataset(
                records=[],
                summary=summary,
                cups_configs=cups_configs,
            )

        gen_arr = aligned.data["generation_kwh"].to_numpy(dtype=float)
        hw_cons_list = [
            float(g_rec.consumption)
            if (g_rec := gen_record_map.get(ts_str)) is not None and g_rec.consumption is not None
            else float("nan")
            for ts_str in timestamps
        ]
        hw_sc_list = [
            max(0.0, float(g_rec.self_consumption))
            if (g_rec := gen_record_map.get(ts_str)) is not None
            else 0.0
            for ts_str in timestamps
        ]
        hw_exp_list = [
            max(0.0, float(g_rec.exported_energy))
            if (g_rec := gen_record_map.get(ts_str)) is not None
            else 0.0
            for ts_str in timestamps
        ]
        hw_imp_list = [
            max(0.0, float(g_rec.imported_energy))
            if (g_rec := gen_record_map.get(ts_str)) is not None
            else 0.0
            for ts_str in timestamps
        ]

        hw_cons_arr = np.array(hw_cons_list, dtype=float)
        hw_sc_arr = np.array(hw_sc_list, dtype=float)
        hw_exp_arr = np.array(hw_exp_list, dtype=float)
        hw_imp_arr = np.array(hw_imp_list, dtype=float)

        total_gen_kwh = float(np.sum(gen_arr))

        if n_cups > 0:
            datadis_mat = aligned.data[sorted_cups].to_numpy(dtype=float)
            is_primary_mask = np.array([cfg.primary for cfg in sorted_cfgs], dtype=bool)
            has_hw = (~np.isnan(hw_cons_arr))[:, np.newaxis]
            hw_cons_2d = np.where(has_hw, hw_cons_arr[:, np.newaxis], 0.0)
            use_hw = (
                is_primary_mask[np.newaxis, :]
                & has_hw
                & ((hw_cons_2d > 0.0) | (datadis_mat <= 0.0))
            )

            final_cons_mat = np.where(use_hw, hw_cons_2d, datadis_mat)
            diff_mat = final_cons_mat - datadis_mat
            reconciled_mat = use_hw & (diff_mat > 0.001)

            recovered_kwh = float(np.sum(np.where(reconciled_mat, diff_mat, 0.0)))
            reconciled_hours_count = int(np.sum(np.any(reconciled_mat, axis=1)))
            cups_reconciled_counts = {
                cid: int(cnt)
                for cid, cnt in zip(sorted_cups, np.sum(reconciled_mat, axis=0), strict=True)
            }
            cups_total_cons = {
                cid: float(tot)
                for cid, tot in zip(sorted_cups, np.sum(final_cons_mat, axis=0), strict=True)
            }
            hour_cons_sums = np.sum(final_cons_mat, axis=1)

            self_cons_mat = np.where(
                is_primary_mask[np.newaxis, :],
                np.maximum(
                    0.0,
                    np.minimum(
                        np.minimum(hw_sc_arr[:, np.newaxis], gen_arr[:, np.newaxis]),
                        final_cons_mat,
                    ),
                ),
                0.0,
            )
            exp_mat = np.where(is_primary_mask[np.newaxis, :], hw_exp_arr[:, np.newaxis], 0.0)
            imp_mat = np.where(is_primary_mask[np.newaxis, :], hw_imp_arr[:, np.newaxis], 0.0)

            cons_rows = final_cons_mat.tolist()
            rec_rows = reconciled_mat.tolist()
            sc_rows = self_cons_mat.tolist()
            exp_rows = exp_mat.tolist()
            imp_rows = imp_mat.tolist()
        else:
            recovered_kwh = 0.0
            reconciled_hours_count = 0
            cups_reconciled_counts = {}
            cups_total_cons = {}
            hour_cons_sums = np.zeros(t_steps, dtype=float)
            cons_rows = [[] for _ in range(t_steps)]
            rec_rows = [[] for _ in range(t_steps)]
            sc_rows = [[] for _ in range(t_steps)]
            exp_rows = [[] for _ in range(t_steps)]
            imp_rows = [[] for _ in range(t_steps)]

        total_cons_kwh = float(np.sum(hour_cons_sums))
        gen_rows = gen_arr.tolist()
        hour_sum_rows = hour_cons_sums.tolist()

        records: list[CuratedHourRecord] = []
        for idx, ts_str in enumerate(timestamps):
            cups_readings = [
                CuratedCupsReading(
                    id=sorted_cups[c_idx],
                    use=sorted_cfgs[c_idx].use,
                    consumption=format_energy_value(cons_rows[idx][c_idx]),
                    primary=sorted_cfgs[c_idx].primary,
                    reconciled=bool(rec_rows[idx][c_idx]),
                    self_consumption=format_energy_value(sc_rows[idx][c_idx]),
                    exported_energy=format_energy_value(exp_rows[idx][c_idx]),
                    imported_energy=format_energy_value(imp_rows[idx][c_idx]),
                )
                for c_idx in range(n_cups)
            ]

            w_reading = weather_map.get(ts_str)
            temp_val, cloud_val = w_reading if w_reading is not None else (None, None)

            records.append(
                CuratedHourRecord(
                    timestamp=ts_str,
                    generation=format_energy_value(gen_rows[idx]),
                    cups=cups_readings,
                    total_consumption=format_energy_value(hour_sum_rows[idx]),
                    temperature=temp_val,
                    cloud_cover=cloud_val,
                )
            )

        summary = CuratedSummary(
            total_hours=len(records),
            reconciled_hours_count=reconciled_hours_count,
            recovered_kwh=round(recovered_kwh, 2),
            total_generation_kwh=round(total_gen_kwh, 2),
            total_consumption_kwh=round(total_cons_kwh, 2),
            start_time=records[0].timestamp if records else "",
            end_time=records[-1].timestamp if records else "",
            cups_count=len(aligned.cups_list),
            primary_cups=primary_cups,
            cups_reconciled_hours=cups_reconciled_counts,
            cups_total_consumption={c: round(v, 2) for c, v in cups_total_cons.items()},
        )

        return CuratedDataset(
            records=records,
            summary=summary,
            cups_configs=cups_configs,
        )

    @classmethod
    def export_excel(
        cls,
        dataset: CuratedDataset,
        curated_dir: Path | str,
        base_name: str = "esd",
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export master ESD curated dataset to a styled Excel (.xlsx) file.

        Args:
            dataset: The CuratedDataset to export.
            curated_dir: Directory where the Excel file should be written.
            base_name: File basename without extension (defaults to 'esd').
            df: Optional pre-built DataFrame to avoid recomputing to_dataframe().

        Returns:
            Path to the generated Excel file.
        """
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(output_dir=curated_dir)
        return exporter.export_curated_excel(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
            df=df,
        )

    @classmethod
    def export_csv(
        cls,
        dataset: CuratedDataset,
        curated_dir: Path | str,
        base_name: str = "esd",
        delimiter: str = ";",
        export_excel: bool = True,
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export master ESD curated dataset to a clean CSV file and optional sibling styled Excel (.xlsx) file.

        Args:
            dataset: The CuratedDataset to export.
            curated_dir: Directory where the CSV and Excel files should be written.
            base_name: File basename without extension (defaults to 'esd').
            delimiter: CSV delimiter character (defaults to ';').
            export_excel: Whether to also generate the sibling styled Excel workbook.
            df: Optional pre-built DataFrame to avoid recomputing to_dataframe().

        Returns:
            Path to the generated CSV file.
        """
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(
            output_dir=curated_dir,
            delimiter=delimiter,
            decimal_char="," if delimiter == ";" else ".",
        )
        curated_df = df if df is not None else dataset.to_dataframe()
        csv_file = exporter.export_curated_dataset(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
            df=curated_df,
        )
        if export_excel:
            cls.export_excel(
                dataset=dataset,
                curated_dir=curated_dir,
                base_name=base_name,
                df=curated_df,
            )
        return csv_file

    @staticmethod
    def _stat_directory_files(
        base_dir: Path,
        extensions: tuple[str, ...],
        recursive: bool,
    ) -> list[list[str | int]]:
        """Collect lightweight [relpath, size, mtime_ns] entries for O(1) cache validation."""
        if not base_dir.exists() or not base_dir.is_dir():
            return []
        iterator = base_dir.rglob("*") if recursive else base_dir.iterdir()
        entries: list[list[str | int]] = []
        for f in iterator:
            if (
                not f.is_file()
                or f.suffix.lower() not in extensions
                or f.name.startswith(".")
                or f.name.startswith("~$")
            ):
                continue
            st = f.stat()
            rel = str(f.relative_to(base_dir)) if recursive else f.name
            entries.append([rel, int(st.st_size), int(st.st_mtime_ns)])
        entries.sort(key=lambda item: str(item[0]))
        return entries

    def _build_manifest(
        self,
        base_name: str,
        delimiter: str,
        has_excel: bool,
        cups_configs: dict[str, SupplyPoint],
    ) -> dict[str, object]:
        """Build lightweight input/config fingerprint for O(1) curated cache validation."""
        resolved_cups = self._resolve_cups_path()
        cups_entry: dict[str, str] | None = None
        if resolved_cups is not None and resolved_cups.is_file():
            cups_entry = {
                "path": str(resolved_cups.resolve()),
                "sha256": hashlib.sha256(resolved_cups.read_bytes()).hexdigest(),
            }
        default_loc = self.get_default_location(cups_configs)
        return {
            "schema_version": CURATED_SCHEMA_VERSION,
            "base_name": base_name,
            "delimiter": delimiter,
            "has_excel": has_excel,
            "cups_config": cups_entry,
            "default_location": list(default_loc) if default_loc is not None else None,
            "consumption_files": self._stat_directory_files(
                self.consumption_dir, (".csv",), recursive=True
            ),
            "generation_files": self._stat_directory_files(
                self.generation_dir, (".xlsx", ".xls"), recursive=False
            ),
            "weather_files": self._stat_directory_files(
                self.weather_dir, (".csv",), recursive=False
            ),
        }

    @staticmethod
    def _is_manifest_valid(
        stored: dict[str, object],
        expected: dict[str, object],
        export_excel: bool,
    ) -> bool:
        """Return True iff stored manifest fingerprint matches current workspace inputs/settings."""
        if export_excel and not bool(stored.get("has_excel")):
            return False
        for key in (
            "schema_version",
            "base_name",
            "delimiter",
            "cups_config",
            "default_location",
            "consumption_files",
            "generation_files",
            "weather_files",
        ):
            if stored.get(key) != expected.get(key):
                return False
        return True

    def ensure_curated(
        self,
        force: bool = False,
        base_name: str = "esd",
        delimiter: str = ";",
        export_excel: bool = True,
    ) -> Path:
        """Ensure aggregated generation, consumption, and master ESD CSV (and optional Excel) files exist.

        Executes the full 3-stage pipeline if missing, stale, or forced:
        1. Aggregate generation -> generation.csv (+ generation.xlsx if export_excel)
        2. Aggregate consumption -> consumption.csv (+ consumption.xlsx if export_excel)
        3. Curate master ESD dataset -> esd.csv (+ esd.xlsx if export_excel)

        Args:
            force: If True, re-runs full aggregation and curation even if files already exist.
            base_name: Base filename for master dataset (defaults to 'esd').
            delimiter: CSV separator (defaults to ';').
            export_excel: Whether to generate sibling styled .xlsx files (defaults to True).

        Returns:
            Path to the verified master ESD CSV file.
        """
        self._last_curated_dataset = None
        self._last_curated_df = None

        target_dir = self.curated_dir
        if target_dir.is_file():
            target_dir = target_dir.parent

        target_dir.mkdir(parents=True, exist_ok=True)
        csv_path = target_dir / f"{base_name}.csv"
        xlsx_path = target_dir / f"{base_name}.xlsx"
        gen_csv = target_dir / "generation.csv"
        gen_xlsx = target_dir / "generation.xlsx"
        cons_csv = target_dir / "consumption.csv"
        cons_xlsx = target_dir / "consumption.xlsx"
        manifest_path = target_dir / MANIFEST_FILENAME

        cups_configs = self.load_cups_config()

        excel_ok = not export_excel or (
            xlsx_path.exists()
            and xlsx_path.stat().st_size > 0
            and gen_xlsx.exists()
            and cons_xlsx.exists()
        )
        outputs_present = (
            not force
            and csv_path.exists()
            and csv_path.stat().st_size > 0
            and gen_csv.exists()
            and cons_csv.exists()
            and excel_ok
        )
        if outputs_present and manifest_path.is_file():
            try:
                stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                expected_manifest = self._build_manifest(
                    base_name=base_name,
                    delimiter=delimiter,
                    has_excel=export_excel,
                    cups_configs=cups_configs,
                )
                if isinstance(stored_manifest, dict) and self._is_manifest_valid(
                    stored_manifest,
                    expected_manifest,
                    export_excel=export_excel,
                ):
                    return csv_path
            except Exception:
                pass
        elif outputs_present:
            try:
                with csv_path.open("r", encoding="utf-8") as fh:
                    first_line = fh.readline().rstrip("\r\n")
                sep = (
                    delimiter
                    if delimiter in first_line
                    else sniff_csv_delimiter(csv_path, encoding="utf-8", default=",")
                )
                cols = [c.strip() for c in first_line.split(sep)]
                if (
                    "community_demand" in cols
                    and "year" in cols
                    and "temperature" in cols
                    and "cloud_cover" in cols
                    and "self_consumption" in cols
                    and "hourly_self_consumption" not in cols
                    and "exported_energy" in cols
                    and "imported_energy" in cols
                    and "primary" not in cols
                    and "reconciled" not in cols
                ):
                    df_existing = pd.read_csv(
                        csv_path,
                        sep=sep,
                        usecols=["cups_id", "year", "temperature"],
                        dtype={"cups_id": str, "year": int, "temperature": str},
                    )
                    cups_match = True
                    if cups_configs:
                        existing_cups = set(df_existing["cups_id"].astype(str).str.strip().unique())
                        cups_match = existing_cups == set(cups_configs.keys())

                    weather_ok = True
                    default_coords = self.get_default_location(cups_configs)
                    if default_coords is not None and not df_existing.empty:
                        years_in_csv = sorted(df_existing["year"].dropna().unique().tolist())
                        w_loader = WeatherLoader(self.weather_dir)
                        for yr in years_in_csv:
                            try:
                                w_loader.load_year(
                                    year=int(yr),
                                    latitude=default_coords[0],
                                    longitude=default_coords[1],
                                )
                            except Exception:
                                weather_ok = False
                                break
                        if weather_ok:
                            temp_clean = df_existing["temperature"].dropna().astype(str).str.strip()
                            temp_clean = temp_clean[
                                (temp_clean != "") & (temp_clean.str.lower() != "nan")
                            ]
                            if temp_clean.empty:
                                weather_ok = False

                    if cups_match and weather_ok:
                        return csv_path
            except Exception:
                pass

        gen_dataset = self.aggregate_generation()
        self.export_generation(
            gen_dataset,
            curated_dir=target_dir,
            delimiter=delimiter,
            export_excel=export_excel,
        )

        cons_dataset = self.aggregate_consumption(cups_configs=cups_configs)
        self.export_consumption(
            cons_dataset,
            curated_dir=target_dir,
            delimiter=delimiter,
            export_excel=export_excel,
        )

        dataset = self.curate(
            generation_dataset=gen_dataset,
            consumption_dataset=cons_dataset,
        )
        curated_df = dataset.to_dataframe()
        self._last_curated_dataset = dataset
        self._last_curated_df = curated_df
        out_csv = self.export_csv(
            dataset,
            curated_dir=target_dir,
            base_name=base_name,
            delimiter=delimiter,
            export_excel=export_excel,
            df=curated_df,
        )
        try:
            fresh_manifest = self._build_manifest(
                base_name=base_name,
                delimiter=delimiter,
                has_excel=export_excel,
                cups_configs=cups_configs,
            )
            manifest_path.write_text(json.dumps(fresh_manifest, indent=2), encoding="utf-8")
        except Exception:
            pass
        return out_csv

    @classmethod
    def load_aligned_dataset(
        cls,
        curated_path: Path | str,
        year: int | None = None,
        month: int | None = None,
        delimiter: str | None = None,
        cups_config_path: Path | str | None = None,
    ) -> AlignedDataset:
        """Load master ESD curated CSV file and reconstruct an AlignedDataset for calculation.

        Args:
            curated_path: Path to esd.csv file or directory containing it.
            year: Optional calendar year filter.
            month: Optional calendar month filter (1-12).
            delimiter: Optional CSV delimiter character. If None, auto-detected.

        Returns:
            AlignedDataset ready for optimization and evaluation.

        Raises:
            CurationError: If the file does not exist or schema is invalid.
            AlignmentError: If no rows match the specified filters.
        """
        path = Path(curated_path)
        if path.is_dir():
            esd_candidate = path / "esd.csv"
            if esd_candidate.exists():
                path = esd_candidate
            else:
                csvs = [
                    f
                    for f in sorted(path.glob("*.csv"))
                    if f.name not in ("generation.csv", "consumption.csv")
                ]
                if not csvs:
                    raise CurationError(f"No curated ESD CSV files found in directory '{path}'.")
                path = csvs[0]

        if not path.exists() or not path.is_file():
            raise CurationError(f"Curated file '{path}' does not exist.")

        df = read_curated_csv(
            path,
            delimiter=delimiter,
            dtype={"cups_id": str, "timestamp": str},
            dataset_label="curated",
        )

        effective_cups_path: Path | str | None = cups_config_path
        if effective_cups_path is None:
            app_cfg = load_config()
            default_curated_dirs = {
                DEFAULT_CURATED_DIR.resolve(),
                Path(app_cfg.curated_dir).resolve(),
            }
            if path.parent.resolve() in default_curated_dirs:
                effective_cups_path = resolve_cups_config_path(config=app_cfg)
            else:
                parent = path.parent.resolve()
                for candidate in (
                    parent / "cups.json",
                    parent.parent / "cups" / "cups.json",
                    parent.parent / "cups.json",
                ):
                    if candidate.exists() and candidate.is_file():
                        effective_cups_path = candidate
                        break

        return dataframe_to_aligned_dataset(
            df,
            year=year,
            month=month,
            cups_config_path=effective_cups_path,
        )
