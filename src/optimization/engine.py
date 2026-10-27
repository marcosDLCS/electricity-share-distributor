"""Core optimization engine for collective PV self-consumption distribution coefficients (RD 244/2019)."""

from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.optimize as opt
from scipy.sparse import dok_matrix

from src.domain.exceptions import (
    EsdError as EsdError,
)
from src.domain.exceptions import (
    OptimizationError as OptimizationError,
)
from src.domain.models import BylawConstraints
from src.ingestion.schema import AlignedDataset
from src.optimization.efficiency import calculate_solar_efficiency
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    HourlyOptimizationResult,
    HourlyProfileMatrix,
    OptimizationResult,
    OptimizationStrategy,
)


class DistributionOptimizer:
    """Computes optimal and baseline electricity distribution coefficients (beta_i)."""

    @staticmethod
    def _solve_optimal_betas(
        consumption: np.ndarray,
        generation: np.ndarray,
        cups_list: list[str] | None = None,
        constraints: BylawConstraints | None = None,
    ) -> np.ndarray:
        """Formulate and solve Linear Program to find betas maximizing collective self-consumption.

        Args:
            consumption: 2D array of shape (T, N) with hourly kWh consumption per CUPS.
            generation: 1D array of shape (T,) with hourly kWh solar PV generation.
            cups_list: Optional list of CUPS identifiers for constraint lookup.
            constraints: Optional regulatory or community bylaw constraints.

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
            # No solar generation in this period: return uniform or bounded distribution with 1% floor
            raw = np.full(n_cups, 1.0 / n_cups)
            if constraints and constraints.is_active and cups_list:
                for i, cups in enumerate(cups_list):
                    l_b, u_b = constraints.get_bounds(cups)
                    l_b = max(0.01, l_b)
                    u_b = max(l_b, u_b)
                    raw[i] = max(l_b, min(u_b, raw[i]))
                raw_sum = float(np.sum(raw))
                if raw_sum > 0:
                    raw = raw / raw_sum
            elif n_cups * 0.01 <= 1.0:
                raw = np.maximum(raw, 0.01)
                raw = raw / np.sum(raw)
            return raw

        # -------------------------------------------------------------------------
        # Linear Programming Epigraph Formulation (RD 244/2019):
        # We want to solve:
        #   max sum_{i, k} min(C_{i, k}, beta_i * G_k)
        #
        # Because min(A, B) is non-linear, we introduce auxiliary variables s_{i, k}:
        #   s_{i, k} represents the self-consumed energy by CUPS i in hour k.
        #
        # For each hour k and CUPS i:
        #   s_{i, k} <= C_{i, k}          (upper bounded by demand)
        #   s_{i, k} <= beta_i * G_k      (upper bounded by allocated generation)
        #
        # Rewriting the second inequality as a standard form constraint:
        #   s_{i, k} - beta_i * G_k <= 0
        #
        # Decision Variables Vector:
        #   [beta_0, ..., beta_{N-1}, s_{0, 0}, ..., s_{N-1, n_sun-1}]
        #   Length: n_cups (the share coefficients) + n_cups * n_sun (hourly self-consumption)
        # -------------------------------------------------------------------------
        n_vars = n_cups + n_cups * n_sun

        # Objective: Maximize sum(s_{i, k}) with slight incentive to allocate generation up to bounds
        c = np.zeros(n_vars)
        c[:n_cups] = -1e-5
        c[n_cups:] = -1.0

        # Constraints Matrix (A_ub * x <= b_ub):
        # Constraint 1: sum(beta_i) <= 1.0 (Regulatory constraint: total share cannot exceed 100%)
        # Constraint 2..M: s_{i, k} - beta_i * G_k <= 0 (Self-consumption cannot exceed allocated generation)
        n_constraints = 1 + n_cups * n_sun
        a_ub = dok_matrix((n_constraints, n_vars))
        b_ub = np.zeros(n_constraints)

        # Constraint 1: sum(beta_i) <= 1.0
        for i in range(n_cups):
            a_ub[0, i] = 1.0
        b_ub[0] = 1.0

        # Constraints 2..M: s_{i, k} - beta_i * G_{sun[k]} <= 0
        row = 1
        for k, t_idx in enumerate(sun_indices):
            g_k = float(generation[t_idx])
            for i in range(n_cups):
                var_idx = n_cups + i * n_sun + k
                a_ub[row, var_idx] = 1.0
                a_ub[row, i] = -g_k
                row += 1

        # Variable Bounds:
        # beta_i in [lower_bound, upper_bound] (minimum 1% floor per CUPS)
        # s_{i, k} in [0.0, C_{i, k}] (cannot self-consume more than actual demand)
        bounds: list[tuple[float, float]] = []
        for i in range(n_cups):
            cups = cups_list[i] if cups_list and i < len(cups_list) else str(i)
            l_b, u_b = constraints.get_bounds(cups) if constraints else (0.0, 1.0)
            l_b = max(0.01, l_b)
            u_b = max(l_b, u_b)
            bounds.append((float(l_b), float(u_b)))

        for i in range(n_cups):
            for t_idx in sun_indices:
                c_val = float(consumption[t_idx, i])
                bounds.append((0.0, max(0.0, c_val)))

        # Solve LP using SciPy HiGHS simplex/interior-point solver
        res = opt.linprog(
            c,
            A_ub=a_ub.tocsc(),
            b_ub=b_ub,
            bounds=bounds,
            method="highs",
        )

        if not res.success:
            raise OptimizationError(f"Linear programming optimization failed: {res.message}")

        betas = np.zeros(n_cups)
        for i in range(n_cups):
            cups = cups_list[i] if cups_list and i < len(cups_list) else str(i)
            l_b, u_b = constraints.get_bounds(cups) if constraints else (0.0, 1.0)
            l_b = max(0.01, l_b)
            u_b = max(l_b, u_b)
            betas[i] = float(np.clip(res.x[i], l_b, u_b))

        # Normalize or distribute remaining share if below 1.0
        beta_sum = float(np.sum(betas))
        if beta_sum > 1.00001:
            betas = betas / beta_sum
        elif beta_sum < 0.9999 and np.sum(generation) > 0:
            rem = 1.0 - beta_sum
            for _ in range(5):
                if rem <= 1e-5:
                    break
                headrooms = np.array(
                    [
                        max(
                            0.0,
                            (
                                constraints.get_bounds(
                                    cups_list[i] if cups_list and i < len(cups_list) else str(i)
                                )[1]
                                if constraints
                                else 1.0
                            )
                            - betas[i],
                        )
                        for i in range(n_cups)
                    ]
                )
                tot_hr = float(np.sum(headrooms))
                if tot_hr <= 1e-6:
                    break
                alloc = np.minimum(headrooms, rem * (headrooms / tot_hr))
                alloc_sum = float(np.sum(alloc))
                if alloc_sum <= 1e-7:
                    break
                betas += alloc
                rem -= alloc_sum

        return betas

    @staticmethod
    def _round_betas(
        betas: np.ndarray,
        precision: int = 0,
        cups_list: list[str] | None = None,
        constraints: BylawConstraints | None = None,
    ) -> np.ndarray:
        """Round coefficients to specified percentage precision using Hare-Niemeyer largest remainder method.

        Guarantees that:
          1. sum(round(betas * 100, precision)) == 100.0 exactly
          2. sum(betas) == 1.0000 exactly
          3. All betas >= 0.0 and respect bylaw constraints (min_share, max_share).
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

        min_floor_units = max(1, round(0.01 * scale))
        lower_units = np.full(n, min_floor_units, dtype=int)
        upper_units = np.full(n, scale, dtype=int)
        if constraints and constraints.is_active and cups_list:
            for i, c in enumerate(cups_list):
                l_b, u_b = constraints.get_bounds(c)
                l_b = max(0.01, l_b)
                lower_units[i] = max(min_floor_units, int(np.floor(round(l_b * scale, 6))))
                upper_units[i] = int(np.ceil(round(u_b * scale, 6)))

        # Clamp initial floors
        floors = np.maximum(floors, lower_units)
        floors = np.minimum(floors, upper_units)

        deficit = scale - int(np.sum(floors))

        if deficit > 0:
            # Distribute remaining units to items with largest remainders that haven't hit upper_units
            order = np.lexsort((-exact_alloc, -remainders))
            for i in range(deficit):
                allocated = False
                for step in range(n):
                    idx = order[(i + step) % n]
                    if floors[idx] < upper_units[idx]:
                        floors[idx] += 1
                        allocated = True
                        break
                if not allocated:
                    floors[order[i % n]] += 1
        elif deficit < 0:
            # Deduct units from items with smallest remainders that haven't hit lower_units
            order = np.lexsort((exact_alloc, remainders))
            for i in range(abs(deficit)):
                allocated = False
                for step in range(n):
                    idx = order[(i + step) % n]
                    if floors[idx] > lower_units[idx]:
                        floors[idx] -= 1
                        allocated = True
                        break
                if not allocated:
                    if floors[order[i % n]] > lower_units[order[i % n]]:
                        floors[order[i % n]] -= 1

        rounded_betas = floors / scale
        return rounded_betas

    @classmethod
    def calculate_betas(
        cls,
        consumption: np.ndarray,
        generation: np.ndarray,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        precision: int = 0,
        cups_list: list[str] | None = None,
        constraints: BylawConstraints | None = None,
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
            raw = cls._solve_optimal_betas(
                consumption, generation, cups_list=cups_list, constraints=constraints
            )

        # Ensure 1% minimum share floor per CUPS prior to rounding
        if n_cups * 0.01 <= 1.0:
            raw = np.maximum(raw, 0.01)
            raw = raw / np.sum(raw)

        return cls._round_betas(
            raw, precision=precision, cups_list=cups_list, constraints=constraints
        )

    @classmethod
    def evaluate_month(
        cls,
        df_month: pd.DataFrame,
        cups_list: list[str],
        month_name: str,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        precision: int = 0,
        cups_uses: dict[str, str] | None = None,
        constraints: BylawConstraints | None = None,
    ) -> CommunityMonthlyMetrics:
        """Evaluate and compute self-consumption metrics for a single month."""
        consumption = df_month[cups_list].values
        generation = df_month["generation_kwh"].values

        betas = cls.calculate_betas(
            consumption,
            generation,
            strategy=strategy,
            precision=precision,
            cups_list=cups_list,
            constraints=constraints,
        )

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

        # Demand specifically during sunlit hours (generation > 1e-4 kWh)
        sun_mask = generation > 1e-4
        if np.any(sun_mask):
            solar_c_cups = np.sum(consumption[sun_mask], axis=0)
        else:
            solar_c_cups = np.zeros(len(cups_list))

        cups_metrics: list[CupsMonthlyMetrics] = []
        for i, cups in enumerate(cups_list):
            c_kwh = float(total_c_cups[i])
            alloc_kwh = float(total_alloc_cups[i])
            sc_kwh = float(total_sc_cups[i])
            surplus_kwh = float(total_surplus_cups[i])
            grid_kwh = float(total_grid_cups[i])
            solar_c_kwh = float(solar_c_cups[i])

            sc_rate = (sc_kwh / alloc_kwh * 100.0) if alloc_kwh > 0 else 0.0
            cov_rate = (sc_kwh / c_kwh * 100.0) if c_kwh > 0 else 0.0
            solar_cov_rate = (sc_kwh / solar_c_kwh * 100.0) if solar_c_kwh > 0 else 0.0

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
                    solar_hours_consumption_kwh=solar_c_kwh,
                    solar_hours_coverage_rate=solar_cov_rate,
                    use=cups_uses.get(cups, "") if cups_uses else "",
                )
            )

        # Community aggregate totals
        comm_cons = float(np.sum(total_c_cups))
        comm_gen = float(np.sum(generation))
        comm_sc = float(np.sum(total_sc_cups))
        comm_surplus = float(comm_gen - comm_sc)
        comm_grid = float(comm_cons - comm_sc)
        comm_solar_cons = float(np.sum(solar_c_cups))

        comm_sc_rate = (comm_sc / comm_gen * 100.0) if comm_gen > 0 else 0.0
        comm_cov_rate = (comm_sc / comm_cons * 100.0) if comm_cons > 0 else 0.0
        comm_solar_cov_rate = (comm_sc / comm_solar_cons * 100.0) if comm_solar_cons > 0 else 0.0

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
            solar_hours_consumption_kwh=comm_solar_cons,
            solar_hours_coverage_rate=comm_solar_cov_rate,
        )

    @staticmethod
    def is_complete_month(df: pd.DataFrame, year: int, month: int) -> bool:
        """Determine whether an aligned dataset for a year-month constitutes a complete month.

        A month is considered complete if:
        1. It spans across the month (earliest day <= 2 and latest day >= days_in_month - 1).
        2. At least 90% of the calendar days in the month are represented.
        3. Total hourly readings cover at least 90% of expected hours in the month.
        """
        if df.empty:
            return False

        days_in_month = calendar.monthrange(year, month)[1]
        ts_days = pd.to_datetime(df.index).day
        unique_days = ts_days.unique()

        if min(unique_days) > 2 or max(unique_days) < days_in_month - 1:
            return False

        if len(unique_days) < int(days_in_month * 0.90):
            return False

        expected_hours = days_in_month * 24
        if len(df) < int(expected_hours * 0.90):
            return False

        return True

    @classmethod
    def _evaluate_calendar_months(
        cls,
        aligned_dataset: AlignedDataset,
        cups_list: list[str],
        strategy: OptimizationStrategy,
        precision: int,
        require_full_month: bool = True,
        cups_uses: dict[str, str] | None = None,
        constraints: BylawConstraints | None = None,
    ) -> list[CommunityMonthlyMetrics]:
        """Evaluate each calendar month (01 to 12), aggregating multi-year data and skipping incomplete months."""
        monthly_results: list[CommunityMonthlyMetrics] = []
        effective_uses = cups_uses or getattr(aligned_dataset, "cups_uses", {}) or {}

        for m in range(1, 13):
            m_str = f"{m:02d}"
            complete_dfs: list[pd.DataFrame] = []

            for ym, group_df in aligned_dataset.monthly_groups.items():
                try:
                    parts = ym.split("-")
                    y_val, m_val = int(parts[0]), int(parts[1])
                    if m_val == m:
                        if not require_full_month or cls.is_complete_month(group_df, y_val, m):
                            complete_dfs.append(group_df)
                except ValueError, IndexError:
                    continue

            if not complete_dfs:
                # Month does not have complete data: skip calculation
                monthly_results.append(
                    CommunityMonthlyMetrics(
                        month=m_str,
                        strategy=strategy.value,
                        total_consumption_kwh=0.0,
                        total_generation_kwh=0.0,
                        total_self_consumed_kwh=0.0,
                        total_surplus_kwh=0.0,
                        total_grid_demand_kwh=0.0,
                        self_consumption_rate=0.0,
                        solar_coverage_rate=0.0,
                        beta_sum=0.0,
                        cups_metrics=[],
                        has_data=False,
                    )
                )
            elif len(complete_dfs) == 1:
                # Exactly one complete year for this calendar month
                res = cls.evaluate_month(
                    complete_dfs[0],
                    cups_list=cups_list,
                    month_name=m_str,
                    strategy=strategy,
                    precision=precision,
                    cups_uses=effective_uses,
                    constraints=constraints,
                )
                res.has_data = True
                monthly_results.append(res)
            else:
                # Multi-year complete data: aggregate by pooling historical observations
                k = len(complete_dfs)
                pooled_df = pd.concat(complete_dfs)
                res = cls.evaluate_month(
                    pooled_df,
                    cups_list=cups_list,
                    month_name=m_str,
                    strategy=strategy,
                    precision=precision,
                    cups_uses=effective_uses,
                    constraints=constraints,
                )
                # Scale energy totals by 1/k to reflect single upcoming year expected energy:
                res.total_generation_kwh /= k
                res.total_consumption_kwh /= k
                res.total_self_consumed_kwh /= k
                res.total_surplus_kwh /= k
                res.total_grid_demand_kwh /= k
                res.solar_hours_consumption_kwh /= k
                scaled_cups: list[CupsMonthlyMetrics] = []
                for cm in res.cups_metrics:
                    scaled_cups.append(
                        CupsMonthlyMetrics(
                            cups=cm.cups,
                            month=cm.month,
                            beta=cm.beta,
                            consumption_kwh=cm.consumption_kwh / k,
                            generation_allocated_kwh=cm.generation_allocated_kwh / k,
                            self_consumed_kwh=cm.self_consumed_kwh / k,
                            surplus_kwh=cm.surplus_kwh / k,
                            grid_demand_kwh=cm.grid_demand_kwh / k,
                            self_consumption_rate=cm.self_consumption_rate,
                            solar_coverage_rate=cm.solar_coverage_rate,
                            solar_hours_consumption_kwh=cm.solar_hours_consumption_kwh / k,
                            solar_hours_coverage_rate=cm.solar_hours_coverage_rate,
                            use=cm.use,
                        )
                    )
                res.cups_metrics = scaled_cups
                res.has_data = True
                monthly_results.append(res)

        return monthly_results

    @classmethod
    def compute_hourly_optimization(
        cls,
        aligned_dataset: AlignedDataset,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        precision: int = 0,
        primary_cups: str | None = None,
        constraints: BylawConstraints | None = None,
    ) -> HourlyOptimizationResult:
        """Compute 24-hour diurnal distribution profile and full hourly time-series balance.

        Args:
            aligned_dataset: Ingested and aligned dataset containing hourly timestamps.
            strategy: Primary optimization strategy ('optimal', 'consumption_share', 'equal').
            precision: Share percentage precision (0, 1, or 2 decimal places).
            primary_cups: Optional identifier of primary CUPS. If None, derived from dataset or configuration.
            constraints: Optional regulatory or community bylaw constraints.

        Returns:
            HourlyOptimizationResult containing HourlyProfileMatrix and time_series_df.
        """
        aligned_df = aligned_dataset.data
        cups_list = aligned_dataset.cups_list
        n_cups = len(cups_list)

        hours_str = [f"{h:02d}" for h in range(24)]

        # Resolve CUPS functional uses for labeling and sorting
        cups_uses: dict[str, str] = getattr(aligned_dataset, "cups_uses", {}) or {}
        if not cups_uses:
            try:
                from src.curation.curator import DataCurator

                cfg = DataCurator().load_cups_config()
                cups_uses = {c.cups: c.use for c in cfg.values() if c.use}
            except Exception:
                cups_uses = {}

        if aligned_df.empty or n_cups == 0:
            empty_matrix = HourlyProfileMatrix(
                cups_list=cups_list,
                hours=hours_str,
                matrix={c: dict.fromkeys(hours_str) for c in cups_list},
                hourly_sums=dict.fromkeys(hours_str),
                average_shares=dict.fromkeys(cups_list),
                average_sum=None,
                cups_uses=cups_uses,
            )
            return HourlyOptimizationResult(
                profile_matrix=empty_matrix,
                time_series_df=pd.DataFrame(),
            )

        # Identify effective primary CUPS if configured
        effective_primary = primary_cups or getattr(aligned_dataset, "primary_cups", None)
        if effective_primary is None:
            try:
                from src.curation.curator import DataCurator

                cups_cfg = DataCurator().load_cups_config()
                candidate = next((c.cups for c in cups_cfg.values() if c.primary), None)
                if candidate and candidate in cups_list:
                    effective_primary = candidate
            except Exception:
                pass

        pri_idx = (
            cups_list.index(effective_primary)
            if effective_primary and effective_primary in cups_list
            else None
        )

        # -------------------------------------------------------------------------
        # 1. 24-Hour Diurnal Profile Matrix (Hours 00:00 to 23:00)
        # -------------------------------------------------------------------------
        dt_index = pd.to_datetime(aligned_df.index)
        hour_series = dt_index.hour

        matrix: dict[str, dict[str, float | None]] = {c: {} for c in cups_list}
        hourly_sums: dict[str, float | None] = {}
        hourly_gen_totals: dict[str, float] = {}

        for h in range(24):
            h_str = f"{h:02d}"
            mask = hour_series == h
            subset = aligned_df.loc[mask]

            if subset.empty:
                for c in cups_list:
                    matrix[c][h_str] = None
                hourly_sums[h_str] = None
                hourly_gen_totals[h_str] = 0.0
            else:
                c_h = subset[cups_list].values
                g_h = subset["generation_kwh"].values
                tot_g_h = float(np.sum(g_h))
                hourly_gen_totals[h_str] = tot_g_h

                if pri_idx is not None and tot_g_h <= 1e-6:
                    raw_zero = np.full(n_cups, 0.01)
                    raw_zero[pri_idx] = 1.0
                    betas_h = cls._round_betas(
                        raw_zero,
                        precision=precision,
                        cups_list=cups_list,
                        constraints=constraints,
                    )
                    for i, c in enumerate(cups_list):
                        matrix[c][h_str] = float(betas_h[i])
                    hourly_sums[h_str] = round(float(np.sum(betas_h)), 6)
                else:
                    betas_h = cls.calculate_betas(
                        c_h,
                        g_h,
                        strategy=strategy,
                        precision=precision,
                        cups_list=cups_list,
                        constraints=constraints,
                    )
                    for i, c in enumerate(cups_list):
                        matrix[c][h_str] = float(betas_h[i])
                    hourly_sums[h_str] = round(float(np.sum(betas_h)), 6)

        # Diurnal generation-weighted average share across all 24 hours
        tot_gen = sum(hourly_gen_totals.values())
        average_shares: dict[str, float | None] = {}
        if tot_gen > 0:
            for c in cups_list:
                weighted_sum = sum(
                    (matrix[c][h_str] or 0.0) * hourly_gen_totals[h_str]
                    for h_str in hours_str
                    if matrix[c][h_str] is not None
                )
                average_shares[c] = weighted_sum / tot_gen
        else:
            for c in cups_list:
                valid_vals = [
                    matrix[c][h_str] for h_str in hours_str if matrix[c][h_str] is not None
                ]
                average_shares[c] = (sum(valid_vals) / len(valid_vals)) if valid_vals else None

        avg_sum = (
            round(sum(v for v in average_shares.values() if v is not None), 6)
            if average_shares
            else None
        )

        profile_matrix = HourlyProfileMatrix(
            cups_list=cups_list,
            hours=hours_str,
            matrix=matrix,
            hourly_sums=hourly_sums,
            average_shares=average_shares,
            average_sum=avg_sum,
            cups_uses=cups_uses,
        )

        # -------------------------------------------------------------------------
        # 2. Full Time-Series Hourly Evaluation & Balance
        # -------------------------------------------------------------------------
        timestamps = aligned_df.index.tolist()
        t_steps = len(timestamps)
        c_arr = aligned_df[cups_list].values
        g_arr = aligned_df["generation_kwh"].values

        if strategy == OptimizationStrategy.EQUAL:
            raw_betas = np.full((t_steps, n_cups), 1.0 / n_cups)
        else:
            c_row_sums = np.sum(c_arr, axis=1, keepdims=True)
            with np.errstate(divide="ignore", invalid="ignore"):
                raw_betas = np.where(c_row_sums > 0, c_arr / c_row_sums, 1.0 / n_cups)

        # Enforce bylaw constraints or 1% minimum share floor per CUPS row-by-row
        if constraints and constraints.is_active and cups_list:
            for i, cups in enumerate(cups_list):
                l_b, u_b = constraints.get_bounds(cups)
                l_b = max(0.01, l_b)
                u_b = max(l_b, u_b)
                raw_betas[:, i] = np.clip(raw_betas[:, i], l_b, u_b)
            raw_betas = raw_betas / np.sum(raw_betas, axis=1, keepdims=True)
        elif n_cups * 0.01 <= 1.0:
            raw_betas = np.maximum(raw_betas, 0.01)
            raw_betas = raw_betas / np.sum(raw_betas, axis=1, keepdims=True)

        # Apply exact Hare-Niemeyer rounding row-by-row respecting constraints
        # In zero-generation hours (e.g. night hours), assign 1% to all and remainder to primary CUPS (bounded by constraints)
        rounded_betas = np.zeros_like(raw_betas)
        for t in range(t_steps):
            if pri_idx is not None and g_arr[t] <= 1e-6:
                raw_zero = np.full(n_cups, 0.01)
                raw_zero[pri_idx] = 1.0
                rounded_betas[t] = cls._round_betas(
                    raw_zero,
                    precision=precision,
                    cups_list=cups_list,
                    constraints=constraints,
                )
            else:
                rounded_betas[t] = cls._round_betas(
                    raw_betas[t],
                    precision=precision,
                    cups_list=cups_list,
                    constraints=constraints,
                )

        # Precompute solar efficiency index once per timestamp
        efficiencies = np.zeros(t_steps, dtype=int)
        temp_arr = (
            aligned_df["temperature"].to_numpy() if "temperature" in aligned_df.columns else None
        )
        cloud_arr = (
            aligned_df["cloud_cover"].to_numpy() if "cloud_cover" in aligned_df.columns else None
        )
        months = dt_index.month.to_numpy()
        hours = dt_index.hour.to_numpy()

        for t in range(t_steps):
            if g_arr[t] > 1e-6:
                t_temp = (
                    float(temp_arr[t]) if temp_arr is not None and pd.notna(temp_arr[t]) else None
                )
                t_cloud = (
                    float(cloud_arr[t])
                    if cloud_arr is not None and pd.notna(cloud_arr[t])
                    else None
                )
                efficiencies[t] = calculate_solar_efficiency(
                    month=int(months[t]),
                    hour=int(hours[t]),
                    temperature=t_temp,
                    cloud_cover=t_cloud,
                )

        uses_list = [cups_uses.get(c, "") for c in cups_list]

        # Vectorized actual shares
        actual_shares = [f"{val:.{precision}f}%" for val in (rounded_betas * 100).flatten()]

        # Precompute 24-hour profile matrix formatted cells per CUPS: shape (24, n_cups)
        est_grid = np.array(
            [
                [
                    profile_matrix.format_cell(cups, f"{h:02d}", precision=precision)
                    for cups in cups_list
                ]
                for h in range(24)
            ],
            dtype=object,
        )
        est_matrix = est_grid[hours]  # shape (t_steps, n_cups)
        est_flat = est_matrix.flatten()
        est_shares = [
            actual if est == "—" else est
            for est, actual in zip(est_flat, actual_shares, strict=False)
        ]

        # Build long-format hourly time series via vectorized arrays
        ts_df = pd.DataFrame(
            {
                "timestamp": np.repeat(timestamps, n_cups),
                "hour": np.repeat(hours, n_cups),
                "cups": np.tile(cups_list, t_steps),
                "use": np.tile(uses_list, t_steps),
                "consumption_kwh": np.round(c_arr, 4).flatten(),
                "generation_kwh": np.repeat(np.round(g_arr, 4), n_cups),
                "share_pct": actual_shares,
                "estimated_share_pct": est_shares,
                "solar_efficiency": np.repeat(efficiencies, n_cups),
            }
        )

        if not ts_df.empty:
            sort_cols = [c for c in ["timestamp", "use", "cups"] if c in ts_df.columns]
            ts_df = ts_df.sort_values(
                by=sort_cols,
                key=lambda col: col.astype(str).str.lower() if col.name in ("use", "cups") else col,
                ascending=[True] * len(sort_cols),
            ).reset_index(drop=True)

        return HourlyOptimizationResult(
            profile_matrix=profile_matrix,
            time_series_df=ts_df,
        )

    @classmethod
    def optimize_dataset(
        cls,
        aligned_dataset: AlignedDataset,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        include_baselines: bool = True,
        precision: int | None = None,
        require_full_month: bool = True,
        compute_hourly: bool = False,
        primary_cups: str | None = None,
        constraints: BylawConstraints | None = None,
    ) -> OptimizationResult:
        """Run optimization for an upcoming calendar year (January to December).

        Args:
            aligned_dataset: Ingested and aligned dataset.
            strategy: Primary optimization strategy.
            include_baselines: If True, also computes results for baseline strategies.
            precision: Share percentage precision (0, 1, or 2 decimals). If None, uses configured setting.
            require_full_month: If True, skips months that do not have at least one complete month of data.
            compute_hourly: If True, computes 24-hour diurnal profile and full hourly time-series balance.
            primary_cups: Optional identifier of primary CUPS.
            constraints: Optional regulatory or community bylaw constraints.

        Returns:
            OptimizationResult containing 12-month calendar prevision, total summary, baselines, and optional hourly_result.
        """
        from src.config import get_precision, validate_share_precision

        active_precision = (
            get_precision() if precision is None else validate_share_precision(precision)
        )
        cups_list = aligned_dataset.cups_list

        cups_uses: dict[str, str] = getattr(aligned_dataset, "cups_uses", {}) or {}
        if not cups_uses:
            try:
                from src.curation.curator import DataCurator

                cups_cfg = DataCurator().load_cups_config()
                cups_uses = {c.cups: c.use for c in cups_cfg.values() if c.use}
            except Exception:
                cups_uses = {}

        # Resolve effective primary CUPS
        effective_primary = primary_cups or getattr(aligned_dataset, "primary_cups", None)
        if effective_primary is None:
            try:
                from src.curation.curator import DataCurator

                cups_cfg = DataCurator().load_cups_config()
                candidate = next((c.cups for c in cups_cfg.values() if c.primary), None)
                if candidate and candidate in cups_list:
                    effective_primary = candidate
            except Exception:
                pass

        monthly_results = cls._evaluate_calendar_months(
            aligned_dataset=aligned_dataset,
            cups_list=cups_list,
            strategy=strategy,
            precision=active_precision,
            require_full_month=require_full_month,
            cups_uses=cups_uses,
            constraints=constraints,
        )

        total_summary = cls._aggregate_summary(
            monthly_results, cups_list, strategy.value, cups_uses=cups_uses
        )

        baselines: dict[str, OptimizationResult] = {}
        if include_baselines:
            for base_strat in (OptimizationStrategy.CONSUMPTION_SHARE, OptimizationStrategy.EQUAL):
                if base_strat != strategy:
                    base_monthly = cls._evaluate_calendar_months(
                        aligned_dataset=aligned_dataset,
                        cups_list=cups_list,
                        strategy=base_strat,
                        precision=active_precision,
                        require_full_month=require_full_month,
                        cups_uses=cups_uses,
                    )
                    base_summary = cls._aggregate_summary(
                        base_monthly, cups_list, base_strat.value, cups_uses=cups_uses
                    )
                    baselines[base_strat.value] = OptimizationResult(
                        strategy=base_strat.value,
                        monthly_results=base_monthly,
                        total_summary=base_summary,
                        baselines={},
                        cups_list=cups_list,
                        cups_uses=cups_uses,
                        primary_cups=effective_primary,
                    )

        hourly_result: HourlyOptimizationResult | None = None
        if compute_hourly:
            hourly_result = cls.compute_hourly_optimization(
                aligned_dataset=aligned_dataset,
                strategy=strategy,
                precision=active_precision,
                primary_cups=effective_primary,
                constraints=constraints,
            )

        return OptimizationResult(
            strategy=strategy.value,
            monthly_results=monthly_results,
            total_summary=total_summary,
            baselines=baselines,
            cups_list=cups_list,
            hourly_result=hourly_result,
            cups_uses=cups_uses,
            constraints=constraints,
            primary_cups=effective_primary,
        )

    @staticmethod
    def _aggregate_summary(
        monthly_results: list[CommunityMonthlyMetrics],
        cups_list: list[str],
        strategy: str,
        cups_uses: dict[str, str] | None = None,
    ) -> CommunityMonthlyMetrics:
        """Compute aggregate total metrics across multiple months."""
        active_months = [m for m in monthly_results if m.has_data]
        if not active_months:
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
                cups_metrics=[
                    CupsMonthlyMetrics(
                        cups=c,
                        month="Total",
                        beta=0.0,
                        consumption_kwh=0.0,
                        generation_allocated_kwh=0.0,
                        self_consumed_kwh=0.0,
                        surplus_kwh=0.0,
                        grid_demand_kwh=0.0,
                        self_consumption_rate=0.0,
                        solar_coverage_rate=0.0,
                        use=cups_uses.get(c, "") if cups_uses else "",
                    )
                    for c in cups_list
                ],
                has_data=False,
            )

        tot_cons = sum(m.total_consumption_kwh for m in active_months)
        tot_gen = sum(m.total_generation_kwh for m in active_months)
        tot_sc = sum(m.total_self_consumed_kwh for m in active_months)
        tot_surplus = sum(m.total_surplus_kwh for m in active_months)
        tot_grid = sum(m.total_grid_demand_kwh for m in active_months)
        tot_solar_cons = sum(m.solar_hours_consumption_kwh for m in active_months)

        sc_rate = (tot_sc / tot_gen * 100.0) if tot_gen > 0 else 0.0
        cov_rate = (tot_sc / tot_cons * 100.0) if tot_cons > 0 else 0.0
        solar_cov_rate = (tot_sc / tot_solar_cons * 100.0) if tot_solar_cons > 0 else 0.0

        # Aggregate per CUPS
        cups_aggregates: dict[str, dict[str, float]] = {
            c: {
                "cons": 0.0,
                "alloc": 0.0,
                "sc": 0.0,
                "surplus": 0.0,
                "grid": 0.0,
                "weighted_beta": 0.0,
                "solar_cons": 0.0,
            }
            for c in cups_list
        }

        for m in active_months:
            m_gen = m.total_generation_kwh
            for cm in m.cups_metrics:
                entry = cups_aggregates[cm.cups]
                entry["cons"] += cm.consumption_kwh
                entry["alloc"] += cm.generation_allocated_kwh
                entry["sc"] += cm.self_consumed_kwh
                entry["surplus"] += cm.surplus_kwh
                entry["grid"] += cm.grid_demand_kwh
                entry["weighted_beta"] += cm.beta * m_gen
                entry["solar_cons"] += cm.solar_hours_consumption_kwh

        cups_summary_metrics: list[CupsMonthlyMetrics] = []
        for cups in cups_list:
            c_data = cups_aggregates[cups]
            c_cons = c_data["cons"]
            c_alloc = c_data["alloc"]
            c_sc = c_data["sc"]
            c_surplus = c_data["surplus"]
            c_grid = c_data["grid"]
            c_solar_cons = c_data["solar_cons"]
            avg_beta = (
                (c_data["weighted_beta"] / tot_gen) if tot_gen > 0 else (1.0 / len(cups_list))
            )

            c_sc_rate = (c_sc / c_alloc * 100.0) if c_alloc > 0 else 0.0
            c_cov_rate = (c_sc / c_cons * 100.0) if c_cons > 0 else 0.0
            c_solar_cov_rate = (c_sc / c_solar_cons * 100.0) if c_solar_cons > 0 else 0.0

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
                    solar_hours_consumption_kwh=c_solar_cons,
                    solar_hours_coverage_rate=c_solar_cov_rate,
                    use=cups_uses.get(cups, "") if cups_uses else "",
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
            has_data=True,
            solar_hours_consumption_kwh=tot_solar_cons,
            solar_hours_coverage_rate=solar_cov_rate,
        )

    @classmethod
    def resolve_full_year_monthly_betas(
        cls,
        opt_result: OptimizationResult,
        aligned_dataset: AlignedDataset | None = None,
        consumption_dir: Path | str | None = None,
        target_year: int | None = None,
        precision: int = 4,
    ) -> dict[str, dict[str, float]]:
        """Resolve distribution coefficients for all 12 calendar months (01..12).

        Uses solved monthly optimization results where complete generation data exists.
        For missing or incomplete months, estimates coefficients using available
        consumption data (prioritizing solar daylight hours 08:00..18:00).
        If no consumption data is available for a month, falls back to the average of
        resolved months or uniform allocation.

        All coefficients are rounded using Hare-Niemeyer rounding (precision=4, scale=10^6)
        and respect bylaw constraints (min_share, max_share).

        Returns:
            Dictionary mapping month strings '01'..'12' to {cups: beta_float}.
        """
        cups_list = list(opt_result.cups_list)
        if not cups_list and aligned_dataset:
            cups_list = list(aligned_dataset.cups_list)
        if not cups_list and opt_result.total_summary and opt_result.total_summary.cups_metrics:
            cups_list = [c.cups for c in opt_result.total_summary.cups_metrics]
        if not cups_list:
            for m in opt_result.monthly_results:
                if m.cups_metrics:
                    cups_list = [c.cups for c in m.cups_metrics]
                    break

        if not cups_list:
            return {}

        n_cups = len(cups_list)
        complete_monthly: dict[str, np.ndarray] = {}

        # 1. Collect already-optimized months that have complete data
        for m_res in opt_result.monthly_results:
            if m_res.has_data and m_res.cups_metrics:
                m_key = m_res.month.split("-")[-1] if "-" in m_res.month else m_res.month
                try:
                    m_str = f"{int(m_key):02d}"
                except ValueError:
                    continue
                cups_beta = {c.cups: c.beta for c in m_res.cups_metrics}
                raw = np.array([cups_beta.get(c, 0.0) for c in cups_list], dtype=float)
                if np.sum(raw) > 0:
                    rounded = cls._round_betas(
                        raw,
                        precision=precision,
                        cups_list=cups_list,
                        constraints=opt_result.constraints,
                    )
                    complete_monthly[m_str] = rounded

        # 2. For missing months, estimate from aligned curated dataset
        missing_months = [f"{m:02d}" for m in range(1, 13) if f"{m:02d}" not in complete_monthly]
        if missing_months:
            cons_df: pd.DataFrame | None = None
            _ = consumption_dir

            if aligned_dataset is not None and not aligned_dataset.data.empty:
                try:
                    avail_cols = [c for c in cups_list if c in aligned_dataset.data.columns]
                    if avail_cols:
                        p_df = aligned_dataset.data[avail_cols].reset_index()
                        ts_col = "timestamp" if "timestamp" in p_df.columns else p_df.columns[0]
                        cons_df = p_df.melt(
                            id_vars=[ts_col],
                            value_vars=avail_cols,
                            var_name="cups",
                            value_name="consumption_kwh",
                        ).rename(columns={ts_col: "timestamp"})
                except Exception:
                    cons_df = None

            # Process missing months if we have consumption records
            if cons_df is not None and not cons_df.empty:
                cons_df["timestamp"] = cons_df["timestamp"].astype(str)
                cons_df["consumption_kwh"] = pd.to_numeric(
                    cons_df["consumption_kwh"], errors="coerce"
                ).fillna(0.0)

                for m_str in list(missing_months):
                    sub = pd.DataFrame()
                    if target_year is not None:
                        prefix = f"{target_year:04d}-{m_str}"
                        sub = cons_df[cons_df["timestamp"].str.startswith(prefix)]

                    if sub.empty:
                        sub = cons_df[cons_df["timestamp"].str.slice(5, 7) == m_str]

                    if sub.empty:
                        continue

                    # Filter for daytime solar hours (08:00 to 18:00)
                    ts_hour = pd.to_numeric(
                        sub["timestamp"].str.slice(11, 13), errors="coerce"
                    ).fillna(0)
                    solar_mask = (ts_hour >= 8) & (ts_hour <= 18)
                    solar_sub = sub[solar_mask]

                    if not solar_sub.empty and solar_sub["consumption_kwh"].sum() > 0:
                        grouped = solar_sub.groupby("cups")["consumption_kwh"].sum()
                    else:
                        grouped = sub.groupby("cups")["consumption_kwh"].sum()

                    raw_c = np.array([float(grouped.get(c, 0.0)) for c in cups_list], dtype=float)
                    if np.sum(raw_c) > 0:
                        c_shares = raw_c / np.sum(raw_c)
                        if n_cups * 0.01 <= 1.0:
                            c_shares = np.maximum(c_shares, 0.01)
                            c_shares = c_shares / np.sum(c_shares)
                        rounded = cls._round_betas(
                            c_shares,
                            precision=precision,
                            cups_list=cups_list,
                            constraints=opt_result.constraints,
                        )
                        complete_monthly[m_str] = rounded
                        missing_months.remove(m_str)

        # 3. For any remaining missing months, fallback to average of resolved months or uniform
        if missing_months:
            if complete_monthly:
                avg_raw = np.mean(list(complete_monthly.values()), axis=0)
            else:
                avg_raw = np.full(n_cups, 1.0 / n_cups)

            fallback_rounded = cls._round_betas(
                avg_raw,
                precision=precision,
                cups_list=cups_list,
                constraints=opt_result.constraints,
            )
            for m_str in missing_months:
                complete_monthly[m_str] = fallback_rounded

        # Build output dictionary for all 12 months in order '01'..'12'
        result: dict[str, dict[str, float]] = {}
        for m in range(1, 13):
            m_str = f"{m:02d}"
            betas_arr = complete_monthly[m_str]
            result[m_str] = {c: float(betas_arr[i]) for i, c in enumerate(cups_list)}

        return result
