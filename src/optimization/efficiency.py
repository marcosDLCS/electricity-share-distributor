"""Model and calculation formula for photovoltaic solar efficiency index."""

from __future__ import annotations

import math


def calculate_solar_efficiency(
    month: int,
    hour: int,
    temperature: float | None = None,
    cloud_cover: float | int | None = None,
) -> float:
    """Calculate hourly solar efficiency index (scale 1.0 to 100.0) based on weather and solar geometry.

    Formula:
        SEI = clip(100.0 * f_cloud * f_temp * f_season * f_hour, 1.0, 100.0)

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
        month: Calendar month (1-12).
        hour: Hour of the day (0-23).
        temperature: Ambient 2m temperature in degrees Celsius (°C), or None.
        cloud_cover: Cloud cover percentage (0-100), or None.

    Returns:
        Solar efficiency index rounded to 1 decimal place (1.0 to 100.0).
    """
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
    return round(max(1.0, min(100.0, raw_score)), 1)
