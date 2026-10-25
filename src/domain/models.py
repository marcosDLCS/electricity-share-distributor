"""Pure domain models and value objects for Electricity Share Distributor (esd)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.exceptions import EsdError

CUPS_PATTERN = re.compile(r"^[A-Z]{2}[0-9A-Z]{18,22}$")


@dataclass(frozen=True, slots=True)
class SupplyPoint:
    """Domain entity representing a participating Universal Supply Point Code (CUPS)."""

    cups: str
    use: str = ""
    primary: bool = False
    latitude: float | None = None
    longitude: float | None = None

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
