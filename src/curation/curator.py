"""Engine and logic for curating, reconciling, and exporting time-series datasets."""

from __future__ import annotations

import json
from pathlib import Path

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
    CuratedCupsReading,
    CuratedDataset,
    CuratedHourRecord,
    CuratedSummary,
    CurationError,
)
from src.domain.exceptions import EsdError
from src.domain.models import SupplyPoint, parse_share_fraction
from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.generation import HuaweiGenerationLoader
from src.ingestion.schema import (
    AlignedDataset,
    AlignmentError,
    IngestionSummary,
)
from src.ingestion.weather import (
    OpenMeteoWeatherDownloader,
    WeatherLoader,
    extract_coordinates_from_cups_file,
    parse_coordinate_pair,
)


def dataframe_to_aligned_dataset(
    df: pd.DataFrame,
    year: int | None = None,
    month: int | None = None,
    primary_cups: str | None = None,
    cups_config_path: Path | str | None = None,
) -> AlignedDataset:
    """Convert a curated DataFrame into an AlignedDataset for calculation.

    Args:
        df: Curated DataFrame containing timestamp, cups_id, consumption, and generation.
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
        if num_col in df_clean.columns and (
            pd.api.types.is_string_dtype(df_clean[num_col].dtype)
            or df_clean[num_col].dtype == object
        ):
            df_clean[num_col] = (
                df_clean[num_col].astype(str).str.replace(",", ".", regex=False).str.strip()
            )
    df_clean["consumption"] = pd.to_numeric(df_clean["consumption"], errors="coerce").fillna(0.0)
    df_clean["generation"] = pd.to_numeric(df_clean["generation"], errors="coerce").fillna(0.0)
    if "community_demand" in df_clean.columns:
        df_clean["community_demand"] = pd.to_numeric(
            df_clean["community_demand"], errors="coerce"
        ).fillna(0.0)
    for add_col in (
        "self_consumption",
        "exported_energy",
        "imported_energy",
    ):
        if add_col in df_clean.columns:
            df_clean[add_col] = pd.to_numeric(df_clean[add_col], errors="coerce").fillna(0.0)

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

    # Extract primary CUPS if available
    resolved_primary = primary_cups
    if not resolved_primary and "primary" in df_clean.columns:
        pri_mask = df_clean["primary"].astype(str).str.lower().isin(["true", "1"])
        pri_rows = df_clean[pri_mask]
        if not pri_rows.empty:
            cand = str(pri_rows["cups_id"].iloc[0])
            if cand in cups_list:
                resolved_primary = cand

    if not resolved_primary:
        try:
            cfg = DataCurator(cups_config_path=cups_config_path).load_cups_config()
            cand = next((c.cups for c in cfg.values() if c.primary), None)
            if cand and cand in cups_list:
                resolved_primary = cand
        except Exception:
            pass

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
    """Coordinates ingestion, CUPS configuration lookup, primary meter reconciliation, and export."""

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

    def load_cups_config(self) -> dict[str, SupplyPoint]:
        """Discover and parse CUPS configuration file containing uses, primary flags, and coordinates.

        Returns:
            Dictionary mapping CUPS string identifiers to SupplyPoint instances.
        """
        found_path = resolve_cups_config_path(custom_path=self.cups_config_path)
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

        # 1. Primary CUPS coordinates take first priority
        for cfg in configs.values():
            if cfg.primary and cfg.latitude is not None and cfg.longitude is not None:
                return (round(cfg.latitude, 4), round(cfg.longitude, 4))

        # 2. Any other participating CUPS coordinates
        for cfg in configs.values():
            if cfg.latitude is not None and cfg.longitude is not None:
                return (round(cfg.latitude, 4), round(cfg.longitude, 4))

        # 3. Direct extraction from cups configuration file if configs was empty
        found_path = resolve_cups_config_path(custom_path=self.cups_config_path)
        if found_path:
            coords = extract_coordinates_from_cups_file(found_path)
            if coords:
                return coords[0]

        # 4. Fallback to persistent configuration if custom cups config not specified
        if not self.cups_config_path:
            app_cfg = load_config()
            if app_cfg.latitude is not None and app_cfg.longitude is not None:
                return (round(app_cfg.latitude, 4), round(app_cfg.longitude, 4))

        return None

    def curate(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> CuratedDataset:
        """Execute full time-series reconciliation across consumption and PV generation.

        Reconciliation algorithm:
        1. Ingest DATADIS consumption and Huawei FusionSolar generation datasets.
        2. Align datasets on common hourly timestamps, respecting any year/month filters.
        3. For each participating CUPS:
           - Retrieve the human-readable 'use' from cups.json config.
           - If marked as 'primary' and the solar generation file records an active consumption
             reading ('Consumo (kWh)'), reconcile by adopting the Huawei consumption to correct
             the fake-zero readings caused by direct behind-the-meter PV self-consumption.
           - Otherwise, use the standard DATADIS consumption reading.
        4. Calculate hourly community totals, solar surplus, and residual grid demand.
        5. Return structured CuratedDataset with full metadata and summary metrics.

        Args:
            year: Optional calendar year filter.
            month: Optional calendar month filter (1-12).

        Returns:
            CuratedDataset containing aligned hourly records and summary metrics.

        Raises:
            CurationError: If ingestion or alignment fails.
        """
        try:
            c_loader = DatadisConsumptionLoader(self.consumption_dir)
            g_loader = HuaweiGenerationLoader(self.generation_dir)

            c_df = c_loader.load_all()
            g_df = g_loader.load_all()

            c_files_count = len(c_loader.discover_files())
            g_files_count = len(g_loader.discover_files())

            aligner = TimeSeriesAligner(
                c_df,
                g_df,
                consumption_files_loaded=c_files_count,
                generation_files_loaded=g_files_count,
            )
            aligned = aligner.align(year=year, month=month)
        except Exception as err:
            raise CurationError(f"Curation pre-flight ingestion failed: {err}") from err

        cups_configs = self.load_cups_config()
        primary_cups: str | None = next(
            (c.cups for c in cups_configs.values() if c.primary),
            None,
        )

        # Index Huawei generation DataFrame by timestamp for fast lookup
        g_has_cons = "consumption_kwh" in g_df.columns
        g_cons_series: pd.Series[float] = (
            g_df.set_index("timestamp")["consumption_kwh"] if g_has_cons else pd.Series(dtype=float)
        )
        g_has_self_cons = "self_consumption_kwh" in g_df.columns
        g_self_cons_series: pd.Series[float] = (
            g_df.set_index("timestamp")["self_consumption_kwh"]
            if g_has_self_cons
            else pd.Series(dtype=float)
        )
        g_has_exp = "exported_energy_kwh" in g_df.columns
        g_exp_series: pd.Series[float] = (
            g_df.set_index("timestamp")["exported_energy_kwh"]
            if g_has_exp
            else pd.Series(dtype=float)
        )
        g_has_imp = "imported_energy_kwh" in g_df.columns
        g_imp_series: pd.Series[float] = (
            g_df.set_index("timestamp")["imported_energy_kwh"]
            if g_has_imp
            else pd.Series(dtype=float)
        )

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

        records: list[CuratedHourRecord] = []
        total_gen_kwh = 0.0
        total_cons_kwh = 0.0
        recovered_kwh = 0.0
        reconciled_hours_set: set[str] = set()
        cups_reconciled_counts: dict[str, int] = dict.fromkeys(aligned.cups_list, 0)
        cups_total_cons: dict[str, float] = dict.fromkeys(aligned.cups_list, 0.0)

        for ts in aligned.data.index:
            ts_str = str(ts)
            date_str = ts_str.split(" ")[0]
            try:
                hour_int = int(ts_str[11:13])
            except ValueError, IndexError:
                hour_int = 0
            hour_str = f"{hour_int}:00"

            gen_val = float(aligned.data.loc[ts, "generation_kwh"])
            total_gen_kwh += gen_val

            # Huawei meter consumption reading for this interval if present
            hw_cons_val: float | None = None
            if g_has_cons and ts_str in g_cons_series.index:
                val = g_cons_series.loc[ts_str]
                if pd.notna(val):
                    try:
                        hw_cons_val = float(val)
                    except ValueError, TypeError:
                        hw_cons_val = None

            # Huawei meter self-consumption reading for this interval if present
            hw_sc_val = 0.0
            if g_has_self_cons and ts_str in g_self_cons_series.index:
                sc_raw = g_self_cons_series.loc[ts_str]
                if pd.notna(sc_raw):
                    try:
                        hw_sc_val = max(0.0, float(sc_raw))
                    except ValueError, TypeError:
                        hw_sc_val = 0.0

            # Huawei meter export reading for this interval if present
            hw_exp_val = 0.0
            if g_has_exp and ts_str in g_exp_series.index:
                exp_raw = g_exp_series.loc[ts_str]
                if pd.notna(exp_raw):
                    try:
                        hw_exp_val = max(0.0, float(exp_raw))
                    except ValueError, TypeError:
                        hw_exp_val = 0.0

            # Huawei meter import reading for this interval if present
            hw_imp_val = 0.0
            if g_has_imp and ts_str in g_imp_series.index:
                imp_raw = g_imp_series.loc[ts_str]
                if pd.notna(imp_raw):
                    try:
                        hw_imp_val = max(0.0, float(imp_raw))
                    except ValueError, TypeError:
                        hw_imp_val = 0.0

            cups_readings: list[CuratedCupsReading] = []
            hour_cons_sum = 0.0

            for cups_id in aligned.cups_list:
                cfg = cups_configs.get(cups_id, SupplyPoint(cups=cups_id, use="", primary=False))
                datadis_cons = float(aligned.data.loc[ts, cups_id])

                is_reconciled = False
                final_cons = datadis_cons

                # For primary CUPS: use the plain raw solar inverter consumption reading directly when present
                if cfg.primary and hw_cons_val is not None:
                    final_cons = hw_cons_val
                    if (hw_cons_val - datadis_cons) > 0.001:
                        is_reconciled = True
                        diff = hw_cons_val - datadis_cons
                        recovered_kwh += diff
                        reconciled_hours_set.add(ts_str)
                        cups_reconciled_counts[cups_id] += 1

                # Self-consumed electricity: primary CUPS receives the Huawei reading, others receive 0.0
                c_self_cons = hw_sc_val if cfg.primary else 0.0
                c_exp = hw_exp_val if cfg.primary else 0.0
                c_imp = hw_imp_val if cfg.primary else 0.0

                cups_total_cons[cups_id] += final_cons
                hour_cons_sum += final_cons

                cups_readings.append(
                    CuratedCupsReading(
                        id=cups_id,
                        use=cfg.use,
                        consumption=format_energy_value(final_cons),
                        primary=cfg.primary,
                        reconciled=is_reconciled,
                        self_consumption=format_energy_value(c_self_cons),
                        exported_energy=format_energy_value(c_exp),
                        imported_energy=format_energy_value(c_imp),
                    )
                )

            cups_readings.sort(key=lambda c: (str(c.use or "").strip().lower(), str(c.id).lower()))

            total_cons_kwh += hour_cons_sum
            surplus = max(0.0, gen_val - hour_cons_sum)
            grid_demand = max(0.0, hour_cons_sum - gen_val)

            # Weather readings for this interval if present
            w_reading = weather_map.get(ts_str)
            temp_val, cloud_val = w_reading if w_reading is not None else (None, None)

            records.append(
                CuratedHourRecord(
                    date=date_str,
                    hour=hour_str,
                    generation=format_energy_value(gen_val),
                    cups=cups_readings,
                    timestamp=ts_str,
                    total_consumption=format_energy_value(hour_cons_sum),
                    solar_surplus=format_energy_value(surplus),
                    net_grid_demand=format_energy_value(grid_demand),
                    self_consumption=format_energy_value(hw_sc_val),
                    exported_energy=format_energy_value(hw_exp_val),
                    imported_energy=format_energy_value(hw_imp_val),
                    temperature=temp_val,
                    cloud_cover=cloud_val,
                )
            )

        summary = CuratedSummary(
            total_hours=len(records),
            reconciled_hours_count=len(reconciled_hours_set),
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
        base_name: str = "curated",
    ) -> Path:
        """Export curated dataset to a styled Excel (.xlsx) file.

        Args:
            dataset: The CuratedDataset to export.
            curated_dir: Directory where the Excel file should be written.
            base_name: File basename without extension (e.g. 'curated').

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
        base_name: str = "curated",
        delimiter: str = ";",
    ) -> Path:
        """Export curated dataset to a clean CSV file and sibling styled Excel (.xlsx) file.

        Args:
            dataset: The CuratedDataset to export.
            curated_dir: Directory where the CSV and Excel files should be written.
            base_name: File basename without extension (e.g. 'curated').
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
        base_name: str = "curated",
        delimiter: str = ";",
    ) -> Path:
        """Ensure that curated CSV and sibling Excel files exist, generating them if missing or forced.

        Args:
            force: If True, re-runs curation even if the curated CSV already exists.
            base_name: Base filename (defaults to 'curated').
            delimiter: CSV separator (defaults to ';').

        Returns:
            Path to the verified curated CSV file.
        """
        target_dir = self.curated_dir
        if target_dir.is_file():
            target_dir = target_dir.parent

        target_dir.mkdir(parents=True, exist_ok=True)
        csv_path = target_dir / f"{base_name}.csv"
        xlsx_path = target_dir / f"{base_name}.xlsx"
        if (
            not force
            and csv_path.exists()
            and csv_path.stat().st_size > 0
            and xlsx_path.exists()
            and xlsx_path.stat().st_size > 0
        ):
            try:
                first_line = csv_path.read_text(encoding="utf-8").splitlines()[0]
                sep = delimiter if delimiter in first_line else (";" if ";" in first_line else ",")
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
                    return csv_path
            except Exception:
                pass

        dataset = self.curate()
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
        """Load curated CSV file and reconstruct an AlignedDataset for calculation.

        Args:
            curated_path: Path to curated CSV file or directory containing it.
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
            candidate = path / "curated.csv"
            if candidate.exists():
                path = candidate
            else:
                csvs = sorted(path.glob("*.csv"))
                if not csvs:
                    raise CurationError(f"No curated CSV files found in directory '{path}'.")
                path = csvs[0]

        if not path.exists() or not path.is_file():
            raise CurationError(f"Curated file '{path}' does not exist.")

        # Auto-detect delimiter if not provided
        sep = delimiter
        if sep is None:
            first_line = (
                path.read_text(encoding="utf-8").splitlines()[0] if path.stat().st_size > 0 else ""
            )
            sep = ";" if ";" in first_line else ","

        decimal_char = "," if sep == ";" else "."
        try:
            df = pd.read_csv(
                path,
                sep=sep,
                decimal=decimal_char,
                dtype={"cups_id": str, "timestamp": str},
            )
        except Exception as err:
            raise CurationError(f"Failed to read curated CSV '{path}': {err}") from err

        return dataframe_to_aligned_dataset(
            df,
            year=year,
            month=month,
            cups_config_path=cups_config_path,
        )
