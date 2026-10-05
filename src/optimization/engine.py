"""Core optimization engine for collective PV self-consumption distribution coefficients (RD 244/2019)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.optimize as opt
from scipy.sparse import dok_matrix

from src.ingestion.schema import AlignedDataset, EsdError
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    OptimizationResult,
    OptimizationStrategy,
)


class OptimizationError(EsdError):
    """Raised when coefficient optimization fails or produces invalid results."""


class DistributionOptimizer:
    """Computes optimal and baseline electricity distribution coefficients (beta_i)."""

    @staticmethod
    def _solve_optimal_betas(
        consumption: np.ndarray,
        generation: np.ndarray,
    ) -> np.ndarray:
        """Formulate and solve Linear Program to find betas maximizing collective self-consumption.

        Args:
            consumption: 2D array of shape (T, N) with hourly kWh consumption per CUPS.
            generation: 1D array of shape (T,) with hourly kWh solar PV generation.

        Returns:
            1D array of shape (N,) with optimal coefficients beta_i summing to <= 1.0.
        """
        t_steps, n_cups = consumption.shape
        if n_cups == 0:
            raise OptimizationError("No CUPS provided for optimization.")
        if t_steps == 0:
            raise OptimizationError("No time steps provided for optimization.")

        # Identify sunlit hours (where generation > 0)
        sun_indices = np.where(generation > 1e-4)[0]
        n_sun = len(sun_indices)

        if n_sun == 0 or np.sum(generation) <= 0:
            # No solar generation in this period: return equal or zero distribution
            return np.full(n_cups, 1.0 / n_cups)

        # Variables: [beta_0, ..., beta_{N-1}, s_{0, 0}, ..., s_{N-1, n_sun-1}]
        n_vars = n_cups + n_cups * n_sun

        # Objective: Maximize sum(s_{i, k}) -> Minimize -sum(s_{i, k})
        c = np.zeros(n_vars)
        c[n_cups:] = -1.0

        # Constraints:
        # 1) sum(beta_i) <= 1.0 (1 row)
        # 2) s_{i, k} - beta_i * G_k <= 0 (n_cups * n_sun rows)
        n_constraints = 1 + n_cups * n_sun
        a_ub = dok_matrix((n_constraints, n_vars))
        b_ub = np.zeros(n_constraints)

        # sum(beta_i) <= 1.0
        for i in range(n_cups):
            a_ub[0, i] = 1.0
        b_ub[0] = 1.0

        # s_{i, k} - beta_i * G_{sun[k]} <= 0
        row = 1
        for k, t_idx in enumerate(sun_indices):
            g_k = float(generation[t_idx])
            for i in range(n_cups):
                var_idx = n_cups + i * n_sun + k
                a_ub[row, var_idx] = 1.0
                a_ub[row, i] = -g_k
                row += 1

        # Bounds: beta_i in [0, 1]; s_{i, k} in [0, C_{k, i}]
        bounds: list[tuple[float, float]] = [(0.0, 1.0) for _ in range(n_cups)]
        for i in range(n_cups):
            for t_idx in sun_indices:
                c_val = float(consumption[t_idx, i])
                bounds.append((0.0, max(0.0, c_val)))

        # Solve LP using HiGHS
        res = opt.linprog(
            c,
            A_ub=a_ub.tocsc(),
            b_ub=b_ub,
            bounds=bounds,
            method="highs",
        )

        if not res.success:
            raise OptimizationError(f"Linear programming optimization failed: {res.message}")

        betas = np.maximum(0.0, res.x[:n_cups])

        # Normalize or adjust if sum slightly exceeds 1.0 due to float precision
        beta_sum = np.sum(betas)
        if beta_sum > 1.0:
            betas = betas / beta_sum
        elif beta_sum < 0.9999 and np.sum(generation) > 0:
            # If total generation exceeds total consumption, allocate remaining share proportionally
            rem = 1.0 - beta_sum
            betas = betas + (rem / n_cups)

        return betas

    @staticmethod
    def _round_betas(betas: np.ndarray, precision: int = 0) -> np.ndarray:
        """Round coefficients to specified percentage precision using Hare-Niemeyer largest remainder method.

        Guarantees that:
          1. sum(round(betas * 100, precision)) == 100.0 exactly
          2. sum(betas) == 1.0000 exactly
          3. All betas >= 0.0
        """
        n = len(betas)
        if n == 0:
            return betas

        # Scale factor for target precision:
        # precision=0 -> scale=100 (integer percentages, sum=100)
        # precision=1 -> scale=1000 (tenth of percent, sum=1000)
        # precision=2 -> scale=10000 (hundredth of percent, sum=10000)
        scale = 100 * (10**precision)

        # Normalize raw betas to sum to 1.0 before rounding
        beta_sum = float(np.sum(betas))
        if beta_sum > 0:
            norm_betas = betas / beta_sum
        else:
            norm_betas = np.full(n, 1.0 / n)

        exact_alloc = norm_betas * scale
        floors = np.floor(exact_alloc).astype(int)
        remainders = exact_alloc - floors

        deficit = scale - int(np.sum(floors))

        if deficit > 0:
            # Distribute remaining units to items with largest remainders
            order = np.lexsort((-exact_alloc, -remainders))
            for i in range(deficit):
                floors[order[i % n]] += 1
        elif deficit < 0:
            order = np.lexsort((exact_alloc, remainders))
            for i in range(abs(deficit)):
                idx = order[i % n]
                if floors[idx] > 0:
                    floors[idx] -= 1

        rounded_betas = floors / scale
        return rounded_betas

    @classmethod
    def calculate_betas(
        cls,
        consumption: np.ndarray,
        generation: np.ndarray,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        precision: int = 0,
    ) -> np.ndarray:
        """Calculate distribution coefficients for given consumption and generation arrays."""
        _, n_cups = consumption.shape

        if strategy == OptimizationStrategy.EQUAL:
            raw = np.full(n_cups, 1.0 / n_cups)
        elif strategy == OptimizationStrategy.CONSUMPTION_SHARE:
            c_totals = np.sum(consumption, axis=0)
            c_sum = np.sum(c_totals)
            raw = c_totals / c_sum if c_sum > 0 else np.full(n_cups, 1.0 / n_cups)
        else:
            raw = cls._solve_optimal_betas(consumption, generation)

        return cls._round_betas(raw, precision=precision)

    @classmethod
    def evaluate_month(
        cls,
        df_month: pd.DataFrame,
        cups_list: list[str],
        month_name: str,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        precision: int = 0,
    ) -> CommunityMonthlyMetrics:
        """Evaluate and compute self-consumption metrics for a single month."""
        consumption = df_month[cups_list].values
        generation = df_month["generation_kwh"].values

        betas = cls.calculate_betas(consumption, generation, strategy=strategy, precision=precision)

        # Vectorized hourly energy balance:
        # allocated_gen shape: (T, N)
        allocated_gen = np.outer(generation, betas)
        # self_consumed shape: (T, N)
        self_consumed = np.minimum(consumption, allocated_gen)
        # surplus shape: (T, N)
        surplus = allocated_gen - self_consumed
        # grid_demand shape: (T, N)
        grid_demand = consumption - self_consumed

        # Monthly sums per CUPS
        total_c_cups = np.sum(consumption, axis=0)
        total_alloc_cups = np.sum(allocated_gen, axis=0)
        total_sc_cups = np.sum(self_consumed, axis=0)
        total_surplus_cups = np.sum(surplus, axis=0)
        total_grid_cups = np.sum(grid_demand, axis=0)

        cups_metrics: list[CupsMonthlyMetrics] = []
        for i, cups in enumerate(cups_list):
            c_kwh = float(total_c_cups[i])
            alloc_kwh = float(total_alloc_cups[i])
            sc_kwh = float(total_sc_cups[i])
            surplus_kwh = float(total_surplus_cups[i])
            grid_kwh = float(total_grid_cups[i])

            sc_rate = (sc_kwh / alloc_kwh * 100.0) if alloc_kwh > 0 else 0.0
            cov_rate = (sc_kwh / c_kwh * 100.0) if c_kwh > 0 else 0.0

            cups_metrics.append(
                CupsMonthlyMetrics(
                    cups=cups,
                    month=month_name,
                    beta=float(betas[i]),
                    consumption_kwh=c_kwh,
                    generation_allocated_kwh=alloc_kwh,
                    self_consumed_kwh=sc_kwh,
                    surplus_kwh=surplus_kwh,
                    grid_demand_kwh=grid_kwh,
                    self_consumption_rate=sc_rate,
                    solar_coverage_rate=cov_rate,
                )
            )

        # Community aggregate totals
        comm_cons = float(np.sum(total_c_cups))
        comm_gen = float(np.sum(generation))
        comm_sc = float(np.sum(total_sc_cups))
        comm_surplus = float(comm_gen - comm_sc)
        comm_grid = float(comm_cons - comm_sc)

        comm_sc_rate = (comm_sc / comm_gen * 100.0) if comm_gen > 0 else 0.0
        comm_cov_rate = (comm_sc / comm_cons * 100.0) if comm_cons > 0 else 0.0

        return CommunityMonthlyMetrics(
            month=month_name,
            strategy=strategy.value,
            total_consumption_kwh=comm_cons,
            total_generation_kwh=comm_gen,
            total_self_consumed_kwh=comm_sc,
            total_surplus_kwh=comm_surplus,
            total_grid_demand_kwh=comm_grid,
            self_consumption_rate=comm_sc_rate,
            solar_coverage_rate=comm_cov_rate,
            beta_sum=float(np.sum(betas)),
            cups_metrics=cups_metrics,
        )

    @classmethod
    def optimize_dataset(
        cls,
        aligned_dataset: AlignedDataset,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        include_baselines: bool = True,
        precision: int | None = None,
    ) -> OptimizationResult:
        """Run optimization across all months in the dataset.

        Args:
            aligned_dataset: Ingested and aligned dataset.
            strategy: Primary optimization strategy.
            include_baselines: If True, also computes results for baseline strategies.
            precision: Share percentage precision (0, 1, or 2 decimals). If None, uses configured setting.

        Returns:
            OptimizationResult containing monthly breakdowns, total summary, and baselines.
        """
        from src.config import get_precision, validate_share_precision

        active_precision = (
            get_precision() if precision is None else validate_share_precision(precision)
        )
        cups_list = aligned_dataset.cups_list
        sorted_months = sorted(aligned_dataset.monthly_groups.keys())

        monthly_results: list[CommunityMonthlyMetrics] = []
        for ym in sorted_months:
            m_df = aligned_dataset.get_month_data(ym)
            res = cls.evaluate_month(
                m_df,
                cups_list=cups_list,
                month_name=ym,
                strategy=strategy,
                precision=active_precision,
            )
            monthly_results.append(res)

        total_summary = cls._aggregate_summary(monthly_results, cups_list, strategy.value)

        baselines: dict[str, OptimizationResult] = {}
        if include_baselines:
            for base_strat in (OptimizationStrategy.CONSUMPTION_SHARE, OptimizationStrategy.EQUAL):
                if base_strat != strategy:
                    base_monthly = [
                        cls.evaluate_month(
                            aligned_dataset.get_month_data(ym),
                            cups_list=cups_list,
                            month_name=ym,
                            strategy=base_strat,
                            precision=active_precision,
                        )
                        for ym in sorted_months
                    ]
                    base_summary = cls._aggregate_summary(base_monthly, cups_list, base_strat.value)
                    baselines[base_strat.value] = OptimizationResult(
                        strategy=base_strat.value,
                        monthly_results=base_monthly,
                        total_summary=base_summary,
                        baselines={},
                    )

        return OptimizationResult(
            strategy=strategy.value,
            monthly_results=monthly_results,
            total_summary=total_summary,
            baselines=baselines,
        )

    @staticmethod
    def _aggregate_summary(
        monthly_results: list[CommunityMonthlyMetrics],
        cups_list: list[str],
        strategy: str,
    ) -> CommunityMonthlyMetrics:
        """Compute aggregate total metrics across multiple months."""
        if not monthly_results:
            return CommunityMonthlyMetrics(
                month="Total",
                strategy=strategy,
                total_consumption_kwh=0.0,
                total_generation_kwh=0.0,
                total_self_consumed_kwh=0.0,
                total_surplus_kwh=0.0,
                total_grid_demand_kwh=0.0,
                self_consumption_rate=0.0,
                solar_coverage_rate=0.0,
                beta_sum=1.0,
            )

        tot_cons = sum(m.total_consumption_kwh for m in monthly_results)
        tot_gen = sum(m.total_generation_kwh for m in monthly_results)
        tot_sc = sum(m.total_self_consumed_kwh for m in monthly_results)
        tot_surplus = sum(m.total_surplus_kwh for m in monthly_results)
        tot_grid = sum(m.total_grid_demand_kwh for m in monthly_results)

        sc_rate = (tot_sc / tot_gen * 100.0) if tot_gen > 0 else 0.0
        cov_rate = (tot_sc / tot_cons * 100.0) if tot_cons > 0 else 0.0

        # Aggregate per CUPS
        cups_aggregates: dict[str, dict[str, float]] = {
            c: {
                "cons": 0.0,
                "alloc": 0.0,
                "sc": 0.0,
                "surplus": 0.0,
                "grid": 0.0,
                "weighted_beta": 0.0,
            }
            for c in cups_list
        }

        for m in monthly_results:
            m_gen = m.total_generation_kwh
            for cm in m.cups_metrics:
                entry = cups_aggregates[cm.cups]
                entry["cons"] += cm.consumption_kwh
                entry["alloc"] += cm.generation_allocated_kwh
                entry["sc"] += cm.self_consumed_kwh
                entry["surplus"] += cm.surplus_kwh
                entry["grid"] += cm.grid_demand_kwh
                entry["weighted_beta"] += cm.beta * m_gen

        cups_summary_metrics: list[CupsMonthlyMetrics] = []
        for cups in cups_list:
            c_data = cups_aggregates[cups]
            c_cons = c_data["cons"]
            c_alloc = c_data["alloc"]
            c_sc = c_data["sc"]
            c_surplus = c_data["surplus"]
            c_grid = c_data["grid"]
            avg_beta = (
                (c_data["weighted_beta"] / tot_gen) if tot_gen > 0 else (1.0 / len(cups_list))
            )

            c_sc_rate = (c_sc / c_alloc * 100.0) if c_alloc > 0 else 0.0
            c_cov_rate = (c_sc / c_cons * 100.0) if c_cons > 0 else 0.0

            cups_summary_metrics.append(
                CupsMonthlyMetrics(
                    cups=cups,
                    month="Total",
                    beta=avg_beta,
                    consumption_kwh=c_cons,
                    generation_allocated_kwh=c_alloc,
                    self_consumed_kwh=c_sc,
                    surplus_kwh=c_surplus,
                    grid_demand_kwh=c_grid,
                    self_consumption_rate=c_sc_rate,
                    solar_coverage_rate=c_cov_rate,
                )
            )

        return CommunityMonthlyMetrics(
            month="Total",
            strategy=strategy,
            total_consumption_kwh=tot_cons,
            total_generation_kwh=tot_gen,
            total_self_consumed_kwh=tot_sc,
            total_surplus_kwh=tot_surplus,
            total_grid_demand_kwh=tot_grid,
            self_consumption_rate=sc_rate,
            solar_coverage_rate=cov_rate,
            beta_sum=1.0,
            cups_metrics=cups_summary_metrics,
        )
