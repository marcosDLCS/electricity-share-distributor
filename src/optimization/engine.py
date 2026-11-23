"""Core optimization engine for collective PV self-consumption distribution coefficients (RD 244/2019)."""

from __future__ import annotations

import calendar

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

    MIN_FORTNIGHT_SOLAR_DAYS: int = 5

    @staticmethod
    def _count_calendar_days(dfs: list[pd.DataFrame]) -> int:
        """Count distinct calendar dates across DataFrames."""
        dates: set[object] = set()
        for df in dfs:
            if not df.empty:
                dates.update(pd.to_datetime(df.index).date)
        return len(dates)

    @staticmethod
    def _count_active_solar_days(dfs: list[pd.DataFrame]) -> int:
        """Count distinct calendar dates across DataFrames with active solar generation."""
        active_dates: set[object] = set()
        for df in dfs:
            if df.empty or "generation_kwh" not in df.columns:
                continue
            sun_mask = df["generation_kwh"].values > 1e-4
            if np.any(sun_mask):
                sun_dates = pd.to_datetime(df.index[sun_mask]).date
                active_dates.update(sun_dates)
        return len(active_dates)

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
        """Round 1D (N,) or 2D (T, N) coefficients via vectorized Hare-Niemeyer largest remainder.

        Guarantees per row that:
          1. sum(round(betas * 100, precision)) == 100.0 exactly
          2. sum(betas) == 1.0000 exactly
          3. All betas >= 0.0 and respect bylaw constraints (min_share, max_share).
        """
        arr = np.asarray(betas, dtype=float)
        was_1d = arr.ndim == 1
        mat = np.atleast_2d(arr)
        t_rows, n = mat.shape
        if t_rows == 0 or n == 0:
            return arr

        # Scale factor for target precision:
        # precision=0 -> scale=100, precision=1 -> scale=1000, precision=2 -> scale=10000
        scale = 100 * (10**precision)

        # Normalize raw betas per row to sum to 1.0 before rounding
        row_sums = np.sum(mat, axis=1, keepdims=True)
        norm_mat = np.where(row_sums > 0, mat / np.where(row_sums > 0, row_sums, 1.0), 1.0 / n)

        exact_alloc = norm_mat * scale
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

        # Clamp initial floors to regulatory / bylaw bounds
        floors = np.clip(floors, lower_units, upper_units)
        deficits = scale - np.sum(floors, axis=1)

        # Allocate positive deficits to largest remainders not at upper_units
        while True:
            pos_rows = np.where(deficits > 0)[0]
            if len(pos_rows) == 0:
                break
            sub_floors = floors[pos_rows]
            eligible = sub_floors < upper_units
            elig_counts = np.sum(eligible, axis=1)
            no_elig = elig_counts == 0
            if np.any(no_elig):
                eligible = np.where(no_elig[:, np.newaxis], True, eligible)
                elig_counts = np.where(no_elig, n, elig_counts)

            sub_exact = exact_alloc[pos_rows]
            sub_rem = remainders[pos_rows]

            c1 = np.argsort(-sub_exact, axis=1, kind="mergesort")
            c2 = np.take_along_axis(
                c1,
                np.argsort(-np.take_along_axis(sub_rem, c1, axis=1), axis=1, kind="mergesort"),
                axis=1,
            )
            order = np.take_along_axis(
                c2,
                np.argsort(~np.take_along_axis(eligible, c2, axis=1), axis=1, kind="mergesort"),
                axis=1,
            )
            k_p = np.minimum(deficits[pos_rows], elig_counts)
            p_idx, pos_idx = np.where(np.arange(n)[np.newaxis, :] < k_p[:, np.newaxis])
            np.add.at(floors, (pos_rows[p_idx], order[p_idx, pos_idx]), 1)
            deficits[pos_rows] -= k_p

        # Deduct negative deficits from smallest remainders above lower_units
        while True:
            neg_rows = np.where(deficits < 0)[0]
            if len(neg_rows) == 0:
                break
            sub_floors = floors[neg_rows]
            eligible = sub_floors > lower_units
            elig_counts = np.sum(eligible, axis=1)
            has_elig = elig_counts > 0
            if not np.any(has_elig):
                break
            if not np.all(has_elig):
                neg_rows = neg_rows[has_elig]
                sub_floors = sub_floors[has_elig]
                eligible = eligible[has_elig]
                elig_counts = elig_counts[has_elig]

            sub_exact = exact_alloc[neg_rows]
            sub_rem = remainders[neg_rows]

            c1 = np.argsort(sub_exact, axis=1, kind="mergesort")
            c2 = np.take_along_axis(
                c1,
                np.argsort(np.take_along_axis(sub_rem, c1, axis=1), axis=1, kind="mergesort"),
                axis=1,
            )
            order = np.take_along_axis(
                c2,
                np.argsort(~np.take_along_axis(eligible, c2, axis=1), axis=1, kind="mergesort"),
                axis=1,
            )
            k_n = np.minimum(-deficits[neg_rows], elig_counts)
            p_idx, pos_idx = np.where(np.arange(n)[np.newaxis, :] < k_n[:, np.newaxis])
            np.add.at(floors, (neg_rows[p_idx], order[p_idx, pos_idx]), -1)
            deficits[neg_rows] += k_n

        rounded_betas = floors / scale
        return rounded_betas[0] if was_1d else rounded_betas

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
        override_betas: np.ndarray | None = None,
    ) -> CommunityMonthlyMetrics:
        """Evaluate and compute self-consumption metrics for a single month."""
        consumption = df_month[cups_list].values
        generation = df_month["generation_kwh"].values

        if override_betas is not None and len(override_betas) == len(cups_list):
            betas = override_betas
        else:
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
        comm_solar_hours_count = int(np.sum(sun_mask))
        comm_solar_gen = float(np.sum(generation[sun_mask])) if np.any(sun_mask) else 0.0
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
            solar_gen_kwh = float(comm_solar_gen * betas[i])

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
                    solar_hours_generation_kwh=solar_gen_kwh,
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
            solar_hours_generation_kwh=comm_solar_gen,
            solar_hours_count=comm_solar_hours_count,
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

    @staticmethod
    def is_complete_fortnight(df: pd.DataFrame, year: int, month: int, fortnight: int) -> bool:
        """Determine whether an aligned dataset for a year-month-fortnight is complete (>= 90% hours)."""
        if df.empty or fortnight not in (1, 2):
            return False

        days_in_month = calendar.monthrange(year, month)[1]
        days_in_fortnight = 15 if fortnight == 1 else (days_in_month - 15)
        expected_hours = days_in_fortnight * 24
        return len(df) >= int(expected_hours * 0.90)

    @classmethod
    def _collect_calendar_month_dfs(
        cls,
        aligned_dataset: AlignedDataset,
        month: int,
        require_full_month: bool = False,
    ) -> list[tuple[int, pd.DataFrame]]:
        """Collect (year, DataFrame) entries matching calendar month, optionally filtering complete months."""
        monthly_groups = aligned_dataset.monthly_groups
        if not monthly_groups and not aligned_dataset.data.empty:
            monthly_groups = {
                str(ym): group
                for ym, group in aligned_dataset.data.groupby(
                    aligned_dataset.data.index.astype(str).str.slice(0, 7)
                )
            }

        entries: list[tuple[int, pd.DataFrame]] = []
        for ym, group_df in monthly_groups.items():
            try:
                parts = ym.split("-")
                y_val, m_val = int(parts[0]), int(parts[1])
                if m_val == month and not group_df.empty:
                    if not require_full_month or cls.is_complete_month(group_df, y_val, month):
                        entries.append((y_val, group_df))
            except ValueError, IndexError:
                continue
        return entries

    @classmethod
    def _evaluate_calendar_months(
        cls,
        aligned_dataset: AlignedDataset,
        cups_list: list[str],
        strategy: OptimizationStrategy,
        precision: int,
        require_full_month: bool = False,
        cups_uses: dict[str, str] | None = None,
        constraints: BylawConstraints | None = None,
    ) -> list[CommunityMonthlyMetrics]:
        """Evaluate each calendar month (01 to 12), aggregating multi-year data and skipping incomplete months."""
        monthly_results: list[CommunityMonthlyMetrics] = []
        effective_uses = cups_uses or getattr(aligned_dataset, "cups_uses", {}) or {}

        for m in range(1, 13):
            m_str = f"{m:02d}"
            complete_dfs = [
                df
                for _, df in cls._collect_calendar_month_dfs(
                    aligned_dataset, m, require_full_month=require_full_month
                )
            ]

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
                        solar_hours_consumption_kwh=0.0,
                        solar_hours_coverage_rate=0.0,
                        solar_hours_generation_kwh=0.0,
                        solar_hours_count=0,
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
                res.solar_hours_generation_kwh /= k
                res.solar_hours_count = round(res.solar_hours_count / k)
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
                            solar_hours_generation_kwh=cm.solar_hours_generation_kwh / k,
                            use=cm.use,
                        )
                    )
                res.cups_metrics = scaled_cups
                res.has_data = True
                monthly_results.append(res)

        return monthly_results

    @classmethod
    def _evaluate_calendar_fortnights(
        cls,
        aligned_dataset: AlignedDataset,
        cups_list: list[str],
        strategy: OptimizationStrategy,
        precision: int,
        require_full_month: bool = False,
        cups_uses: dict[str, str] | None = None,
        constraints: BylawConstraints | None = None,
    ) -> list[CommunityMonthlyMetrics]:
        """Evaluate each calendar fortnight (24 half-month periods: days 1-15 and days 16-end per month)."""
        fortnight_results: list[CommunityMonthlyMetrics] = []
        effective_uses = cups_uses or getattr(aligned_dataset, "cups_uses", {}) or {}

        for m in range(1, 13):
            m_str = f"{m:02d}"
            month_entries = cls._collect_calendar_month_dfs(
                aligned_dataset, m, require_full_month=require_full_month
            )
            month_dfs = [df for _, df in month_entries]

            month_solar_days = cls._count_active_solar_days(month_dfs)
            month_fallback_betas: np.ndarray | None = None

            for f in (1, 2):
                period_str = f"{m_str}-{f}"
                fortnight_dfs: list[pd.DataFrame] = []

                for y_val, group_df in month_entries:
                    ts_days = pd.to_datetime(group_df.index).day
                    f_df = group_df[ts_days <= 15] if f == 1 else group_df[ts_days >= 16]
                    if f_df.empty:
                        continue
                    if require_full_month and not cls.is_complete_fortnight(f_df, y_val, m, f):
                        continue
                    fortnight_dfs.append(f_df)

                if not fortnight_dfs:
                    fortnight_results.append(
                        CommunityMonthlyMetrics(
                            month=period_str,
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
                            solar_hours_consumption_kwh=0.0,
                            solar_hours_coverage_rate=0.0,
                            solar_hours_generation_kwh=0.0,
                            solar_hours_count=0,
                        )
                    )
                    continue

                # Resilient fallback: if a multi-day fortnight has fewer than MIN_FORTNIGHT_SOLAR_DAYS
                # active solar days (e.g. due to an inverter telemetry outage) and the full
                # calendar month has broader solar coverage, derive betas from the full month.
                override_betas: np.ndarray | None = None
                fortnight_total_days = cls._count_calendar_days(fortnight_dfs)
                fortnight_solar_days = cls._count_active_solar_days(fortnight_dfs)
                if (
                    fortnight_total_days >= cls.MIN_FORTNIGHT_SOLAR_DAYS
                    and fortnight_solar_days < cls.MIN_FORTNIGHT_SOLAR_DAYS
                    and month_solar_days > fortnight_solar_days
                ):
                    if month_fallback_betas is None:
                        pooled_month_df = pd.concat(month_dfs)
                        month_fallback_betas = cls.calculate_betas(
                            pooled_month_df[cups_list].values,
                            pooled_month_df["generation_kwh"].values,
                            strategy=strategy,
                            precision=precision,
                            cups_list=cups_list,
                            constraints=constraints,
                        )
                    override_betas = month_fallback_betas

                if len(fortnight_dfs) == 1:
                    res = cls.evaluate_month(
                        fortnight_dfs[0],
                        cups_list=cups_list,
                        month_name=period_str,
                        strategy=strategy,
                        precision=precision,
                        cups_uses=effective_uses,
                        constraints=constraints,
                        override_betas=override_betas,
                    )
                    res.has_data = True
                    fortnight_results.append(res)
                else:
                    k = len(fortnight_dfs)
                    pooled_df = pd.concat(fortnight_dfs)
                    res = cls.evaluate_month(
                        pooled_df,
                        cups_list=cups_list,
                        month_name=period_str,
                        strategy=strategy,
                        precision=precision,
                        cups_uses=effective_uses,
                        constraints=constraints,
                        override_betas=override_betas,
                    )
                    res.total_generation_kwh /= k
                    res.total_consumption_kwh /= k
                    res.total_self_consumed_kwh /= k
                    res.total_surplus_kwh /= k
                    res.total_grid_demand_kwh /= k
                    res.solar_hours_consumption_kwh /= k
                    res.solar_hours_generation_kwh /= k
                    res.solar_hours_count = round(res.solar_hours_count / k)
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
                                solar_hours_generation_kwh=cm.solar_hours_generation_kwh / k,
                                use=cm.use,
                            )
                        )
                    res.cups_metrics = scaled_cups
                    res.has_data = True
                    fortnight_results.append(res)

        return fortnight_results

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

        # Read pre-resolved CUPS functional uses directly from aligned_dataset
        cups_uses: dict[str, str] = (
            dict(aligned_dataset.cups_uses) if aligned_dataset.cups_uses else {}
        )

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

        # Read pre-resolved primary CUPS directly from argument or aligned_dataset
        effective_primary = primary_cups or aligned_dataset.primary_cups
        if effective_primary and effective_primary not in cups_list:
            effective_primary = None

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

        # Apply exact 2D Hare-Niemeyer rounding respecting constraints
        # In zero-generation hours (e.g. night hours), assign 1% to all and remainder to primary CUPS (bounded by constraints)
        sun_mask = g_arr > 1e-6
        if pri_idx is not None:
            rounded_betas = np.empty_like(raw_betas)
            if np.any(sun_mask):
                rounded_betas[sun_mask] = cls._round_betas(
                    raw_betas[sun_mask],
                    precision=precision,
                    cups_list=cups_list,
                    constraints=constraints,
                )
            zero_mask = ~sun_mask
            if np.any(zero_mask):
                raw_zero = np.full(n_cups, 0.01)
                raw_zero[pri_idx] = 1.0
                rounded_betas[zero_mask] = cls._round_betas(
                    raw_zero,
                    precision=precision,
                    cups_list=cups_list,
                    constraints=constraints,
                )
        else:
            rounded_betas = cls._round_betas(
                raw_betas,
                precision=precision,
                cups_list=cups_list,
                constraints=constraints,
            )

        # Precompute solar efficiency index in a single vectorized call across sunlit timestamps
        efficiencies = np.zeros(t_steps, dtype=int)
        temp_arr = (
            pd.to_numeric(aligned_df["temperature"], errors="coerce").to_numpy(dtype=float)
            if "temperature" in aligned_df.columns
            else None
        )
        cloud_arr = (
            pd.to_numeric(aligned_df["cloud_cover"], errors="coerce").to_numpy(dtype=float)
            if "cloud_cover" in aligned_df.columns
            else None
        )
        months = dt_index.month.to_numpy()
        hours = dt_index.hour.to_numpy()

        if np.any(sun_mask):
            efficiencies[sun_mask] = calculate_solar_efficiency(
                month=months[sun_mask],
                hour=hours[sun_mask],
                temperature=temp_arr[sun_mask] if temp_arr is not None else None,
                cloud_cover=cloud_arr[sun_mask] if cloud_arr is not None else None,
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
    def _evaluate_hourly_df_self_consumption(
        cls,
        df: pd.DataFrame,
        cups_list: list[str],
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        precision: int = 0,
        constraints: BylawConstraints | None = None,
    ) -> float:
        """Compute total collective dynamic hourly self-consumption (kWh) over a single DataFrame."""
        n_cups = len(cups_list)
        if df.empty or n_cups == 0 or "generation_kwh" not in df.columns:
            return 0.0

        c_arr = df[cups_list].to_numpy(dtype=float)
        g_arr = df["generation_kwh"].to_numpy(dtype=float)

        # Only hours with non-zero generation contribute to self-consumption
        sun_mask = g_arr > 1e-6
        if not np.any(sun_mask):
            return 0.0

        sun_indices = np.where(sun_mask)[0]
        c_sun = c_arr[sun_indices]
        g_sun = g_arr[sun_indices]

        if strategy == OptimizationStrategy.EQUAL:
            raw_betas = np.full((len(sun_indices), n_cups), 1.0 / n_cups)
        else:
            c_row_sums = np.sum(c_sun, axis=1, keepdims=True)
            with np.errstate(divide="ignore", invalid="ignore"):
                raw_betas = np.where(c_row_sums > 0, c_sun / c_row_sums, 1.0 / n_cups)

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

        rounded_betas = cls._round_betas(
            raw_betas,
            precision=precision,
            cups_list=cups_list,
            constraints=constraints,
        )

        alloc_sun = rounded_betas * g_sun[:, np.newaxis]
        sc_sun = np.minimum(c_sun, alloc_sun)
        return float(np.sum(sc_sun))

    @classmethod
    def evaluate_hourly_self_consumption(
        cls,
        aligned_dataset: AlignedDataset,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        precision: int = 0,
        primary_cups: str | None = None,
        constraints: BylawConstraints | None = None,
        require_full_month: bool = False,
    ) -> float:
        """Calculate exact collective self-consumption under dynamic hourly allocation (Orden TED/1247/2021).

        Applies per-calendar-month completeness filtering and 1/k_m multi-year scaling
        matching the monthly and fortnight previsions.

        Args:
            aligned_dataset: Ingested and aligned dataset containing hourly timestamps.
            strategy: Primary optimization strategy.
            precision: Share percentage precision (0, 1, or 2 decimal places).
            primary_cups: Optional identifier of primary CUPS.
            constraints: Optional regulatory or community bylaw constraints.
            require_full_month: If True, excludes incomplete calendar months (<90% days/hours).

        Returns:
            Scaled expected annual kilowatt-hours self-consumed collectively.
        """
        del (
            primary_cups
        )  # Unused by dynamic hourly proportionality; retained for API compatibility.
        aligned_df = aligned_dataset.data
        cups_list = aligned_dataset.cups_list
        if aligned_df.empty or not cups_list or "generation_kwh" not in aligned_df.columns:
            return 0.0

        total_hourly_sc = 0.0
        for m in range(1, 13):
            month_entries = cls._collect_calendar_month_dfs(
                aligned_dataset, m, require_full_month=require_full_month
            )
            if not month_entries:
                continue

            month_dfs = [df for _, df in month_entries]
            pooled_df = month_dfs[0] if len(month_dfs) == 1 else pd.concat(month_dfs)
            month_sc = cls._evaluate_hourly_df_self_consumption(
                pooled_df,
                cups_list=cups_list,
                strategy=strategy,
                precision=precision,
                constraints=constraints,
            )
            total_hourly_sc += month_sc / len(month_entries)

        return float(total_hourly_sc)

    @classmethod
    def _evaluate_current_self_consumption(
        cls,
        aligned_dataset: AlignedDataset,
        effective_primary: str | None,
        total_summary: CommunityMonthlyMetrics,
        require_full_month: bool = False,
    ) -> float:
        """Evaluate bounded physical behind-the-meter self-consumption with 1/k_m calendar scaling."""
        aligned_df = aligned_dataset.data
        has_curated_sc = (
            "self_consumption" in aligned_df.columns
            and float(aligned_df["self_consumption"].sum()) > 0
        )
        has_primary_series = bool(
            effective_primary
            and effective_primary in aligned_df.columns
            and "generation_kwh" in aligned_df.columns
        )

        if has_curated_sc or has_primary_series:
            total_current_sc = 0.0
            for m in range(1, 13):
                month_entries = cls._collect_calendar_month_dfs(
                    aligned_dataset, m, require_full_month=require_full_month
                )
                if not month_entries:
                    continue

                month_dfs = [df for _, df in month_entries]
                pooled_df = month_dfs[0] if len(month_dfs) == 1 else pd.concat(month_dfs)

                g_val = (
                    np.clip(pooled_df["generation_kwh"].to_numpy(dtype=float), 0.0, None)
                    if "generation_kwh" in pooled_df.columns
                    else None
                )
                c_pri = (
                    np.clip(pooled_df[effective_primary].to_numpy(dtype=float), 0.0, None)
                    if effective_primary and effective_primary in pooled_df.columns
                    else None
                )

                if has_curated_sc and "self_consumption" in pooled_df.columns:
                    sc_vals = np.clip(
                        pooled_df["self_consumption"].to_numpy(dtype=float), 0.0, None
                    )
                    if g_val is not None:
                        sc_vals = np.minimum(sc_vals, g_val)
                    if c_pri is not None:
                        sc_vals = np.minimum(sc_vals, c_pri)
                    month_sc = float(np.sum(sc_vals))
                elif c_pri is not None and g_val is not None:
                    month_sc = float(np.sum(np.minimum(c_pri, g_val)))
                else:
                    month_sc = 0.0

                total_current_sc += month_sc / len(month_entries)
            return float(total_current_sc)

        pri_metric = (
            next((c for c in total_summary.cups_metrics if c.cups == effective_primary), None)
            if effective_primary
            else (total_summary.cups_metrics[0] if total_summary.cups_metrics else None)
        )
        return float(pri_metric.self_consumed_kwh) if pri_metric else 0.0

    @classmethod
    def optimize_dataset(
        cls,
        aligned_dataset: AlignedDataset,
        strategy: OptimizationStrategy = OptimizationStrategy.OPTIMAL,
        include_baselines: bool = True,
        precision: int | None = None,
        require_full_month: bool = False,
        compute_hourly: bool = True,
        primary_cups: str | None = None,
        constraints: BylawConstraints | None = None,
    ) -> OptimizationResult:
        """Run optimization for an upcoming calendar year (January to December).

        Args:
            aligned_dataset: Ingested and aligned dataset.
            strategy: Primary optimization strategy.
            include_baselines: If True, also computes results for baseline strategies.
            precision: Share percentage precision (0, 1, or 2 decimals). If None, uses configured setting.
            require_full_month: If True, skips months that do not have at least one complete month of data. Defaults to False.
            compute_hourly: If True, computes 24-hour diurnal profile and full hourly time-series balance. Defaults to True.
            primary_cups: Optional identifier of primary CUPS.
            constraints: Optional regulatory or community bylaw constraints.

        Returns:
            OptimizationResult containing 12-month calendar prevision, 24-fortnight prevision, total summary, baselines, and hourly_result.
        """
        from src.config import get_precision, validate_share_precision

        active_precision = (
            get_precision() if precision is None else validate_share_precision(precision)
        )
        cups_list = aligned_dataset.cups_list

        cups_uses: dict[str, str] = (
            dict(aligned_dataset.cups_uses) if aligned_dataset.cups_uses else {}
        )
        effective_primary = primary_cups or aligned_dataset.primary_cups
        if effective_primary and effective_primary not in cups_list:
            effective_primary = None

        monthly_results = cls._evaluate_calendar_months(
            aligned_dataset=aligned_dataset,
            cups_list=cups_list,
            strategy=strategy,
            precision=active_precision,
            require_full_month=require_full_month,
            cups_uses=cups_uses,
            constraints=constraints,
        )

        fortnight_results = cls._evaluate_calendar_fortnights(
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

        # 1. Current Self-Consumption (physical baseline prior to collective distribution)
        current_sc = cls._evaluate_current_self_consumption(
            aligned_dataset=aligned_dataset,
            effective_primary=effective_primary,
            total_summary=total_summary,
            require_full_month=require_full_month,
        )

        # 2. Monthly Share Self-Consumption (RD 244/2019 fixed monthly betas)
        monthly_sc = float(total_summary.total_self_consumed_kwh)

        # 3. Fortnight Share Self-Consumption (half-month betas)
        fortnight_sc = float(
            sum(f.total_self_consumed_kwh for f in fortnight_results if f.has_data)
        )

        # 4. Dynamic Hourly Share Self-Consumption (Orden TED/1247/2021)
        hourly_sc = cls.evaluate_hourly_self_consumption(
            aligned_dataset=aligned_dataset,
            strategy=strategy,
            precision=active_precision,
            primary_cups=effective_primary,
            constraints=constraints,
            require_full_month=require_full_month,
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
                    base_fortnight = cls._evaluate_calendar_fortnights(
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
                        fortnight_results=base_fortnight,
                        cups_uses=cups_uses,
                        primary_cups=effective_primary,
                        current_self_consumed_kwh=current_sc,
                        monthly_share_self_consumed_kwh=float(base_summary.total_self_consumed_kwh),
                        fortnight_share_self_consumed_kwh=float(
                            sum(f.total_self_consumed_kwh for f in base_fortnight if f.has_data)
                        ),
                        hourly_share_self_consumed_kwh=cls.evaluate_hourly_self_consumption(
                            aligned_dataset=aligned_dataset,
                            strategy=base_strat,
                            precision=active_precision,
                            primary_cups=effective_primary,
                            constraints=constraints,
                            require_full_month=require_full_month,
                        ),
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
            fortnight_results=fortnight_results,
            cups_uses=cups_uses,
            constraints=constraints,
            primary_cups=effective_primary,
            current_self_consumed_kwh=current_sc,
            monthly_share_self_consumed_kwh=monthly_sc,
            fortnight_share_self_consumed_kwh=fortnight_sc,
            hourly_share_self_consumed_kwh=hourly_sc,
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
                        solar_hours_consumption_kwh=0.0,
                        solar_hours_coverage_rate=0.0,
                        solar_hours_generation_kwh=0.0,
                        use=cups_uses.get(c, "") if cups_uses else "",
                    )
                    for c in cups_list
                ],
                has_data=False,
                solar_hours_consumption_kwh=0.0,
                solar_hours_coverage_rate=0.0,
                solar_hours_generation_kwh=0.0,
                solar_hours_count=0,
            )

        tot_cons = sum(m.total_consumption_kwh for m in active_months)
        tot_gen = sum(m.total_generation_kwh for m in active_months)
        tot_sc = sum(m.total_self_consumed_kwh for m in active_months)
        tot_surplus = sum(m.total_surplus_kwh for m in active_months)
        tot_grid = sum(m.total_grid_demand_kwh for m in active_months)
        tot_solar_cons = sum(m.solar_hours_consumption_kwh for m in active_months)
        tot_solar_gen = sum(m.solar_hours_generation_kwh for m in active_months)
        tot_solar_hours = sum(m.solar_hours_count for m in active_months)

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
                "solar_gen": 0.0,
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
                entry["solar_gen"] += cm.solar_hours_generation_kwh

        cups_summary_metrics: list[CupsMonthlyMetrics] = []
        for cups in cups_list:
            c_data = cups_aggregates[cups]
            c_cons = c_data["cons"]
            c_alloc = c_data["alloc"]
            c_sc = c_data["sc"]
            c_surplus = c_data["surplus"]
            c_grid = c_data["grid"]
            c_solar_cons = c_data["solar_cons"]
            c_solar_gen = c_data["solar_gen"]
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
                    solar_hours_generation_kwh=c_solar_gen,
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
            solar_hours_generation_kwh=tot_solar_gen,
            solar_hours_count=tot_solar_hours,
        )
