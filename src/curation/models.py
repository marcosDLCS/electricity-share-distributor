"""Domain models and data structures for time-series curation and reconciliation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from src.domain.exceptions import (
    CurationError as CurationError,
)
from src.domain.exceptions import (
    EsdError as EsdError,
)


@dataclass
class CupsConfig:
    """Configuration metadata for a CUPS supply point.

    Attributes:
        cups: Universal supply point identifier code.
        use: Functional human-readable description of this supply point (e.g., 'piscina').
        primary: Whether this CUPS is the primary point connected to the PV generation plant.
        latitude: Optional geographical latitude coordinate.
        longitude: Optional geographical longitude coordinate.
    """

    cups: str
    use: str = ""
    primary: bool = False
    latitude: float | None = None
    longitude: float | None = None
    min_share: float | None = None
    max_share: float | None = None


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
        hourly_self_consumption: Regulatory hourly self-consumed electricity min(consumption, generation) (kWh).
        exported_energy: Solar generation exported to the grid in this hour (in kWh).
        imported_energy: Grid electricity imported by this point in this hour (in kWh).
    """

    id: str
    use: str
    consumption: float | int
    primary: bool = False
    reconciled: bool = False
    self_consumption: float | int = 0
    hourly_self_consumption: float | int = 0
    exported_energy: float | int = 0
    imported_energy: float | int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary matching the target format."""
        return {
            "id": self.id,
            "use": self.use,
            "consumption": self.consumption,
            "self_consumption": self.self_consumption,
            "hourly_self_consumption": self.hourly_self_consumption,
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
        hourly_self_consumption: Regulatory hourly self-consumption for primary installation (kWh).
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
    hourly_self_consumption: float | int = 0
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
            "hourly_self_consumption": self.hourly_self_consumption,
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
    """Summary metrics of the curated time-series reconciliation dataset."""

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


_DAYS_OF_WEEK: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass
class CuratedDataset:
    """Complete container for curated and reconciled time-series dataset."""

    records: list[CuratedHourRecord]
    summary: CuratedSummary
    cups_configs: dict[str, CupsConfig]

    def to_json(self, indent: int = 2) -> str:
        """Serialize curated dataset to formatted JSON string."""
        data = [r.to_dict() for r in self.records]
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def to_dataframe(self) -> pd.DataFrame:
        """Flatten hourly records into a tidy DataFrame for CSV export.

        Columns are grouped logically by analytical role:
        1. Temporal coordinates: timestamp, year, month, day, hour, day_of_week, is_weekend
        2. Individual consumer: cups_id, use, consumption
        3. Community & solar balance: community_demand, generation, self_consumption, hourly_self_consumption, exported_energy, imported_energy
        4. Weather context: temperature, cloud_cover
        """
        rows: list[dict[str, Any]] = []
        for r in self.records:
            year: int | None = None
            month: int | None = None
            day: int | None = None
            hour: int | None = None
            day_of_week: str = ""
            is_weekend: bool = False

            if r.timestamp:
                try:
                    dt = datetime.fromisoformat(r.timestamp)
                    year = dt.year
                    month = dt.month
                    day = dt.day
                    hour = dt.hour
                    day_of_week = _DAYS_OF_WEEK[dt.weekday()]
                    is_weekend = dt.weekday() >= 5
                except ValueError, TypeError:
                    ts_dt = pd.to_datetime(r.timestamp, errors="coerce")
                    if pd.notna(ts_dt):
                        year = int(ts_dt.year)
                        month = int(ts_dt.month)
                        day = int(ts_dt.day)
                        hour = int(ts_dt.hour)
                        day_of_week = _DAYS_OF_WEEK[ts_dt.weekday()]
                        is_weekend = bool(ts_dt.weekday() >= 5)
            elif r.date:
                try:
                    dt = datetime.fromisoformat(r.date)
                    year = dt.year
                    month = dt.month
                    day = dt.day
                    h_val = int(r.hour.split(":")[0]) if r.hour and ":" in r.hour else 0
                    hour = h_val
                    day_of_week = _DAYS_OF_WEEK[dt.weekday()]
                    is_weekend = dt.weekday() >= 5
                except ValueError, TypeError:
                    pass

            comm_demand = r.total_consumption

            for c in r.cups:
                self_cons = getattr(c, "self_consumption", 0)
                if self_cons == 0 and c.primary and getattr(r, "self_consumption", 0):
                    self_cons = r.self_consumption

                h_sc = getattr(c, "hourly_self_consumption", 0)
                if h_sc == 0 and c.primary and getattr(r, "hourly_self_consumption", 0):
                    h_sc = r.hourly_self_consumption

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
                        "hourly_self_consumption": h_sc,
                        "exported_energy": exp_e,
                        "imported_energy": imp_e,
                        "temperature": r.temperature,
                        "cloud_cover": r.cloud_cover,
                    }
                )

        columns = [
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
            "hourly_self_consumption",
            "exported_energy",
            "imported_energy",
            "temperature",
            "cloud_cover",
        ]
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
