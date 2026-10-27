"""DATADIS hourly electricity consumption CSV parser and loader."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    REQUIRED_CONSUMPTION_COLUMNS,
    SUPPORTED_DELIMITERS,
    SUPPORTED_ENCODINGS,
)
from src.ingestion.schema import IngestionError, ParseError, ValidationError


class DatadisConsumptionLoader:
    """Discovers, validates, and normalizes DATADIS hourly consumption CSV files."""

    def __init__(self, consumption_dir: Path | str) -> None:
        self.consumption_dir = Path(consumption_dir)

    def discover_files(self) -> list[Path]:
        """Find all CSV files in the consumption directory."""
        if not self.consumption_dir.exists():
            raise IngestionError(f"Consumption directory not found: {self.consumption_dir}")

        files = sorted(self.consumption_dir.glob("*.csv"))
        if not files:
            raise IngestionError(
                f"No CSV files found in consumption directory: {self.consumption_dir}"
            )
        return files

    @staticmethod
    def detect_encoding(file_path: Path) -> str:
        """Detect file encoding from supported set."""
        raw_bytes = file_path.read_bytes()[:4096]
        for enc in SUPPORTED_ENCODINGS:
            try:
                raw_bytes.decode(enc)
                return enc
            except UnicodeDecodeError, LookupError:
                continue
        return "utf-8"

    @staticmethod
    def detect_delimiter(file_path: Path, encoding: str) -> str:
        """Detect CSV delimiter (semicolon, comma, tab)."""
        sample_text = file_path.read_text(encoding=encoding, errors="replace")[:4096]
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample_text, delimiters=";,\t")
            return dialect.delimiter
        except Exception:
            for delim in SUPPORTED_DELIMITERS:
                if delim in sample_text:
                    return delim
            return ";"

    @classmethod
    def parse_file(cls, file_path: Path) -> pd.DataFrame:
        """Parse a single DATADIS CSV file into a normalized DataFrame."""
        encoding = cls.detect_encoding(file_path)
        delimiter = cls.detect_delimiter(file_path, encoding)

        try:
            df = pd.read_csv(
                file_path,
                sep=delimiter,
                encoding=encoding,
                dtype=str,
            )
        except Exception as err:
            raise ParseError(f"Failed to parse CSV file {file_path.name}: {err}") from err

        # Normalize column names (strip whitespace and quotes)
        df.columns = [c.strip().strip('"').strip("'") for c in df.columns]

        # Case-insensitive column matching
        col_map = {c.lower(): c for c in df.columns}
        for req in REQUIRED_CONSUMPTION_COLUMNS:
            if req.lower() not in col_map:
                raise ValidationError(
                    f"File {file_path.name} missing required DATADIS column: '{req}'"
                )

        # Extract required columns
        cups_col = col_map["cups"]
        fecha_col = col_map["fecha"]
        hora_col = col_map["hora"]
        consumo_col = col_map["consumo_kwh"]

        clean_df = pd.DataFrame(
            {
                "cups": df[cups_col].astype(str).str.strip().str.strip('"'),
                "fecha": df[fecha_col].astype(str).str.strip().str.strip('"'),
                "hora": df[hora_col].astype(str).str.strip().str.strip('"'),
                "consumo_raw": df[consumo_col].astype(str).str.strip().str.strip('"'),
            }
        )

        # Parse numeric consumption (handling decimal comma or dot)
        clean_df["consumption_kwh"] = (
            clean_df["consumo_raw"].str.replace(" ", "").str.replace(",", ".").astype(float)
        )

        # Convert fecha and hora to interval-start canonical timestamps YYYY-MM-DD HH:MM:SS
        # Normalize date strings (YYYY-MM-DD, YYYY/MM/DD, DD/MM/YYYY, DD-MM-YYYY) to canonical YYYY-MM-DD
        norm_date = (
            clean_df["fecha"]
            .str.strip()
            .str.replace(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", r"\3-\2-\1", regex=True)
            .str.replace("/", "-", regex=False)
        )
        # Pad single-digit month and day if present (e.g. 2026-5-1 -> 2026-05-01)
        norm_date = norm_date.str.replace(r"^(\d{4})-(\d{1})-(\d{1,2})$", r"\1-0\2-\3", regex=True)
        norm_date = norm_date.str.replace(r"^(\d{4})-(\d{2})-(\d{1})$", r"\1-\2-0\3", regex=True)
        clean_df["fecha"] = norm_date

        # Parse hour integer from hora column (e.g. "01:00" -> 1)
        h_extracted = clean_df["hora"].str.split(":").str[0]
        h_series = pd.to_numeric(h_extracted, errors="coerce")

        group_cols = ["cups", "fecha"] if clean_df["cups"].nunique() > 1 else "fecha"
        idx_series = clean_df.groupby(group_cols, sort=False).cumcount()
        group_len = clean_df.groupby(group_cols, sort=False)["fecha"].transform("size")

        # Fallback for unparseable hora strings matches idx + 1
        h_series = h_series.fillna(idx_series + 1).astype(int)

        # Determine interval start hour based on DST transition rules
        # Case 1: 25-hour autumn DST transition (sequential intervals with duplicate hour 02:00)
        autumn_mask = group_len == 25
        h_autumn = np.where(idx_series <= 2, idx_series, idx_series - 1)

        # Case 2: 23-hour spring DST transition (hour 02:00 skipped, 03:00 -> 01:00)
        spring_mask = group_len == 23
        h_spring = np.where(h_series == 3, 1, np.clip(h_series - 1, 0, 23))

        # Case 3: Standard 24h day: 01:00 -> 00:00, 24:00 -> 23:00
        h_standard = np.clip(h_series - 1, 0, 23)

        h_start = np.where(
            autumn_mask,
            h_autumn,
            np.where(spring_mask, h_spring, h_standard),
        )

        h_str = pd.Series(h_start, index=clean_df.index).astype(str).str.zfill(2)
        clean_df["timestamp"] = norm_date + " " + h_str + ":00:00"
        return clean_df[["cups", "timestamp", "consumption_kwh"]]

    def load_all(self) -> pd.DataFrame:
        """Load, validate, and deduplicate all CSV files in the consumption directory.

        Returns:
            DataFrame with columns ['cups', 'timestamp', 'consumption_kwh'].
        """
        files = self.discover_files()
        dfs = []
        for f in files:
            dfs.append(self.parse_file(f))

        combined = pd.concat(dfs, ignore_index=True)

        # Deduplicate identical (cups, timestamp) readings, keeping latest
        combined = combined.drop_duplicates(subset=["cups", "timestamp"], keep="last")
        combined = combined.sort_values(by=["cups", "timestamp"]).reset_index(drop=True)
        return combined
