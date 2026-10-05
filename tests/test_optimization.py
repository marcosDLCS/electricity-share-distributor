"""Automated tests for the RD 244/2019 distribution coefficient optimization engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ingestion.schema import AlignedDataset, IngestionSummary
from src.optimization.engine import DistributionOptimizer, OptimizationError
from src.optimization.models import OptimizationStrategy


def test_optimizer_prefers_daytime_consumer() -> None:
    """Test that LP optimizer allocates solar PV generation to daytime consumers over night consumers."""
    # 24 hours: Solar generation peaks between hour 10 and 15
    hours = 24
    gen = np.zeros(hours)
    gen[10:16] = 10.0  # 60 kWh total solar generation

    # CUPS 1 consumes during midday (hours 10-15)
    # CUPS 2 consumes only at night (hours 0-5)
    cons = np.zeros((hours, 2))
    cons[10:16, 0] = 10.0  # CUPS 1: 60 kWh daytime demand
    cons[0:6, 1] = 10.0  # CUPS 2: 60 kWh nighttime demand

    betas = DistributionOptimizer.calculate_betas(cons, gen, strategy=OptimizationStrategy.OPTIMAL)

    # CUPS 1 should receive 100% (or near 100%) because it consumes during solar hours
    assert betas[0] > 0.95
    assert betas[1] < 0.05
    assert np.isclose(np.sum(betas), 1.0, atol=1e-4)


def test_optimizer_baseline_strategies() -> None:
    hours = 10
    gen = np.full(hours, 5.0)
    # CUPS 1 consumes 80 kWh total, CUPS 2 consumes 20 kWh total
    cons = np.zeros((hours, 2))
    cons[:, 0] = 8.0
    cons[:, 1] = 2.0

    # Equal strategy
    equal_betas = DistributionOptimizer.calculate_betas(
        cons, gen, strategy=OptimizationStrategy.EQUAL
    )
    assert np.isclose(equal_betas[0], 0.5)
    assert np.isclose(equal_betas[1], 0.5)

    # Consumption share strategy
    share_betas = DistributionOptimizer.calculate_betas(
        cons, gen, strategy=OptimizationStrategy.CONSUMPTION_SHARE
    )
    assert np.isclose(share_betas[0], 0.8)
    assert np.isclose(share_betas[1], 0.2)


def test_evaluate_month_energy_balance() -> None:
    # 24 hours dataset for 2 CUPS
    timestamps = [f"2026-05-01 {h:02d}:00:00" for h in range(24)]
    gen = [0.0] * 8 + [5.0] * 8 + [0.0] * 8  # 40 kWh gen
    c1 = [1.0] * 24  # 24 kWh
    c2 = [2.0] * 24  # 48 kWh

    df_month = pd.DataFrame(
        {
            "ES0021000000000001AA": c1,
            "ES0021000000000002BB": c2,
            "generation_kwh": gen,
        },
        index=timestamps,
    )

    res = DistributionOptimizer.evaluate_month(
        df_month,
        cups_list=["ES0021000000000001AA", "ES0021000000000002BB"],
        month_name="2026-05",
        strategy=OptimizationStrategy.OPTIMAL,
    )

    assert res.month == "2026-05"
    assert np.isclose(res.total_generation_kwh, 40.0)
    assert np.isclose(res.total_consumption_kwh, 72.0)
    # Self-consumption + surplus must equal generation
    assert np.isclose(res.total_self_consumed_kwh + res.total_surplus_kwh, res.total_generation_kwh)
    # Self-consumption + grid demand must equal consumption
    assert np.isclose(
        res.total_self_consumed_kwh + res.total_grid_demand_kwh, res.total_consumption_kwh
    )
    assert np.isclose(res.beta_sum, 1.0, atol=1e-4)


def test_optimize_dataset_with_baselines() -> None:
    # 2 months dataset
    timestamps_m1 = [f"2026-05-01 {h:02d}:00:00" for h in range(24)]
    timestamps_m2 = [f"2026-06-01 {h:02d}:00:00" for h in range(24)]
    timestamps = timestamps_m1 + timestamps_m2

    gen = [2.0] * len(timestamps)
    c1 = [1.0] * len(timestamps)
    c2 = [3.0] * len(timestamps)

    cups_list = ["ES0021000000000001AA", "ES0021000000000002BB"]
    df = pd.DataFrame(
        {
            "ES0021000000000001AA": c1,
            "ES0021000000000002BB": c2,
            "generation_kwh": gen,
        },
        index=timestamps,
    )

    summary = IngestionSummary(
        cups_count=2,
        cups_list=cups_list,
        consumption_files_loaded=2,
        generation_files_loaded=1,
        start_time=timestamps[0],
        end_time=timestamps[-1],
        total_hours=len(timestamps),
    )

    dataset = AlignedDataset(
        data=df,
        cups_list=cups_list,
        metadata=summary,
        monthly_groups={
            "2026-05": df.iloc[:24],
            "2026-06": df.iloc[24:],
        },
    )

    opt_result = DistributionOptimizer.optimize_dataset(
        dataset, strategy=OptimizationStrategy.OPTIMAL, include_baselines=True
    )

    assert len(opt_result.monthly_results) == 2
    assert opt_result.total_summary.month == "Total"
    assert "consumption_share" in opt_result.baselines
    assert "equal" in opt_result.baselines
    assert (
        opt_result.total_summary.total_self_consumed_kwh
        >= opt_result.baselines["equal"].total_summary.total_self_consumed_kwh
    )


def test_optimizer_empty_cups_raises_error() -> None:
    cons = np.zeros((10, 0))
    gen = np.zeros(10)
    with pytest.raises(OptimizationError, match="No CUPS provided"):
        DistributionOptimizer.calculate_betas(cons, gen)


def test_round_betas_hare_niemeyer_exact_100_percent() -> None:
    """Test Hare-Niemeyer largest remainder rounding guarantees exact 100.0% sum across precisions."""
    # Test on arbitrary non-round numbers across 7 CUPS
    raw_weights = np.array([33.33333, 16.66666, 16.66666, 11.11111, 9.99999, 7.77777, 4.44448])
    raw_betas = raw_weights / np.sum(raw_weights)

    # Precision 0 (integer percentages)
    b0 = DistributionOptimizer._round_betas(raw_betas, precision=0)
    pcts0 = [round(b * 100, 0) for b in b0]
    assert sum(pcts0) == 100
    assert np.isclose(np.sum(b0), 1.0)
    assert all(b >= 0.0 for b in b0)
    # Check each element is an integer percentage
    for b in b0:
        assert np.isclose(b * 100, round(b * 100))

    # Precision 1 (tenths of percent)
    b1 = DistributionOptimizer._round_betas(raw_betas, precision=1)
    pcts1 = [round(b * 100, 1) for b in b1]
    assert np.isclose(sum(pcts1), 100.0)
    assert np.isclose(np.sum(b1), 1.0)
    assert all(b >= 0.0 for b in b1)

    # Precision 2 (hundredths of percent)
    b2 = DistributionOptimizer._round_betas(raw_betas, precision=2)
    pcts2 = [round(b * 100, 2) for b in b2]
    assert np.isclose(sum(pcts2), 100.00)
    assert np.isclose(np.sum(b2), 1.0)
    assert all(b >= 0.0 for b in b2)
