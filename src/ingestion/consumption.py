"""DATADIS hourly electricity consumption CSV validator, parser, and loader."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from src.config import REQUIRED_CONSUMPTION_COLUMNS
from src.ingestion.csv_utils import (
    clean_numeric_series,
    detect_file_encoding,
    is_autumn_dst_date,
    sniff_csv_delimiter,
)
from src.ingestion.schema import IngestionError, ParseError, ValidationError, ValidationResult

CONSUMPTION_COLUMN_ALIASES: Final[dict[str, str]] = {
    "cups": "cups",
    "fecha": "fecha",
    "hora": "hora",
    "consumo_kwh": "consumo_kWh",
    "consumokwh": "consumo_kWh",
}


def _clean_header(raw: str) -> str:
    """Strip UTF-8 BOM, surrounding whitespace, and quotes from a CSV header."""
    return raw.lstrip("\ufeff").strip().strip('"').strip("'")


class DatadisValidator:
    """Validates DATADIS consumption CSV files for encoding, delimiter, and schema conformance."""

    @classmethod
    def detect_encoding(cls, file_path: Path) -> str:
        """Detect file encoding from the supported set (UTF-8 BOM, UTF-8, Latin-1, CP1252)."""
        return detect_file_encoding(file_path)

    @classmethod
    def detect_delimiter(cls, file_path: Path, encoding: str) -> str:
        """Detect CSV delimiter (semicolon, comma, or tab)."""
        return sniff_csv_delimiter(file_path, encoding=encoding, default=";")

    @classmethod
    def validate_file(cls, file_path: Path) -> ValidationResult:
        """Validate a single DATADIS CSV file for existence, readability, columns, and rows."""
        if not file_path.exists() or not file_path.is_file():
            return ValidationResult(
                file_path=file_path,
                is_valid=False,
                error_message=f"File not found: {file_path}",
            )

        if file_path.stat().st_size == 0:
            return ValidationResult(
                file_path=file_path,
                is_valid=False,
                error_message="File is empty (0 bytes).",
            )

        encoding = cls.detect_encoding(file_path)
        delimiter = cls.detect_delimiter(file_path, encoding)

        try:
            with file_path.open(encoding=encoding, errors="replace") as handle:
                header_line = handle.readline()
                if not header_line:
                    return ValidationResult(
                        file_path=file_path,
                        is_valid=False,
                        delimiter=delimiter,
                        encoding=encoding,
                        error_message="File has no headers.",
                    )
                raw_headers = next(csv.reader([header_line], delimiter=delimiter), [])
                if not raw_headers:
                    return ValidationResult(
                        file_path=file_path,
                        is_valid=False,
                        delimiter=delimiter,
                        encoding=encoding,
                        error_message="File has no headers.",
                    )

                cleaned_headers = [_clean_header(h) for h in raw_headers]
                canonical_headers = {
                    CONSUMPTION_COLUMN_ALIASES.get(h.lower(), h) for h in cleaned_headers if h
                }
                missing = [
                    req for req in REQUIRED_CONSUMPTION_COLUMNS if req not in canonical_headers
                ]
                if missing:
                    return ValidationResult(
                        file_path=file_path,
                        is_valid=False,
                        delimiter=delimiter,
                        encoding=encoding,
                        detected_columns=cleaned_headers,
                        missing_columns=missing,
                        error_message=f"Missing required columns: {', '.join(missing)}",
                    )

                strip_chars = f" \t\r\n{delimiter}"
                row_count = sum(1 for line in handle if line.strip(strip_chars))
                if row_count == 0:
                    return ValidationResult(
                        file_path=file_path,
                        is_valid=False,
                        delimiter=delimiter,
                        encoding=encoding,
                        detected_columns=cleaned_headers,
                        total_rows=0,
                        error_message="File contains header but has zero data rows.",
                    )

                return ValidationResult(
                    file_path=file_path,
                    is_valid=True,
                    delimiter=delimiter,
                    encoding=encoding,
                    detected_columns=cleaned_headers,
                    total_rows=row_count,
                )
        except Exception as exc:
            return ValidationResult(
                file_path=file_path,
                is_valid=False,
                delimiter=delimiter,
                encoding=encoding,
                error_message=f"Error reading file: {exc}",
            )


class DatadisConsumptionLoader:
    """Discovers, validates, and normalizes DATADIS hourly consumption CSV files."""

    def __init__(self, consumption_dir: Path | str) -> None:
        self.consumption_dir = Path(consumption_dir)

    def _is_hidden_relative(self, file_path: Path) -> bool:
        """Return True if any path segment relative to consumption_dir starts with '.'."""
        rel_parts = file_path.relative_to(self.consumption_dir).parts
        return any(part.startswith(".") for part in rel_parts)

    def discover_files(self, year: int | None = None) -> list[Path]:
        """Recursively discover DATADIS CSV files under flat or annualized directories."""
        if not self.consumption_dir.exists():
            raise IngestionError(f"Consumption directory not found: {self.consumption_dir}")

        files: list[Path] = []
        if year is not None:
            year_dir = self.consumption_dir / str(year)
            if year_dir.exists() and year_dir.is_dir():
                files = [
                    p
                    for p in year_dir.rglob("*.csv")
                    if p.is_file() and not self._is_hidden_relative(p)
                ]

        if not files:
            files = [
                p
                for p in self.consumption_dir.rglob("*.csv")
                if p.is_file() and not self._is_hidden_relative(p)
            ]

        if not files:
            raise IngestionError(
                f"No CSV files found in consumption directory: {self.consumption_dir}"
            )
        return sorted(files)

    @staticmethod
    def detect_encoding(file_path: Path) -> str:
        """Detect file encoding from supported set."""
        return DatadisValidator.detect_encoding(file_path)

    @staticmethod
    def detect_delimiter(file_path: Path, encoding: str) -> str:
        """Detect CSV delimiter (semicolon, comma, tab)."""
        return DatadisValidator.detect_delimiter(file_path, encoding)

    @classmethod
    def parse_file(
        cls,
        file_path: Path,
        encoding: str | None = None,
        delimiter: str | None = None,
    ) -> pd.DataFrame:
        """Parse a single DATADIS CSV file into a normalized DataFrame."""
        enc = encoding or cls.detect_encoding(file_path)
        delim = delimiter or cls.detect_delimiter(file_path, enc)

        try:
            df = pd.read_csv(
                file_path,
                sep=delim,
                encoding=enc,
                dtype=str,
            )
        except Exception as err:
            raise ParseError(f"Failed to parse CSV file {file_path.name}: {err}") from err

        df.columns = [_clean_header(str(c)) for c in df.columns]

        canonical_map: dict[str, str] = {}
        for col in df.columns:
            canonical = CONSUMPTION_COLUMN_ALIASES.get(col.lower())
            if canonical and canonical not in canonical_map:
                canonical_map[canonical] = col

        for req in REQUIRED_CONSUMPTION_COLUMNS:
            if req not in canonical_map:
                raise ValidationError(
                    f"File {file_path.name} missing required DATADIS column: '{req}'"
                )

        cups_col = canonical_map["cups"]
        fecha_col = canonical_map["fecha"]
        hora_col = canonical_map["hora"]
        consumo_col = canonical_map["consumo_kWh"]

        clean_df = pd.DataFrame(
            {
                "cups": df[cups_col].astype(str).str.strip().str.strip('"'),
                "fecha": df[fecha_col].astype(str).str.strip().str.strip('"'),
                "hora": df[hora_col].astype(str).str.strip().str.strip('"'),
                "consumo_raw": df[consumo_col],
            }
        )

        # Parse numeric consumption (handling decimal comma, dot, quotes, and spaces)
        clean_df["consumption_kwh"] = clean_numeric_series(clean_df["consumo_raw"], fill_na=0.0)

        # Normalize unique fecha strings once instead of running 3 regexes over all rows
        fecha_codes, uniq_fecha = pd.factorize(clean_df["fecha"], sort=False)
        norm_uniq_fecha = (
            pd.Series(uniq_fecha, dtype="string")
            .str.strip()
            .str.replace(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", r"\3-\2-\1", regex=True)
            .str.replace("/", "-", regex=False)
            .str.replace(r"^(\d{4})-(\d{1})-(\d{1,2})$", r"\1-0\2-\3", regex=True)
            .str.replace(r"^(\d{4})-(\d{2})-(\d{1})$", r"\1-\2-0\3", regex=True)
            .to_numpy(dtype=object)
        )
        norm_date = pd.Series(
            np.where(fecha_codes >= 0, norm_uniq_fecha[np.maximum(fecha_codes, 0)], ""),
            index=clean_df.index,
            dtype=object,
        )
        clean_df["fecha"] = norm_date

        # Factorize unique hora strings for fast hour extraction
        hora_codes, uniq_hora = pd.factorize(clean_df["hora"], sort=False)
        uniq_h_num = pd.to_numeric(
            pd.Series(uniq_hora, dtype="string").str.split(":").str[0],
            errors="coerce",
        ).to_numpy(dtype=float)
        h_series = pd.Series(
            np.where(hora_codes >= 0, uniq_h_num[np.maximum(hora_codes, 0)], np.nan),
            index=clean_df.index,
        )

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

        h_lookup = np.array([f" {h:02d}:00:00" for h in range(24)], dtype=object)
        h_suffix = h_lookup[np.clip(np.asarray(h_start, dtype=int), 0, 23)]
        clean_df["timestamp"] = clean_df["fecha"].astype(str) + h_suffix
        return clean_df[["cups", "timestamp", "consumption_kwh"]]

    @staticmethod
    def consolidate_autumn_dst(df: pd.DataFrame) -> pd.DataFrame:
        """Sum the repeated 02:00 interval on 25-hour European autumn DST days within a single file."""
        if df.empty or "timestamp" not in df.columns:
            return df

        ts_str = df["timestamp"].astype(str)
        is_oct_02 = ts_str.str.slice(5, 7).eq("10") & ts_str.str.endswith(" 02:00:00")
        if not bool(is_oct_02.any()):
            return df

        # Check duplicate (cups, timestamp) only inside the tiny ~31-row October 02:00 slice first
        oct_02_df = df.loc[is_oct_02]
        oct_dups = oct_02_df.duplicated(subset=["cups", "timestamp"], keep=False)
        if not bool(oct_dups.any()):
            return df

        dup_dates_raw = ts_str.loc[oct_02_df.index[oct_dups]].str.slice(0, 10)
        cand_dates_set = set(dup_dates_raw.unique())
        dst_dates = {str(d) for d in cand_dates_set if is_autumn_dst_date(str(d))}

        # Also check day row count == 25 only on candidate duplicate dates
        all_dates = ts_str.str.slice(0, 10)
        cand_rows_mask = all_dates.isin(cand_dates_set)
        cand_day_counts = (
            df.loc[cand_rows_mask]
            .assign(_d=all_dates.loc[cand_rows_mask])
            .groupby(["cups", "_d"], sort=False)["consumption_kwh"]
            .transform("size")
            .reindex(df.index, fill_value=0)
        )

        ts_counts = (
            oct_02_df.groupby(["cups", "timestamp"], sort=False)["consumption_kwh"]
            .transform("size")
            .reindex(df.index, fill_value=0)
        )
        dst_mask = (
            is_oct_02 & (ts_counts == 2) & (all_dates.isin(dst_dates) | (cand_day_counts == 25))
        )
        if not bool(dst_mask.any()):
            return df

        non_dst = df.loc[~dst_mask]
        dst_summed = (
            df.loc[dst_mask]
            .groupby(["cups", "timestamp"], as_index=False, sort=False)["consumption_kwh"]
            .sum()
        )
        return pd.concat([non_dst, dst_summed], ignore_index=True)[df.columns]

    @staticmethod
    def _combine_and_filter(dfs: list[pd.DataFrame], year: int | None = None) -> pd.DataFrame:
        """Concatenate parsed DataFrames, conserve autumn DST energy, deduplicate, and filter."""
        consolidated = [DatadisConsumptionLoader.consolidate_autumn_dst(df) for df in dfs]
        combined = pd.concat(consolidated, ignore_index=True)
        combined = combined.drop_duplicates(subset=["cups", "timestamp"], keep="last")
        combined = combined.sort_values(by=["cups", "timestamp"]).reset_index(drop=True)
        if year is not None:
            combined = combined[combined["timestamp"].str.startswith(f"{year:04d}-")].reset_index(
                drop=True
            )
        return combined

    def load_all_with_validation(
        self, year: int | None = None
    ) -> tuple[pd.DataFrame, list[ValidationResult]]:
        """Validate and load all discovered CSV files, skipping invalid ones and surfacing warnings."""
        files = self.discover_files(year=year)
        dfs: list[pd.DataFrame] = []
        validation_results: list[ValidationResult] = []

        for file_path in files:
            val_res = DatadisValidator.validate_file(file_path)
            validation_results.append(val_res)
            if val_res.is_valid:
                try:
                    dfs.append(
                        self.parse_file(
                            file_path,
                            encoding=val_res.encoding,
                            delimiter=val_res.delimiter,
                        )
                    )
                except Exception as exc:
                    val_res.is_valid = False
                    val_res.error_message = str(exc)

        if not dfs:
            raise IngestionError(
                f"Found {len(files)} CSV file(s) in {self.consumption_dir}, but none could be loaded."
            )

        return self._combine_and_filter(dfs, year=year), validation_results

    def load_all(self, year: int | None = None, strict: bool = True) -> pd.DataFrame:
        """Load, validate, and deduplicate all CSV files in the consumption directory.

        Args:
            year: Optional calendar year filter.
            strict: If True (default), raise immediately on invalid files; if False, skip
                invalid files via ``load_all_with_validation()``.

        Returns:
            DataFrame with columns ['cups', 'timestamp', 'consumption_kwh'].
        """
        if not strict:
            df, _ = self.load_all_with_validation(year=year)
            return df

        files = self.discover_files(year=year)
        dfs = [self.parse_file(f) for f in files]
        return self._combine_and_filter(dfs, year=year)
