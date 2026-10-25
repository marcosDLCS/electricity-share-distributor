"""Unit tests for pure domain models, value objects, and domain exceptions."""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    AlignmentError,
    CurationError,
    EsdError,
    IngestionError,
    OptimizationError,
)
from src.domain.models import EnergyBalance, ShareAllocation, SupplyPoint


def test_domain_exceptions_hierarchy() -> None:
    """Verify all domain exceptions inherit cleanly from EsdError."""
    assert issubclass(IngestionError, EsdError)
    assert issubclass(AlignmentError, EsdError)
    assert issubclass(CurationError, EsdError)
    assert issubclass(OptimizationError, EsdError)


def test_supply_point_valid() -> None:
    """Verify valid SupplyPoint construction and properties."""
    sp = SupplyPoint(
        cups="ES0021000000000001AA",
        use="Aerotermia",
        primary=True,
        latitude=40.4168,
        longitude=-3.7038,
    )
    assert sp.cups == "ES0021000000000001AA"
    assert sp.use == "Aerotermia"
    assert sp.primary is True
    assert sp.masked_cups == "…000001AA"
    assert sp.display_label(compact=True) == "…000001AA"
    assert "Aerotermia" in sp.display_label(compact=False)


def test_supply_point_invalid_cups() -> None:
    """Verify that invalid CUPS formats trigger EsdError."""
    with pytest.raises(EsdError, match="Invalid CUPS format"):
        SupplyPoint(cups="INVALID_CUPS_123")

    with pytest.raises(EsdError, match="cannot be empty"):
        SupplyPoint(cups="")


def test_share_allocation_valid() -> None:
    """Verify ShareAllocation percentage calculations and formatting."""
    sa = ShareAllocation(cups="ES0021000000000001AA", share=0.5286, use="Aerotermia")
    assert pytest.approx(sa.percentage, rel=1e-4) == 52.86
    assert sa.format_share(precision=0) == "53%"
    assert sa.format_share(precision=1) == "52.9%"
    assert sa.format_share(precision=2) == "52.86%"


def test_share_allocation_out_of_bounds() -> None:
    """Verify that beta values outside [0.0, 1.0] raise an EsdError."""
    with pytest.raises(EsdError, match="Share coefficient beta must be between"):
        ShareAllocation(cups="ES0021000000000001AA", share=1.2)

    with pytest.raises(EsdError, match="Share coefficient beta must be between"):
        ShareAllocation(cups="ES0021000000000001AA", share=-0.05)


def test_energy_balance_rates() -> None:
    """Verify EnergyBalance self-consumption and solar coverage calculations."""
    eb = EnergyBalance(
        consumption_kwh=100.0,
        generation_allocated_kwh=80.0,
        self_consumed_kwh=60.0,
        surplus_kwh=20.0,
        grid_demand_kwh=40.0,
    )
    # self_consumption_rate: 60 / 80 = 75.0%
    assert pytest.approx(eb.self_consumption_rate, rel=1e-4) == 75.0
    # solar_coverage_rate: 60 / 100 = 60.0%
    assert pytest.approx(eb.solar_coverage_rate, rel=1e-4) == 60.0


def test_energy_balance_zero_division() -> None:
    """Verify zero generation and zero consumption edge cases."""
    eb_zero_gen = EnergyBalance(
        consumption_kwh=100.0,
        generation_allocated_kwh=0.0,
        self_consumed_kwh=0.0,
        surplus_kwh=0.0,
        grid_demand_kwh=100.0,
    )
    assert eb_zero_gen.self_consumption_rate == 0.0
    assert eb_zero_gen.solar_coverage_rate == 0.0

    eb_zero_cons = EnergyBalance(
        consumption_kwh=0.0,
        generation_allocated_kwh=50.0,
        self_consumed_kwh=0.0,
        surplus_kwh=50.0,
        grid_demand_kwh=0.0,
    )
    assert eb_zero_cons.self_consumption_rate == 0.0
    assert eb_zero_cons.solar_coverage_rate == 100.0
