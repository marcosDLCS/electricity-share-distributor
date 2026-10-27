"""Unit tests for regulatory constraints and community bylaw limits."""

from __future__ import annotations

import numpy as np
import pytest

from src.domain.exceptions import EsdError, OptimizationError
from src.domain.models import BylawConstraints
from src.optimization.engine import DistributionOptimizer


def test_bylaw_constraints_validation() -> None:
    """Verify bounds and validation logic in BylawConstraints."""
    # Valid constraints
    c = BylawConstraints(min_share=0.05, max_share=0.70)
    assert c.is_active
    assert c.get_bounds("ES0021000000000001AA") == (0.05, 0.70)

    # Inactive constraints
    c_empty = BylawConstraints()
    assert not c_empty.is_active
    assert c_empty.get_bounds("ES0021000000000001AA") == (0.0, 1.0)

    # Invalid range (< 0.0 or > 1.0)
    with pytest.raises(EsdError, match="min_share must be between"):
        BylawConstraints(min_share=-0.1)

    with pytest.raises(EsdError, match="max_share must be between"):
        BylawConstraints(max_share=1.5)

    # min_share > max_share
    with pytest.raises(EsdError, match="cannot exceed max_share"):
        BylawConstraints(min_share=0.60, max_share=0.40)


def test_bylaw_feasibility_check() -> None:
    """Verify feasibility validation across multiple participating CUPS."""
    cups_list = [f"ES002100000000000{i}AA" for i in range(1, 6)]  # 5 CUPS

    # Feasible: 5 * 0.10 = 0.50 <= 1.0
    c_feasible = BylawConstraints(min_share=0.10, max_share=0.80)
    c_feasible.validate_feasibility(cups_list)

    # Infeasible lower bounds: 5 * 0.25 = 1.25 > 1.0
    c_infeasible_min = BylawConstraints(min_share=0.25)
    with pytest.raises(OptimizationError, match="mathematically infeasible"):
        c_infeasible_min.validate_feasibility(cups_list)

    # Infeasible upper bounds: 5 * 0.15 = 0.75 < 1.0
    c_infeasible_max = BylawConstraints(max_share=0.15)
    with pytest.raises(OptimizationError, match="overly restrictive"):
        c_infeasible_max.validate_feasibility(cups_list)


def test_solve_optimal_betas_with_bylaw_constraints() -> None:
    """Verify that DistributionOptimizer enforces bylaw bounds in linear program."""
    n_hours = 24
    n_cups = 4
    cups = [f"ES002100000000000{i}AA" for i in range(1, n_cups + 1)]

    # CUPS 0 has huge demand, others have almost zero
    consumption = np.zeros((n_hours, n_cups))
    consumption[:, 0] = 50.0
    consumption[:, 1] = 0.5
    consumption[:, 2] = 0.5
    consumption[:, 3] = 0.5

    # Constant solar generation
    generation = np.full(n_hours, 20.0)

    # 1. Unconstrained: CUPS 0 will capture ~97% of solar share
    betas_unconstrained = DistributionOptimizer._solve_optimal_betas(consumption, generation, cups)
    assert betas_unconstrained[0] > 0.85

    # 2. Constrained: max_share=0.50, min_share=0.08
    constraints = BylawConstraints(min_share=0.08, max_share=0.50)
    betas_constrained = DistributionOptimizer._solve_optimal_betas(
        consumption, generation, cups, constraints=constraints
    )

    # CUPS 0 cannot exceed 50%
    assert betas_constrained[0] <= 0.50001
    # Every CUPS must have at least 8%
    for i in range(n_cups):
        assert betas_constrained[i] >= 0.07999

    # Sum of shares must be <= 1.0
    assert np.isclose(np.sum(betas_constrained), 1.0, atol=1e-4)


