"""Optimization package for collective PV self-consumption allocation."""

from src.optimization.engine import DistributionOptimizer, OptimizationError
from src.optimization.models import (
    CoefficientsMatrix,
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    OptimizationResult,
    OptimizationStrategy,
)

__all__ = [
    "CoefficientsMatrix",
    "CommunityMonthlyMetrics",
    "CupsMonthlyMetrics",
    "DistributionOptimizer",
    "OptimizationError",
    "OptimizationResult",
    "OptimizationStrategy",
]
