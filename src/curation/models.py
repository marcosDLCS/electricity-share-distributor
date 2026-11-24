"""Domain models and data structures for time-series curation, aggregation, and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

import numpy as np
import pandas as pd

from src.domain.exceptions import (
    CurationError as CurationError,
)
from src.domain.exceptions import (
    EsdError as EsdError,
)
from src.domain.models import SupplyPoint
from src.ingestion.csv_utils import clean_numeric_series

_DAYS_OF_WEEK: Final[tuple[str, ...]] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

GENERATION_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp",
    "year",
    "month",
    "day",
    "hour",
    "day_of_week",
    "is_weekend",
    "generation",
    "consumption",
    "self_consumption",
    "exported_energy",
    "imported_energy",
)

CONSUMPTION_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp",
    "year",
    "month",
    "day",
    "hour",
    "day_of_week",
    "is_weekend",
    "cups_id",
    "use",
    "consumption",
)

ESD_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp",
    "year",
    "month",
    "day",
    "hour",
    "day_of_week",
    "is_weekend",
    "cups_id",
    "use",
    "consumption",
    "community_demand",
    "generation",
    "self_consumption",
    "exported_energy",
    "imported_energy",
    "temperature",
    "cloud_cover",
)


def _add_calendar_columns(df: pd.DataFrame) -> None:
    """Populate year, month, day, hour, day_of_week, and is_weekend from timestamps."""
    codes, uniques = pd.factorize(df["timestamp"], sort=False)
    dt_uniq = pd.to_datetime(uniques, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    if dt_uniq.isna().any():
        dt_uniq = dt_uniq.fillna(pd.to_datetime(uniques, errors="coerce"))

    valid = codes >= 0
    if bool(valid.all()) and not bool(dt_uniq.isna().any()):
        dow_arr = dt_uniq.day_of_week.to_numpy(dtype="int64")[codes]
        dow_names = np.array(_DAYS_OF_WEEK, dtype=object)
        df["year"] = pd.array(dt_uniq.year.to_numpy(dtype="int64")[codes], dtype="Int64")
        df["month"] = pd.array(dt_uniq.month.to_numpy(dtype="int64")[codes], dtype="Int64")
        df["day"] = pd.array(dt_uniq.day.to_numpy(dtype="int64")[codes], dtype="Int64")
        df["hour"] = pd.array(dt_uniq.hour.to_numpy(dtype="int64")[codes], dtype="Int64")
        df["day_of_week"] = dow_names[dow_arr]
        df["is_weekend"] = (dow_arr >= 5).astype(bool)
    else:
        dt_series = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        if dt_series.isna().any():
            dt_series = dt_series.fillna(pd.to_datetime(df["timestamp"], errors="coerce"))
        dow_idx = dt_series.dt.day_of_week
        df["year"] = dt_series.dt.year.astype("Int64")
        df["month"] = dt_series.dt.month.astype("Int64")
        df["day"] = dt_series.dt.day.astype("Int64")
        df["hour"] = dt_series.dt.hour.astype("Int64")
        df["day_of_week"] = dow_idx.map(dict(enumerate(_DAYS_OF_WEEK))).fillna("")
        df["is_weekend"] = (dow_idx >= 5).fillna(False).astype(bool)


def _sort_by_timestamp_use_cups(df: pd.DataFrame, sort_cols: list[str]) -> pd.DataFrame:
    """Sort DataFrame by (timestamp, use, cups_id) using fast unique-value lowercasing."""

    def _key(col: pd.Series) -> pd.Series:
        if col.name not in ("use", "cups_id"):
            return col
        uniq = col.unique()
        lower_map = {val: str(val).lower() for val in uniq}
        return col.map(lower_map)

    return df.sort_values(
        by=sort_cols,
        key=_key,
        ascending=[True] * len(sort_cols),
    ).reset_index(drop=True)


def extract_temporal_features(
    timestamp: str,
    fallback_date: str = "",
    fallback_hour: str = "",
) -> tuple[int | None, int | None, int | None, int | None, str, bool]:
    """Decompose an ISO timestamp string into canonical calendar features.

    Returns:
        Tuple of (year, month, day, hour, day_of_week, is_weekend).
    """
    year: int | None = None
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    day_of_week: str = ""
    is_weekend: bool = False

    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            year = dt.year
            month = dt.month
            day = dt.day
            hour = dt.hour
            day_of_week = _DAYS_OF_WEEK[dt.weekday()]
            is_weekend = dt.weekday() >= 5
        except ValueError, TypeError:
            ts_dt = pd.to_datetime(timestamp, errors="coerce")
            if pd.notna(ts_dt):
                year = int(ts_dt.year)
                month = int(ts_dt.month)
                day = int(ts_dt.day)
                hour = int(ts_dt.hour)
                day_of_week = _DAYS_OF_WEEK[ts_dt.weekday()]
                is_weekend = bool(ts_dt.weekday() >= 5)
    elif fallback_date:
        try:
            dt = datetime.fromisoformat(fallback_date)
            year = dt.year
            month = dt.month
            day = dt.day
            h_val = (
                int(fallback_hour.split(":")[0]) if fallback_hour and ":" in fallback_hour else 0
            )
            hour = h_val
            day_of_week = _DAYS_OF_WEEK[dt.weekday()]
            is_weekend = dt.weekday() >= 5
        except ValueError, TypeError:
            pass

    return year, month, day, hour, day_of_week, is_weekend


_clean_numeric_series = clean_numeric_series


@dataclass
class GenerationRecord:
    """Canonical hourly solar PV generation record decoupled from vendor export formats.

    Attributes:
        timestamp: Canonical interval-start timestamp (YYYY-MM-DD HH:MM:SS).
        generation: Solar PV generated electricity in kWh.
        consumption: Behind-the-meter plant / primary point electricity demand in kWh (None if not metered).
        self_consumption: Physical instantaneous self-consumed solar energy in kWh.
        exported_energy: Surplus solar energy exported to the grid in kWh.
        imported_energy: Grid electricity imported at the inverter metering point in kWh.
    """

    timestamp: str
    generation: float | int
    consumption: float | int | None = None
    self_consumption: float | int = 0
    exported_energy: float | int = 0
    imported_energy: float | int = 0


@dataclass
class GenerationSummary:
    """Summary statistics for the aggregated solar PV generation dataset."""

    total_hours: int
    source_files_count: int
    total_generation_kwh: float
    total_consumption_kwh: float
    total_self_consumption_kwh: float
    total_exported_kwh: float
    total_imported_kwh: float
    start_time: str
    end_time: str
    has_plant_consumption: bool = False


@dataclass
class GenerationDataset:
    """Canonical container for aggregated solar PV generation time-series data."""

    records: list[GenerationRecord]
    summary: GenerationSummary

    def to_dataframe(self) -> pd.DataFrame:
        """Convert canonical generation records into a tidy, calendar-enriched DataFrame."""
        columns = list(GENERATION_COLUMNS)
        if not self.records:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(
            {
                "timestamp": [r.timestamp for r in self.records],
                "generation": [r.generation for r in self.records],
                "consumption": [r.consumption for r in self.records],
                "self_consumption": [r.self_consumption for r in self.records],
                "exported_energy": [r.exported_energy for r in self.records],
                "imported_energy": [r.imported_energy for r in self.records],
            }
        )
        _add_calendar_columns(df)

        df = df[columns].sort_values(by="timestamp", ascending=True).reset_index(drop=True)
        return df

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        source_files_count: int = 1,
    ) -> GenerationDataset:
        """Reconstruct a canonical GenerationDataset from an aggregated generation DataFrame."""
        from src.curation.curator import format_energy_value

        if df.empty:
            return cls(
                records=[],
                summary=GenerationSummary(
                    total_hours=0,
                    source_files_count=source_files_count,
                    total_generation_kwh=0.0,
                    total_consumption_kwh=0.0,
                    total_self_consumption_kwh=0.0,
                    total_exported_kwh=0.0,
                    total_imported_kwh=0.0,
                    start_time="",
                    end_time="",
                    has_plant_consumption=False,
                ),
            )

        df_clean = df.copy()
        if "generation_kwh" in df_clean.columns and "generation" not in df_clean.columns:
            df_clean["generation"] = df_clean["generation_kwh"]
        if "consumption_kwh" in df_clean.columns and "consumption" not in df_clean.columns:
            df_clean["consumption"] = df_clean["consumption_kwh"]
        if (
            "self_consumption_kwh" in df_clean.columns
            and "self_consumption" not in df_clean.columns
        ):
            df_clean["self_consumption"] = df_clean["self_consumption_kwh"]
        if "exported_energy_kwh" in df_clean.columns and "exported_energy" not in df_clean.columns:
            df_clean["exported_energy"] = df_clean["exported_energy_kwh"]
        if "imported_energy_kwh" in df_clean.columns and "imported_energy" not in df_clean.columns:
            df_clean["imported_energy"] = df_clean["imported_energy_kwh"]

        required = {"timestamp", "generation"}
        missing = required - set(df_clean.columns)
        if missing:
            raise CurationError(
                f"Generation dataset is missing required canonical columns: {sorted(missing)}"
            )

        df_clean["timestamp"] = df_clean["timestamp"].astype(str).str.strip()
        df_clean = df_clean.sort_values("timestamp").reset_index(drop=True)

        gen_series = _clean_numeric_series(df_clean["generation"]).fillna(0.0)
        has_cons = "consumption" in df_clean.columns and bool(
            _clean_numeric_series(df_clean["consumption"]).notna().any()
        )
        cons_series = (
            _clean_numeric_series(df_clean["consumption"])
            if "consumption" in df_clean.columns
            else pd.Series([None] * len(df_clean), index=df_clean.index)
        )
        sc_series = (
            _clean_numeric_series(df_clean["self_consumption"]).fillna(0.0)
            if "self_consumption" in df_clean.columns
            else pd.Series(0.0, index=df_clean.index)
        )
        exp_series = (
            _clean_numeric_series(df_clean["exported_energy"]).fillna(0.0)
            if "exported_energy" in df_clean.columns
            else pd.Series(0.0, index=df_clean.index)
        )
        imp_series = (
            _clean_numeric_series(df_clean["imported_energy"]).fillna(0.0)
            if "imported_energy" in df_clean.columns
            else pd.Series(0.0, index=df_clean.index)
        )

        records: list[GenerationRecord] = []
        total_gen = 0.0
        total_cons = 0.0
        total_sc = 0.0
        total_exp = 0.0
        total_imp = 0.0

        for ts, g_val, c_val, sc_val, exp_val, imp_val in zip(
            df_clean["timestamp"],
            gen_series,
            cons_series,
            sc_series,
            exp_series,
            imp_series,
            strict=False,
        ):
            g_float = float(g_val)
            sc_float = max(0.0, float(sc_val))
            exp_float = max(0.0, float(exp_val))
            imp_float = max(0.0, float(imp_val))
            c_formatted: float | int | None = None
            if has_cons and pd.notna(c_val):
                c_float = float(c_val)
                total_cons += c_float
                c_formatted = format_energy_value(c_float)

            total_gen += g_float
            total_sc += sc_float
            total_exp += exp_float
            total_imp += imp_float

            records.append(
                GenerationRecord(
                    timestamp=str(ts),
                    generation=format_energy_value(g_float),
                    consumption=c_formatted,
                    self_consumption=format_energy_value(sc_float),
                    exported_energy=format_energy_value(exp_float),
                    imported_energy=format_energy_value(imp_float),
                )
            )

        summary = GenerationSummary(
            total_hours=len(records),
            source_files_count=source_files_count,
            total_generation_kwh=round(total_gen, 2),
            total_consumption_kwh=round(total_cons, 2),
            total_self_consumption_kwh=round(total_sc, 2),
            total_exported_kwh=round(total_exp, 2),
            total_imported_kwh=round(total_imp, 2),
            start_time=records[0].timestamp if records else "",
            end_time=records[-1].timestamp if records else "",
            has_plant_consumption=has_cons,
        )
        return cls(records=records, summary=summary)


@dataclass
class ConsumptionRecord:
    """Canonical hourly electricity consumption record per CUPS decoupled from DSO formats.

    Attributes:
        timestamp: Canonical interval-start timestamp (YYYY-MM-DD HH:MM:SS).
        cups_id: Universal Supply Point Code (CUPS) identifier.
        use: Functional description of the supply point (e.g. 'Aerotermia', 'Piscina').
        consumption: Hourly electricity consumption in kWh.
    """

    timestamp: str
    cups_id: str
    use: str = ""
    consumption: float | int = 0


@dataclass
class ConsumptionSummary:
    """Summary statistics for the aggregated CUPS electricity consumption dataset."""

    total_records: int
    total_hours: int
    cups_count: int
    cups_list: list[str]
    source_files_count: int
    total_consumption_kwh: float
    start_time: str
    end_time: str
    cups_total_consumption: dict[str, float] = field(default_factory=dict)


@dataclass
class ConsumptionDataset:
    """Canonical container for aggregated CUPS electricity consumption time-series data."""

    records: list[ConsumptionRecord]
    summary: ConsumptionSummary

    def to_dataframe(self) -> pd.DataFrame:
        """Convert canonical consumption records into a tidy, calendar-enriched DataFrame."""
        columns = list(CONSUMPTION_COLUMNS)
        if not self.records:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(
            {
                "timestamp": [r.timestamp for r in self.records],
                "cups_id": [r.cups_id for r in self.records],
                "use": [r.use for r in self.records],
                "consumption": [r.consumption for r in self.records],
            }
        )
        _add_calendar_columns(df)

        df = df[columns]
        sort_cols = [col for col in ["timestamp", "use", "cups_id"] if col in df.columns]
        return _sort_by_timestamp_use_cups(df, sort_cols)

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        source_files_count: int = 1,
        cups_uses: dict[str, str] | None = None,
    ) -> ConsumptionDataset:
        """Reconstruct a canonical ConsumptionDataset from an aggregated consumption DataFrame."""
        from src.curation.curator import format_energy_value

        if df.empty:
            return cls(
                records=[],
                summary=ConsumptionSummary(
                    total_records=0,
                    total_hours=0,
                    cups_count=0,
                    cups_list=[],
                    source_files_count=source_files_count,
                    total_consumption_kwh=0.0,
                    start_time="",
                    end_time="",
                    cups_total_consumption={},
                ),
            )

        df_clean = df.copy()
        if "cups" in df_clean.columns and "cups_id" not in df_clean.columns:
            df_clean["cups_id"] = df_clean["cups"]
        if "consumption_kwh" in df_clean.columns and "consumption" not in df_clean.columns:
            df_clean["consumption"] = df_clean["consumption_kwh"]

        required = {"timestamp", "cups_id", "consumption"}
        missing = required - set(df_clean.columns)
        if missing:
            raise CurationError(
                f"Consumption dataset is missing required canonical columns: {sorted(missing)}"
            )

        df_clean["timestamp"] = df_clean["timestamp"].astype(str).str.strip()
        df_clean["cups_id"] = df_clean["cups_id"].astype(str).str.strip()
        if "use" not in df_clean.columns:
            df_clean["use"] = df_clean["cups_id"].map(cups_uses).fillna("") if cups_uses else ""
        else:
            df_clean["use"] = df_clean["use"].fillna("").astype(str).str.strip()
            if cups_uses:
                empty_mask = df_clean["use"] == ""
                df_clean.loc[empty_mask, "use"] = (
                    df_clean.loc[empty_mask, "cups_id"].map(cups_uses).fillna("")
                )

        cons_series = _clean_numeric_series(df_clean["consumption"]).fillna(0.0)
        df_clean["_cons_num"] = cons_series

        df_clean = _sort_by_timestamp_use_cups(df_clean, ["timestamp", "use", "cups_id"])

        total_cons = float(df_clean["_cons_num"].sum())
        cups_totals = {
            str(k): float(v)
            for k, v in df_clean.groupby("cups_id", sort=False)["_cons_num"].sum().items()
        }
        records = [
            ConsumptionRecord(
                timestamp=ts,
                cups_id=cid,
                use=use_val,
                consumption=format_energy_value(c_val),
            )
            for ts, cid, use_val, c_val in zip(
                df_clean["timestamp"].tolist(),
                df_clean["cups_id"].tolist(),
                df_clean["use"].tolist(),
                df_clean["_cons_num"].to_numpy(dtype=float).tolist(),
                strict=False,
            )
        ]

        cups_list = sorted(cups_totals.keys())
        unique_ts = sorted(df_clean["timestamp"].unique())

        summary = ConsumptionSummary(
            total_records=len(records),
            total_hours=len(unique_ts),
            cups_count=len(cups_list),
            cups_list=cups_list,
            source_files_count=source_files_count,
            total_consumption_kwh=round(total_cons, 2),
            start_time=str(unique_ts[0]) if unique_ts else "",
            end_time=str(unique_ts[-1]) if unique_ts else "",
            cups_total_consumption={k: round(v, 2) for k, v in sorted(cups_totals.items())},
        )
        return cls(records=records, summary=summary)


@dataclass
class CuratedCupsReading:
    """Reconciled consumption reading for an individual CUPS at a given hour.

    Attributes:
        id: CUPS identifier code.
        use: Functional description (e.g. 'piscina', 'Aerotermia').
        consumption: Electricity consumption value (in kWh, matching generation units).
        primary: Whether this CUPS is the primary point directly connected to the solar plant.
        reconciled: Whether this reading was reconciled/corrected from the PV generation meter.
        self_consumption: PV physical instantaneous self-consumed electricity in this hour (in kWh).
        exported_energy: Solar generation exported to the grid in this hour (in kWh).
        imported_energy: Grid electricity imported by this point in this hour (in kWh).
    """

    id: str
    use: str
    consumption: float | int
    primary: bool = False
    reconciled: bool = False
    self_consumption: float | int = 0
    exported_energy: float | int = 0
    imported_energy: float | int = 0


@dataclass
class CuratedHourRecord:
    """Reconciled time-series record for a single hour across all community supply points.

    Attributes:
        timestamp: Canonical interval-start timestamp (YYYY-MM-DD HH:MM:SS).
        generation: Solar PV generation (in kWh, matching consumption units).
        cups: List of per-CUPS curated readings.
        total_consumption: Sum of consumption across all participating CUPS for this hour.
        temperature: Ambient temperature in degrees Celsius (°C), if available.
        cloud_cover: Cloud cover percentage (0-100%), if available.
    """

    timestamp: str
    generation: float | int
    cups: list[CuratedCupsReading] = field(default_factory=list)
    total_consumption: float | int = 0
    temperature: float | None = None
    cloud_cover: int | float | None = None


@dataclass
class CuratedSummary:
    """Summary metrics of the curated ESD time-series reconciliation dataset."""

    total_hours: int
    reconciled_hours_count: int
    recovered_kwh: float
    total_generation_kwh: float
    total_consumption_kwh: float
    start_time: str
    end_time: str
    cups_count: int
    primary_cups: str | None
    cups_reconciled_hours: dict[str, int] = field(default_factory=dict)
    cups_total_consumption: dict[str, float] = field(default_factory=dict)


@dataclass
class CuratedDataset:
    """Master ESD dataset container for curated and reconciled time-series data."""

    records: list[CuratedHourRecord]
    summary: CuratedSummary
    cups_configs: dict[str, SupplyPoint]

    def to_dataframe(self) -> pd.DataFrame:
        """Flatten hourly records into a tidy master ESD DataFrame for CSV/Excel export.

        Columns are grouped logically by analytical role:
        1. Temporal coordinates: timestamp, year, month, day, hour, day_of_week, is_weekend
        2. Individual consumer: cups_id, use, consumption
        3. Community & solar balance: community_demand, generation, self_consumption, exported_energy, imported_energy
        4. Weather context: temperature, cloud_cover
        """
        columns = list(ESD_COLUMNS)
        if not self.records:
            return pd.DataFrame(columns=columns)

        ts_col: list[str] = []
        cups_col: list[str] = []
        use_col: list[str] = []
        cons_col: list[float | int] = []
        comm_col: list[float | int] = []
        gen_col: list[float | int] = []
        sc_col: list[float | int] = []
        exp_col: list[float | int] = []
        imp_col: list[float | int] = []
        temp_col: list[float | None] = []
        cloud_col: list[int | float | None] = []

        for r in self.records:
            ts = r.timestamp
            comm = r.total_consumption
            gen = r.generation
            temp = r.temperature
            cloud = r.cloud_cover
            for c in r.cups:
                ts_col.append(ts)
                cups_col.append(c.id)
                use_col.append(c.use)
                cons_col.append(c.consumption)
                comm_col.append(comm)
                gen_col.append(gen)
                sc_col.append(c.self_consumption)
                exp_col.append(c.exported_energy)
                imp_col.append(c.imported_energy)
                temp_col.append(temp)
                cloud_col.append(cloud)

        if not ts_col:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(
            {
                "timestamp": ts_col,
                "cups_id": cups_col,
                "use": use_col,
                "consumption": cons_col,
                "community_demand": comm_col,
                "generation": gen_col,
                "self_consumption": sc_col,
                "exported_energy": exp_col,
                "imported_energy": imp_col,
                "temperature": temp_col,
                "cloud_cover": cloud_col,
            }
        )

        _add_calendar_columns(df)

        df["cloud_cover"] = pd.to_numeric(df["cloud_cover"], errors="coerce").astype("Int64")
        df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce").round(1)

        return _sort_by_timestamp_use_cups(df[columns], ["timestamp", "use", "cups_id"])

    def to_aligned_dataset(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> Any:
        """Convert in-memory curated dataset into AlignedDataset for calculation."""
        from src.curation.curator import dataframe_to_aligned_dataset

        primary = self.summary.primary_cups
        if not primary and self.cups_configs:
            primary = next((c.cups for c in self.cups_configs.values() if c.primary), None)

        return dataframe_to_aligned_dataset(
            self.to_dataframe(),
            year=year,
            month=month,
            primary_cups=primary,
        )


# Domain alias for master ESD dataset
EsdDataset = CuratedDataset
