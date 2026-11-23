"""Vectorized community consumption aggregation and fair-share analytics."""

from __future__ import annotations

import pandas as pd

from src.analytics.models import (
    AnnualConsumptionSummary,
    CommunityConsumptionSummary,
    CupsConsumptionShare,
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
        dt = pd.to_datetime(work["timestamp"], errors="coerce")
        valid_mask = dt.notna()
        if not valid_mask.any():
            raise EsdError("No valid timestamps found in consumption DataFrame.")

        work = work.loc[valid_mask].copy()
        dt_valid = dt.loc[valid_mask]
        work["date_str"] = dt_valid.dt.strftime("%Y-%m-%d")
        work["year"] = dt_valid.dt.year.astype(int)
        work["month"] = dt_valid.dt.month.astype(int)
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
