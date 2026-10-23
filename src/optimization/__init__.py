"""Optimization package for collective PV self-consumption allocation."""

from src.optimization.engine import DistributionOptimizer, OptimizationError
from src.optimization.models import (
    CoefficientsMatrix,
    CommunityMonthlyMetrics,
    CupsHourlyMetrics,
    CupsMonthlyMetrics,
    HourlyOptimizationResult,
    HourlyProfileMatrix,
    OptimizationResult,
    OptimizationStrategy,
)

__all__ = [
    "CoefficientsMatrix",
    "CommunityMonthlyMetrics",
    "CupsHourlyMetrics",
    "CupsMonthlyMetrics",
    "DistributionOptimizer",
    "HourlyOptimizationResult",
    "HourlyProfileMatrix",
    "OptimizationError",
    "OptimizationResult",
    "OptimizationStrategy",
]