def test_hare_niemeyer_rounding_with_constraints() -> None:
    """Verify that _round_betas honors bylaw bounds while maintaining exact 100% sum."""
    n_cups = 3
    cups = [f"ES002100000000000{i}AA" for i in range(1, n_cups + 1)]
    raw_betas = np.array([0.75, 0.20, 0.05])
    constraints = BylawConstraints(min_share=0.10, max_share=0.70)

    rounded = DistributionOptimizer._round_betas(
        raw_betas,
        precision=1,
        cups_list=cups,
        constraints=constraints,
    )

    # Exact sum
    assert np.isclose(np.sum(rounded), 1.0, atol=1e-6)
    # Bounds respected after rounding
    assert rounded[0] <= 0.7001
    for i in range(n_cups):
        assert rounded[i] >= 0.0999


def test_compute_hourly_optimization_with_global_bylaw_constraints() -> None:
    """Verify compute_hourly_optimization enforces global min_share and max_share across hours."""
    import pandas as pd

    from src.ingestion.schema import AlignedDataset, IngestionSummary
    from src.optimization.models import OptimizationStrategy

    pri_cups = "ES0021000000000001AA"
    cups_2 = "ES0021000000000002BB"
    cups_3 = "ES0021000000000003CC"
    cups_list = [pri_cups, cups_2, cups_3]
    timestamps = [f"2026-05-01 {h:02d}:00:00" for h in range(24)]

    # CUPS 1 has dominant demand, CUPS 2 and 3 have minor demand
    df = pd.DataFrame(
        {
            pri_cups: [40.0] * 24,
            cups_2: [0.5] * 24,
            cups_3: [0.5] * 24,
            "generation_kwh": [0.0 if (h < 7 or h > 20) else 15.0 for h in range(24)],
        },
        index=timestamps,
    )
    summary = IngestionSummary(
        cups_count=3,
        cups_list=cups_list,
        consumption_files_loaded=3,
        generation_files_loaded=1,
        start_time=timestamps[0],
        end_time=timestamps[-1],
        total_hours=24,
    )
    dataset = AlignedDataset(
        data=df,
        cups_list=cups_list,
        metadata=summary,
        monthly_groups={"2026-05": df},
        primary_cups=pri_cups,
    )

    constraints = BylawConstraints(min_share=0.08, max_share=0.60)
    res = DistributionOptimizer.compute_hourly_optimization(
        dataset,
        strategy=OptimizationStrategy.OPTIMAL,
        precision=1,
        constraints=constraints,
    )

    matrix = res.profile_matrix
    ts_df = res.time_series_df

    # 1. Check 24-hour diurnal matrix
    for h in range(24):
        h_str = f"{h:02d}"
        for cups in cups_list:
            share = matrix.matrix[cups][h_str]
            assert share is not None
            assert share >= 0.0799, f"CUPS {cups} in hour {h_str} below min_share: {share}"
            assert share <= 0.6001, f"CUPS {cups} in hour {h_str} above max_share: {share}"
        assert np.isclose(matrix.hourly_sums[h_str], 1.0, atol=1e-4)

    # 2. Check full time-series rows
    for h in range(24):
        ts = f"2026-05-01 {h:02d}:00:00"
        ts_slice = ts_df[ts_df["timestamp"] == ts]
        for _, row in ts_slice.iterrows():
            pct = float(str(row["share_pct"]).replace("%", ""))
            est_pct = float(str(row["estimated_share_pct"]).replace("%", ""))
            assert pct >= 7.99, f"{row['cups']} at {ts} share_pct {pct}% below min_share"
            assert pct <= 60.01, f"{row['cups']} at {ts} share_pct {pct}% above max_share"
            assert est_pct >= 7.99, (
                f"{row['cups']} at {ts} estimated_share_pct {est_pct}% below min_share"
            )
            assert est_pct <= 60.01, (
                f"{row['cups']} at {ts} estimated_share_pct {est_pct}% above max_share"
            )


