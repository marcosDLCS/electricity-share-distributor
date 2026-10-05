"""Data diagnostic and health check engine for electricity-share-distributor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_CONSUMPTION_DIR, DEFAULT_GENERATION_DIR
from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.generation import HuaweiGenerationLoader


@dataclass
class GapInterval:
    """Represents a continuous gap of missing hourly intervals."""

    start_time: str
    end_time: str
    missing_hours: int


@dataclass
class SeriesCheckResult:
    """Diagnostic health summary for a single time series (CUPS or PV generation)."""

    identifier: str
    source_type: str  # "consumption" or "generation"
    files_count: int
    date_start: str | None = None
    date_end: str | None = None
    total_records: int = 0
    expected_hours: int = 0
    missing_hours: int = 0
    duplicate_records: int = 0
    negative_records: int = 0
    null_records: int = 0
    zero_ratio_pct: float = 0.0
    gaps: list[GapInterval] = field(default_factory=list)
    status: str = "ok"  # "ok", "warning", "error"
    notes: list[str] = field(default_factory=list)


@dataclass
class OverlapCheckResult:
    """Diagnostic check on time-series overlap between consumption and generation."""

    consumption_start: str | None = None
    consumption_end: str | None = None
    generation_start: str | None = None
    generation_end: str | None = None
    common_start: str | None = None
    common_end: str | None = None
    common_hours: int = 0
    participating_cups: list[str] = field(default_factory=list)
    cups_count: int = 0
    status: str = "ok"  # "ok", "warning", "error"
    notes: list[str] = field(default_factory=list)


@dataclass
class DoctorReport:
    """Comprehensive diagnostic report aggregating all data health checks."""

    consumption_results: list[SeriesCheckResult]
    generation_result: SeriesCheckResult | None
    overlap: OverlapCheckResult
    overall_status: str  # "ok", "warning", "error"
    can_calculate: bool
    summary_messages: list[str] = field(default_factory=list)


class DataDoctor:
    """Diagnostic engine to audit input data files, detecting gaps and anomalies."""

    def __init__(
        self,
        consumption_dir: Path | str = DEFAULT_CONSUMPTION_DIR,
        generation_dir: Path | str = DEFAULT_GENERATION_DIR,
    ) -> None:
        self.consumption_dir = Path(consumption_dir)
        self.generation_dir = Path(generation_dir)

    def diagnose(self) -> DoctorReport:
        """Execute full diagnostics across consumption and generation datasets."""
        consumption_results: list[SeriesCheckResult] = []
        gen_result: SeriesCheckResult | None = None
        summary_messages: list[str] = []

        # 1. Check directories existence
        if not self.consumption_dir.exists():
            return DoctorReport(
                consumption_results=[],
                generation_result=None,
                overlap=OverlapCheckResult(
                    status="error",
                    notes=[f"Consumption directory not found: {self.consumption_dir}"],
                ),
                overall_status="error",
                can_calculate=False,
                summary_messages=[f"Consumption directory not found: {self.consumption_dir}"],
            )

        if not self.generation_dir.exists():
            return DoctorReport(
                consumption_results=[],
                generation_result=None,
                overlap=OverlapCheckResult(
                    status="error",
                    notes=[f"Generation directory not found: {self.generation_dir}"],
                ),
                overall_status="error",
                can_calculate=False,
                summary_messages=[f"Generation directory not found: {self.generation_dir}"],
            )

        # 2. Check Consumption Files
        c_loader = DatadisConsumptionLoader(self.consumption_dir)
        c_files = c_loader.discover_files()
        c_df_all: pd.DataFrame | None = None

        if not c_files:
            summary_messages.append(f"No consumption CSV files found in {self.consumption_dir}")
        else:
            try:
                c_df_all = c_loader.load_all()
                cups_groups = c_df_all.groupby("cups")
                for cups, group in cups_groups:
                    diag = self._audit_time_series(
                        df=group,
                        identifier=str(cups),
                        source_type="consumption",
                        value_col="consumption_kwh",
                        files_count=len(c_files),
                    )
                    consumption_results.append(diag)
            except Exception as err:
                summary_messages.append(f"Failed parsing consumption files: {err}")

        # 3. Check Generation Files
        g_loader = HuaweiGenerationLoader(self.generation_dir)
        g_files = g_loader.discover_files()
        g_df: pd.DataFrame | None = None

        if not g_files:
            summary_messages.append(f"No generation Excel files found in {self.generation_dir}")
        else:
            try:
                g_df = g_loader.load_all()
                gen_result = self._audit_time_series(
                    df=g_df,
                    identifier="Huawei FusionSolar Generation",
                    source_type="generation",
                    value_col="generation_kwh",
                    files_count=len(g_files),
                )
            except Exception as err:
                summary_messages.append(f"Failed parsing generation files: {err}")

        # 4. Check Overlap & Cross-Alignment
        overlap = self._audit_overlap(consumption_results, gen_result, c_df_all, g_df)

        # 5. Determine Overall Health Status
        overall_status = "ok"
        can_calculate = True

        if not consumption_results or gen_result is None or overlap.common_hours == 0:
            overall_status = "error"
            can_calculate = False
        else:
            has_warnings = (
                any(c.status == "warning" for c in consumption_results)
                or (gen_result and gen_result.status == "warning")
                or overlap.status == "warning"
            )
            has_errors = (
                any(c.status == "error" for c in consumption_results)
                or (gen_result and gen_result.status == "error")
                or overlap.status == "error"
            )

            if has_errors:
                overall_status = "error"
            elif has_warnings:
                overall_status = "warning"

        return DoctorReport(
            consumption_results=consumption_results,
            generation_result=gen_result,
            overlap=overlap,
            overall_status=overall_status,
            can_calculate=can_calculate,
            summary_messages=summary_messages,
        )

    def _audit_time_series(
        self,
        df: pd.DataFrame,
        identifier: str,
        source_type: str,
        value_col: str,
        files_count: int,
    ) -> SeriesCheckResult:
        """Audit an individual time series for missing intervals, duplicates, and anomalies."""
        notes: list[str] = []
        status = "ok"

        total_records = len(df)
        if total_records == 0:
            return SeriesCheckResult(
                identifier=identifier,
                source_type=source_type,
                files_count=files_count,
                status="error",
                notes=["No records found in series."],
            )

        # Null checks
        null_count = int(df[value_col].isna().sum())
        if null_count > 0:
            notes.append(f"{null_count} null/NaN readings found.")
            status = "warning"

        # Negative checks
        valid_vals = df[value_col].dropna()
        neg_count = int((valid_vals < 0).sum())
        if neg_count > 0:
            notes.append(f"{neg_count} negative energy readings found.")
            status = "warning"

        # Zero activity check
        zero_count = int((valid_vals == 0).sum())
        zero_ratio = (zero_count / len(valid_vals) * 100.0) if len(valid_vals) > 0 else 0.0
        if zero_ratio >= 99.0 and source_type == "consumption":
            notes.append("Inactive meter: 99%+ of consumption readings are 0.0 kWh.")
            if status != "error":
                status = "warning"

        # Timestamps analysis
        ts_clean = df["timestamp"].astype(str)
        dup_count = int(ts_clean.duplicated().sum())
        if dup_count > 0:
            notes.append(f"{dup_count} duplicate timestamp readings found.")
            status = "warning"

        # Sort and inspect gaps
        sorted_ts = pd.to_datetime(ts_clean.drop_duplicates()).sort_values()
        date_start = sorted_ts.iloc[0].strftime("%Y-%m-%d %H:%M:%S")
        date_end = sorted_ts.iloc[-1].strftime("%Y-%m-%d %H:%M:%S")

        # Full hourly sequence from min to max
        full_range = pd.date_range(sorted_ts.iloc[0], sorted_ts.iloc[-1], freq="h")
        expected_hours = len(full_range)

        # Missing hours analysis
        all_missing = full_range.difference(sorted_ts)

        # Separate expected Spring DST skips (last Sunday of March at 02:00) from unexpected gaps
        unexpected_missing: list[pd.Timestamp] = []
        dst_shifts = 0

        for dt in all_missing:
            # Check if dt is the European spring DST skip (last Sunday of March, 02:00)
            if dt.month == 3 and dt.weekday() == 6 and dt.day >= 25 and dt.hour == 2:
                dst_shifts += 1
            else:
                unexpected_missing.append(dt)

        missing_hours = len(unexpected_missing)
        gaps: list[GapInterval] = []

        if dst_shifts > 0:
            notes.append(f"{dst_shifts} regulatory spring DST transition(s) detected (23h day).")

        if missing_hours > 0:
            status = "warning" if status != "error" else status
            notes.append(f"{missing_hours} unexpected missing hourly intervals detected.")

            missing_series = pd.Series(unexpected_missing).sort_values()
            gap_starts = [missing_series.iloc[0]]
            gap_ends: list[pd.Timestamp] = []

            for i in range(1, len(missing_series)):
                diff = missing_series.iloc[i] - missing_series.iloc[i - 1]
                if diff > pd.Timedelta(hours=1):
                    gap_ends.append(missing_series.iloc[i - 1])
                    gap_starts.append(missing_series.iloc[i])
            gap_ends.append(missing_series.iloc[-1])

            for g_start, g_end in zip(gap_starts, gap_ends, strict=True):
                g_hours = int((g_end - g_start) / pd.Timedelta(hours=1)) + 1
                gaps.append(
                    GapInterval(
                        start_time=g_start.strftime("%Y-%m-%d %H:%M"),
                        end_time=g_end.strftime("%Y-%m-%d %H:%M"),
                        missing_hours=g_hours,
                    )
                )

        if not notes:
            notes.append("All checks passed: zero gaps, no duplicates.")

        return SeriesCheckResult(
            identifier=identifier,
            source_type=source_type,
            files_count=files_count,
            date_start=date_start,
            date_end=date_end,
            total_records=total_records,
            expected_hours=expected_hours,
            missing_hours=missing_hours,
            duplicate_records=dup_count,
            negative_records=neg_count,
            null_records=null_count,
            zero_ratio_pct=round(zero_ratio, 1),
            gaps=gaps,
            status=status,
            notes=notes,
        )

    def _audit_overlap(
        self,
        c_results: list[SeriesCheckResult],
        g_result: SeriesCheckResult | None,
        c_df: pd.DataFrame | None,
        g_df: pd.DataFrame | None,
    ) -> OverlapCheckResult:
        """Audit the temporal intersection and alignment between consumption and generation."""
        notes: list[str] = []
        cups_list = [c.identifier for c in c_results]
        cups_count = len(cups_list)

        if not c_results or g_result is None or c_df is None or g_df is None:
            return OverlapCheckResult(
                status="error",
                cups_count=cups_count,
                participating_cups=cups_list,
                notes=["Cannot compute overlap: missing either consumption or generation data."],
            )

        c_starts = [pd.to_datetime(c.date_start) for c in c_results if c.date_start]
        c_ends = [pd.to_datetime(c.date_end) for c in c_results if c.date_end]

        if not c_starts or not c_ends or not g_result.date_start or not g_result.date_end:
            return OverlapCheckResult(
                status="error",
                cups_count=cups_count,
                participating_cups=cups_list,
                notes=["Invalid date bounds in time series."],
            )

        # Consumption overall date range
        c_min_start = min(c_starts)
        c_max_end = max(c_ends)

        # Generation date range
        g_start = pd.to_datetime(g_result.date_start)
        g_end = pd.to_datetime(g_result.date_end)

        # Common date range
        common_start_dt = max(c_min_start, g_start)
        common_end_dt = min(c_max_end, g_end)

        if common_start_dt > common_end_dt:
            notes.append("Zero date overlap between consumption and generation curves.")
            return OverlapCheckResult(
                consumption_start=c_min_start.strftime("%Y-%m-%d %H:%M:%S"),
                consumption_end=c_max_end.strftime("%Y-%m-%d %H:%M:%S"),
                generation_start=g_start.strftime("%Y-%m-%d %H:%M:%S"),
                generation_end=g_end.strftime("%Y-%m-%d %H:%M:%S"),
                common_start=None,
                common_end=None,
                common_hours=0,
                participating_cups=cups_list,
                cups_count=cups_count,
                status="error",
                notes=notes,
            )

        # Compute common hourly timestamps across generation and all CUPS
        g_ts_set = set(g_df["timestamp"].dropna().unique())
        # Filter consumption within common window
        c_in_window = c_df[
            (c_df["timestamp"] >= common_start_dt.strftime("%Y-%m-%d %H:%M:%S"))
            & (c_df["timestamp"] <= common_end_dt.strftime("%Y-%m-%d %H:%M:%S"))
        ]

        # Check intersection per CUPS
        cups_in_window = c_in_window["cups"].unique()
        if len(cups_in_window) < cups_count:
            notes.append(
                f"{cups_count - len(cups_in_window)} CUPS have no consumption data within the overlapping window."
            )

        # Common timestamps intersection
        c_piv = c_in_window.pivot(index="timestamp", columns="cups", values="consumption_kwh")
        common_intersection = c_piv.dropna().index.intersection(pd.Index(list(g_ts_set)))
        common_hours = len(common_intersection)

        status = "ok"
        if common_hours == 0:
            status = "error"
            notes.append("No common aligned hours found between datasets.")
        else:
            notes.append(
                f"{common_hours:,} synchronized hours ready for optimization across {len(cups_in_window)} CUPS."
            )

        return OverlapCheckResult(
            consumption_start=c_min_start.strftime("%Y-%m-%d %H:%M:%S"),
            consumption_end=c_max_end.strftime("%Y-%m-%d %H:%M:%S"),
            generation_start=g_start.strftime("%Y-%m-%d %H:%M:%S"),
            generation_end=g_end.strftime("%Y-%m-%d %H:%M:%S"),
            common_start=common_start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            common_end=common_end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            common_hours=common_hours,
            participating_cups=cups_list,
            cups_count=cups_count,
            status=status,
            notes=notes,
        )
