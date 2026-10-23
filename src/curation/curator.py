"""Engine and logic for curating, reconciling, and exporting time-series datasets."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import (
    DEFAULT_CONSUMPTION_DIR,
    DEFAULT_CUPS_CONFIG_PATH,
    DEFAULT_CURATED_DIR,
    DEFAULT_GENERATION_DIR,
)
from src.curation.models import (
    CupsConfig,
    CuratedCupsReading,
    CuratedDataset,
    CuratedHourRecord,
    CuratedSummary,
    CurationError,
)
from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.generation import HuaweiGenerationLoader
from src.ingestion.schema import (
    AlignedDataset,
    AlignmentError,
    IngestionSummary,
)


def dataframe_to_aligned_dataset(
    df: pd.DataFrame,
    year: int | None = None,
    month: int | None = None,
) -> AlignedDataset:
    """Convert a curated DataFrame into an AlignedDataset for calculation.

    Args:
        df: Curated DataFrame containing timestamp, cups_id, consumption, and generation.
        year: Optional calendar year filter.
        month: Optional calendar month filter (1-12).

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
    df_clean["consumption"] = pd.to_numeric(df_clean["consumption"], errors="coerce").fillna(0.0)
    df_clean["generation"] = pd.to_numeric(df_clean["generation"], errors="coerce").fillna(0.0)

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
    aligned_df = aligned_df.sort_index()

    # Extract CUPS functional uses if available
    cups_uses: dict[str, str] = {}
    if "use" in df_clean.columns:
        for cups, use_val in zip(df_clean["cups_id"], df_clean["use"], strict=False):
            if cups and pd.notna(use_val) and str(use_val).strip():
                cups_uses[str(cups)] = str(use_val).strip()

    # Extract primary CUPS if available
    primary_cups: str | None = None
    if "primary" in df_clean.columns:
        pri_mask = df_clean["primary"].astype(str).str.lower().isin(["true", "1"])
        pri_rows = df_clean[pri_mask]
        if not pri_rows.empty:
            cand = str(pri_rows["cups_id"].iloc[0])
            if cand in cups_list:
                primary_cups = cand

    if not primary_cups:
        try:
            cfg = DataCurator().load_cups_config()
            cand = next((c.cups for c in cfg.values() if c.primary), None)
            if cand and cand in cups_list:
                primary_cups = cand
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
        primary_cups=primary_cups,
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
    ) -> None:
        self.consumption_dir = Path(consumption_dir)
        self.generation_dir = Path(generation_dir)
        self.cups_config_path = Path(cups_config_path) if cups_config_path else None
        self.curated_dir = Path(curated_dir)

    def load_cups_config(self) -> dict[str, CupsConfig]:
        """Discover and parse CUPS configuration file containing uses and primary flags.

        Returns:
            Dictionary mapping CUPS string identifiers to CupsConfig instances.
        """
        candidate_paths: list[Path] = []
        if self.cups_config_path:
            candidate_paths.append(self.cups_config_path)
        else:
            candidate_paths.extend(
                [
                    DEFAULT_CUPS_CONFIG_PATH,
                    Path(".input/cups.json"),
                    Path("cups.json"),
                ]
            )

        found_path: Path | None = None
        for cp in candidate_paths:
            if cp.exists() and cp.is_file():
                found_path = cp
                break

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

        configs: dict[str, CupsConfig] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            cups_id = str(item.get("cups") or item.get("id") or "").strip()
            if not cups_id:
                continue
            use = str(item.get("use") or "").strip()
            primary = bool(item.get("primary", False))
            configs[cups_id] = CupsConfig(cups=cups_id, use=use, primary=primary)

        return configs

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

            cups_readings: list[CuratedCupsReading] = []
            hour_cons_sum = 0.0

            for cups_id in aligned.cups_list:
                cfg = cups_configs.get(cups_id, CupsConfig(cups=cups_id, use="", primary=False))
                datadis_cons = float(aligned.data.loc[ts, cups_id])

                is_reconciled = False
                final_cons = datadis_cons

                # Reconcile primary CUPS if Huawei consumption reading is present and positive
                if cfg.primary and hw_cons_val is not None and hw_cons_val > 0:
                    final_cons = hw_cons_val
                    # It's a genuine reconciliation if DATADIS reported 0 or significantly less
                    if datadis_cons <= 0.001 or (hw_cons_val - datadis_cons) > 0.01:
                        is_reconciled = True
                        diff = max(0.0, hw_cons_val - datadis_cons)
                        recovered_kwh += diff
                        reconciled_hours_set.add(ts_str)
                        cups_reconciled_counts[cups_id] += 1

                cups_total_cons[cups_id] += final_cons
                hour_cons_sum += final_cons

                cups_readings.append(
                    CuratedCupsReading(
                        id=cups_id,
                        use=cfg.use,
                        consumption=format_energy_value(final_cons),
                        primary=cfg.primary,
                        reconciled=is_reconciled,
                    )
                )

            total_cons_kwh += hour_cons_sum
            surplus = max(0.0, gen_val - hour_cons_sum)
            grid_demand = max(0.0, hour_cons_sum - gen_val)

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
    def export_csv(
        cls,
        dataset: CuratedDataset,
        curated_dir: Path | str,
        base_name: str = "curated",
        delimiter: str = ",",
    ) -> Path:
        """Export curated dataset to a clean CSV file.

        Args:
            dataset: The CuratedDataset to export.
            curated_dir: Directory where the CSV file should be written.
            base_name: File basename without extension (e.g. 'curated').
            delimiter: CSV delimiter character (defaults to ',').

        Returns:
            Path to the generated CSV file.
        """
        out_path = Path(curated_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        csv_file = out_path / f"{base_name}.csv"
        df = dataset.to_dataframe()
        df.to_csv(csv_file, index=False, sep=delimiter, encoding="utf-8")

        return csv_file

    def ensure_curated(
        self,
        force: bool = False,
        base_name: str = "curated",
        delimiter: str = ",",
    ) -> Path:
        """Ensure that a curated CSV file exists, generating it if missing or forced.

        Args:
            force: If True, re-runs curation even if the curated CSV already exists.
            base_name: Base filename (defaults to 'curated').
            delimiter: CSV separator (defaults to ',').

        Returns:
            Path to the verified curated CSV file.
        """
        target_dir = self.curated_dir
        if target_dir.is_file():
            target_dir = target_dir.parent

        target_dir.mkdir(parents=True, exist_ok=True)
        csv_path = target_dir / f"{base_name}.csv"
        if not force and csv_path.exists() and csv_path.stat().st_size > 0:
            return csv_path

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

        try:
            df = pd.read_csv(path, sep=sep, dtype={"cups_id": str, "timestamp": str})
        except Exception as err:
            raise CurationError(f"Failed to read curated CSV '{path}': {err}") from err

        return dataframe_to_aligned_dataset(df, year=year, month=month)
