"""Pure typed data preparation layer for the neighbour-friendly interactive story HTML report."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import numpy as np
import pandas as pd

from src.ingestion.csv_utils import clean_numeric_series
from src.optimization.efficiency import calculate_solar_efficiency

if TYPE_CHECKING:
    from src.domain.models import SupplyPoint
    from src.ingestion.schema import AlignedDataset, IngestionSummary
    from src.optimization.models import CommunityMonthlyMetrics, OptimizationResult

CUPS_PALETTE: Final[tuple[str, ...]] = (
    "#0284c7",  # Sky Blue
    "#d97706",  # Warm Amber
    "#059669",  # Emerald
    "#7c3aed",  # Violet
    "#db2777",  # Rose
    "#0891b2",  # Cyan
    "#ea580c",  # Terracotta
    "#4f46e5",  # Indigo
    "#65a30d",  # Olive Lime
    "#be123c",  # Crimson
)

YEAR_PALETTE: Final[tuple[str, ...]] = (
    "#0284c7",
    "#d97706",
    "#059669",
    "#7c3aed",
    "#db2777",
    "#0891b2",
)

POINT_SHAPES: Final[tuple[str, ...]] = ("circle", "square", "diamond", "triangle")

STROKE_DASHES: Final[tuple[str, ...]] = ("", "6 4", "2 3", "10 4 2 4")


def parse_month_int(m_str: str) -> int:
    """Safely parse month integer from 'MM', 'YYYY-MM', or integer-like strings."""
    try:
        val = int(m_str.split("-")[-1]) if "-" in m_str else int(m_str)
        return max(1, min(12, val))
    except ValueError, TypeError:
        return 6


def _hare_niemeyer_percentages(values: list[float], decimals: int = 1) -> list[float]:
    """Round non-negative numbers into percentages summing strictly to 100.0 (or 0.0 if total == 0)."""
    if not values:
        return []
    total = sum(max(0.0, float(v)) for v in values)
    if total <= 0.0:
        return [0.0] * len(values)

    scale = 100 * (10**decimals)
    exact = [max(0.0, float(v)) / total * scale for v in values]
    floors = [int(x) for x in exact]
    remainders = [x - f for x, f in zip(exact, floors, strict=True)]
    deficit = scale - sum(floors)

    if deficit > 0:
        order = sorted(
            range(len(values)),
            key=lambda i: (-remainders[i], -exact[i], i),
        )
        for idx in order[:deficit]:
            floors[idx] += 1

    divisor = float(10**decimals)
    return [f / divisor for f in floors]


def _classify_month_status(
    year: int,
    month: int,
    unique_days: int,
    min_day: int,
    max_day: int,
    unique_hours: int,
) -> tuple[str, tuple[int, int]]:
    """Classify a year-month as 'no_data', 'complete', or 'incomplete' using the 90% rule."""
    days_in_month = calendar.monthrange(year, month)[1]
    if unique_days <= 0 or unique_hours <= 0:
        return "no_data", (0, days_in_month)

    expected_hours = days_in_month * 24
    is_complete = (
        min_day <= 2
        and max_day >= days_in_month - 1
        and unique_days >= int(days_in_month * 0.90)
        and unique_hours >= int(expected_hours * 0.90)
    )
    return ("complete" if is_complete else "incomplete"), (unique_days, days_in_month)


@dataclass(frozen=True, slots=True)
class ActiveCupsInfo:
    """Display summary for one active community CUPS in Chapter 1."""

    cups: str
    use: str
    primary: bool
    min_share: float | None
    max_share: float | None
    annual_consumption_kwh: float
    consumption_share_pct: float
    avg_solar_beta_pct: float
    color: str


@dataclass(frozen=True, slots=True)
class MonthlySeriesYear:
    """Twelve-month calendar series for a single year with completeness metadata."""

    year: int
    values: list[float | None]
    statuses: list[str]
    days: list[tuple[int, int]]
    annual_total_kwh: float
    complete_months_count: int


@dataclass(frozen=True, slots=True)
class ConsumptionHistoryData:
    """Multi-year community and per-CUPS consumption history for interactive charts."""

    years: list[int]
    cups_order: list[str]
    community: dict[int, MonthlySeriesYear]
    by_cups: dict[str, dict[int, MonthlySeriesYear]]
    reference_period_label: str
    reconciled_hours_count: int
    recovered_kwh: float
    reference_year_is_complete: bool = True


@dataclass(frozen=True, slots=True)
class GenerationHistoryData:
    """Multi-year solar PV generation history plus optional daylight demand overlay."""

    years: list[int]
    by_year: dict[int, MonthlySeriesYear]
    solar_hours_demand_by_month: list[float | None]


@dataclass(frozen=True, slots=True)
class SeasonalSpotlightSide:
    """Single seasonal snapshot (Winter or Summer) for Chapter 4 spotlight."""

    season: str
    month_code: str
    generation_kwh: float
    consumption_kwh: float
    self_consumed_kwh: float
    shares: list[tuple[str, str, float, str]]


@dataclass(frozen=True, slots=True)
class SeasonalSpotlight:
    """Side-by-side Winter vs. Summer coefficient comparison."""

    winter: SeasonalSpotlightSide | None
    summer: SeasonalSpotlightSide | None
    top_mover_cups: str
    top_mover_use: str
    top_mover_winter_pct: float
    top_mover_summer_pct: float


@dataclass(frozen=True, slots=True)
class FortnightMatrixData:
    """24 half-month (01-1..12-2) distribution matrix data."""

    cups_list: list[str]
    cups_uses: dict[str, str]
    periods: list[str]
    matrix: dict[str, dict[str, float | None]]
    period_sums: dict[str, float | None]
    has_fortnight_data: bool


@dataclass(frozen=True, slots=True)
class WeatherYearData:
    """Monthly temperature, clear-sky, and day classification summary for one year."""

    year: int
    temp_avg: list[float | None]
    temp_min: list[float | None]
    temp_max: list[float | None]
    clear_sky_pct: list[float | None]
    cloud_cover_pct: list[float | None]
    statuses: list[str]
    days: list[tuple[int, int]]
    annual_avg_temp: float | None
    annual_avg_clear_pct: float | None
    annual_avg_cloud_pct: float | None
    sunny_days: int
    cloudy_days: int
    rainy_days: int
    has_weather_codes: bool
    partly_cloudy_days: int = 0
    observed_days: int = 0
    abs_min_temp: float | None = None
    abs_max_temp: float | None = None
    cold_days: int = 0
    frost_days: int = 0
    hot_days: int = 0
    monthly_sunny_days: list[int | None] = field(default_factory=lambda: [None] * 12)
    monthly_partly_days: list[int | None] = field(default_factory=lambda: [None] * 12)
    monthly_cloudy_days: list[int | None] = field(default_factory=lambda: [None] * 12)
    monthly_rainy_days: list[int | None] = field(default_factory=lambda: [None] * 12)


@dataclass(frozen=True, slots=True)
class WeatherEnergyInsights:
    """Cross-insights linking local weather patterns to community consumption and PV generation."""

    cold_month_avg_kwh: float | None
    mild_month_avg_kwh: float | None
    cold_vs_mild_ratio: float | None
    sunniest_month_code: str
    sunniest_month_clear_pct: float | None
    cloudiest_month_code: str
    cloudiest_month_clear_pct: float | None
    peak_solar_month_code: str
    peak_solar_month_clear_pct: float | None
    peak_solar_month_temp: float | None


@dataclass(frozen=True, slots=True)
class WeatherHistoryData:
    """Multi-year weather history strictly scoped to the analyzed years."""

    years: list[int]
    by_year: dict[int, WeatherYearData]
    has_data: bool
    insights: WeatherEnergyInsights | None = None


@dataclass(frozen=True, slots=True)
class StoryReportContext:
    """Aggregated data context powering the neighbour-friendly storytelling report."""

    active_cups: list[ActiveCupsInfo]
    consumption_history: ConsumptionHistoryData
    generation_history: GenerationHistoryData
    seasonal_spotlight: SeasonalSpotlight
    fortnight_matrix: FortnightMatrixData
    has_multi_year_consumption: bool
    has_multi_year_generation: bool
    weather_history: WeatherHistoryData = field(
        default_factory=lambda: WeatherHistoryData(years=[], by_year={}, has_data=False)
    )


def calculate_hourly_prevision(
    opt_result: OptimizationResult,
) -> dict[str, bool | int | float | str]:
    """Read 4-way self-consumption progression metrics directly from OptimizationResult.

    Covers all four operational modalities without re-parsing time-series DataFrames:
    1. Current Self-Consumption (single CUPS tied behind inverter meter)
    2. Fixed Monthly Share (Real Decreto 244/2019)
    3. Fortnight Share (24 half-month periods)
    4. Dynamic Hourly Share (Orden TED/1247/2021)
    """
    tot = opt_result.total_summary
    tot_gen = tot.total_generation_kwh
    tot_dem = tot.total_consumption_kwh
    monthly_sc = (
        opt_result.monthly_share_self_consumed_kwh
        if opt_result.monthly_share_self_consumed_kwh > 0
        else tot.total_self_consumed_kwh
    )

    primary_cups: str | None = opt_result.primary_cups
    if primary_cups and opt_result.cups_list and primary_cups not in opt_result.cups_list:
        primary_cups = None
    if not primary_cups and opt_result.cups_list:
        primary_cups = opt_result.cups_list[0]
    primary_name: str = opt_result.cups_uses.get(primary_cups, "") if primary_cups else ""

    if opt_result.current_self_consumed_kwh > 0:
        single_sc_val = opt_result.current_self_consumed_kwh
    else:
        pri_metric = (
            next((c for c in tot.cups_metrics if c.cups == primary_cups), None)
            if primary_cups
            else None
        )
        single_sc_val = float(pri_metric.self_consumed_kwh) if pri_metric else 0.0
    single_sc = round(max(0.0, min(monthly_sc, single_sc_val)), 1)

    has_fortnight = opt_result.fortnight_share_self_consumed_kwh > 0
    if has_fortnight:
        fortnight_sc = round(
            max(0.0, min(tot_gen, min(tot_dem, opt_result.fortnight_share_self_consumed_kwh))),
            1,
        )
    else:
        fortnight_sc = round(max(0.0, min(tot_gen, min(tot_dem, monthly_sc))), 1)

    is_simulated = opt_result.hourly_share_self_consumed_kwh > 0
    if is_simulated:
        hourly_sc = round(
            max(0.0, min(tot_gen, min(tot_dem, opt_result.hourly_share_self_consumed_kwh))),
            1,
        )
    else:
        hourly_sc = round(max(0.0, min(tot_gen, min(tot_dem, max(monthly_sc, fortnight_sc)))), 1)

    single_sc_rate = (single_sc / max(tot_gen, 1e-6)) * 100.0
    single_surplus_kwh = max(0.0, tot_gen - single_sc)
    single_cov_rate = (single_sc / max(tot_dem, 1e-6)) * 100.0

    monthly_sc_rate = (
        (monthly_sc / max(tot_gen, 1e-6)) * 100.0 if tot_gen > 0 else tot.self_consumption_rate
    )
    monthly_surplus_kwh = max(0.0, tot_gen - monthly_sc) if tot_gen > 0 else tot.total_surplus_kwh
    monthly_cov_rate = (
        (monthly_sc / max(tot_dem, 1e-6)) * 100.0 if tot_dem > 0 else tot.solar_coverage_rate
    )

    fortnight_sc_rate = (fortnight_sc / max(tot_gen, 1e-6)) * 100.0
    fortnight_surplus_kwh = max(0.0, tot_gen - fortnight_sc)
    fortnight_cov_rate = (fortnight_sc / max(tot_dem, 1e-6)) * 100.0

    hourly_sc_rate = (hourly_sc / max(tot_gen, 1e-6)) * 100.0
    hourly_surplus_kwh = max(0.0, tot_gen - hourly_sc)
    hourly_cov_rate = (hourly_sc / max(tot_dem, 1e-6)) * 100.0

    gain_monthly_kwh = max(0.0, monthly_sc - single_sc)
    gain_monthly_pct = (gain_monthly_kwh / max(single_sc, 1e-6)) * 100.0

    gain_fortnight_kwh = max(0.0, fortnight_sc - single_sc)
    gain_fortnight_pct = (gain_fortnight_kwh / max(single_sc, 1e-6)) * 100.0

    gain_fortnight_vs_monthly_kwh = max(0.0, fortnight_sc - monthly_sc)
    gain_fortnight_vs_monthly_pct = (gain_fortnight_vs_monthly_kwh / max(monthly_sc, 1e-6)) * 100.0

    gain_hourly_kwh = max(0.0, hourly_sc - monthly_sc)
    gain_hourly_pct = (gain_hourly_kwh / max(monthly_sc, 1e-6)) * 100.0

    gain_total_kwh = max(0.0, hourly_sc - single_sc)
    gain_total_pct = (gain_total_kwh / max(single_sc, 1e-6)) * 100.0

    return {
        "primary_cups": primary_cups or "",
        "primary_name": primary_name or "Primary CUPS",
        "single_sc_kwh": single_sc,
        "single_sc_rate": round(single_sc_rate, 1),
        "single_surplus_kwh": round(single_surplus_kwh, 1),
        "single_cov_rate": round(single_cov_rate, 1),
        "monthly_sc_kwh": round(monthly_sc, 1),
        "monthly_sc_rate": round(monthly_sc_rate, 1),
        "monthly_surplus_kwh": round(monthly_surplus_kwh, 1),
        "monthly_cov_rate": round(monthly_cov_rate, 1),
        "gain_monthly_kwh": round(gain_monthly_kwh, 1),
        "gain_monthly_pct": round(gain_monthly_pct, 1),
        "has_fortnight": has_fortnight,
        "fortnight_sc_kwh": fortnight_sc,
        "fortnight_sc_rate": round(fortnight_sc_rate, 1),
        "fortnight_surplus_kwh": round(fortnight_surplus_kwh, 1),
        "fortnight_cov_rate": round(fortnight_cov_rate, 1),
        "gain_fortnight_kwh": round(gain_fortnight_kwh, 1),
        "gain_fortnight_pct": round(gain_fortnight_pct, 1),
        "gain_fortnight_vs_monthly_kwh": round(gain_fortnight_vs_monthly_kwh, 1),
        "gain_fortnight_vs_monthly_pct": round(gain_fortnight_vs_monthly_pct, 1),
        "hourly_sc_kwh": hourly_sc,
        "hourly_sc_rate": round(hourly_sc_rate, 1),
        "hourly_surplus_kwh": round(hourly_surplus_kwh, 1),
        "hourly_cov_rate": round(hourly_cov_rate, 1),
        "gain_hourly_kwh": round(gain_hourly_kwh, 1),
        "gain_hourly_pct": round(gain_hourly_pct, 1),
        "gain_total_kwh": round(gain_total_kwh, 1),
        "gain_total_pct": round(gain_total_pct, 1),
        "is_simulated": is_simulated,
        "gain_kwh": round(gain_hourly_kwh, 1),
        "gain_pct": round(gain_hourly_pct, 1),
    }


def calculate_monthly_efficiency(opt_result: OptimizationResult) -> list[dict[str, str | float]]:
    """Calculate average and peak solar efficiency index per calendar month."""
    active_months = [m for m in opt_result.monthly_results if m.has_data]
    active_m_strs = (
        [f"{i:02d}" for i in range(1, 13)]
        if not active_months
        else [m.month for m in active_months]
    )

    has_hourly = (
        opt_result.hourly_result is not None
        and opt_result.hourly_result.time_series_df is not None
        and not opt_result.hourly_result.time_series_df.empty
        and "solar_efficiency" in opt_result.hourly_result.time_series_df.columns
    )

    points: list[dict[str, str | float]] = []
    if has_hourly and opt_result.hourly_result is not None:
        df = opt_result.hourly_result.time_series_df
        sun_df = df[df["generation_kwh"] > 1e-6] if "generation_kwh" in df.columns else df
        m_stats = (
            sun_df.groupby(sun_df["timestamp"].str.slice(5, 7), sort=False)["solar_efficiency"].agg(
                ["mean", "max"]
            )
            if not sun_df.empty
            else None
        )
        ym_stats = None
        for m_str in active_m_strs:
            m_int = parse_month_int(m_str)
            m_2d = f"{m_int:02d}"
            row = None
            if m_stats is not None:
                if m_2d in m_stats.index:
                    row = m_stats.loc[m_2d]
                else:
                    if ym_stats is None:
                        ym_stats = sun_df.groupby(sun_df["timestamp"].str.slice(0, 7), sort=False)[
                            "solar_efficiency"
                        ].agg(["mean", "max"])
                    if m_str in ym_stats.index:
                        row = ym_stats.loc[m_str]

            if row is not None:
                avg_eff = float(row["mean"])
                peak_eff = float(row["max"])
            else:
                avg_eff = float(
                    sum(calculate_solar_efficiency(m_int, h) for h in range(8, 19)) / 11.0
                )
                peak_eff = float(calculate_solar_efficiency(m_int, 13))
            points.append(
                {
                    "month": m_str,
                    "avg_eff": round(avg_eff, 1),
                    "peak_eff": round(peak_eff, 1),
                }
            )
    else:
        for m_str in active_m_strs:
            m_int = parse_month_int(m_str)
            avg_eff = float(sum(calculate_solar_efficiency(m_int, h) for h in range(8, 19)) / 11.0)
            peak_eff = float(calculate_solar_efficiency(m_int, 13))
            points.append(
                {
                    "month": m_str,
                    "avg_eff": round(avg_eff, 1),
                    "peak_eff": round(peak_eff, 1),
                }
            )
    return points


def build_fortnight_matrix(opt_result: OptimizationResult) -> FortnightMatrixData:
    """Construct the 24 half-month (01-1..12-2) distribution coefficient matrix."""
    periods = [f"{m:02d}-{f}" for m in range(1, 13) for f in (1, 2)]
    has_fortnight_data = bool(
        opt_result.fortnight_results and any(f.has_data for f in opt_result.fortnight_results)
    )
    source_results = (
        opt_result.fortnight_results if opt_result.fortnight_results else opt_result.monthly_results
    )

    cups_set: list[str] = list(opt_result.cups_list)
    if not cups_set:
        seen: set[str] = set()
        for f_res in source_results:
            for cm in f_res.cups_metrics:
                if cm.cups not in seen:
                    seen.add(cm.cups)
                    cups_set.append(cm.cups)

    uses_map: dict[str, str] = dict(opt_result.cups_uses)
    matrix: dict[str, dict[str, float | None]] = {c: dict.fromkeys(periods, None) for c in cups_set}
    period_sums: dict[str, float | None] = dict.fromkeys(periods, None)

    for f_res in source_results:
        if not f_res.has_data or not f_res.cups_metrics:
            continue
        raw_period = str(f_res.month)
        if "-" in raw_period:
            parts = raw_period.split("-")
            if len(parts) == 2 and len(parts[0]) == 2:
                f_keys = [f"{parts[0]}-{parts[1].lstrip('Ff')}"]
            elif len(parts) >= 3:
                f_keys = [f"{parts[1]}-{parts[2].lstrip('Ff')}"]
            else:
                m_two = f"{parse_month_int(raw_period):02d}"
                f_keys = [f"{m_two}-1", f"{m_two}-2"]
        else:
            m_two = f"{parse_month_int(raw_period):02d}"
            f_keys = [f"{m_two}-1", f"{m_two}-2"]

        p_sum = 0.0
        for cm in f_res.cups_metrics:
            if cm.use and not uses_map.get(cm.cups):
                uses_map[cm.cups] = cm.use
            matrix.setdefault(cm.cups, dict.fromkeys(periods, None))
            for fk in f_keys:
                if fk in matrix[cm.cups]:
                    matrix[cm.cups][fk] = cm.beta
            p_sum += cm.beta
        for fk in f_keys:
            if fk in period_sums:
                period_sums[fk] = round(p_sum, 6)

    return FortnightMatrixData(
        cups_list=cups_set,
        cups_uses=uses_map,
        periods=periods,
        matrix=matrix,
        period_sums=period_sums,
        has_fortnight_data=has_fortnight_data,
    )


def _extract_calendar_columns(
    ts_series: pd.Series,
) -> tuple[pd.Series, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Factorize timestamp strings and extract year, month, day, and valid mask."""
    ts_clean = ts_series.astype(str).str.strip()
    codes, uniques = pd.factorize(ts_clean, sort=False)
    dt_uniq = pd.to_datetime(uniques, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    if dt_uniq.isna().any():
        missing = dt_uniq.isna()
        dt_uniq = dt_uniq.where(~missing, pd.to_datetime(uniques[missing], errors="coerce"))

    uniq_valid = ~dt_uniq.isna()
    valid_mask = (codes >= 0) & np.where(codes >= 0, uniq_valid[np.maximum(codes, 0)], False)
    year_uniq = dt_uniq.year.fillna(0).to_numpy(dtype=int)
    month_uniq = dt_uniq.month.fillna(0).to_numpy(dtype=int)
    day_uniq = dt_uniq.day.fillna(0).to_numpy(dtype=int)
    return ts_clean, codes, year_uniq, month_uniq, day_uniq, valid_mask


def _series_map_from_grouped(
    grouped: pd.DataFrame,
    years: list[int],
) -> dict[int, MonthlySeriesYear]:
    """Convert a (year, month) aggregated DataFrame into MonthlySeriesYear mapping."""
    out: dict[int, MonthlySeriesYear] = {}
    for yr in years:
        values: list[float | None] = []
        statuses: list[str] = []
        days: list[tuple[int, int]] = []
        annual_total = 0.0
        complete_cnt = 0
        for m in range(1, 13):
            if (yr, m) in grouped.index:
                row = grouped.loc[(yr, m)]
                val = round(float(row["sum_kwh"]), 2)
                status, day_pair = _classify_month_status(
                    yr,
                    m,
                    int(row["unique_days"]),
                    int(row["min_day"]),
                    int(row["max_day"]),
                    int(row["unique_hours"]),
                )
                values.append(val)
                statuses.append(status)
                days.append(day_pair)
                annual_total += val
                if status == "complete":
                    complete_cnt += 1
            else:
                exp_days = calendar.monthrange(yr, m)[1]
                values.append(None)
                statuses.append("no_data")
                days.append((0, exp_days))

        out[yr] = MonthlySeriesYear(
            year=yr,
            values=values,
            statuses=statuses,
            days=days,
            annual_total_kwh=round(annual_total, 2),
            complete_months_count=complete_cnt,
        )
    return out


def _empty_series_year(year: int) -> MonthlySeriesYear:
    """Create a 12-month no_data MonthlySeriesYear placeholder."""
    return MonthlySeriesYear(
        year=year,
        values=[None] * 12,
        statuses=["no_data"] * 12,
        days=[(0, calendar.monthrange(year, m)[1]) for m in range(1, 13)],
        annual_total_kwh=0.0,
        complete_months_count=0,
    )


def _fallback_year_from_summary(ingestion_summary: IngestionSummary) -> int:
    """Parse fallback calendar year from IngestionSummary start_time."""
    raw = str(getattr(ingestion_summary, "start_time", "") or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return 2026


def _prepare_consumption_df(
    consumption_df: pd.DataFrame | None,
    aligned_dataset: AlignedDataset | None,
    active_cups_set: set[str],
    primary_cups: str | None,
) -> tuple[pd.DataFrame | None, int, float]:
    """Normalize consumption DataFrame to active CUPS and reconcile primary CUPS behind-the-meter load."""
    recovered_kwh = 0.0
    reconciled_hours_count = 0

    df_src: pd.DataFrame | None = None
    if consumption_df is not None and not consumption_df.empty:
        ts_col = "timestamp" if "timestamp" in consumption_df.columns else None
        cups_col = (
            "cups_id"
            if "cups_id" in consumption_df.columns
            else ("cups" if "cups" in consumption_df.columns else None)
        )
        val_col = (
            "consumption"
            if "consumption" in consumption_df.columns
            else ("consumption_kwh" if "consumption_kwh" in consumption_df.columns else None)
        )
        if ts_col and cups_col and val_col:
            work = pd.DataFrame(
                {
                    "timestamp": consumption_df[ts_col],
                    "cups_id": consumption_df[cups_col].astype(str).str.strip(),
                    "_val": clean_numeric_series(consumption_df[val_col], fill_na=0.0).astype(
                        float
                    ),
                }
            )
            if active_cups_set:
                work = work[work["cups_id"].isin(active_cups_set)].copy()
            if not work.empty:
                df_src = work.reset_index(drop=True)
    elif aligned_dataset is not None and not aligned_dataset.data.empty:
        cups_cols = [
            c for c in aligned_dataset.cups_list if not active_cups_set or c in active_cups_set
        ]
        if cups_cols:
            sub = aligned_dataset.data[cups_cols].copy()
            sub.index.name = "timestamp"
            melted = sub.reset_index().melt(
                id_vars="timestamp",
                value_vars=cups_cols,
                var_name="cups_id",
                value_name="_val",
            )
            melted["_val"] = (
                pd.to_numeric(melted["_val"], errors="coerce").fillna(0.0).astype(float)
            )
            df_src = melted

    if df_src is None or df_src.empty:
        return None, 0, 0.0

    ts_clean, codes, year_uniq, month_uniq, day_uniq, valid_mask = _extract_calendar_columns(
        df_src["timestamp"]
    )
    if not bool(valid_mask.any()):
        return None, 0, 0.0

    df_valid = df_src.loc[valid_mask].copy()
    valid_codes = codes[valid_mask]
    df_valid["timestamp"] = ts_clean.loc[valid_mask]
    df_valid["_ts_code"] = valid_codes
    df_valid["_year"] = year_uniq[valid_codes]
    df_valid["_month"] = month_uniq[valid_codes]
    df_valid["_day"] = day_uniq[valid_codes]

    if (
        primary_cups
        and aligned_dataset is not None
        and not aligned_dataset.data.empty
        and primary_cups in aligned_dataset.data.columns
    ):
        aligned_pri = pd.to_numeric(aligned_dataset.data[primary_cups], errors="coerce").dropna()
        if not aligned_pri.empty:
            aligned_map: dict[str, float] = {
                str(idx).strip(): float(val) for idx, val in aligned_pri.items()
            }
            pri_mask = df_valid["cups_id"] == primary_cups
            if bool(pri_mask.any()):
                mapped = df_valid.loc[pri_mask, "timestamp"].map(aligned_map)
                has_match = mapped.notna()
                if bool(has_match.any()):
                    match_idx = mapped[has_match].index
                    raw_arr = df_valid.loc[match_idx, "_val"].to_numpy(dtype=float)
                    aln_arr = mapped.loc[match_idx].to_numpy(dtype=float)
                    new_arr = np.maximum(raw_arr, aln_arr)
                    diff_arr = np.maximum(0.0, new_arr - raw_arr)
                    recovered_kwh = round(float(np.sum(diff_arr)), 2)
                    reconciled_hours_count = int(np.sum(diff_arr > 0.001))
                    df_valid.loc[match_idx, "_val"] = new_arr

    return df_valid, reconciled_hours_count, recovered_kwh


def _build_consumption_history(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    active_cups_order: list[str],
    consumption_df: pd.DataFrame | None,
    aligned_dataset: AlignedDataset | None,
    primary_cups: str | None,
) -> ConsumptionHistoryData:
    """Build multi-year community and per-CUPS monthly consumption history."""
    active_set = set(active_cups_order)
    prepared, rec_hours, rec_kwh = _prepare_consumption_df(
        consumption_df=consumption_df,
        aligned_dataset=aligned_dataset,
        active_cups_set=active_set,
        primary_cups=primary_cups,
    )

    if prepared is not None and not prepared.empty:
        years = sorted(int(y) for y in prepared["_year"].unique())
        comm_grouped = prepared.groupby(["_year", "_month"], sort=True).agg(
            sum_kwh=("_val", "sum"),
            unique_days=("_day", "nunique"),
            min_day=("_day", "min"),
            max_day=("_day", "max"),
            unique_hours=("_ts_code", "nunique"),
        )
        community_series = _series_map_from_grouped(comm_grouped, years)

        cups_grouped = prepared.groupby(["cups_id", "_year", "_month"], sort=True).agg(
            sum_kwh=("_val", "sum"),
            unique_days=("_day", "nunique"),
            min_day=("_day", "min"),
            max_day=("_day", "max"),
            unique_hours=("_ts_code", "nunique"),
        )
        by_cups: dict[str, dict[int, MonthlySeriesYear]] = {}
        for cid in active_cups_order:
            if cid in cups_grouped.index.get_level_values(0):
                sub_grouped = cups_grouped.xs(cid, level=0)
                by_cups[cid] = _series_map_from_grouped(sub_grouped, years)
            else:
                by_cups[cid] = {yr: _empty_series_year(yr) for yr in years}
    else:
        fallback_year = _fallback_year_from_summary(ingestion_summary)
        years = [fallback_year]
        comm_vals: list[float | None] = [None] * 12
        comm_stat: list[str] = ["no_data"] * 12
        comm_days: list[tuple[int, int]] = [
            (0, calendar.monthrange(fallback_year, m)[1]) for m in range(1, 13)
        ]
        cups_vals: dict[str, list[float | None]] = {c: [None] * 12 for c in active_cups_order}
        cups_stat: dict[str, list[str]] = {c: ["no_data"] * 12 for c in active_cups_order}
        cups_days: dict[str, list[tuple[int, int]]] = {
            c: [(0, calendar.monthrange(fallback_year, m)[1]) for m in range(1, 13)]
            for c in active_cups_order
        }

        comm_total = 0.0
        complete_cnt = 0
        for m_res in opt_result.monthly_results:
            if not m_res.has_data:
                continue
            m_int = parse_month_int(m_res.month)
            idx = m_int - 1
            exp_days = calendar.monthrange(fallback_year, m_int)[1]
            val = round(float(m_res.total_consumption_kwh), 2)
            comm_vals[idx] = val
            comm_stat[idx] = "complete"
            comm_days[idx] = (exp_days, exp_days)
            comm_total += val
            complete_cnt += 1
            for cm in m_res.cups_metrics:
                if cm.cups in cups_vals:
                    cups_vals[cm.cups][idx] = round(float(cm.consumption_kwh), 2)
                    cups_stat[cm.cups][idx] = "complete"
                    cups_days[cm.cups][idx] = (exp_days, exp_days)

        community_series = {
            fallback_year: MonthlySeriesYear(
                year=fallback_year,
                values=comm_vals,
                statuses=comm_stat,
                days=comm_days,
                annual_total_kwh=round(comm_total, 2),
                complete_months_count=complete_cnt,
            )
        }
        by_cups = {}
        for cid in active_cups_order:
            c_tot = round(sum(v for v in cups_vals[cid] if v is not None), 2)
            c_cnt = sum(1 for st in cups_stat[cid] if st == "complete")
            by_cups[cid] = {
                fallback_year: MonthlySeriesYear(
                    year=fallback_year,
                    values=cups_vals[cid],
                    statuses=cups_stat[cid],
                    days=cups_days[cid],
                    annual_total_kwh=c_tot,
                    complete_months_count=c_cnt,
                )
            }

    full_years = [y for y in years if community_series[y].complete_months_count == 12]
    ref_year_is_complete = bool(full_years)
    if full_years:
        ref_year = max(full_years)
    else:
        ref_year = max(
            years,
            key=lambda y: (community_series[y].complete_months_count, y),
        )

    return ConsumptionHistoryData(
        years=years,
        cups_order=list(active_cups_order),
        community=community_series,
        by_cups=by_cups,
        reference_period_label=str(ref_year),
        reconciled_hours_count=rec_hours,
        recovered_kwh=rec_kwh,
        reference_year_is_complete=ref_year_is_complete,
    )


def _build_generation_history(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    generation_df: pd.DataFrame | None,
    aligned_dataset: AlignedDataset | None,
) -> GenerationHistoryData:
    """Build multi-year PV generation history plus optional daylight demand reference."""
    solar_demand_by_month: list[float | None] = [None] * 12
    for m_res in opt_result.monthly_results:
        if m_res.has_data:
            idx = parse_month_int(m_res.month) - 1
            sol_dem = (
                m_res.solar_hours_consumption_kwh
                if m_res.solar_hours_consumption_kwh > 0
                else m_res.total_consumption_kwh
            )
            solar_demand_by_month[idx] = round(float(sol_dem), 2)

    df_src: pd.DataFrame | None = None
    if generation_df is not None and not generation_df.empty:
        val_col = (
            "generation"
            if "generation" in generation_df.columns
            else ("generation_kwh" if "generation_kwh" in generation_df.columns else None)
        )
        if "timestamp" in generation_df.columns and val_col is not None:
            df_src = pd.DataFrame(
                {
                    "timestamp": generation_df["timestamp"],
                    "_val": clean_numeric_series(generation_df[val_col], fill_na=0.0).astype(float),
                }
            )
    elif (
        aligned_dataset is not None
        and not aligned_dataset.data.empty
        and "generation_kwh" in aligned_dataset.data.columns
    ):
        df_src = pd.DataFrame(
            {
                "timestamp": aligned_dataset.data.index,
                "_val": pd.to_numeric(aligned_dataset.data["generation_kwh"], errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float),
            }
        )

    if df_src is not None and not df_src.empty:
        _, codes, year_uniq, month_uniq, day_uniq, valid_mask = _extract_calendar_columns(
            df_src["timestamp"]
        )
        if bool(valid_mask.any()):
            df_valid = df_src.loc[valid_mask].copy()
            valid_codes = codes[valid_mask]
            df_valid["_ts_code"] = valid_codes
            df_valid["_year"] = year_uniq[valid_codes]
            df_valid["_month"] = month_uniq[valid_codes]
            df_valid["_day"] = day_uniq[valid_codes]
            years = sorted(int(y) for y in df_valid["_year"].unique())
            grouped = df_valid.groupby(["_year", "_month"], sort=True).agg(
                sum_kwh=("_val", "sum"),
                unique_days=("_day", "nunique"),
                min_day=("_day", "min"),
                max_day=("_day", "max"),
                unique_hours=("_ts_code", "nunique"),
            )
            by_year = _series_map_from_grouped(grouped, years)
            return GenerationHistoryData(
                years=years,
                by_year=by_year,
                solar_hours_demand_by_month=solar_demand_by_month,
            )

    fallback_year = _fallback_year_from_summary(ingestion_summary)
    vals: list[float | None] = [None] * 12
    statuses: list[str] = ["no_data"] * 12
    days: list[tuple[int, int]] = [
        (0, calendar.monthrange(fallback_year, m)[1]) for m in range(1, 13)
    ]
    total_gen = 0.0
    complete_cnt = 0
    for m_res in opt_result.monthly_results:
        if not m_res.has_data:
            continue
        m_int = parse_month_int(m_res.month)
        idx = m_int - 1
        exp_days = calendar.monthrange(fallback_year, m_int)[1]
        val = round(float(m_res.total_generation_kwh), 2)
        vals[idx] = val
        statuses[idx] = "complete"
        days[idx] = (exp_days, exp_days)
        total_gen += val
        complete_cnt += 1

    return GenerationHistoryData(
        years=[fallback_year],
        by_year={
            fallback_year: MonthlySeriesYear(
                year=fallback_year,
                values=vals,
                statuses=statuses,
                days=days,
                annual_total_kwh=round(total_gen, 2),
                complete_months_count=complete_cnt,
            )
        },
        solar_hours_demand_by_month=solar_demand_by_month,
    )


def _build_spotlight_side(
    season: str,
    m_res: CommunityMonthlyMetrics,
    cups_uses: dict[str, str],
    cups_colors: dict[str, str],
) -> SeasonalSpotlightSide:
    """Build one side (Winter or Summer) of the seasonal spotlight."""
    m_code = f"{parse_month_int(m_res.month):02d}"
    shares: list[tuple[str, str, float, str]] = [
        (
            cm.cups,
            cm.use or cups_uses.get(cm.cups, ""),
            round(cm.beta * 100.0, 1),
            cups_colors.get(cm.cups, CUPS_PALETTE[0]),
        )
        for cm in m_res.cups_metrics
    ]
    shares.sort(key=lambda item: (-item[2], item[1].lower(), item[0]))
    return SeasonalSpotlightSide(
        season=season,
        month_code=m_code,
        generation_kwh=round(m_res.total_generation_kwh, 1),
        consumption_kwh=round(m_res.total_consumption_kwh, 1),
        self_consumed_kwh=round(m_res.total_self_consumed_kwh, 1),
        shares=shares,
    )


def _build_seasonal_spotlight(
    opt_result: OptimizationResult,
    cups_uses: dict[str, str],
    cups_colors: dict[str, str],
) -> SeasonalSpotlight:
    """Select representative Winter and Summer months and identify the biggest seasonal mover."""
    active_months = [m for m in opt_result.monthly_results if m.has_data]
    if not active_months:
        return SeasonalSpotlight(
            winter=None,
            summer=None,
            top_mover_cups="",
            top_mover_use="",
            top_mover_winter_pct=0.0,
            top_mover_summer_pct=0.0,
        )

    winter_pool = [
        m for m in active_months if f"{parse_month_int(m.month):02d}" in ("01", "02", "12")
    ]
    summer_pool = [
        m for m in active_months if f"{parse_month_int(m.month):02d}" in ("06", "07", "08")
    ]

    winter_m = (
        max(winter_pool, key=lambda m: (m.total_consumption_kwh, -parse_month_int(m.month)))
        if winter_pool
        else min(active_months, key=lambda m: (m.total_generation_kwh, parse_month_int(m.month)))
    )
    summer_m = (
        max(summer_pool, key=lambda m: (m.total_generation_kwh, parse_month_int(m.month)))
        if summer_pool
        else max(active_months, key=lambda m: (m.total_generation_kwh, parse_month_int(m.month)))
    )

    w_code = f"{parse_month_int(winter_m.month):02d}"
    s_code = f"{parse_month_int(summer_m.month):02d}"
    if w_code == s_code:
        m_num = int(w_code)
        if 4 <= m_num <= 9:
            return SeasonalSpotlight(
                winter=None,
                summer=_build_spotlight_side("summer", summer_m, cups_uses, cups_colors),
                top_mover_cups="",
                top_mover_use="",
                top_mover_winter_pct=0.0,
                top_mover_summer_pct=0.0,
            )
        return SeasonalSpotlight(
            winter=_build_spotlight_side("winter", winter_m, cups_uses, cups_colors),
            summer=None,
            top_mover_cups="",
            top_mover_use="",
            top_mover_winter_pct=0.0,
            top_mover_summer_pct=0.0,
        )

    winter_side = _build_spotlight_side("winter", winter_m, cups_uses, cups_colors)
    summer_side = _build_spotlight_side("summer", summer_m, cups_uses, cups_colors)

    w_map = {c: pct for c, _, pct, _ in winter_side.shares}
    s_map = {c: pct for c, _, pct, _ in summer_side.shares}
    common_cups = sorted(set(w_map) | set(s_map))
    top_cups = ""
    top_use = ""
    top_w = 0.0
    top_s = 0.0
    best_delta = -1.0
    for cid in common_cups:
        wp = w_map.get(cid, 0.0)
        sp = s_map.get(cid, 0.0)
        delta = abs(sp - wp)
        if delta > best_delta:
            best_delta = delta
            top_cups = cid
            top_use = cups_uses.get(cid, "") or cid
            top_w = wp
            top_s = sp

    return SeasonalSpotlight(
        winter=winter_side,
        summer=summer_side,
        top_mover_cups=top_cups,
        top_mover_use=top_use,
        top_mover_winter_pct=top_w,
        top_mover_summer_pct=top_s,
    )


def _parse_daylight_mask(is_day_series: pd.Series, hours_series: pd.Series) -> pd.Series:
    """Resolve boolean daylight mask from is_day column, falling back to 08:00-19:00."""
    out: list[bool] = []
    for raw_val, hr in zip(is_day_series.tolist(), hours_series.tolist(), strict=False):
        if raw_val is not None and pd.notna(raw_val):
            if isinstance(raw_val, (bool, np.bool_)):
                out.append(bool(raw_val))
            elif isinstance(raw_val, (int, float, np.integer, np.floating)):
                out.append(float(raw_val) != 0.0)
            else:
                out.append(str(raw_val).strip().lower() in ("true", "1", "1.0", "yes"))
        else:
            out.append(8 <= int(hr) <= 19)
    return pd.Series(out, index=is_day_series.index, dtype=bool)


def _normalize_weather_source(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Parse timestamps and index deduplicated weather rows by canonical YYYY-MM-DD HH:MM:SS key."""
    ts_col = df_raw["timestamp"]
    if pd.api.types.is_datetime64_any_dtype(ts_col):
        dt_series = ts_col
    else:
        dt_series = pd.to_datetime(
            ts_col.astype(str).str.strip(), format="%Y-%m-%d %H:%M:%S", errors="coerce"
        )
        if dt_series.isna().any():
            missing = dt_series.isna()
            dt_series = dt_series.where(~missing, pd.to_datetime(ts_col[missing], errors="coerce"))

    valid_mask = dt_series.notna() & (
        df_raw["temperature"].notna()
        | df_raw["cloud_cover"].notna()
        | df_raw["weather_code"].notna()
    )
    if not bool(valid_mask.any()):
        return pd.DataFrame()

    work = df_raw.loc[valid_mask].copy()
    dt_valid = dt_series.loc[valid_mask]
    work["_year"] = dt_valid.dt.year.astype(int)
    work["_month"] = dt_valid.dt.month.astype(int)
    work["_day"] = dt_valid.dt.day.astype(int)
    work["_hour"] = dt_valid.dt.hour.astype(int)
    work["_ts_key"] = dt_valid.dt.strftime("%Y-%m-%d %H:%M:%S")
    return work.drop_duplicates(subset=["_ts_key"], keep="last").set_index("_ts_key")


def _extract_aligned_weather_df(aligned_dataset: AlignedDataset | None) -> pd.DataFrame | None:
    """Extract weather columns from AlignedDataset (sourced from master esd.csv)."""
    if aligned_dataset is None or aligned_dataset.data.empty:
        return None
    aln = aligned_dataset.data
    if (
        "temperature" not in aln.columns
        and "cloud_cover" not in aln.columns
        and "weather_code" not in aln.columns
    ):
        return None
    return pd.DataFrame(
        {
            "timestamp": aln.index,
            "temperature": (
                pd.to_numeric(aln["temperature"], errors="coerce").to_numpy()
                if "temperature" in aln.columns
                else np.full(len(aln), float("nan"))
            ),
            "cloud_cover": (
                pd.to_numeric(aln["cloud_cover"], errors="coerce").to_numpy()
                if "cloud_cover" in aln.columns
                else np.full(len(aln), float("nan"))
            ),
            "weather_code": (
                pd.to_numeric(aln["weather_code"], errors="coerce").to_numpy()
                if "weather_code" in aln.columns
                else np.full(len(aln), float("nan"))
            ),
            "is_day": (
                aln["is_day"].to_numpy() if "is_day" in aln.columns else np.full(len(aln), None)
            ),
        }
    )


def _extract_supplement_weather_df(weather_df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Extract supplemental pre-solar weather columns from cached weather CSV DataFrame."""
    if (
        weather_df is None
        or weather_df.empty
        or "timestamp" not in weather_df.columns
        or (
            "temperature" not in weather_df.columns
            and "cloud_cover" not in weather_df.columns
            and "weather_code" not in weather_df.columns
        )
    ):
        return None
    return pd.DataFrame(
        {
            "timestamp": weather_df["timestamp"],
            "temperature": (
                pd.to_numeric(weather_df["temperature"], errors="coerce")
                if "temperature" in weather_df.columns
                else pd.Series(float("nan"), index=weather_df.index)
            ),
            "cloud_cover": (
                pd.to_numeric(weather_df["cloud_cover"], errors="coerce")
                if "cloud_cover" in weather_df.columns
                else pd.Series(float("nan"), index=weather_df.index)
            ),
            "weather_code": (
                pd.to_numeric(weather_df["weather_code"], errors="coerce")
                if "weather_code" in weather_df.columns
                else pd.Series(float("nan"), index=weather_df.index)
            ),
            "is_day": (
                weather_df["is_day"]
                if "is_day" in weather_df.columns
                else pd.Series([None] * len(weather_df), index=weather_df.index, dtype=object)
            ),
        }
    )


def _build_weather_history(
    analyzed_years: list[int],
    weather_df: pd.DataFrame | None,
    aligned_dataset: AlignedDataset | None,
) -> WeatherHistoryData:
    """Build monthly weather summary prioritizing esd.csv (aligned_dataset) plus pre-solar weather_df."""
    aln_raw = _extract_aligned_weather_df(aligned_dataset)
    sup_raw = _extract_supplement_weather_df(weather_df)

    aln_norm = _normalize_weather_source(aln_raw) if aln_raw is not None else pd.DataFrame()
    sup_norm = _normalize_weather_source(sup_raw) if sup_raw is not None else pd.DataFrame()

    if aln_norm.empty and sup_norm.empty:
        return WeatherHistoryData(years=[], by_year={}, has_data=False)

    if aln_norm.empty:
        work = sup_norm.copy()
    elif sup_norm.empty:
        work = aln_norm.copy()
    else:
        combined_index = aln_norm.index.union(sup_norm.index, sort=False)
        a_reidx = aln_norm.reindex(combined_index)
        s_reidx = sup_norm.reindex(combined_index)
        work = pd.DataFrame(index=combined_index)
        for col in (
            "temperature",
            "cloud_cover",
            "weather_code",
            "is_day",
            "_year",
            "_month",
            "_day",
            "_hour",
        ):
            a_col = a_reidx[col].astype(object) if col == "is_day" else a_reidx[col]
            s_col = s_reidx[col].astype(object) if col == "is_day" else s_reidx[col]
            work[col] = a_col.where(a_col.notna(), s_col)

    work["_ts_key"] = work.index.astype(str)
    work = work.reset_index(drop=True)
    for int_col in ("_year", "_month", "_day", "_hour"):
        work[int_col] = pd.to_numeric(work[int_col], errors="coerce").astype(int)

    if analyzed_years:
        work = work[work["_year"].isin(analyzed_years)].copy()
    if work.empty:
        return WeatherHistoryData(years=[], by_year={}, has_data=False)

    work["_is_daylight"] = _parse_daylight_mask(work["is_day"], work["_hour"])
    years = sorted(int(y) for y in work["_year"].unique())
    by_year: dict[int, WeatherYearData] = {}

    for yr in years:
        yr_df = work[work["_year"] == yr]
        temp_avg: list[float | None] = []
        temp_min: list[float | None] = []
        temp_max: list[float | None] = []
        clear_sky_pct: list[float | None] = []
        cloud_cover_pct: list[float | None] = []
        statuses: list[str] = []
        days: list[tuple[int, int]] = []

        for m in range(1, 13):
            m_df = yr_df[yr_df["_month"] == m]
            if m_df.empty:
                exp_days = calendar.monthrange(yr, m)[1]
                temp_avg.append(None)
                temp_min.append(None)
                temp_max.append(None)
                clear_sky_pct.append(None)
                cloud_cover_pct.append(None)
                statuses.append("no_data")
                days.append((0, exp_days))
                continue

            unique_days = int(m_df["_day"].nunique())
            min_day = int(m_df["_day"].min())
            max_day = int(m_df["_day"].max())
            unique_hours = int(m_df["_ts_key"].nunique())
            status, day_pair = _classify_month_status(
                yr, m, unique_days, min_day, max_day, unique_hours
            )
            statuses.append(status)
            days.append(day_pair)

            valid_t = m_df.dropna(subset=["temperature"])
            if not valid_t.empty:
                temp_avg.append(round(float(valid_t["temperature"].mean()), 1))
                daily_t = valid_t.groupby("_day")["temperature"].agg(["min", "max"])
                temp_min.append(round(float(daily_t["min"].mean()), 1))
                temp_max.append(round(float(daily_t["max"].mean()), 1))
            else:
                temp_avg.append(None)
                temp_min.append(None)
                temp_max.append(None)

            day_cloud = m_df[m_df["_is_daylight"]]["cloud_cover"].dropna()
            cloud_series = day_cloud if not day_cloud.empty else m_df["cloud_cover"].dropna()
            if not cloud_series.empty:
                c_val = round(max(0.0, min(100.0, float(cloud_series.mean()))), 1)
                cloud_cover_pct.append(c_val)
                clear_sky_pct.append(round(100.0 - c_val, 1))
            else:
                cloud_cover_pct.append(None)
                clear_sky_pct.append(None)

        yr_t = yr_df["temperature"].dropna()
        ann_temp = round(float(yr_t.mean()), 1) if not yr_t.empty else None
        abs_min_temp = round(float(yr_t.min()), 1) if not yr_t.empty else None
        abs_max_temp = round(float(yr_t.max()), 1) if not yr_t.empty else None

        valid_t_rows = yr_df.dropna(subset=["temperature"])
        if not valid_t_rows.empty:
            daily_yr_t = valid_t_rows.groupby(["_month", "_day"])["temperature"].agg(
                ["mean", "min", "max"]
            )
            cold_days = int((daily_yr_t["mean"] < 10.0).sum())
            frost_days = int((daily_yr_t["min"] <= 0.0).sum())
            hot_days = int((daily_yr_t["max"] >= 30.0).sum())
        else:
            cold_days = 0
            frost_days = 0
            hot_days = 0

        yr_day_cloud = yr_df[yr_df["_is_daylight"]]["cloud_cover"].dropna()
        yr_cloud_all = yr_day_cloud if not yr_day_cloud.empty else yr_df["cloud_cover"].dropna()
        if not yr_cloud_all.empty:
            ann_cloud: float | None = round(max(0.0, min(100.0, float(yr_cloud_all.mean()))), 1)
            ann_clear: float | None = round(100.0 - ann_cloud, 1)
        else:
            ann_cloud = None
            ann_clear = None

        has_codes = bool(yr_df["weather_code"].notna().any())
        daylight_rows = yr_df[yr_df["_is_daylight"]]
        daylight_codes = (
            daylight_rows.groupby(["_month", "_day"])["weather_code"].max().to_dict()
            if has_codes and not daylight_rows.empty
            else {}
        )
        all_codes = (
            yr_df.groupby(["_month", "_day"])["weather_code"].max().to_dict() if has_codes else {}
        )
        day_cloud_src = daylight_rows if not daylight_rows.empty else yr_df
        day_clouds = day_cloud_src.groupby(["_month", "_day"])["cloud_cover"].mean().to_dict()
        all_day_keys = sorted(
            set(zip(yr_df["_month"].tolist(), yr_df["_day"].tolist(), strict=False))
        )

        month_day_counts: dict[int, list[int]] = {m: [0, 0, 0, 0] for m in range(1, 13)}
        for d_key in all_day_keys:
            m_num = int(d_key[0])
            w_code = daylight_codes.get(d_key)
            if w_code is None or pd.isna(w_code):
                w_code = all_codes.get(d_key)
            if has_codes and w_code is not None and pd.notna(w_code):
                code_int = round(float(w_code))
                if code_int >= 51:
                    month_day_counts[m_num][3] += 1  # Rainy / Precipitation
                elif code_int <= 1:
                    month_day_counts[m_num][0] += 1  # Sunny / Mainly clear (0, 1)
                elif code_int == 2:
                    month_day_counts[m_num][1] += 1  # Partly cloudy (2)
                else:
                    month_day_counts[m_num][2] += 1  # Overcast / Fog (3, 45, 48, ...)
            else:
                c_mean = day_clouds.get(d_key)
                if c_mean is not None and pd.notna(c_mean):
                    c_val_f = float(c_mean)
                    if c_val_f < 30.0:
                        month_day_counts[m_num][0] += 1
                    elif c_val_f >= 70.0:
                        month_day_counts[m_num][2] += 1
                    else:
                        month_day_counts[m_num][1] += 1
                else:
                    month_day_counts[m_num][1] += 1

        sunny_days = sum(month_day_counts[m][0] for m in range(1, 13))
        partly_cloudy_days = sum(month_day_counts[m][1] for m in range(1, 13))
        cloudy_days = sum(month_day_counts[m][2] for m in range(1, 13))
        rainy_days = sum(month_day_counts[m][3] for m in range(1, 13))
        observed_days = len(all_day_keys)

        monthly_sunny: list[int | None] = [
            month_day_counts[m][0] if statuses[m - 1] != "no_data" else None for m in range(1, 13)
        ]
        monthly_partly: list[int | None] = [
            month_day_counts[m][1] if statuses[m - 1] != "no_data" else None for m in range(1, 13)
        ]
        monthly_cloudy: list[int | None] = [
            month_day_counts[m][2] if statuses[m - 1] != "no_data" else None for m in range(1, 13)
        ]
        monthly_rainy: list[int | None] = [
            month_day_counts[m][3] if statuses[m - 1] != "no_data" else None for m in range(1, 13)
        ]

        by_year[yr] = WeatherYearData(
            year=yr,
            temp_avg=temp_avg,
            temp_min=temp_min,
            temp_max=temp_max,
            clear_sky_pct=clear_sky_pct,
            cloud_cover_pct=cloud_cover_pct,
            statuses=statuses,
            days=days,
            annual_avg_temp=ann_temp,
            annual_avg_clear_pct=ann_clear,
            annual_avg_cloud_pct=ann_cloud,
            sunny_days=sunny_days,
            cloudy_days=cloudy_days,
            rainy_days=rainy_days,
            has_weather_codes=has_codes,
            partly_cloudy_days=partly_cloudy_days,
            observed_days=observed_days,
            abs_min_temp=abs_min_temp,
            abs_max_temp=abs_max_temp,
            cold_days=cold_days,
            frost_days=frost_days,
            hot_days=hot_days,
            monthly_sunny_days=monthly_sunny,
            monthly_partly_days=monthly_partly,
            monthly_cloudy_days=monthly_cloudy,
            monthly_rainy_days=monthly_rainy,
        )

    return WeatherHistoryData(years=years, by_year=by_year, has_data=bool(by_year))


def _build_weather_energy_insights(
    weather_by_year: dict[int, WeatherYearData],
    consumption_history: ConsumptionHistoryData,
    generation_history: GenerationHistoryData,
) -> WeatherEnergyInsights | None:
    """Compute cross-insights linking local weather with community consumption and PV generation."""
    if not weather_by_year:
        return None

    cold_vals: list[float] = []
    mild_vals: list[float] = []
    month_clear_lists: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    month_temp_lists: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    month_gen_lists: dict[int, list[float]] = {m: [] for m in range(1, 13)}

    for yr, wy in weather_by_year.items():
        comm_yr = consumption_history.community.get(yr)
        for m_idx in range(12):
            m_num = m_idx + 1
            t_avg = wy.temp_avg[m_idx]
            clr = wy.clear_sky_pct[m_idx]
            if clr is not None and wy.statuses[m_idx] != "no_data":
                month_clear_lists[m_num].append(float(clr))
            if t_avg is not None and wy.statuses[m_idx] != "no_data":
                month_temp_lists[m_num].append(float(t_avg))

            if (
                t_avg is not None
                and wy.statuses[m_idx] != "no_data"
                and comm_yr is not None
                and comm_yr.statuses[m_idx] == "complete"
                and comm_yr.values[m_idx] is not None
            ):
                kwh = float(comm_yr.values[m_idx])
                if t_avg < 12.0:
                    cold_vals.append(kwh)
                elif 15.0 <= t_avg <= 23.0:
                    mild_vals.append(kwh)

    for gy in generation_history.by_year.values():
        for m_idx in range(12):
            g_val = gy.values[m_idx]
            if g_val is not None and gy.statuses[m_idx] != "no_data":
                month_gen_lists[m_idx + 1].append(float(g_val))

    cold_avg = round(sum(cold_vals) / len(cold_vals), 1) if cold_vals else None
    mild_avg = round(sum(mild_vals) / len(mild_vals), 1) if mild_vals else None
    cold_ratio = (
        round(cold_avg / mild_avg, 2)
        if cold_avg is not None and mild_avg is not None and mild_avg > 0
        else None
    )

    clear_avgs: dict[int, float] = {
        m: round(sum(vals) / len(vals), 1) for m, vals in month_clear_lists.items() if vals
    }
    if clear_avgs:
        sunniest_m = max(clear_avgs, key=lambda m: (clear_avgs[m], -m))
        cloudiest_m = min(clear_avgs, key=lambda m: (clear_avgs[m], m))
        sunniest_code = f"{sunniest_m:02d}"
        sunniest_clear: float | None = clear_avgs[sunniest_m]
        cloudiest_code = f"{cloudiest_m:02d}"
        cloudiest_clear: float | None = clear_avgs[cloudiest_m]
    else:
        sunniest_code = ""
        sunniest_clear = None
        cloudiest_code = ""
        cloudiest_clear = None

    gen_avgs: dict[int, float] = {
        m: sum(vals) / len(vals) for m, vals in month_gen_lists.items() if vals
    }
    if gen_avgs:
        peak_m = max(gen_avgs, key=lambda m: (gen_avgs[m], -m))
        peak_code = f"{peak_m:02d}"
        peak_clear: float | None = clear_avgs.get(peak_m)
        t_list = month_temp_lists.get(peak_m, [])
        peak_temp: float | None = round(sum(t_list) / len(t_list), 1) if t_list else None
    else:
        peak_code = ""
        peak_clear = None
        peak_temp = None

    return WeatherEnergyInsights(
        cold_month_avg_kwh=cold_avg,
        mild_month_avg_kwh=mild_avg,
        cold_vs_mild_ratio=cold_ratio,
        sunniest_month_code=sunniest_code,
        sunniest_month_clear_pct=sunniest_clear,
        cloudiest_month_code=cloudiest_code,
        cloudiest_month_clear_pct=cloudiest_clear,
        peak_solar_month_code=peak_code,
        peak_solar_month_clear_pct=peak_clear,
        peak_solar_month_temp=peak_temp,
    )


def build_story_context(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    cups_configs: dict[str, SupplyPoint] | None = None,
    consumption_df: pd.DataFrame | None = None,
    generation_df: pd.DataFrame | None = None,
    aligned_dataset: AlignedDataset | None = None,
    weather_df: pd.DataFrame | None = None,
) -> StoryReportContext:
    """Assemble the complete typed storytelling context without performing any disk I/O."""
    matrix = opt_result.build_matrix()

    if cups_configs:
        candidate_cups = list(cups_configs.keys())
    elif opt_result.cups_list:
        candidate_cups = list(opt_result.cups_list)
    else:
        candidate_cups = list(matrix.cups_list)

    if not candidate_cups and ingestion_summary.cups_list:
        candidate_cups = list(ingestion_summary.cups_list)

    cups_uses: dict[str, str] = dict(opt_result.cups_uses)
    if cups_configs:
        for cid, sp in cups_configs.items():
            if sp.use:
                cups_uses[cid] = sp.use

    primary_cups = opt_result.primary_cups
    if cups_configs:
        cfg_primary = next((sp.cups for sp in cups_configs.values() if sp.primary), None)
        if cfg_primary:
            primary_cups = cfg_primary

    consumption_history = _build_consumption_history(
        opt_result=opt_result,
        ingestion_summary=ingestion_summary,
        active_cups_order=candidate_cups,
        consumption_df=consumption_df,
        aligned_dataset=aligned_dataset,
        primary_cups=primary_cups,
    )

    ref_year = int(consumption_history.reference_period_label)
    tot_summary_map = {
        cm.cups: float(cm.consumption_kwh) for cm in opt_result.total_summary.cups_metrics
    }
    raw_ref_totals: dict[str, float] = {}
    has_ref_year_data = consumption_history.community[ref_year].annual_total_kwh > 0.0
    for cid in candidate_cups:
        yr_tot = consumption_history.by_cups.get(cid, {}).get(ref_year)
        if has_ref_year_data and yr_tot is not None:
            raw_ref_totals[cid] = yr_tot.annual_total_kwh
        else:
            raw_ref_totals[cid] = tot_summary_map.get(cid, 0.0)

    sorted_cups = sorted(
        candidate_cups,
        key=lambda c: (-raw_ref_totals.get(c, 0.0), cups_uses.get(c, "").lower(), c),
    )
    sorted_vals = [raw_ref_totals.get(c, 0.0) for c in sorted_cups]
    share_pcts = _hare_niemeyer_percentages(sorted_vals, decimals=1)

    cups_colors: dict[str, str] = {
        cid: CUPS_PALETTE[idx % len(CUPS_PALETTE)] for idx, cid in enumerate(sorted_cups)
    }

    active_cups: list[ActiveCupsInfo] = []
    for cid, c_kwh, share_pct in zip(sorted_cups, sorted_vals, share_pcts, strict=True):
        sp = cups_configs.get(cid) if cups_configs else None
        min_s: float | None = sp.min_share if sp is not None else None
        max_s: float | None = sp.max_share if sp is not None else None
        if sp is None and opt_result.constraints is not None:
            if cid in opt_result.constraints.cups_min_shares:
                min_s = opt_result.constraints.cups_min_shares[cid]
            if cid in opt_result.constraints.cups_max_shares:
                max_s = opt_result.constraints.cups_max_shares[cid]

        ann_beta = matrix.annual_shares.get(cid)
        avg_beta_pct = round(ann_beta * 100.0, 1) if ann_beta is not None else 0.0

        active_cups.append(
            ActiveCupsInfo(
                cups=cid,
                use=cups_uses.get(cid, ""),
                primary=(sp.primary if sp is not None else (cid == primary_cups)),
                min_share=min_s,
                max_share=max_s,
                annual_consumption_kwh=round(c_kwh, 2),
                consumption_share_pct=share_pct,
                avg_solar_beta_pct=avg_beta_pct,
                color=cups_colors[cid],
            )
        )

    # Align consumption_history.cups_order with sorted_cups so color & table order match
    consumption_history = ConsumptionHistoryData(
        years=consumption_history.years,
        cups_order=sorted_cups,
        community=consumption_history.community,
        by_cups=consumption_history.by_cups,
        reference_period_label=consumption_history.reference_period_label,
        reconciled_hours_count=consumption_history.reconciled_hours_count,
        recovered_kwh=consumption_history.recovered_kwh,
        reference_year_is_complete=consumption_history.reference_year_is_complete,
    )

    generation_history = _build_generation_history(
        opt_result=opt_result,
        ingestion_summary=ingestion_summary,
        generation_df=generation_df,
        aligned_dataset=aligned_dataset,
    )

    seasonal_spotlight = _build_seasonal_spotlight(
        opt_result=opt_result,
        cups_uses=cups_uses,
        cups_colors=cups_colors,
    )

    fortnight_matrix = build_fortnight_matrix(opt_result)

    analyzed_years = sorted(set(consumption_history.years) | set(generation_history.years))
    weather_raw = _build_weather_history(
        analyzed_years=analyzed_years,
        weather_df=weather_df,
        aligned_dataset=aligned_dataset,
    )
    weather_insights = _build_weather_energy_insights(
        weather_by_year=weather_raw.by_year,
        consumption_history=consumption_history,
        generation_history=generation_history,
    )
    weather_history = WeatherHistoryData(
        years=weather_raw.years,
        by_year=weather_raw.by_year,
        has_data=weather_raw.has_data,
        insights=weather_insights,
    )

    return StoryReportContext(
        active_cups=active_cups,
        consumption_history=consumption_history,
        generation_history=generation_history,
        seasonal_spotlight=seasonal_spotlight,
        fortnight_matrix=fortnight_matrix,
        has_multi_year_consumption=len(consumption_history.years) > 1,
        has_multi_year_generation=len(generation_history.years) > 1,
        weather_history=weather_history,
    )


def story_context_to_json_payload(
    ctx: StoryReportContext,
    opt_result: OptimizationResult,
    precision: int,
) -> dict[str, object]:
    """Serialize interactive story chart & simulator payloads cleanly into JSON-ready primitives."""
    matrix = opt_result.build_matrix()
    cons = ctx.consumption_history
    gen = ctx.generation_history
    weather = ctx.weather_history

    def _serialize_series(series: MonthlySeriesYear) -> dict[str, object]:
        return {
            "year": series.year,
            "values": series.values,
            "statuses": series.statuses,
            "days": [list(pair) for pair in series.days],
            "annual_total_kwh": series.annual_total_kwh,
            "complete_months_count": series.complete_months_count,
        }

    def _serialize_weather_year(w: WeatherYearData) -> dict[str, object]:
        return {
            "year": w.year,
            "temp_avg": w.temp_avg,
            "temp_min": w.temp_min,
            "temp_max": w.temp_max,
            "clear_sky_pct": w.clear_sky_pct,
            "cloud_cover_pct": w.cloud_cover_pct,
            "statuses": w.statuses,
            "days": [list(pair) for pair in w.days],
            "annual_avg_temp": w.annual_avg_temp,
            "annual_avg_clear_pct": w.annual_avg_clear_pct,
            "annual_avg_cloud_pct": w.annual_avg_cloud_pct,
            "sunny_days": w.sunny_days,
            "partly_cloudy_days": w.partly_cloudy_days,
            "cloudy_days": w.cloudy_days,
            "rainy_days": w.rainy_days,
            "observed_days": w.observed_days,
            "abs_min_temp": w.abs_min_temp,
            "abs_max_temp": w.abs_max_temp,
            "cold_days": w.cold_days,
            "frost_days": w.frost_days,
            "hot_days": w.hot_days,
            "monthly_sunny_days": w.monthly_sunny_days,
            "monthly_partly_days": w.monthly_partly_days,
            "monthly_cloudy_days": w.monthly_cloudy_days,
            "monthly_rainy_days": w.monthly_rainy_days,
            "has_weather_codes": w.has_weather_codes,
        }

    def _serialize_weather_insights(ins: WeatherEnergyInsights | None) -> dict[str, object] | None:
        if ins is None:
            return None
        return {
            "cold_month_avg_kwh": ins.cold_month_avg_kwh,
            "mild_month_avg_kwh": ins.mild_month_avg_kwh,
            "cold_vs_mild_ratio": ins.cold_vs_mild_ratio,
            "sunniest_month_code": ins.sunniest_month_code,
            "sunniest_month_clear_pct": ins.sunniest_month_clear_pct,
            "cloudiest_month_code": ins.cloudiest_month_code,
            "cloudiest_month_clear_pct": ins.cloudiest_month_clear_pct,
            "peak_solar_month_code": ins.peak_solar_month_code,
            "peak_solar_month_clear_pct": ins.peak_solar_month_clear_pct,
            "peak_solar_month_temp": ins.peak_solar_month_temp,
        }

    cups_meta = [
        {
            "cups": item.cups,
            "use": item.use,
            "primary": item.primary,
            "color": item.color,
            "annual_consumption_kwh": item.annual_consumption_kwh,
            "consumption_share_pct": item.consumption_share_pct,
        }
        for item in ctx.active_cups
    ]

    monthly_shares: dict[str, list[dict[str, object]]] = {}
    color_lookup = {item.cups: item.color for item in ctx.active_cups}
    use_lookup = {item.cups: item.use for item in ctx.active_cups}
    ordered_cups = [item.cups for item in ctx.active_cups] or list(matrix.cups_list)

    for m_str in matrix.months:
        if matrix.monthly_sums.get(m_str) is None:
            continue
        entries: list[dict[str, object]] = []
        for cid in ordered_cups:
            raw_beta = matrix.matrix.get(cid, {}).get(m_str)
            if raw_beta is None:
                continue
            pct = round(raw_beta * 100.0, precision)
            entries.append(
                {
                    "cups": cid,
                    "use": use_lookup.get(cid, matrix.cups_uses.get(cid, "")),
                    "pct": pct,
                    "color": color_lookup.get(cid, CUPS_PALETTE[0]),
                }
            )
        entries.sort(
            key=lambda item: (-float(item["pct"]), str(item["use"]).lower(), str(item["cups"]))
        )
        monthly_shares[m_str] = entries

    return {
        "cups": cups_meta,
        "year_palette": list(YEAR_PALETTE),
        "shapes": list(POINT_SHAPES),
        "dashes": list(STROKE_DASHES),
        "consumption": {
            "years": cons.years,
            "reference_year": int(cons.reference_period_label),
            "reference_year_is_complete": cons.reference_year_is_complete,
            "cups_order": cons.cups_order,
            "community": {str(y): _serialize_series(s) for y, s in cons.community.items()},
            "by_cups": {
                cid: {str(y): _serialize_series(s) for y, s in yr_map.items()}
                for cid, yr_map in cons.by_cups.items()
            },
        },
        "generation": {
            "years": gen.years,
            "by_year": {str(y): _serialize_series(s) for y, s in gen.by_year.items()},
            "solar_hours_demand_by_month": gen.solar_hours_demand_by_month,
        },
        "weather": {
            "has_data": weather.has_data,
            "years": weather.years,
            "by_year": {str(y): _serialize_weather_year(w) for y, w in weather.by_year.items()},
            "insights": _serialize_weather_insights(weather.insights),
        },
        "simulator": {
            "precision": precision,
            "active_months": sorted(monthly_shares.keys()),
            "monthly_shares": monthly_shares,
        },
    }
