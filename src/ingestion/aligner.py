"""Time-series synchronization and alignment between CUPS consumption and PV generation."""

from __future__ import annotations

import pandas as pd

from src.ingestion.schema import (
    AlignedDataset,
    AlignmentError,
    IngestionSummary,
)


class TimeSeriesAligner:
    """Synchronizes hourly time-series from DATADIS consumption and PV generation."""

    def __init__(
        self,
        consumption_df: pd.DataFrame,
        generation_df: pd.DataFrame,
        consumption_files_loaded: int = 0,
        generation_files_loaded: int = 0,
    ) -> None:
        self.consumption_df = consumption_df
        self.generation_df = generation_df
        self.consumption_files_loaded = consumption_files_loaded
        self.generation_files_loaded = generation_files_loaded

    def align(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> AlignedDataset:
        """Align consumption and generation datasets on common hourly timestamps.

        Args:
            year: Optional calendar year to filter (e.g. 2026).
            month: Optional calendar month to filter (1-12).

        Returns:
            AlignedDataset containing aligned DataFrame and summary metadata.

        Raises:
            AlignmentError: If no overlapping timestamps exist between datasets.
        """
        if self.consumption_df.empty:
            raise AlignmentError("Consumption dataset is empty.")
        if self.generation_df.empty:
            raise AlignmentError("Generation dataset is empty.")

        # Pivot consumption: index=timestamp, columns=cups, values=consumption_kwh
        pivot_cons = self.consumption_df.pivot(
            index="timestamp",
            columns="cups",
            values="consumption_kwh",
        )
        cups_list = sorted(pivot_cons.columns)

        # Prepare generation series
        gen_indexed = self.generation_df.set_index("timestamp")["generation_kwh"]

        # Intersect timestamps
        common_timestamps = pivot_cons.index.intersection(gen_indexed.index)
        if common_timestamps.empty:
            raise AlignmentError(
                "No overlapping hourly timestamps found between consumption and generation data.\n"
                f"Consumption range: {pivot_cons.index.min()} to {pivot_cons.index.max()}\n"
                f"Generation range:  {gen_indexed.index.min()} to {gen_indexed.index.max()}"
            )

        # Apply year / month filters if specified
        if year is not None:
            prefix = f"{year:04d}"
            if month is not None:
                prefix = f"{year:04d}-{month:02d}"
            common_timestamps = [ts for ts in common_timestamps if ts.startswith(prefix)]
            if not common_timestamps:
                raise AlignmentError(
                    f"No aligned data points found for specified filter (year={year}, month={month})."
                )
            common_timestamps = pd.Index(sorted(common_timestamps))
        elif month is not None:
            # Month without specific year: filter all matching months
            m_str = f"-{month:02d}-"
            common_timestamps = [ts for ts in common_timestamps if m_str in ts]
            if not common_timestamps:
                raise AlignmentError(f"No aligned data points found for month={month}.")
            common_timestamps = pd.Index(sorted(common_timestamps))

        # Build aligned DataFrame
        aligned_df = pivot_cons.loc[common_timestamps].copy()
        aligned_df["generation_kwh"] = gen_indexed.loc[common_timestamps]

        # Handle missing consumption values across CUPS (fill NaN with 0.0 and record count)
        missing_count = int(aligned_df[cups_list].isna().sum().sum())
        aligned_df[cups_list] = aligned_df[cups_list].fillna(0.0)

        # Sort chronologically
        aligned_df = aligned_df.sort_index()

        # Build metadata summary
        summary = IngestionSummary(
            cups_count=len(cups_list),
            cups_list=cups_list,
            consumption_files_loaded=self.consumption_files_loaded,
            generation_files_loaded=self.generation_files_loaded,
            start_time=str(aligned_df.index[0]),
            end_time=str(aligned_df.index[-1]),
            total_hours=len(aligned_df),
            missing_hours_count=missing_count,
        )

        # Group data by year-month
        monthly_groups: dict[str, pd.DataFrame] = {}
        for ym, group in aligned_df.groupby(aligned_df.index.str.slice(0, 7)):
            monthly_groups[ym] = group

        return AlignedDataset(
            data=aligned_df,
            cups_list=cups_list,
            metadata=summary,
            monthly_groups=monthly_groups,
        )
