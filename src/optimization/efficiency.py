"""Model and calculation formula for photovoltaic solar efficiency index."""

from __future__ import annotations

import math
from typing import overload

import numpy as np


@overload
def calculate_solar_efficiency(
    month: int,
    hour: int,
    temperature: float | None = None,
    cloud_cover: float | int | None = None,
) -> int: ...


@overload
def calculate_solar_efficiency(
    month: np.ndarray,
    hour: np.ndarray,
    temperature: np.ndarray | float | None = None,
    cloud_cover: np.ndarray | float | int | None = None,
) -> np.ndarray: ...


def calculate_solar_efficiency(
    month: int | np.ndarray,
    hour: int | np.ndarray,
    temperature: float | np.ndarray | None = None,
    cloud_cover: float | int | np.ndarray | None = None,
) -> int | np.ndarray:
    """Calculate hourly solar efficiency index (scale 1 to 100) based on weather and solar geometry.

    Supports both scalar inputs (returning Python int) and 1D NumPy arrays (returning int ndarray).

    Formula:
        SEI = clip(round(100.0 * f_cloud * f_temp * f_season * f_hour), 1, 100)

    Components:
        1. Cloud Optical Attenuation (f_cloud):
           f_cloud = 1.0 - 0.75 * (CC / 100.0) ** 1.2
           where CC in [0, 100] is cloud cover percentage.
           Non-linear optical transmission capturing direct beam attenuation while
           retaining ~25% diffuse solar irradiance even under 100% cloud cover.

        2. Photovoltaic Temperature Derating (f_temp):
           f_temp = 1.0 - 0.004 * (T_amb - 20.0)
           clamped between [0.80, 1.08].
           Standard silicon PV power temperature coefficient of -0.4%/°C relative to
           20°C ambient reference. Cooler ambient temperatures increase open-circuit voltage
           and boost conversion efficiency, while summer heat degrades panel efficiency.

        3. Seasonal Solar Elevation & Air Mass (f_season):
           f_season = 0.85 + 0.15 * cos(2 * pi * (month - 6.5) / 12.0)
           Models annual solar declination and air mass path length across Iberian latitudes
           (36°N-43°N). Peaks near the summer solstice (June/July ~ 1.00) and reaches its minimum
           during winter solstice (December/January ~ 0.70).

        4. Diurnal Solar Zenith Angle (f_hour):
           f_hour = 0.70 + 0.30 * sin(pi * (hour - 6.0) / 15.0)  for hour in [6, 21]
           Models the diurnal solar trajectory and optical incidence angle on fixed-tilt rooftop
           arrays, peaking around solar noon (13:00-14:00 in Spain, UTC+1/UTC+2) with minimal
           Fresnel reflection losses, and tapering during morning and evening grazing angles.

    Args:
        month: Calendar month (1-12) or array of months.
        hour: Hour of the day (0-23) or array of hours.
        temperature: Ambient 2m temperature in degrees Celsius (°C), array, or None.
        cloud_cover: Cloud cover percentage (0-100), array, or None.

    Returns:
        Solar efficiency index as integer (1 to 100) or integer ndarray for array inputs.
    """
    if isinstance(month, np.ndarray) or isinstance(hour, np.ndarray):
        m_arr = np.clip(np.asarray(month, dtype=float), 1.0, 12.0)
        h_arr = np.clip(np.asarray(hour, dtype=float), 0.0, 23.0)

        if cloud_cover is None:
            cc_vec = np.zeros_like(m_arr, dtype=float)
        else:
            cc_raw = np.asarray(cloud_cover, dtype=float)
            cc_vec = np.where(np.isnan(cc_raw), 0.0, np.clip(cc_raw, 0.0, 100.0))
        f_cloud_vec = 1.0 - 0.75 * np.power(cc_vec / 100.0, 1.2)

        if temperature is None:
            temp_vec = np.full_like(m_arr, 20.0, dtype=float)
        else:
            t_raw = np.asarray(temperature, dtype=float)
            temp_vec = np.where(np.isnan(t_raw), 20.0, t_raw)
        f_temp_vec = np.clip(1.0 - 0.004 * (temp_vec - 20.0), 0.80, 1.08)

        f_season_vec = 0.85 + 0.15 * np.cos(2.0 * np.pi * (m_arr - 6.5) / 12.0)
        f_hour_vec = np.where(
            (h_arr >= 6.0) & (h_arr <= 21.0),
            0.70 + 0.30 * np.sin(np.pi * (h_arr - 6.0) / 15.0),
            0.65,
        )

        raw_scores = 100.0 * f_cloud_vec * f_temp_vec * f_season_vec * f_hour_vec
        return np.rint(np.clip(raw_scores, 1.0, 100.0)).astype(int)

    # 1. Cloud attenuation factor
    cc = (
        float(cloud_cover)
        if cloud_cover is not None and not math.isnan(float(cloud_cover))
        else 0.0
    )
    cc = max(0.0, min(100.0, cc))
    f_cloud = 1.0 - 0.75 * (cc / 100.0) ** 1.2

    # 2. Temperature derating factor (-0.4%/°C relative to 20°C ambient)
    temp = (
        float(temperature)
        if temperature is not None and not math.isnan(float(temperature))
        else 20.0
    )
    f_temp = 1.0 - 0.004 * (temp - 20.0)
    f_temp = max(0.80, min(1.08, f_temp))

    # 3. Seasonal solar elevation factor
    m = max(1, min(12, int(month)))
    f_season = 0.85 + 0.15 * math.cos(2.0 * math.pi * (m - 6.5) / 12.0)

    # 4. Diurnal solar angle factor
    h = max(0, min(23, int(hour)))
    if 6 <= h <= 21:
        f_hour = 0.70 + 0.30 * math.sin(math.pi * (h - 6.0) / 15.0)
    else:
        f_hour = 0.65

    raw_score = 100.0 * f_cloud * f_temp * f_season * f_hour
    return round(max(1.0, min(100.0, raw_score)))
