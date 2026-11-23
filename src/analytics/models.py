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


@dataclass(frozen=True, slots=True)
class MonthComparison:
    """Monthly multi-year comparison for the community with calendar completeness metadata."""

    month: int
    yearly_kwh: dict[int, float | None]
    diff_kwh: float | None
    pct_change: float | None
    is_complete: bool = True
    year_status: dict[int, str] = field(default_factory=dict)
    year_days: dict[int, tuple[int, int]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CupsComparison:
    """Year-over-year consumption comparison for an individual CUPS over comparable months."""

    cups: str
    yearly_kwh: dict[int, float]
    diff_kwh: float
    pct_change: float | None
    monthly_kwh: dict[int, dict[int, float]] = field(default_factory=dict)
    use: str = ""


@dataclass
class ComparisonSummary:
    """Complete multi-year consumption comparison summary for the residential community."""

    years: list[int]
    monthly_comparisons: list[MonthComparison]
    annual_totals: dict[int, float]
    comparable_annual_totals: dict[int, float]
    comparable_months: list[int]
    excluded_months: list[int]
    total_diff_kwh: float | None
    total_pct_change: float | None
    max_increase_month: MonthComparison | None
    max_decrease_month: MonthComparison | None
    top_saving_cups: CupsComparison | None
    top_increasing_cups: CupsComparison | None
    cups_comparisons: list[CupsComparison]
    cups_monthly_data: dict[str, dict[int, dict[int, float]]] = field(default_factory=dict)
    cups_uses: dict[str, str] = field(default_factory=dict)
