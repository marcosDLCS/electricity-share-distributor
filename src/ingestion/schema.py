"""Domain models, dataclasses, and custom exceptions for data ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.domain.exceptions import (
    AlignmentError as AlignmentError,
)
from src.domain.exceptions import (
    EsdError as EsdError,
)
from src.domain.exceptions import (
    IngestionError as IngestionError,
)
from src.domain.exceptions import (
    ValidationError as ValidationError,
)


class ParseError(IngestionError):
    """Raised when parsing CSV or Excel data formats fails."""


@dataclass(frozen=True)
class IngestionSummary:
    """Metadata summary of an ingested dataset.

    Attributes:
        cups_count: Number of unique supply point codes (CUPS) discovered.
        cups_list: List of CUPS identifiers.
        consumption_files_loaded: Number of consumption CSV files successfully parsed.
        generation_files_loaded: Number of generation Excel files successfully parsed.
        start_time: Earliest timestamp in the dataset.
        end_time: Latest timestamp in the dataset.
        total_hours: Total number of hourly time steps.
        missing_hours_count: Count of missing or filled intervals.
    """

    cups_count: int
    cups_list: list[str]
    consumption_files_loaded: int
    generation_files_loaded: int
    start_time: str
    end_time: str
    total_hours: int
    missing_hours_count: int = 0


@dataclass
class AlignedDataset:
    """Synchronized and validated time-series dataset combining consumption and PV generation.

    Attributes:
        data: DataFrame indexed by canonical hourly timestamps (YYYY-MM-DD HH:MM:SS),
            containing a column per CUPS (consumption in kWh) and a 'generation_kwh' column.
        cups_list: Sorted list of CUPS identifiers present in columns.
        metadata: Summary metadata describing the aligned dataset.
        monthly_groups: Dictionary mapping 'YYYY-MM' strings to filtered subset DataFrames.
        cups_uses: Mapping of CUPS identifiers to functional use descriptions if available.
    """

    data: pd.DataFrame
    cups_list: list[str]
    metadata: IngestionSummary
    monthly_groups: dict[str, pd.DataFrame] = field(default_factory=dict)
    cups_uses: dict[str, str] = field(default_factory=dict)
    primary_cups: str | None = None

    def get_month_data(self, year_month: str) -> pd.DataFrame:
        """Retrieve slice of aligned data for a specific 'YYYY-MM' month."""
        if year_month in self.monthly_groups:
            return self.monthly_groups[year_month]
        mask = self.data.index.str.startswith(year_month)
        month_df = self.data.loc[mask]
        self.monthly_groups[year_month] = month_df
        return month_df
