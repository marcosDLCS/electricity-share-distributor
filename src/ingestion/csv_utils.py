"""Shared CSV encoding detection, delimiter sniffing, and numeric normalization utilities."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import SUPPORTED_DELIMITERS, SUPPORTED_ENCODINGS


def detect_file_encoding(file_path: Path) -> str:
    """Detect the character encoding of a text/CSV file.

    Checks for a UTF-8 BOM first so BOM-prefixed headers are stripped cleanly via
    'utf-8-sig', then tries the configured supported encodings before falling back
    to 'latin-1'.
    """
    with file_path.open("rb") as handle:
        raw_bytes = handle.read(8192)
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    for enc in SUPPORTED_ENCODINGS:
        try:
            raw_bytes.decode(enc)
            return enc
        except UnicodeDecodeError, LookupError:
            continue
    return "latin-1"


def sniff_csv_delimiter(file_path: Path, encoding: str = "utf-8", default: str = ";") -> str:
    """Detect the delimiter character used in a CSV file (';', ',', or '\\t')."""
    try:
        with file_path.open(encoding=encoding, errors="replace") as handle:
            sample_lines: list[str] = []
            for _ in range(5):
                line = handle.readline()
                if not line:
                    break
                sample_lines.append(line)
    except OSError:
        return default

    sample = "".join(sample_lines)
    if not sample.strip():
        return default

    first_non_empty = next((line for line in sample_lines if line.strip()), "")
    if first_non_empty:
        counts = {delim: first_non_empty.count(delim) for delim in SUPPORTED_DELIMITERS}
        best_delim = max(counts, key=lambda d: counts[d])
        if counts[best_delim] > 0:
            return best_delim

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        return dialect.delimiter
    except Exception:
        return default


def clean_numeric_series(series: pd.Series, fill_na: float | None = None) -> pd.Series:
    """Normalize a pandas Series with potential string comma decimals into float values."""
    if pd.api.types.is_string_dtype(series.dtype) or series.dtype == object:
        cleaned = series.astype(str).str.replace(",", ".", regex=False)
        numeric = pd.to_numeric(cleaned, errors="coerce")
        if bool(numeric.isna().any()):
            bad_mask = numeric.isna() & series.notna()
            if bool(bad_mask.any()):
                recleaned = (
                    series.loc[bad_mask]
                    .astype(str)
                    .str.strip()
                    .str.strip('"')
                    .str.strip("'")
                    .str.replace(" ", "", regex=False)
                    .str.replace(",", ".", regex=False)
                )
                numeric.loc[bad_mask] = pd.to_numeric(recleaned, errors="coerce")
    else:
        numeric = pd.to_numeric(series, errors="coerce")

    if fill_na is not None:
        return numeric.fillna(fill_na)
    return numeric


def is_autumn_dst_date(date_str: str) -> bool:
    """Return True if ISO date string (YYYY-MM-DD) is the European autumn DST date."""
    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        return False
    # European DST ends on the last Sunday of October (Oct 25-31, weekday == 6)
    return parsed.month == 10 and parsed.day >= 25 and parsed.weekday() == 6
