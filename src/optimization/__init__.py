"""Optimization package for collective PV self-consumption allocation."""

from src.optimization.engine import DistributionOptimizer, OptimizationError
from src.optimization.models import (
    CoefficientsMatrix,
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    HourlyOptimizationResult,
    HourlyProfileMatrix,
    OptimizationResult,
    OptimizationStrategy,
)

__all__ = [
    "CoefficientsMatrix",
    "CommunityMonthlyMetrics",
    "CupsMonthlyMetrics",
    "DistributionOptimizer",
    "HourlyOptimizationResult",
    "HourlyProfileMatrix",
    "OptimizationError",
    "OptimizationResult",
    "OptimizationStrategy",
]
