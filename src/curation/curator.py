"""Engine and logic for aggregating, curating, reconciling, and exporting time-series datasets."""

from __future__ import annotations

import json
from pathlib import Path

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
from src.domain.models import SupplyPoint, parse_share_fraction
from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader
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
    parse_coordinate_pair,
    resolve_community_coordinates,
)


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
        allowed_cups = set(cups_cfg.keys())
        all_cups_before = set(df_clean["cups_id"].astype(str).str.strip().unique())
        df_clean = df_clean[df_clean["cups_id"].astype(str).str.strip().isin(allowed_cups)].copy()
        if df_clean.empty:
            raise AlignmentError("No curated data points match the CUPS present in cups.json.")
        if "community_demand" in df_clean.columns and all_cups_before != allowed_cups:
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

    # Extract generation series
    gen_series = df_clean.groupby("timestamp")["generation"].first()

    # Combine into aligned DataFrame
    aligned_df = pivot_cons.copy()
    aligned_df["generation_kwh"] = gen_series.loc[aligned_df.index]
    if "community_demand" in df_clean.columns:
        aligned_df["community_demand"] = (
            df_clean.groupby("timestamp")["community_demand"].first().loc[aligned_df.index]
        )
    for add_col in (
        "self_consumption",
        "exported_energy",
        "imported_energy",
    ):
        if add_col in df_clean.columns:
            aligned_df[add_col] = df_clean.groupby("timestamp")[add_col].sum().loc[aligned_df.index]
    if "temperature" in df_clean.columns:
        aligned_df["temperature"] = (
            df_clean.groupby("timestamp")["temperature"].first().loc[aligned_df.index]
        )
    if "cloud_cover" in df_clean.columns:
        aligned_df["cloud_cover"] = (
            df_clean.groupby("timestamp")["cloud_cover"].first().loc[aligned_df.index]
        )
    aligned_df = aligned_df.sort_index()

    # Extract CUPS functional uses if available
    cups_uses: dict[str, str] = {}
    if "use" in df_clean.columns:
        for cups, use_val in zip(df_clean["cups_id"], df_clean["use"], strict=False):
            if cups and pd.notna(use_val) and str(use_val).strip():
                cups_uses[str(cups)] = str(use_val).strip()
    for cid, c_point in cups_cfg.items():
        if cid in cups_list and c_point.use and cid not in cups_uses:
            cups_uses[cid] = c_point.use

    # Extract primary CUPS if available
    resolved_primary = primary_cups
    if not resolved_primary and "primary" in df_clean.columns:
        pri_mask = df_clean["primary"].astype(str).str.lower().isin(["true", "1"])
        pri_rows = df_clean[pri_mask]
        if not pri_rows.empty:
            cand = str(pri_rows["cups_id"].iloc[0])
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

    def _resolve_cups_path(self) -> Path | None:
        """Resolve cups.json path, isolating custom test directories from global workspace config."""
        if self.cups_config_path is not None:
            return resolve_cups_config_path(custom_path=self.cups_config_path)

        app_cfg = load_config()
        default_cons_dirs = {
            DEFAULT_CONSUMPTION_DIR.resolve(),
            Path(app_cfg.consumption_dir).resolve(),
        }
        if self.consumption_dir.resolve() in default_cons_dirs:
            return resolve_cups_config_path(config=app_cfg)

        # Custom consumption_dir without explicit cups_config_path: look relative to custom dir
        parent = self.consumption_dir.resolve().parent
        for candidate in (
            parent / "cups" / "cups.json",
            parent / "cups.json",
            self.consumption_dir.resolve() / "cups.json",
        ):
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def load_cups_config(self) -> dict[str, SupplyPoint]:
        """Discover and parse CUPS configuration file containing uses, primary flags, and coordinates.

        Returns:
            Dictionary mapping CUPS string identifiers to SupplyPoint instances.
        """
        found_path = self._resolve_cups_path()
        if not found_path:
            return {}

        try:
            raw_text = found_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except Exception as err:
            raise CurationError(
                f"Failed to parse CUPS configuration file '{found_path}': {err}"
            ) from err

        if not isinstance(data, list):
            raise CurationError(
                f"Invalid format in CUPS config file '{found_path}': expected JSON array of objects."
            )

        configs: dict[str, SupplyPoint] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            cups_id = str(item.get("cups") or item.get("id") or "").strip()
            if not cups_id:
                continue
            use = str(item.get("use") or "").strip()
            primary = bool(item.get("primary", False))

            coord_pair = parse_coordinate_pair(item)
            lat_val = coord_pair[0] if coord_pair else None
            lon_val = coord_pair[1] if coord_pair else None

            min_val: float | None = None
            max_val: float | None = None
            raw_min = item.get("min_share") or item.get("min") or item.get("cuota_minima")
            raw_max = item.get("max_share") or item.get("max") or item.get("cuota_maxima")
            if raw_min is not None:
                try:
                    min_val = parse_share_fraction(raw_min)
                except (ValueError, TypeError) as err:
                    raise CurationError(
                        f"Invalid min_share '{raw_min}' for CUPS '{cups_id}': {err}"
                    ) from err
            if raw_max is not None:
                try:
                    max_val = parse_share_fraction(raw_max)
                except (ValueError, TypeError) as err:
                    raise CurationError(
                        f"Invalid max_share '{raw_max}' for CUPS '{cups_id}': {err}"
                    ) from err

            try:
                configs[cups_id] = SupplyPoint(
                    cups=cups_id,
                    use=use,
                    primary=primary,
                    latitude=lat_val,
                    longitude=lon_val,
                    min_share=min_val,
                    max_share=max_val,
                )
            except EsdError as err:
                raise CurationError(f"Invalid CUPS configuration for '{cups_id}': {err}") from err

        return configs

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
    ) -> tuple[Path, Path]:
        """Export canonical GenerationDataset to CSV and styled Excel (.xlsx) in curated_dir."""
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(
            output_dir=curated_dir,
            delimiter=delimiter,
            decimal_char="," if delimiter == ";" else ".",
        )
        csv_path = exporter.export_generation_dataset(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
        )
        excel_path = exporter.export_generation_excel(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
        )
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
                allowed_cups = set(configs.keys())
                c_df = c_df[c_df["cups"].astype(str).str.strip().isin(allowed_cups)].reset_index(
                    drop=True
                )
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
    ) -> tuple[Path, Path]:
        """Export canonical ConsumptionDataset to CSV and styled Excel (.xlsx) in curated_dir."""
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(
            output_dir=curated_dir,
            delimiter=delimiter,
            decimal_char="," if delimiter == ";" else ".",
        )
        csv_path = exporter.export_consumption_dataset(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
        )
        excel_path = exporter.export_consumption_excel(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
        )
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
                cls(cups_config_path=cups_config_path).load_cups_config()
                if cups_config_path is not None
                else {}
            )
            if cfg and not df.empty and "cups_id" in df.columns:
                df = df[df["cups_id"].astype(str).str.strip().isin(cfg.keys())].reset_index(
                    drop=True
                )
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
                [
                    {
                        "cups": r.cups_id,
                        "timestamp": r.timestamp,
                        "consumption_kwh": float(r.consumption),
                    }
                    for r in filtered_records
                ],
                columns=["cups", "timestamp", "consumption_kwh"],
            )
            g_df = pd.DataFrame(
                [
                    {
                        "timestamp": r.timestamp,
                        "generation_kwh": float(r.generation),
                    }
                    for r in gen_ds.records
                ],
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
    ) -> Path:
        """Export master ESD curated dataset to a styled Excel (.xlsx) file.

        Args:
            dataset: The CuratedDataset to export.
            curated_dir: Directory where the Excel file should be written.
            base_name: File basename without extension (defaults to 'esd').

        Returns:
            Path to the generated Excel file.
        """
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(output_dir=curated_dir)
        return exporter.export_curated_excel(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
        )

    @classmethod
    def export_csv(
        cls,
        dataset: CuratedDataset,
        curated_dir: Path | str,
        base_name: str = "esd",
        delimiter: str = ";",
    ) -> Path:
        """Export master ESD curated dataset to a clean CSV file and sibling styled Excel (.xlsx) file.

        Args:
            dataset: The CuratedDataset to export.
            curated_dir: Directory where the CSV and Excel files should be written.
            base_name: File basename without extension (defaults to 'esd').
            delimiter: CSV delimiter character (defaults to ';').

        Returns:
            Path to the generated CSV file.
        """
        from src.presentation.export import ReportExporter

        exporter = ReportExporter(
            output_dir=curated_dir,
            delimiter=delimiter,
            decimal_char="," if delimiter == ";" else ".",
        )
        csv_file = exporter.export_curated_dataset(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
        )
        cls.export_excel(
            dataset=dataset,
            curated_dir=curated_dir,
            base_name=base_name,
        )
        return csv_file

    def ensure_curated(
        self,
        force: bool = False,
        base_name: str = "esd",
        delimiter: str = ";",
    ) -> Path:
        """Ensure aggregated generation, consumption, and master ESD CSV/Excel files exist.

        Executes the full 3-stage pipeline if missing or forced:
        1. Aggregate generation -> generation.csv + generation.xlsx
        2. Aggregate consumption -> consumption.csv + consumption.xlsx
        3. Curate master ESD dataset -> esd.csv + esd.xlsx

        Args:
            force: If True, re-runs full aggregation and curation even if files already exist.
            base_name: Base filename for master dataset (defaults to 'esd').
            delimiter: CSV separator (defaults to ';').

        Returns:
            Path to the verified master ESD CSV file.
        """
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

        cups_configs = self.load_cups_config()

        if (
            not force
            and csv_path.exists()
            and csv_path.stat().st_size > 0
            and xlsx_path.exists()
            and xlsx_path.stat().st_size > 0
            and gen_csv.exists()
            and gen_xlsx.exists()
            and cons_csv.exists()
            and cons_xlsx.exists()
        ):
            try:
                first_line = csv_path.read_text(encoding="utf-8").splitlines()[0]
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
        self.export_generation(gen_dataset, curated_dir=target_dir, delimiter=delimiter)

        cons_dataset = self.aggregate_consumption(cups_configs=cups_configs)
        self.export_consumption(cons_dataset, curated_dir=target_dir, delimiter=delimiter)

        dataset = self.curate(
            generation_dataset=gen_dataset,
            consumption_dataset=cons_dataset,
        )
        return self.export_csv(
            dataset,
            curated_dir=target_dir,
            base_name=base_name,
            delimiter=delimiter,
        )

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
