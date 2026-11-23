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
from src.domain.models import (
    SupplyPoint,
    parse_share_fraction,
)


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


def test_supply_point_share_bounds_validation() -> None:
    """Verify min_share and max_share range and consistency validation."""
    # Valid bounds
    sp = SupplyPoint(
        cups="ES0021000000000001AA",
        min_share=0.05,
        max_share=0.75,
    )
    assert sp.min_share == 0.05
    assert sp.max_share == 0.75

    # Out of [0, 1] range
    with pytest.raises(EsdError, match=r"min_share must be between 0\.0 and 1\.0"):
        SupplyPoint(cups="ES0021000000000001AA", min_share=-0.1)

    with pytest.raises(EsdError, match=r"max_share must be between 0\.0 and 1\.0"):
        SupplyPoint(cups="ES0021000000000001AA", max_share=1.2)

    # Inconsistent bounds (min > max)
    with pytest.raises(EsdError, match="cannot exceed max_share"):
        SupplyPoint(cups="ES0021000000000001AA", min_share=0.8, max_share=0.2)


def test_supply_point_coordinate_validation() -> None:
    """Verify latitude and longitude validation in SupplyPoint."""
    with pytest.raises(EsdError, match=r"Latitude must be between -90\.0 and 90\.0"):
        SupplyPoint(cups="ES0021000000000001AA", latitude=95.0)

    with pytest.raises(EsdError, match=r"Longitude must be between -180\.0 and 180\.0"):
        SupplyPoint(cups="ES0021000000000001AA", longitude=-200.0)


def test_parse_share_fraction() -> None:
    """Verify parse_share_fraction normalizes fractions, percentages, strings, and rejects invalid inputs."""
    # None
    assert parse_share_fraction(None) is None

    # Valid fractions <= 1.0
    assert parse_share_fraction(0.25) == 0.25
    assert parse_share_fraction(0.0) == 0.0
    assert parse_share_fraction(1.0) == 1.0
    assert parse_share_fraction(0) == 0.0
    assert parse_share_fraction(1) == 1.0

    # Percentages > 1.0 normalized to fractions
    assert parse_share_fraction(25.0) == 0.25
    assert parse_share_fraction(25) == 0.25
    assert parse_share_fraction(100.0) == 1.0
    assert parse_share_fraction(100) == 1.0

    # String percentage formats
    assert parse_share_fraction("25%") == 0.25
    assert parse_share_fraction("25.0%") == 0.25
    assert parse_share_fraction("100%") == 1.0
    assert parse_share_fraction("1%") == 0.01
    assert parse_share_fraction("0.5%") == 0.005
    assert parse_share_fraction("0.25") == 0.25
    assert parse_share_fraction("25") == 0.25

    # Out-of-range inputs
    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        parse_share_fraction(-0.1)

    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        parse_share_fraction(150.0)

    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        parse_share_fraction("-5%")

    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        parse_share_fraction("150%")

    with pytest.raises(ValueError, match="cannot convert to float"):
        parse_share_fraction("invalid")

    with pytest.raises(ValueError, match="cannot be empty"):
        parse_share_fraction("   ")

    # Invalid types
    with pytest.raises(TypeError, match="cannot be a boolean"):
        parse_share_fraction(True)

    with pytest.raises(TypeError, match="Invalid share value type"):
        parse_share_fraction([0.25])  # type: ignore[arg-type]