def test_compute_hourly_optimization_with_cups_specific_constraints() -> None:
    """Verify compute_hourly_optimization honors per-CUPS min_share and max_share bounds."""
    import pandas as pd

    from src.ingestion.schema import AlignedDataset, IngestionSummary
    from src.optimization.models import OptimizationStrategy

    pri_cups = "ES0021000000000001AA"
    cups_2 = "ES0021000000000002BB"
    cups_3 = "ES0021000000000003CC"
    cups_list = [pri_cups, cups_2, cups_3]
    timestamps = [f"2026-05-01 {h:02d}:00:00" for h in range(24)]

    df = pd.DataFrame(
        {
            pri_cups: [30.0] * 24,
            cups_2: [1.0] * 24,
            cups_3: [1.0] * 24,
            "generation_kwh": [0.0 if (h < 7 or h > 20) else 10.0 for h in range(24)],
        },
        index=timestamps,
    )
    summary = IngestionSummary(
        cups_count=3,
        cups_list=cups_list,
        consumption_files_loaded=3,
        generation_files_loaded=1,
        start_time=timestamps[0],
        end_time=timestamps[-1],
        total_hours=24,
    )
    dataset = AlignedDataset(
        data=df,
        cups_list=cups_list,
        metadata=summary,
        monthly_groups={"2026-05": df},
        primary_cups=pri_cups,
    )

    # CUPS 1 capped at 50%, CUPS 2 guaranteed at least 25%
    constraints = BylawConstraints(
        cups_min_shares={cups_2: 0.25},
        cups_max_shares={pri_cups: 0.50},
    )
    res = DistributionOptimizer.compute_hourly_optimization(
        dataset,
        strategy=OptimizationStrategy.OPTIMAL,
        precision=1,
        constraints=constraints,
    )

    matrix = res.profile_matrix
    ts_df = res.time_series_df

    for h in range(24):
        h_str = f"{h:02d}"
        assert matrix.matrix[pri_cups][h_str] <= 0.5001
        assert matrix.matrix[cups_2][h_str] >= 0.2499
        assert np.isclose(matrix.hourly_sums[h_str], 1.0, atol=1e-4)

    for h in range(24):
        ts = f"2026-05-01 {h:02d}:00:00"
        ts_slice = ts_df[ts_df["timestamp"] == ts]
        pri_pct = float(
            str(ts_slice[ts_slice["cups"] == pri_cups]["share_pct"].iloc[0]).replace("%", "")
        )
        c2_pct = float(
            str(ts_slice[ts_slice["cups"] == cups_2]["share_pct"].iloc[0]).replace("%", "")
        )
        assert pri_pct <= 50.01
        assert c2_pct >= 24.99


def test_optimize_dataset_hourly_propagates_constraints() -> None:
    """Verify that optimize_dataset forwards constraints to compute_hourly_optimization."""
    import pandas as pd

    from src.ingestion.schema import AlignedDataset, IngestionSummary

    pri_cups = "ES0021000000000001AA"
    sec_cups = "ES0021000000000002BB"
    cups_list = [pri_cups, sec_cups]
    timestamps = [f"2026-05-01 {h:02d}:00:00" for h in range(24)]

    df = pd.DataFrame(
        {
            pri_cups: [20.0] * 24,
            sec_cups: [1.0] * 24,
            "generation_kwh": [5.0] * 24,
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
        total_hours=24,
    )
    dataset = AlignedDataset(
        data=df,
        cups_list=cups_list,
        metadata=summary,
        monthly_groups={"2026-05": df},
        primary_cups=pri_cups,
    )

    constraints = BylawConstraints(min_share=0.15, max_share=0.65)
    opt_res = DistributionOptimizer.optimize_dataset(
        dataset,
        compute_hourly=True,
        constraints=constraints,
        require_full_month=False,
    )

    assert opt_res.hourly_result is not None
    matrix = opt_res.hourly_result.profile_matrix
    for h in range(24):
        h_str = f"{h:02d}"
        for cups in cups_list:
            share = matrix.matrix[cups][h_str]
            assert share >= 0.1499
            assert share <= 0.6501
