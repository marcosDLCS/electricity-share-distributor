"""Optimization package for collective PV self-consumption allocation."""

from src.optimization.engine import DistributionOptimizer, OptimizationError
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    OptimizationResult,
    OptimizationStrategy,
)

__all__ = [
    "CommunityMonthlyMetrics",
    "CupsMonthlyMetrics",
    "DistributionOptimizer",
    "OptimizationError",
    "OptimizationResult",
    "OptimizationStrategy",
]
