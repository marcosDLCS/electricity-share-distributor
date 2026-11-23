"""Domain models for residential community electricity consumption analytics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CupsConsumptionShare:
    """Consumption total and relative community share for a single CUPS within a period."""

    cups: str
    consumption_kwh: float
    share_pct: float
    readings_count: int
    avg_hourly_kwh: float
    use: str = ""


@dataclass(frozen=True, slots=True)
class MonthlyConsumptionSummary:
    """Aggregated community consumption and CUPS shares for a specific calendar month."""

    year: int
    month: int
    period_label: str
    community_total_kwh: float
    cups_shares: list[CupsConsumptionShare]
    top_consumer: CupsConsumptionShare


@dataclass(frozen=True, slots=True)
class AnnualConsumptionSummary:
    """Aggregated community consumption and CUPS shares for a calendar year."""

    year: int
    period_label: str
    community_total_kwh: float
    cups_shares: list[CupsConsumptionShare]
    monthly_totals: dict[int, float]
    top_consumer: CupsConsumptionShare
    lowest_consumer: CupsConsumptionShare


@dataclass
class CommunityConsumptionSummary:
    """Complete consumption analytics summary across all loaded DATADIS periods."""

    total_community_kwh: float
    total_readings: int
    unique_cups_count: int
    cups_list: list[str]
    date_min: str
    date_max: str
    annual_summaries: dict[int, AnnualConsumptionSummary]
    monthly_summaries: list[MonthlyConsumptionSummary]
    overall_cups_shares: list[CupsConsumptionShare]
    peak_month_label: str
    peak_month_kwh: float
    lowest_month_label: str
    lowest_month_kwh: float
    cups_uses: dict[str, str] = field(default_factory=dict)
