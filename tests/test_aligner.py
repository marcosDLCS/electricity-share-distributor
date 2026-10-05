"""Automated tests for time-series alignment between consumption and generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.schema import AlignmentError
from tests.test_ingestion import create_mock_datadis_csv, create_mock_huawei_excel


def test_aligner_successful_alignment(tmp_path: Path) -> None:
    # Setup 2 CUPS consumption files
    c_dir = tmp_path / "consumption"
    c_dir.mkdir()
    g_dir = tmp_path / "generation"
    g_dir.mkdir()

    create_mock_datadis_csv(c_dir / "cups1.csv", cups="ES0021000000000001AA", num_days=3)
    create_mock_datadis_csv(c_dir / "cups2.csv", cups="ES0021000000000002BB", num_days=3)
    create_mock_huawei_excel(g_dir / "gen.xlsx", num_days=3)

    from src.ingestion.consumption import DatadisConsumptionLoader
    from src.ingestion.generation import HuaweiGenerationLoader

    c_loader = DatadisConsumptionLoader(c_dir)
    g_loader = HuaweiGenerationLoader(g_dir)

    c_df = c_loader.load_all()
    g_df = g_loader.load_all()

    aligner = TimeSeriesAligner(c_df, g_df)
    aligned = aligner.align()

    assert aligned.cups_list == ["ES0021000000000001AA", "ES0021000000000002BB"]
    assert len(aligned.data) == 72
    assert "generation_kwh" in aligned.data.columns
    assert "ES0021000000000001AA" in aligned.data.columns
    assert "ES0021000000000002BB" in aligned.data.columns
    assert aligned.metadata.total_hours == 72
    assert aligned.metadata.cups_count == 2
    assert "2026-03" in aligned.monthly_groups


def test_aligner_filter_year_month(tmp_path: Path) -> None:
    c_dir = tmp_path / "consumption"
    c_dir.mkdir()
    g_dir = tmp_path / "generation"
    g_dir.mkdir()

    create_mock_datadis_csv(c_dir / "cups1.csv", cups="ES0021000000000001AA", num_days=3)
    create_mock_huawei_excel(g_dir / "gen.xlsx", num_days=3)

    from src.ingestion.consumption import DatadisConsumptionLoader
    from src.ingestion.generation import HuaweiGenerationLoader

    c_df = DatadisConsumptionLoader(c_dir).load_all()
    g_df = HuaweiGenerationLoader(g_dir).load_all()

    aligner = TimeSeriesAligner(c_df, g_df)
    aligned = aligner.align(year=2026, month=3)
    assert len(aligned.data) == 72

    with pytest.raises(AlignmentError, match="No aligned data points found"):
        aligner.align(year=2025)


def test_aligner_no_overlap(tmp_path: Path) -> None:
    c_df = pd.DataFrame(
        {
            "cups": ["ES0021000000000001AA"],
            "timestamp": ["2025-01-01 00:00:00"],
            "consumption_kwh": [0.5],
        }
    )
    g_df = pd.DataFrame(
        {
            "timestamp": ["2026-01-01 00:00:00"],
            "generation_kwh": [1.0],
        }
    )

    aligner = TimeSeriesAligner(c_df, g_df)
    with pytest.raises(AlignmentError, match="No overlapping hourly timestamps found"):
        aligner.align()
