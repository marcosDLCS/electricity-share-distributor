"""Presentation package for Electricity Share Distributor."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, str] = {
    "FORMULA_INJECTION_PREFIXES": "src.presentation.export",
    "ReportExporter": "src.presentation.export",
    "sanitize_formula_injection": "src.presentation.export",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve presentation package exports lazily."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value
