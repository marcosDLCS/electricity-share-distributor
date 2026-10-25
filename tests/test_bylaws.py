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
