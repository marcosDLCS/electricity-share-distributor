"""Domain exceptions for Electricity Share Distributor (esd)."""

from __future__ import annotations


class EsdError(Exception):
    """Base exception for all domain errors within Electricity Share Distributor."""


class IngestionError(EsdError):
    """Raised when discovering, reading, or parsing raw time-series data fails."""


class ValidationError(IngestionError):
    """Raised when schema validation, columns, coordinates, or data types are invalid."""


class AlignmentError(EsdError):
    """Raised when aligning consumption and generation time-series fails."""


class CurationError(EsdError):
    """Raised when reconciling fake-zero loads or curating canonical dataset fails."""


class OptimizationError(EsdError):
    """Raised when coefficient optimization or LP solving fails."""
