"""Presentation views package modularizing Rich terminal UI components."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, str] = {
    "MONTH_ABBR_EN": "src.presentation.views.common",
    "MONTH_ABBR_ES": "src.presentation.views.common",
    "format_month_abbr": "src.presentation.views.common",
    "render_cleanup_result": "src.presentation.views.common",
    "render_config_view": "src.presentation.views.common",
    "render_export_success": "src.presentation.views.common",
    "render_help": "src.presentation.views.common",
    "render_init_success": "src.presentation.views.common",
    "render_not_initialized_warning": "src.presentation.views.common",
    "render_version": "src.presentation.views.common",
    "render_weather_result": "src.presentation.views.common",
    "render_comparison_overview": "src.presentation.views.comparison",
    "render_cups_comparison_table": "src.presentation.views.comparison",
    "render_monthly_comparison_table": "src.presentation.views.comparison",
    "render_annual_consumption_tables": "src.presentation.views.consumption",
    "render_consumption_insights": "src.presentation.views.consumption",
    "render_consumption_overview": "src.presentation.views.consumption",
    "render_cups_consumption_trajectory": "src.presentation.views.consumption",
    "render_detailed_monthly_consumption": "src.presentation.views.consumption",
    "render_monthly_consumption_overview": "src.presentation.views.consumption",
    "render_validation_warnings": "src.presentation.views.consumption",
    "render_curate_summary": "src.presentation.views.curate",
    "render_doctor_report": "src.presentation.views.doctor",
    "render_coefficients_matrix_table": "src.presentation.views.matrix",
    "render_community_summary": "src.presentation.views.summary",
    "render_monthly_trajectory_table": "src.presentation.views.trajectory",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve exported presentation view symbols lazily without loading pandas/scipy upfront."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value
