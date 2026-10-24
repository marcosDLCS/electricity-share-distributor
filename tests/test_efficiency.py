"""Tests for the photovoltaic solar efficiency formula and hourly integration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.schema import AlignedDataset, IngestionSummary
from src.optimization.efficiency import calculate_solar_efficiency
from src.optimization.engine import DistributionOptimizer


def test_calculate_solar_efficiency_clear_sky_noon() -> None:
    """Test solar efficiency under optimal clear-sky conditions at summer solar noon."""
    score = calculate_solar_efficiency(month=6, hour=14, temperature=20.0, cloud_cover=0)
    assert isinstance(score, int)
    assert 95 <= score <= 100


def test_calculate_solar_efficiency_cloud_attenuation() -> None:
    """Test that increasing cloud cover progressively reduces solar efficiency."""
    score_clear = calculate_solar_efficiency(month=6, hour=13, temperature=20.0, cloud_cover=0)
    score_mid = calculate_solar_efficiency(month=6, hour=13, temperature=20.0, cloud_cover=50)
    score_overcast = calculate_solar_efficiency(month=6, hour=13, temperature=20.0, cloud_cover=100)

    assert isinstance(score_clear, int)
    assert isinstance(score_mid, int)
    assert isinstance(score_overcast, int)
    assert score_clear > score_mid > score_overcast
    # Overcast should still retain diffuse light (~20-30%)
    assert score_overcast >= 15


def test_calculate_solar_efficiency_temperature_derating() -> None:
    """Test that high ambient temperatures reduce efficiency while cool temperatures boost it."""
    score_cool = calculate_solar_efficiency(month=5, hour=13, temperature=10.0, cloud_cover=10)
    score_ref = calculate_solar_efficiency(month=5, hour=13, temperature=20.0, cloud_cover=10)
    score_hot = calculate_solar_efficiency(month=5, hour=13, temperature=38.0, cloud_cover=10)

    assert isinstance(score_cool, int)
    assert isinstance(score_ref, int)
    assert isinstance(score_hot, int)
    assert score_cool > score_ref > score_hot


def test_calculate_solar_efficiency_seasonal_variation() -> None:
    """Test seasonal solar elevation impact: June peak vs December minimum."""
    score_june = calculate_solar_efficiency(month=6, hour=13, temperature=20.0, cloud_cover=0)
    score_dec = calculate_solar_efficiency(month=12, hour=13, temperature=20.0, cloud_cover=0)

    assert isinstance(score_june, int)
    assert isinstance(score_dec, int)
    assert score_june > score_dec
    assert score_dec >= 60


def test_calculate_solar_efficiency_diurnal_angle() -> None:
    """Test diurnal angle: noon peak vs morning/dusk grazing angles."""
    score_noon = calculate_solar_efficiency(month=6, hour=14, temperature=20.0, cloud_cover=0)
    score_morning = calculate_solar_efficiency(month=6, hour=7, temperature=20.0, cloud_cover=0)
    score_evening = calculate_solar_efficiency(month=6, hour=20, temperature=20.0, cloud_cover=0)

    assert isinstance(score_noon, int)
    assert isinstance(score_morning, int)
    assert isinstance(score_evening, int)
    assert score_noon > score_morning
    assert score_noon > score_evening


def test_calculate_solar_efficiency_clamping_and_robustness() -> None:
    """Test boundary conditions, NaNs, and bounds clamping (1 to 100)."""
    # Missing / None values use sensible defaults
    score_none = calculate_solar_efficiency(month=6, hour=13, temperature=None, cloud_cover=None)
    assert isinstance(score_none, int)
    assert 80 <= score_none <= 100

    # NaN values handled gracefully
    score_nan = calculate_solar_efficiency(
        month=6, hour=13, temperature=float("nan"), cloud_cover=float("nan")
    )
    assert isinstance(score_nan, int)
    assert 80 <= score_nan <= 100

    # Extreme theoretical limits clamp between 1 and 100
    score_extreme_hot = calculate_solar_efficiency(
        month=12, hour=23, temperature=80.0, cloud_cover=100
    )
    assert isinstance(score_extreme_hot, int)
    assert score_extreme_hot >= 1

    score_extreme_boost = calculate_solar_efficiency(
        month=6, hour=14, temperature=-50.0, cloud_cover=0
    )
    assert isinstance(score_extreme_boost, int)
    assert score_extreme_boost <= 100


def test_hourly_optimization_solar_efficiency_only_on_generation(tmp_path: Path) -> None:
    """Verify that hourly calculation populates integer solar_efficiency and 0 for zero-generation hours."""
    cups = ["ES0021000000000001AA"]
    timestamps = [
        "2026-05-01 02:00:00",  # Night hour, generation = 0.0
        "2026-05-01 12:00:00",  # Sunny hour, generation = 10.0
        "2026-05-01 23:00:00",  # Night hour, generation = 0.0
    ]
    df = pd.DataFrame(
        {
            cups[0]: [1.5, 2.0, 1.2],
            "generation_kwh": [0.0, 10.0, 0.0],
            "temperature": [12.0, 24.5, 14.0],
            "cloud_cover": [0, 15, 0],
        },
        index=timestamps,
    )
    summary = IngestionSummary(
        cups_count=1,
        cups_list=cups,
        consumption_files_loaded=1,
        generation_files_loaded=1,
        start_time=timestamps[0],
        end_time=timestamps[-1],
        total_hours=3,
    )
    dataset = AlignedDataset(data=df, cups_list=cups, metadata=summary)

    opt = DistributionOptimizer.compute_hourly_optimization(dataset)
    ts_df = opt.time_series_df

    assert "solar_efficiency" in ts_df.columns
    # Night hour 02:00 has generation = 0, so solar_efficiency must be integer 0
    row_02 = ts_df[ts_df["timestamp"] == timestamps[0]].iloc[0]
    assert row_02["solar_efficiency"] == 0

    # Midday hour 12:00 has generation = 10.0, so solar_efficiency must be populated integer >= 50
    row_12 = ts_df[ts_df["timestamp"] == timestamps[1]].iloc[0]
    assert int(row_12["solar_efficiency"]) == row_12["solar_efficiency"]
    assert 50 <= row_12["solar_efficiency"] <= 100

    # Night hour 23:00 has generation = 0, so solar_efficiency must be integer 0
    row_23 = ts_df[ts_df["timestamp"] == timestamps[2]].iloc[0]
    assert row_23["solar_efficiency"] == 0
