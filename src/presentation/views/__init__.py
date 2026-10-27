"""Presentation views package modularizing Rich terminal UI components."""

from src.presentation.views.common import (
    MONTH_ABBR_EN,
    MONTH_ABBR_ES,
    format_month_abbr,
    render_cleanup_result,
    render_config_view,
    render_export_success,
    render_help,
    render_init_success,
    render_not_initialized_warning,
    render_version,
    render_weather_result,
)
from src.presentation.views.curate import render_curate_summary
from src.presentation.views.doctor import render_doctor_report
from src.presentation.views.matrix import (
    render_coefficients_matrix_table,
    render_hourly_profile_table,
    render_monthly_coefficients_table,
)
from src.presentation.views.summary import render_community_summary
from src.presentation.views.trajectory import (
    render_monthly_trajectory_table,
    render_strategy_comparison_table,
)

__all__ = [
    "MONTH_ABBR_EN",
    "MONTH_ABBR_ES",
    "format_month_abbr",
    "render_cleanup_result",
    "render_coefficients_matrix_table",
    "render_community_summary",
    "render_config_view",
    "render_curate_summary",
    "render_doctor_report",
    "render_export_success",
    "render_help",
    "render_hourly_profile_table",
    "render_init_success",
    "render_monthly_coefficients_table",
    "render_monthly_trajectory_table",
    "render_not_initialized_warning",
    "render_strategy_comparison_table",
    "render_version",
    "render_weather_result",
]
