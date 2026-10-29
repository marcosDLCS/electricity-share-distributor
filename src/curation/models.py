"""Domain models and data structures for time-series curation, aggregation, and reconciliation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

import pandas as pd

from src.domain.exceptions import (
    CurationError as CurationError,
)
from src.domain.exceptions import (
    EsdError as EsdError,
)
from src.domain.models import SupplyPoint

# Canonical domain model alias for backward compatibility
CupsConfig = SupplyPoint

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


def _clean_numeric_series(series: pd.Series) -> pd.Series:
    """Normalize a pandas Series with potential string comma decimals into float values."""
    if pd.api.types.is_string_dtype(series.dtype) or series.dtype == object:
        cleaned = series.astype(str).str.replace(",", ".", regex=False).str.strip()
        return pd.to_numeric(cleaned, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize record to canonical dictionary."""
        return {
            "timestamp": self.timestamp,
            "generation": self.generation,
            "consumption": self.consumption,
            "self_consumption": self.self_consumption,
            "exported_energy": self.exported_energy,
            "imported_energy": self.imported_energy,
        }


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
            [
                {
                    "timestamp": r.timestamp,
                    "generation": r.generation,
                    "consumption": r.consumption,
                    "self_consumption": r.self_consumption,
                    "exported_energy": r.exported_energy,
                    "imported_energy": r.imported_energy,
                }
                for r in self.records
            ]
        )
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

    def to_dict(self) -> dict[str, Any]:
        """Serialize record to canonical dictionary."""
        return {
            "timestamp": self.timestamp,
            "cups_id": self.cups_id,
            "use": self.use,
            "consumption": self.consumption,
        }


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
            [
                {
                    "timestamp": r.timestamp,
                    "cups_id": r.cups_id,
                    "use": r.use,
                    "consumption": r.consumption,
                }
                for r in self.records
            ]
        )
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

        df = df[columns]
        sort_cols = [col for col in ["timestamp", "use", "cups_id"] if col in df.columns]
        df = df.sort_values(
            by=sort_cols,
            key=lambda col: col.astype(str).str.lower() if col.name in ("use", "cups_id") else col,
            ascending=[True] * len(sort_cols),
        ).reset_index(drop=True)
        return df

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

        sort_cols = ["timestamp", "use", "cups_id"]
        df_clean = df_clean.sort_values(
            by=sort_cols,
            key=lambda col: col.astype(str).str.lower() if col.name in ("use", "cups_id") else col,
            ascending=[True, True, True],
        ).reset_index(drop=True)

        records: list[ConsumptionRecord] = []
        cups_totals: dict[str, float] = {}
        total_cons = 0.0

        for ts, cid, use_val, c_val in zip(
            df_clean["timestamp"],
            df_clean["cups_id"],
            df_clean["use"],
            df_clean["_cons_num"],
            strict=False,
        ):
            c_float = float(c_val)
            total_cons += c_float
            cups_totals[str(cid)] = cups_totals.get(str(cid), 0.0) + c_float
            records.append(
                ConsumptionRecord(
                    timestamp=str(ts),
                    cups_id=str(cid),
                    use=str(use_val),
                    consumption=format_energy_value(c_float),
                )
            )

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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary matching the target format."""
        return {
            "id": self.id,
            "use": self.use,
            "consumption": self.consumption,
            "self_consumption": self.self_consumption,
            "exported_energy": self.exported_energy,
            "imported_energy": self.imported_energy,
            "primary": self.primary,
            "reconciled": self.reconciled,
        }


@dataclass
class CuratedHourRecord:
    """Reconciled time-series record for a single hour across all community supply points.

    Attributes:
        date: Calendar date in YYYY-MM-DD format.
        hour: Hour string in H:00 format (e.g. '7:00').
        generation: Solar PV generation (in kWh, matching consumption units).
        cups: List of per-CUPS curated readings.
        timestamp: Canonical interval-start timestamp (YYYY-MM-DD HH:MM:SS).
        total_consumption: Sum of consumption across all participating CUPS for this hour.
        solar_surplus: Surplus generation exceeding collective demand (kWh).
        net_grid_demand: Net grid electricity demand exceeding solar generation (kWh).
        self_consumption: Solar PV physical instantaneous self-consumed electricity (kWh).
        exported_energy: Solar PV generation exported to grid from inverter meter (kWh).
        imported_energy: Grid electricity imported from inverter meter (kWh).
        temperature: Ambient temperature in degrees Celsius (°C), if available.
        cloud_cover: Cloud cover percentage (0-100%), if available.
    """

    date: str
    hour: str
    generation: float | int
    cups: list[CuratedCupsReading] = field(default_factory=list)
    timestamp: str = ""
    total_consumption: float | int = 0
    solar_surplus: float | int = 0
    net_grid_demand: float | int = 0
    self_consumption: float | int = 0
    exported_energy: float | int = 0
    imported_energy: float | int = 0
    temperature: float | None = None
    cloud_cover: int | float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary conforming to the target JSON specification."""
        return {
            "date": self.date,
            "hour": self.hour,
            "generation": self.generation,
            "self_consumption": self.self_consumption,
            "exported_energy": self.exported_energy,
            "imported_energy": self.imported_energy,
            "cups": [c.to_dict() for c in self.cups],
            "timestamp": self.timestamp,
            "total_consumption": self.total_consumption,
            "solar_surplus": self.solar_surplus,
            "net_grid_demand": self.net_grid_demand,
            "temperature": self.temperature,
            "cloud_cover": self.cloud_cover,
        }


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
    cups_configs: dict[str, CupsConfig]

    def to_json(self, indent: int = 2) -> str:
        """Serialize curated dataset to formatted JSON string."""
        data = [r.to_dict() for r in self.records]
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def to_dataframe(self) -> pd.DataFrame:
        """Flatten hourly records into a tidy master ESD DataFrame for CSV/Excel export.

        Columns are grouped logically by analytical role:
        1. Temporal coordinates: timestamp, year, month, day, hour, day_of_week, is_weekend
        2. Individual consumer: cups_id, use, consumption
        3. Community & solar balance: community_demand, generation, self_consumption, exported_energy, imported_energy
        4. Weather context: temperature, cloud_cover
        """
        rows: list[dict[str, Any]] = []
        for r in self.records:
            year, month, day, hour, day_of_week, is_weekend = extract_temporal_features(
                r.timestamp,
                fallback_date=r.date,
                fallback_hour=r.hour,
            )

            comm_demand = r.total_consumption

            for c in r.cups:
                self_cons = getattr(c, "self_consumption", 0)
                if self_cons == 0 and c.primary and getattr(r, "self_consumption", 0):
                    self_cons = r.self_consumption

                exp_e = getattr(c, "exported_energy", 0)
                if exp_e == 0 and c.primary and getattr(r, "exported_energy", 0):
                    exp_e = r.exported_energy

                imp_e = getattr(c, "imported_energy", 0)
                if imp_e == 0 and c.primary and getattr(r, "imported_energy", 0):
                    imp_e = r.imported_energy

                rows.append(
                    {
                        "timestamp": r.timestamp,
                        "year": year,
                        "month": month,
                        "day": day,
                        "hour": hour,
                        "day_of_week": day_of_week,
                        "is_weekend": is_weekend,
                        "cups_id": c.id,
                        "use": c.use,
                        "consumption": c.consumption,
                        "community_demand": comm_demand,
                        "generation": r.generation,
                        "self_consumption": self_cons,
                        "exported_energy": exp_e,
                        "imported_energy": imp_e,
                        "temperature": r.temperature,
                        "cloud_cover": r.cloud_cover,
                    }
                )

        columns = list(ESD_COLUMNS)
        if not rows:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(rows)
        for int_col in ("year", "month", "day", "hour", "cloud_cover"):
            if int_col in df.columns:
                df[int_col] = pd.to_numeric(df[int_col], errors="coerce").astype("Int64")
        if "temperature" in df.columns:
            df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce").round(1)
        if "is_weekend" in df.columns:
            df["is_weekend"] = df["is_weekend"].astype(bool)

        sort_cols = [col for col in ["timestamp", "use", "cups_id"] if col in df.columns]
        df = df.sort_values(
            by=sort_cols,
            key=lambda col: col.astype(str).str.lower() if col.name in ("use", "cups_id") else col,
            ascending=[True] * len(sort_cols),
        ).reset_index(drop=True)
        return df

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
