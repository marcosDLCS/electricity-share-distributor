"""DATADIS hourly electricity consumption CSV parser and loader."""

from __future__ import annotations

import csv
from pathlib import Path

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
            except (UnicodeDecodeError, LookupError):
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
        timestamps: list[str] = []
        for date_val, group in clean_df.groupby("fecha", sort=False):
            norm_date = date_val.replace("/", "-").strip()
            group_len = len(group)
            is_spring_dst = group_len == 23

            for idx, (_, row) in enumerate(group.iterrows()):
                hora_str = row["hora"]
                try:
                    h = int(hora_str.split(":")[0])
                except (ValueError, IndexError):
                    h = idx + 1

                if is_spring_dst and h >= 3:
                    # In 23-hour spring daylight saving switch:
                    # 01:00 -> 00:00
                    # 03:00 -> 01:00
                    # 04:00 -> 03:00
                    h_start = 1 if h == 3 else h - 1
                elif group_len == 25:
                    # In 25-hour autumn daylight saving switch:
                    # sequential 25 intervals
                    if idx <= 1:
                        h_start = idx
                    elif idx == 2:
                        h_start = 2
                    else:
                        h_start = idx - 1
                else:
                    # Standard 24h day: 01:00 -> 00:00, 24:00 -> 23:00
                    h_start = max(0, min(23, h - 1))

                timestamps.append(f"{norm_date} {h_start:02d}:00:00")

        clean_df["timestamp"] = timestamps
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
