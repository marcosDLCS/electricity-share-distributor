"""Pure domain models and value objects for Electricity Share Distributor (esd)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.exceptions import EsdError, OptimizationError

CUPS_PATTERN = re.compile(r"^[A-Z]{2}[0-9A-Z]{18,22}$")


@dataclass(frozen=True, slots=True)
class SupplyPoint:
    """Domain entity representing a participating Universal Supply Point Code (CUPS)."""

    cups: str
    use: str = ""
    primary: bool = False
    latitude: float | None = None
    longitude: float | None = None
    min_share: float | None = None
    max_share: float | None = None

    def __post_init__(self) -> None:
        clean_cups = self.cups.strip().upper()
        if not clean_cups:
            raise EsdError("SupplyPoint CUPS identifier cannot be empty.")
        if not CUPS_PATTERN.match(clean_cups):
            raise EsdError(
                f"Invalid CUPS format: '{self.cups}'. Expected 20-22 character alphanumeric string starting with country code."
            )
        # frozen dataclass mutation via object.__setattr__
        object.__setattr__(self, "cups", clean_cups)

        if self.min_share is not None and not (0.0 <= self.min_share <= 1.0):
            raise EsdError(f"min_share must be between 0.0 and 1.0 (got {self.min_share}).")
        if self.max_share is not None and not (0.0 <= self.max_share <= 1.0):
            raise EsdError(f"max_share must be between 0.0 and 1.0 (got {self.max_share}).")
        if (
            self.min_share is not None
            and self.max_share is not None
            and self.min_share > self.max_share
        ):
            raise EsdError(
                f"min_share ({self.min_share * 100:.1f}%) cannot exceed max_share ({self.max_share * 100:.1f}%)."
            )
        if self.latitude is not None and not (-90.0 <= self.latitude <= 90.0):
            raise EsdError(f"Latitude must be between -90.0 and 90.0 (got {self.latitude}).")
        if self.longitude is not None and not (-180.0 <= self.longitude <= 180.0):
            raise EsdError(f"Longitude must be between -180.0 and 180.0 (got {self.longitude}).")

    @property
    def masked_cups(self) -> str:
        """Return masked CUPS for privacy-safe display (e.g. …000001AA)."""
        if len(self.cups) > 10:
            return f"…{self.cups[-8:]}"
        return self.cups

    def display_label(self, compact: bool = False) -> str:
        """Formatted label combining use and masked CUPS."""
        if compact:
            return self.masked_cups
        if self.use:
            return f"{self.use[:11]} ({self.masked_cups})"
        return self.cups


@dataclass(frozen=True, slots=True)
class ShareAllocation:
    """Value object representing an individual CUPS photovoltaic share coefficient (beta_i)."""

    cups: str
    share: float  # In range [0.0, 1.0]
    use: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.share <= 1.0001):
            raise EsdError(
                f"Share coefficient beta must be between 0.0 and 1.0 (got {self.share} for CUPS {self.cups})."
            )

    @property
    def percentage(self) -> float:
        """Share as percentage (0.0 to 100.0)."""
        return self.share * 100.0

    def format_share(self, precision: int = 1) -> str:
        """Format share as localized percentage string."""
        pct = self.percentage
        if precision == 0:
            return f"{round(pct)}%"
        return f"{pct:.{precision}f}%"


@dataclass(frozen=True, slots=True)
class EnergyBalance:
    """Value object representing the energy balance of a supply point under collective self-consumption."""

    consumption_kwh: float
    generation_allocated_kwh: float
    self_consumed_kwh: float
    surplus_kwh: float
    grid_demand_kwh: float
    cups: str | None = None
    use: str = ""

    @property
    def self_consumption_rate(self) -> float:
        """Fraction of allocated solar generation consumed on-site (0.0% to 100.0%)."""
        if self.generation_allocated_kwh <= 0.0:
            return 0.0
        return min(
            100.0, max(0.0, (self.self_consumed_kwh / self.generation_allocated_kwh) * 100.0)
        )

    @property
    def solar_coverage_rate(self) -> float:
        """Fraction of facility consumption satisfied by allocated solar power (0.0% to 100.0%)."""
        if self.consumption_kwh <= 0.0:
            return 100.0 if self.generation_allocated_kwh > 0.0 else 0.0
        return min(100.0, max(0.0, (self.self_consumed_kwh / self.consumption_kwh) * 100.0))


@dataclass(frozen=True, slots=True)
class BylawConstraints:
    """Regulatory and community bylaw constraints on distribution coefficients (beta_i)."""

    min_share: float | None = None  # Global minimum share coefficient (0.0 to 1.0)
    max_share: float | None = None  # Global maximum share coefficient (0.0 to 1.0)
    cups_min_shares: dict[str, float] = field(default_factory=dict)
    cups_max_shares: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.min_share is not None and not (0.0 <= self.min_share <= 1.0):
            raise EsdError(f"min_share must be between 0.0 and 1.0 (got {self.min_share}).")
        if self.max_share is not None and not (0.0 <= self.max_share <= 1.0):
            raise EsdError(f"max_share must be between 0.0 and 1.0 (got {self.max_share}).")
        if (
            self.min_share is not None
            and self.max_share is not None
            and self.min_share > self.max_share
        ):
            raise EsdError(
                f"Global min_share ({self.min_share * 100:.1f}%) cannot exceed max_share ({self.max_share * 100:.1f}%)."
            )

    @property
    def is_active(self) -> bool:
        """Check whether any minimum or maximum constraint is active."""
        return (
            self.min_share is not None
            or self.max_share is not None
            or bool(self.cups_min_shares)
            or bool(self.cups_max_shares)
        )

    def get_bounds(self, cups: str) -> tuple[float, float]:
        """Get (lower_bound, upper_bound) for an individual CUPS."""
        lower = self.cups_min_shares.get(
            cups, self.min_share if self.min_share is not None else 0.0
        )
        upper = self.cups_max_shares.get(
            cups, self.max_share if self.max_share is not None else 1.0
        )
        return (lower, upper)

    def validate_feasibility(self, cups_list: list[str]) -> None:
        """Validate feasibility of the constraints across participating CUPS."""
        if not cups_list or not self.is_active:
            return
        sum_lower = 0.0
        sum_upper = 0.0
        for cups in cups_list:
            lower_b, upper_b = self.get_bounds(cups)
            if lower_b > upper_b:
                raise OptimizationError(
                    f"Infeasible bounds for CUPS '{cups}': min_share ({lower_b * 100:.1f}%) exceeds max_share ({upper_b * 100:.1f}%)."
                )
            sum_lower += lower_b
            sum_upper += upper_b

        if sum_lower > 1.0001:
            raise OptimizationError(
                f"Minimum share constraints are mathematically infeasible: sum of minimum shares ({sum_lower * 100:.1f}%) exceeds 100.0% across {len(cups_list)} participating CUPS."
            )
        if sum_upper < 0.9999:
            raise OptimizationError(
                f"Maximum share caps are overly restrictive: sum of maximum shares ({sum_upper * 100:.1f}%) is less than 100.0% required by RD 244/2019."
            )
