"""Vectorized community consumption aggregation and fair-share analytics."""

from __future__ import annotations

import calendar

import numpy as np
import pandas as pd

from src.analytics.models import (
    AnnualConsumptionSummary,
    CommunityConsumptionSummary,
    ComparisonSummary,
    CupsComparison,
    CupsConsumptionShare,
    MonthComparison,
    MonthlyConsumptionSummary,
)
from src.domain.exceptions import EsdError


class ConsumptionAggregator:
    """Aggregates normalized DATADIS consumption curves into community fair-share summaries."""

    @classmethod
    def _prepare_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Validate schema and enrich a shallow copy with calendar coordinates."""
        if df.empty:
            raise EsdError("Cannot aggregate an empty consumption DataFrame.")

        required = ["cups", "timestamp", "consumption_kwh"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise EsdError(f"Consumption DataFrame missing required columns: {', '.join(missing)}")

        work = df.copy()
        work["cups"] = work["cups"].astype(str).str.strip()
        ts_raw = work["timestamp"]
        codes, uniques = pd.factorize(ts_raw, sort=False)
        dt_uniq = pd.to_datetime(uniques, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        if dt_uniq.isna().any():
            missing_uniq = dt_uniq.isna()
            dt_uniq = dt_uniq.where(
                ~missing_uniq, pd.to_datetime(uniques[missing_uniq], errors="coerce")
            )

        uniq_valid = ~dt_uniq.isna()
        valid_mask = (codes >= 0) & (np.where(codes >= 0, uniq_valid[np.maximum(codes, 0)], False))
        if not bool(valid_mask.any()):
            raise EsdError("No valid timestamps found in consumption DataFrame.")

        work = work.loc[valid_mask].copy()
        valid_codes = codes[valid_mask]
        date_uniq = dt_uniq.strftime("%Y-%m-%d").to_numpy(dtype=object)
        year_uniq = dt_uniq.year.fillna(0).to_numpy(dtype=int)
        month_uniq = dt_uniq.month.fillna(0).to_numpy(dtype=int)
        work["date_str"] = date_uniq[valid_codes]
        work["year"] = year_uniq[valid_codes]
        work["month"] = month_uniq[valid_codes]
        work["consumption_kwh"] = (
            pd.to_numeric(work["consumption_kwh"], errors="coerce").fillna(0.0).astype(float)
        )
        return work

    @classmethod
    def _calculate_cups_shares(
        cls,
        df: pd.DataFrame,
        total_kwh: float,
        cups_uses: dict[str, str],
    ) -> list[CupsConsumptionShare]:
        """Compute vectorized consumption totals and exact 100.00% relative shares per CUPS."""
        grouped = (
            df.groupby("cups", sort=False)["consumption_kwh"].agg(["sum", "count"]).reset_index()
        )
        if grouped.empty:
            return []

        grouped = grouped.sort_values(by=["sum", "cups"], ascending=[False, True]).reset_index(
            drop=True
        )
        counts = grouped["count"].astype(int)
        safe_counts = counts.where(counts > 0, 1)
        avg_hourly = (grouped["sum"] / safe_counts).where(counts > 0, 0.0)
        if total_kwh > 0.0:
            share_pct = grouped["sum"] / total_kwh * 100.0
        else:
            share_pct = pd.Series(0.0, index=grouped.index, dtype=float)

        return [
            CupsConsumptionShare(
                cups=str(cups),
                consumption_kwh=float(kwh),
                share_pct=float(pct),
                readings_count=int(cnt),
                avg_hourly_kwh=float(avg_h),
                use=cups_uses.get(str(cups), ""),
            )
            for cups, kwh, pct, cnt, avg_h in zip(
                grouped["cups"],
                grouped["sum"],
                share_pct,
                counts,
                avg_hourly,
                strict=True,
            )
        ]

    @classmethod
    def aggregate_community(
        cls,
        df: pd.DataFrame,
        cups_uses: dict[str, str] | None = None,
    ) -> CommunityConsumptionSummary:
        """Aggregate total, annual, and monthly community consumption shares per CUPS."""
        work = cls._prepare_dataframe(df)
        uses = dict(cups_uses) if cups_uses else {}

        total_community_kwh = float(work["consumption_kwh"].sum())
        total_readings = len(work)
        unique_cups = sorted(work["cups"].unique().tolist())
        date_min = str(work["date_str"].min())
        date_max = str(work["date_str"].max())

        overall_cups_shares = cls._calculate_cups_shares(work, total_community_kwh, uses)

        monthly_summaries: list[MonthlyConsumptionSummary] = []
        month_totals: dict[str, float] = {}
        for (year_key, month_key), month_df in work.groupby(["year", "month"], sort=True):
            year_int = int(year_key)
            month_int = int(month_key)
            period_label = f"{year_int:04d}-{month_int:02d}"
            month_total_kwh = float(month_df["consumption_kwh"].sum())
            month_totals[period_label] = month_total_kwh

            shares = cls._calculate_cups_shares(month_df, month_total_kwh, uses)
            top_consumer = shares[0] if shares else CupsConsumptionShare("", 0.0, 0.0, 0, 0.0)
            monthly_summaries.append(
                MonthlyConsumptionSummary(
                    year=year_int,
                    month=month_int,
                    period_label=period_label,
                    community_total_kwh=month_total_kwh,
                    cups_shares=shares,
                    top_consumer=top_consumer,
                )
            )

        if month_totals:
            peak_month_label = max(month_totals, key=lambda k: month_totals[k])
            peak_month_kwh = month_totals[peak_month_label]
            lowest_month_label = min(month_totals, key=lambda k: month_totals[k])
            lowest_month_kwh = month_totals[lowest_month_label]
        else:
            peak_month_label = "N/A"
            peak_month_kwh = 0.0
            lowest_month_label = "N/A"
            lowest_month_kwh = 0.0

        annual_summaries: dict[int, AnnualConsumptionSummary] = {}
        for year_key, year_df in work.groupby("year", sort=True):
            year_int = int(year_key)
            year_total_kwh = float(year_df["consumption_kwh"].sum())
            year_shares = cls._calculate_cups_shares(year_df, year_total_kwh, uses)
            monthly_totals = {
                int(m): float(val)
                for m, val in year_df.groupby("month")["consumption_kwh"].sum().items()
            }
            top_consumer = (
                year_shares[0] if year_shares else CupsConsumptionShare("", 0.0, 0.0, 0, 0.0)
            )
            lowest_consumer = (
                year_shares[-1] if year_shares else CupsConsumptionShare("", 0.0, 0.0, 0, 0.0)
            )
            annual_summaries[year_int] = AnnualConsumptionSummary(
                year=year_int,
                period_label=str(year_int),
                community_total_kwh=year_total_kwh,
                cups_shares=year_shares,
                monthly_totals=monthly_totals,
                top_consumer=top_consumer,
                lowest_consumer=lowest_consumer,
            )

        return CommunityConsumptionSummary(
            total_community_kwh=total_community_kwh,
            total_readings=total_readings,
            unique_cups_count=len(unique_cups),
            cups_list=unique_cups,
            date_min=date_min,
            date_max=date_max,
            annual_summaries=annual_summaries,
            monthly_summaries=monthly_summaries,
            overall_cups_shares=overall_cups_shares,
            peak_month_label=peak_month_label,
            peak_month_kwh=peak_month_kwh,
            lowest_month_label=lowest_month_label,
            lowest_month_kwh=lowest_month_kwh,
            cups_uses=uses,
        )

    @classmethod
    def build_monthly_pivot(cls, df: pd.DataFrame, year: int | None = None) -> pd.DataFrame:
        """Build a CUPS-by-month consumption pivot table with Total_kWh and Share_% columns."""
        work = cls._prepare_dataframe(df)
        target_df = work if year is None else work[work["year"] == year]
        if target_df.empty:
            return pd.DataFrame()

        pivot = target_df.pivot_table(
            index="cups",
            columns="month",
            values="consumption_kwh",
            aggfunc="sum",
            fill_value=0.0,
        )
        pivot["Total_kWh"] = pivot.sum(axis=1)
        total_all = float(pivot["Total_kWh"].sum())
        pivot["Share_%"] = (pivot["Total_kWh"] / total_all * 100.0) if total_all > 0.0 else 0.0
        return pivot.sort_values(by="Total_kWh", ascending=False)

    @classmethod
    def compare_years(
        cls,
        df: pd.DataFrame,
        target_years: list[int] | None = None,
        cups_uses: dict[str, str] | None = None,
    ) -> ComparisonSummary:
        """Compare community consumption across multiple years using calendar completeness."""
        work = cls._prepare_dataframe(df)
        uses = dict(cups_uses) if cups_uses else {}

        available_years = sorted(work["year"].unique().tolist())
        if len(available_years) < 2:
            raise EsdError(
                f"At least two years are required for comparison; found only: {', '.join(map(str, available_years))}."
            )

        if target_years:
            missing = [y for y in target_years if y not in available_years]
            if missing:
                raise EsdError(
                    f"Requested year(s) {', '.join(map(str, missing))} not found in dataset. "
                    f"Available years: {', '.join(map(str, available_years))}."
                )
            selected_years = sorted(dict.fromkeys(target_years))
            if len(selected_years) < 2:
                raise EsdError("At least two distinct years must be selected for comparison.")
        else:
            selected_years = available_years

        filtered_df = work[work["year"].isin(selected_years)]
        earliest_year = selected_years[0]
        latest_year = selected_years[-1]

        monthly_sums = filtered_df.groupby(["year", "month"])["consumption_kwh"].sum().to_dict()
        monthly_days = filtered_df.groupby(["year", "month"])["date_str"].nunique().to_dict()

        monthly_comparisons: list[MonthComparison] = []
        for m in range(1, 13):
            if not any((y, m) in monthly_sums for y in selected_years):
                continue

            yearly_kwh: dict[int, float | None] = {}
            year_status: dict[int, str] = {}
            year_days: dict[int, tuple[int, int]] = {}
            all_years_complete = True

            for y in selected_years:
                expected_days = calendar.monthrange(y, m)[1]
                actual_days = int(monthly_days.get((y, m), 0))
                year_days[y] = (actual_days, expected_days)

                if (y, m) not in monthly_sums or actual_days == 0:
                    yearly_kwh[y] = None
                    year_status[y] = "no_data"
                    all_years_complete = False
                elif actual_days < expected_days:
                    yearly_kwh[y] = float(monthly_sums[(y, m)])
                    year_status[y] = "incomplete"
                    all_years_complete = False
                else:
                    yearly_kwh[y] = float(monthly_sums[(y, m)])
                    year_status[y] = "complete"

            if all_years_complete:
                base_kwh = float(yearly_kwh[earliest_year] or 0.0)
                target_kwh = float(yearly_kwh[latest_year] or 0.0)
                diff_kwh: float | None = target_kwh - base_kwh
                pct_change: float | None = (
                    ((diff_kwh / base_kwh) * 100.0)
                    if base_kwh > 0.0
                    else (0.0 if target_kwh == 0.0 else None)
                )
            else:
                diff_kwh = None
                pct_change = None

            monthly_comparisons.append(
                MonthComparison(
                    month=m,
                    yearly_kwh=yearly_kwh,
                    diff_kwh=diff_kwh,
                    pct_change=pct_change,
                    is_complete=all_years_complete,
                    year_status=year_status,
                    year_days=year_days,
                )
            )

        comparable_months = [m.month for m in monthly_comparisons if m.is_complete]
        excluded_months = [m.month for m in monthly_comparisons if not m.is_complete]

        raw_year_totals = filtered_df.groupby("year")["consumption_kwh"].sum().to_dict()
        annual_totals = {y: float(raw_year_totals.get(y, 0.0)) for y in selected_years}

        if comparable_months:
            comp_df = filtered_df[filtered_df["month"].isin(comparable_months)]
            comp_year_totals = comp_df.groupby("year")["consumption_kwh"].sum().to_dict()
            comparable_annual_totals = {
                y: float(comp_year_totals.get(y, 0.0)) for y in selected_years
            }
            total_diff_kwh: float | None = (
                comparable_annual_totals[latest_year] - comparable_annual_totals[earliest_year]
            )
            base_comp = comparable_annual_totals[earliest_year]
            total_pct_change: float | None = (
                ((total_diff_kwh / base_comp) * 100.0)
                if base_comp > 0.0
                else (0.0 if comparable_annual_totals[latest_year] == 0.0 else None)
            )
        else:
            comp_df = filtered_df
            comparable_annual_totals = dict.fromkeys(selected_years, 0.0)
            total_diff_kwh = None
            total_pct_change = None

        valid_months = [
            m for m in monthly_comparisons if m.is_complete and m.pct_change is not None
        ]
        max_increase_month = (
            max(valid_months, key=lambda m: m.pct_change or 0.0) if valid_months else None
        )
        if max_increase_month and (max_increase_month.pct_change or 0.0) <= 0.0:
            max_increase_month = None

        max_decrease_month = (
            min(valid_months, key=lambda m: m.pct_change or 0.0) if valid_months else None
        )
        if max_decrease_month and (max_decrease_month.pct_change or 0.0) >= 0.0:
            max_decrease_month = None

        all_cups = sorted(filtered_df["cups"].unique().tolist())
        cups_monthly_grouped = (
            filtered_df.groupby(["cups", "year", "month"])["consumption_kwh"].sum().to_dict()
        )
        cups_monthly_data: dict[str, dict[int, dict[int, float]]] = {}
        for cups_id in all_cups:
            cups_monthly_data[cups_id] = {
                y: {m: float(cups_monthly_grouped.get((cups_id, y, m), 0.0)) for m in range(1, 13)}
                for y in selected_years
            }

        cups_eval_grouped = comp_df.groupby(["cups", "year"])["consumption_kwh"].sum().to_dict()
        cups_comparisons: list[CupsComparison] = []
        for cups_id in all_cups:
            c_yearly = {y: float(cups_eval_grouped.get((cups_id, y), 0.0)) for y in selected_years}
            c_base = c_yearly[earliest_year]
            c_target = c_yearly[latest_year]
            c_diff = c_target - c_base
            c_pct = (
                ((c_diff / c_base) * 100.0) if c_base > 0.0 else (0.0 if c_target == 0.0 else None)
            )
            cups_comparisons.append(
                CupsComparison(
                    cups=cups_id,
                    yearly_kwh=c_yearly,
                    diff_kwh=c_diff,
                    pct_change=c_pct,
                    monthly_kwh=cups_monthly_data[cups_id],
                    use=uses.get(cups_id, ""),
                )
            )

        cups_comparisons.sort(key=lambda c: (c.diff_kwh, c.cups))
        top_saving_cups = (
            cups_comparisons[0] if cups_comparisons and cups_comparisons[0].diff_kwh < 0.0 else None
        )
        top_increasing_cups = (
            cups_comparisons[-1]
            if cups_comparisons and cups_comparisons[-1].diff_kwh > 0.0
            else None
        )

        return ComparisonSummary(
            years=selected_years,
            monthly_comparisons=monthly_comparisons,
            annual_totals=annual_totals,
            comparable_annual_totals=comparable_annual_totals,
            comparable_months=comparable_months,
            excluded_months=excluded_months,
            total_diff_kwh=total_diff_kwh,
            total_pct_change=total_pct_change,
            max_increase_month=max_increase_month,
            max_decrease_month=max_decrease_month,
            top_saving_cups=top_saving_cups,
            top_increasing_cups=top_increasing_cups,
            cups_comparisons=cups_comparisons,
            cups_monthly_data=cups_monthly_data,
            cups_uses=uses,
        )
