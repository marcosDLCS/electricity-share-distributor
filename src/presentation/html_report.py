"""Interactive standalone HTML report generator for collective PV self-consumption (RD 244/2019)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.optimization.efficiency import calculate_solar_efficiency
from src.presentation.console import format_kwh
from src.presentation.views.common import MONTH_ABBR_EN, MONTH_ABBR_ES
from src.version import get_version

if TYPE_CHECKING:
    from src.ingestion.schema import IngestionSummary
    from src.optimization.models import OptimizationResult


def _parse_month_int(m_str: str) -> int:
    """Safely parse month integer from 'MM', 'YYYY-MM', or integer-like strings."""
    try:
        val = int(m_str.split("-")[-1]) if "-" in m_str else int(m_str)
        return max(1, min(12, val))
    except ValueError, TypeError:
        return 6


def _generate_svg_monthly_chart(
    opt_result: OptimizationResult,
    is_es: bool,
) -> str:
    """Generate inline responsive SVG multi-bar chart comparing generation, demand, and self-consumption."""
    active_months = [m for m in opt_result.monthly_results if m.has_data]
    if not active_months:
        return "<p class='no-data'>No monthly time-series data available for charting.</p>"

    abbr_map = MONTH_ABBR_ES if is_es else MONTH_ABBR_EN

    # Chart dimensions
    width = 960
    height = 360
    pad_left = 70
    pad_right = 30
    pad_top = 40
    pad_bottom = 50

    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    max_val = max(
        max(m.total_generation_kwh for m in active_months),
        max(m.total_consumption_kwh for m in active_months),
        1.0,
    )
    # Round max_val up to nice interval
    y_max = max_val * 1.15

    n_months = len(active_months)
    slot_w = chart_w / n_months
    bar_w = min(18.0, slot_w * 0.22)
    spacing = 3.0

    svg_elements: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg chart-monthly-svg" xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        '  <linearGradient id="gradGen" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#f59e0b" stop-opacity="0.9"/>',
        '    <stop offset="100%" stop-color="#d97706" stop-opacity="0.4"/>',
        "  </linearGradient>",
        '  <linearGradient id="gradDem" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#06b6d4" stop-opacity="0.9"/>',
        '    <stop offset="100%" stop-color="#0284c7" stop-opacity="0.4"/>',
        "  </linearGradient>",
        '  <linearGradient id="gradSc" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#10b981" stop-opacity="0.95"/>',
        '    <stop offset="100%" stop-color="#059669" stop-opacity="0.5"/>',
        "  </linearGradient>",
        '  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">',
        '    <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.25"/>',
        "  </filter>",
        "</defs>",
    ]

    # Y-axis gridlines and labels (4 tiers)
    y_tiers = 4
    for tier in range(y_tiers + 1):
        tier_val = (y_max / y_tiers) * tier
        y_pos = pad_top + chart_h - (chart_h * (tier / y_tiers))
        svg_elements.append(
            f'<line x1="{pad_left}" y1="{y_pos:.1f}" x2="{width - pad_right}" y2="{y_pos:.1f}" class="grid-line"/>'
        )
        lbl_kwh = f"{tier_val:,.0f} kWh" if tier_val < 10000 else f"{tier_val / 1000:,.1f} MWh"
        svg_elements.append(
            f'<text x="{pad_left - 10}" y="{y_pos + 4:.1f}" text-anchor="end" class="axis-label">{lbl_kwh}</text>'
        )

    # Bars per month
    for idx, m in enumerate(active_months):
        cx = pad_left + idx * slot_w + (slot_w / 2.0)
        m_int = _parse_month_int(m.month)
        m_2d = f"{m_int:02d}"
        m_name = abbr_map.get(m.month, abbr_map.get(m_2d, m.month))

        h_gen = (m.total_generation_kwh / y_max) * chart_h
        h_dem = (m.total_consumption_kwh / y_max) * chart_h
        h_sc = (m.total_self_consumed_kwh / y_max) * chart_h

        y_gen = pad_top + chart_h - h_gen
        y_dem = pad_top + chart_h - h_dem
        y_sc = pad_top + chart_h - h_sc

        x_gen = cx - (bar_w * 1.5) - spacing
        x_dem = cx - (bar_w * 0.5)
        x_sc = cx + (bar_w * 0.5) + spacing

        tip_data = json.dumps(
            {
                "month": m_name,
                "month_num": m_2d,
                "gen": f"{m.total_generation_kwh:,.1f} kWh",
                "dem": f"{m.total_consumption_kwh:,.1f} kWh",
                "sc": f"{m.total_self_consumed_kwh:,.1f} kWh",
                "surplus": f"{m.total_surplus_kwh:,.1f} kWh",
                "cov": f"{m.solar_coverage_rate:.1f}%",
                "eff": f"{m.self_consumption_rate:.1f}%",
            }
        ).replace('"', "&quot;")

        svg_elements.append(
            f'<g class="chart-col" data-tooltip="{tip_data}" onmouseenter="showTooltip(event, this)" onmouseleave="hideTooltip()">'
        )
        # Background hit area for easy hover
        svg_elements.append(
            f'  <rect x="{cx - slot_w / 2:.1f}" y="{pad_top}" width="{slot_w:.1f}" height="{chart_h}" class="hover-bg"/>'
        )
        # Gen bar
        svg_elements.append(
            f'  <rect x="{x_gen:.1f}" y="{y_gen:.1f}" width="{bar_w:.1f}" height="{h_gen:.1f}" rx="3" class="bar-gen" fill="url(#gradGen)"/>'
        )
        # Demand bar
        svg_elements.append(
            f'  <rect x="{x_dem:.1f}" y="{y_dem:.1f}" width="{bar_w:.1f}" height="{h_dem:.1f}" rx="3" class="bar-dem" fill="url(#gradDem)"/>'
        )
        # Self-consumption bar
        svg_elements.append(
            f'  <rect x="{x_sc:.1f}" y="{y_sc:.1f}" width="{bar_w:.1f}" height="{h_sc:.1f}" rx="3" class="bar-sc" fill="url(#gradSc)"/>'
        )
        # X-axis label
        svg_elements.append(
            f'  <text x="{cx:.1f}" y="{height - pad_bottom + 22}" text-anchor="middle" class="x-label x-label-bar" data-month="{m_2d}">{m_name}</text>'
        )
        svg_elements.append("</g>")

    svg_elements.append("</svg>")
    return "\n".join(svg_elements)


def _calculate_monthly_efficiency(
    opt_result: OptimizationResult,
) -> list[dict[str, Any]]:
    """Calculate average and peak solar efficiency index per calendar month."""
    active_months = [m for m in opt_result.monthly_results if m.has_data]
    if not active_months:
        active_m_strs = [f"{i:02d}" for i in range(1, 13)]
    else:
        active_m_strs = [m.month for m in active_months]

    has_hourly = (
        opt_result.hourly_result is not None
        and opt_result.hourly_result.time_series_df is not None
        and not opt_result.hourly_result.time_series_df.empty
        and "solar_efficiency" in opt_result.hourly_result.time_series_df.columns
    )

    points: list[dict[str, Any]] = []

    if has_hourly and opt_result.hourly_result is not None:
        df = opt_result.hourly_result.time_series_df
        sun_df = df[df["generation_kwh"] > 1e-6] if "generation_kwh" in df.columns else df
        for m_str in active_m_strs:
            m_int = _parse_month_int(m_str)
            m_2d = f"{m_int:02d}"
            mask = (sun_df["timestamp"].str[5:7] == m_2d) | (sun_df["timestamp"].str[:7] == m_str)
            m_rows = sun_df[mask]
            if not m_rows.empty and "solar_efficiency" in m_rows.columns:
                avg_eff = float(m_rows["solar_efficiency"].mean())
                peak_eff = float(m_rows["solar_efficiency"].max())
            else:
                avg_eff = float(
                    sum(calculate_solar_efficiency(m_int, h) for h in range(8, 19)) / 11.0
                )
                peak_eff = float(calculate_solar_efficiency(m_int, 13))
            points.append(
                {
                    "month": m_str,
                    "avg_eff": round(avg_eff, 1),
                    "peak_eff": round(peak_eff, 1),
                }
            )
    else:
        for m_str in active_m_strs:
            m_int = _parse_month_int(m_str)
            avg_eff = float(sum(calculate_solar_efficiency(m_int, h) for h in range(8, 19)) / 11.0)
            peak_eff = float(calculate_solar_efficiency(m_int, 13))
            points.append(
                {
                    "month": m_str,
                    "avg_eff": round(avg_eff, 1),
                    "peak_eff": round(peak_eff, 1),
                }
            )
    return points


def _generate_svg_efficiency_chart(
    opt_result: OptimizationResult,
    is_es: bool,
) -> str:
    """Generate responsive inline SVG chart illustrating Photovoltaic Solar Efficiency Index (1-100)."""
    points = _calculate_monthly_efficiency(opt_result)
    if not points:
        return "<p class='no-data'>No solar efficiency data available for charting.</p>"

    abbr_map = MONTH_ABBR_ES if is_es else MONTH_ABBR_EN

    width = 960
    height = 290
    pad_left = 65
    pad_right = 35
    pad_top = 40
    pad_bottom = 50

    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    n_pts = len(points)
    slot_w = chart_w / n_pts

    coords: list[tuple[float, float, float, dict[str, Any]]] = []
    for idx, p in enumerate(points):
        cx = pad_left + idx * slot_w + (slot_w / 2.0)
        y_avg = pad_top + chart_h - (p["avg_eff"] / 100.0) * chart_h
        y_peak = pad_top + chart_h - (p["peak_eff"] / 100.0) * chart_h
        coords.append((cx, y_avg, y_peak, p))

    svg_elements: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg chart-eff-svg" xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        '  <linearGradient id="gradEffArea" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#10b981" stop-opacity="0.32"/>',
        '    <stop offset="70%" stop-color="#10b981" stop-opacity="0.08"/>',
        '    <stop offset="100%" stop-color="#10b981" stop-opacity="0.0"/>',
        "  </linearGradient>",
        '  <filter id="effGlow" x="-20%" y="-20%" width="140%" height="140%">',
        '    <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#10b981" flood-opacity="0.3"/>',
        "  </filter>",
        "</defs>",
    ]

    # Y-axis gridlines & labels: 0%, 25%, 50%, 75%, 100%
    y_tiers = [0, 25, 50, 75, 100]
    for tier in y_tiers:
        y_pos = pad_top + chart_h - (tier / 100.0) * chart_h
        svg_elements.append(
            f'<line x1="{pad_left}" y1="{y_pos:.1f}" x2="{width - pad_right}" y2="{y_pos:.1f}" class="grid-line"/>'
        )
        svg_elements.append(
            f'<text x="{pad_left - 10}" y="{y_pos + 4:.1f}" text-anchor="end" class="axis-label">{tier}%</text>'
        )

    # Shaded Area under Average Curve
    area_d_parts = [f"M {coords[0][0]:.1f},{pad_top + chart_h:.1f}"]
    for cx, y_avg, _, _ in coords:
        area_d_parts.append(f"L {cx:.1f},{y_avg:.1f}")
    area_d_parts.append(f"L {coords[-1][0]:.1f},{pad_top + chart_h:.1f} Z")
    area_d = " ".join(area_d_parts)
    svg_elements.append(f'<path d="{area_d}" fill="url(#gradEffArea)"/>')

    # Peak solar noon line (dashed amber)
    peak_line_d = " ".join(
        [f"M {coords[0][0]:.1f},{coords[0][2]:.1f}"]
        + [f"L {cx:.1f},{y_peak:.1f}" for cx, _, y_peak, _ in coords[1:]]
    )
    svg_elements.append(
        f'<path d="{peak_line_d}" fill="none" stroke="#f59e0b" stroke-width="2.2" stroke-dasharray="5 4" stroke-linecap="round"/>'
    )

    # Average efficiency line (solid emerald)
    avg_line_d = " ".join(
        [f"M {coords[0][0]:.1f},{coords[0][1]:.1f}"]
        + [f"L {cx:.1f},{y_avg:.1f}" for cx, y_avg, _, _ in coords[1:]]
    )
    svg_elements.append(
        f'<path d="{avg_line_d}" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" filter="url(#effGlow)"/>'
    )

    # Hover hit areas, markers, and month labels
    for cx, y_avg, y_peak, p in coords:
        m_int = _parse_month_int(p["month"])
        m_2d = f"{m_int:02d}"
        m_name = abbr_map.get(p["month"], abbr_map.get(m_2d, p["month"]))
        eff_tip_data = json.dumps(
            {
                "month": m_name,
                "month_num": m_2d,
                "avg": p["avg_eff"],
                "peak": p["peak_eff"],
            }
        ).replace('"', "&quot;")

        svg_elements.append(
            f'<g class="chart-col eff-col" data-eff-tooltip="{eff_tip_data}" onmouseenter="showEffTooltip(event, this)" onmouseleave="hideTooltip()">'
        )
        svg_elements.append(
            f'  <rect x="{cx - slot_w / 2:.1f}" y="{pad_top}" width="{slot_w:.1f}" height="{chart_h}" class="hover-bg"/>'
        )
        svg_elements.append(
            f'  <circle cx="{cx:.1f}" cy="{y_peak:.1f}" r="4" fill="#f59e0b" stroke="#1e293b" stroke-width="1.5"/>'
        )
        svg_elements.append(
            f'  <circle cx="{cx:.1f}" cy="{y_avg:.1f}" r="5.5" fill="#10b981" stroke="#ffffff" stroke-width="2"/>'
        )
        svg_elements.append(
            f'  <text x="{cx:.1f}" y="{height - pad_bottom + 22}" text-anchor="middle" class="x-label x-label-eff" data-month="{m_2d}">{m_name}</text>'
        )
        svg_elements.append("</g>")

    svg_elements.append("</svg>")
    return "\n".join(svg_elements)


def generate_interactive_html_report(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    lang: str | None = None,
    precision: int | None = None,
) -> str:
    """Generate self-contained, offline interactive HTML report for property owners and HOA boards."""
    from src.config import get_language, get_precision

    active_lang = (lang or get_language() or "en").lower()
    is_es = active_lang.startswith("es")
    prec = get_precision() if precision is None else precision
    version = get_version()

    tot = opt_result.total_summary
    matrix = opt_result.build_matrix()
    abbr_map = MONTH_ABBR_ES if is_es else MONTH_ABBR_EN

    # Baseline comparison calculation
    base_gain_str = ""
    if "equal" in opt_result.baselines:
        eq_sc = opt_result.baselines["equal"].total_summary.total_self_consumed_kwh
        if eq_sc > 0:
            diff_pct = ((tot.total_self_consumed_kwh - eq_sc) / eq_sc) * 100.0
            if diff_pct > 0.05:
                base_gain_str = f"+{diff_pct:.1f}% vs base"

    # Bylaw constraints info
    has_bylaws = opt_result.constraints is not None and opt_result.constraints.is_active
    bylaw_badge = ""
    bylaw_min_str = ""
    bylaw_max_str = ""
    if has_bylaws and opt_result.constraints:
        c = opt_result.constraints
        parts = []
        if c.min_share is not None:
            parts.append(f"Min: {c.min_share * 100:.1f}%")
            bylaw_min_str = f"{c.min_share * 100:.1f}"
        if c.max_share is not None:
            parts.append(f"Max: {c.max_share * 100:.1f}%")
            bylaw_max_str = f"{c.max_share * 100:.1f}"
        lbl = "Límites Estatutarios" if is_es else "Bylaw Limits"
        bylaw_badge = f'<span class="badge badge-bylaw" id="badge-bylaw" data-bylaw-active="true" data-min="{bylaw_min_str}" data-max="{bylaw_max_str}">⚖️ {lbl}: {" | ".join(parts)}</span>'

    svg_monthly_chart = _generate_svg_monthly_chart(opt_result, is_es)
    svg_eff_chart = _generate_svg_efficiency_chart(opt_result, is_es)

    # Initial localized texts
    txt_title = (
        "Informe Ejecutivo de Autoconsumo Colectivo"
        if is_es
        else "Executive Collective Solar Distribution Report"
    )
    txt_subtitle = (
        "Optimización de coeficientes de reparto según Real Decreto 244/2019"
        if is_es
        else "Optimal share coefficient allocation under Spanish RD 244/2019"
    )
    txt_total_gen = "Producción Solar Total" if is_es else "Total Solar Generation"
    txt_total_dem = "Demanda Comunitaria" if is_es else "Collective Demand"
    txt_total_sc = "Energía Autoconsumida" if is_es else "Self-Consumed Energy"
    txt_total_surplus = "Excedente a Red" if is_es else "Solar Surplus"
    txt_eff = "Aprovechamiento Solar" if is_es else "Solar Utilization"
    txt_coverage = "Cobertura Solar" if is_es else "Solar Coverage"
    txt_traj_title = (
        "Trayectoria Anual de Energía (kWh)" if is_es else "Annual Energy Trajectory (kWh)"
    )
    txt_traj_sub = (
        "Generación Solar (ámbar), Demanda Comunitaria (cian) y Autoconsumo Colectivo (verde)"
        if is_es
        else "Solar Generation (amber), Collective Demand (cyan), and Self-Consumption (green)"
    )
    txt_eff_title = "Eficiencia Solar Fotovoltaica" if is_es else "Photovoltaic Solar Efficiency"
    txt_eff_sub = (
        "Índice de Eficiencia Solar (IES, 1-100) modelado con atenuación óptica nubosa, derating térmico y elevación solar estacional"
        if is_es
        else "Solar Efficiency Index (SEI, 1-100) modeled with cloud optical attenuation, thermal derating, and seasonal solar elevation"
    )
    txt_matrix_title = (
        "Matriz de Coeficientes Mensuales" if is_es else "Monthly Coefficients Matrix"
    )
    txt_matrix_sub = (
        "Distribución porcentual fija (βi) mensual establecida para cada servicio común bajo RD 244/2019"
        if is_es
        else "Fixed monthly percentage distribution (βi) established for each common service under RD 244/2019"
    )
    txt_cups_col = "Suministro / CUPS" if is_es else "Supply Point / CUPS"
    txt_avg_col = "Media Anual" if is_es else "Annual Avg"

    # Build matrix table rows
    matrix_rows: list[str] = []
    for cups in matrix.cups_list:
        use_val = matrix.cups_uses.get(cups, "")
        label_html = f"<div class='cups-cell'><span class='cups-use'>{use_val or 'Servicio'}</span><span class='cups-id'>…{cups[-8:]}</span></div>"
        cells = [f"<td>{label_html}</td>"]
        for m in matrix.months:
            raw_val = matrix.matrix.get(cups, {}).get(m)
            formatted = matrix.format_cell(cups, m, precision=prec)
            heat_class = "heat-dim"
            if raw_val is not None:
                if raw_val > 0.50:
                    heat_class = "heat-emerald"
                elif raw_val > 0.20:
                    heat_class = "heat-amber"
                elif raw_val > 0.05:
                    heat_class = "heat-cyan"
            cells.append(f"<td class='text-right {heat_class}'>{formatted}</td>")

        ann_formatted = matrix.format_annual(cups, precision=prec)
        cells.append(f"<td class='text-right font-bold col-avg'>{ann_formatted}</td>")
        matrix_rows.append(
            f"<tr class='matrix-row' data-search='{use_val} {cups}'>{''.join(cells)}</tr>"
        )

    # Matrix table header months
    month_headers = "".join(
        f"<th class='text-right th-month' data-month='{_parse_month_int(m):02d}'>{abbr_map.get(m, abbr_map.get(f'{_parse_month_int(m):02d}', m))}</th>"
        for m in matrix.months
    )

    # Template assembly
    html = f"""<!DOCTYPE html>
<html lang="{active_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{txt_title} — Electricity Share Distributor</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0b0f19;
            --bg-surface: #111827;
            --bg-card: rgba(17, 24, 39, 0.75);
            --bg-card-hover: rgba(30, 41, 59, 0.85);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(16, 185, 129, 0.3);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
            --accent-solar: #f59e0b;
            --accent-solar-glow: rgba(245, 158, 11, 0.2);
            --accent-demand: #06b6d4;
            --accent-demand-glow: rgba(6, 182, 212, 0.2);
            --accent-sc: #10b981;
            --accent-sc-glow: rgba(16, 185, 129, 0.25);
            --accent-purple: #8b5cf6;
            --accent-danger: #ef4444;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 24px;
            --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}

        [data-theme="light"] {{
            --bg-base: #f8fafc;
            --bg-surface: #ffffff;
            --bg-card: #ffffff;
            --bg-card-hover: #f1f5f9;
            --border-subtle: #e2e8f0;
            --border-glow: rgba(16, 185, 129, 0.4);
            --text-main: #0f172a;
            --text-muted: #475569;
            --text-dim: #94a3b8;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: var(--font-sans);
            background: var(--bg-base);
            color: var(--text-main);
            line-height: 1.5;
            padding: 2rem 1.5rem 4rem;
            min-height: 100vh;
            background-image:
                radial-gradient(circle at 15% 10%, rgba(245, 158, 11, 0.06) 0%, transparent 40%),
                radial-gradient(circle at 85% 20%, rgba(6, 182, 212, 0.06) 0%, transparent 40%),
                radial-gradient(circle at 50% 80%, rgba(16, 185, 129, 0.06) 0%, transparent 50%);
            background-attachment: fixed;
        }}

        .container {{
            max-width: 1180px;
            margin: 0 auto;
        }}

        /* Header */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1.5rem;
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .title-group h1 {{
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            background: linear-gradient(135deg, #ffffff 40%, var(--accent-solar) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.35rem;
        }}

        [data-theme="light"] .title-group h1 {{
            background: linear-gradient(135deg, #0f172a 40%, #d97706 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .title-group p {{
            color: var(--text-muted);
            font-size: 0.95rem;
        }}

        .badges-wrap {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            color: var(--text-muted);
        }}

        .badge-rd {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-sc);
            border-color: rgba(16, 185, 129, 0.3);
        }}

        .badge-strat {{
            background: rgba(6, 182, 212, 0.15);
            color: var(--accent-demand);
            border-color: rgba(6, 182, 212, 0.3);
        }}

        .badge-bylaw {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-solar);
            border-color: rgba(245, 158, 11, 0.3);
        }}

        .controls-group {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        /* Segmented Language Switcher */
        .lang-switch {{
            display: inline-flex;
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 2px;
            gap: 2px;
        }}

        .btn-lang {{
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-size: 0.8rem;
            font-weight: 700;
            padding: 0.35rem 0.75rem;
            border-radius: calc(var(--radius-md) - 2px);
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .btn-lang:hover {{
            color: var(--text-main);
        }}

        .btn-lang.active {{
            background: var(--accent-sc);
            color: #ffffff;
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.35);
        }}

        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.5rem 1rem;
            border-radius: var(--radius-md);
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid var(--border-subtle);
            background: var(--bg-surface);
            color: var(--text-main);
            transition: all 0.2s ease;
        }}

        .btn:hover {{
            background: var(--bg-card-hover);
            border-color: var(--text-dim);
            transform: translateY(-1px);
        }}

        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2.5rem;
        }}

        .kpi-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 1.25rem 1.5rem;
            position: relative;
            overflow: hidden;
            transition: all 0.25s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--text-dim);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
        }}

        .kpi-gen::before {{ background: var(--accent-solar); }}
        .kpi-dem::before {{ background: var(--accent-demand); }}
        .kpi-sc::before {{ background: var(--accent-sc); }}
        .kpi-surplus::before {{ background: var(--accent-purple); }}

        .kpi-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}

        .kpi-title {{
            font-size: 0.825rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}

        .kpi-value {{
            font-size: 1.75rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 0.25rem;
        }}

        .kpi-gen .kpi-value {{ color: var(--accent-solar); }}
        .kpi-dem .kpi-value {{ color: var(--accent-demand); }}
        .kpi-sc .kpi-value {{ color: var(--accent-sc); }}
        .kpi-surplus .kpi-value {{ color: var(--accent-purple); }}

        .kpi-subtitle {{
            font-size: 0.85rem;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .gain-badge {{
            background: rgba(16, 185, 129, 0.2);
            color: var(--accent-sc);
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.75rem;
        }}

        /* Section Layouts */
        .section-box {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-xl);
            padding: 1.75rem;
            margin-bottom: 2.5rem;
        }}

        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .section-title {{
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.015em;
        }}

        .section-subtitle {{
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-top: 0.2rem;
        }}

        /* Chart SVG */
        .chart-container {{
            width: 100%;
            position: relative;
        }}

        .chart-svg {{
            width: 100%;
            height: auto;
            overflow: visible;
        }}

        .grid-line {{
            stroke: var(--border-subtle);
            stroke-dasharray: 3 3;
            stroke-width: 1;
        }}

        .axis-label, .x-label {{
            font-size: 11px;
            fill: var(--text-dim);
            font-family: var(--font-sans);
        }}

        .x-label {{
            font-weight: 600;
            fill: var(--text-muted);
        }}

        .chart-col {{
            cursor: pointer;
        }}

        .hover-bg {{
            fill: transparent;
            transition: fill 0.2s;
        }}

        .chart-col:hover .hover-bg {{
            fill: rgba(255, 255, 255, 0.04);
        }}

        /* Solar Efficiency Section Extras */
        .eff-legend {{
            display: flex;
            align-items: center;
            gap: 1.25rem;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .eff-legend-item {{
            display: flex;
            align-items: center;
            gap: 0.45rem;
        }}

        .legend-line {{
            display: inline-block;
            width: 20px;
            height: 3px;
            border-radius: 2px;
        }}

        .line-peak {{
            background: var(--accent-solar);
            border-top: 1px dashed var(--accent-solar);
        }}

        .line-avg {{
            background: var(--accent-sc);
        }}

        .eff-cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-top: 1.5rem;
        }}

        .eff-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1rem 1.15rem;
            transition: all 0.2s ease;
        }}

        .eff-card:hover {{
            border-color: var(--text-dim);
            transform: translateY(-2px);
        }}

        .eff-card h4 {{
            font-size: 0.825rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 0.35rem;
        }}

        .eff-card p {{
            font-size: 0.775rem;
            color: var(--text-muted);
            line-height: 1.45;
        }}

        /* Tooltip */
        #tooltip {{
            position: fixed;
            display: none;
            background: #1e293b;
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: var(--radius-md);
            padding: 0.75rem 1rem;
            font-size: 0.8rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            pointer-events: none;
            z-index: 1000;
            min-width: 190px;
        }}

        /* Matrix Table */
        .search-box {{
            padding: 0.45rem 0.85rem;
            border-radius: var(--radius-md);
            border: 1px solid var(--border-subtle);
            background: var(--bg-surface);
            color: var(--text-main);
            font-size: 0.85rem;
            min-width: 240px;
        }}

        .table-wrap {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }}

        th {{
            padding: 0.75rem 0.65rem;
            font-weight: 600;
            color: var(--text-dim);
            border-bottom: 1px solid var(--border-subtle);
            font-size: 0.775rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        td {{
            padding: 0.65rem 0.65rem;
            border-bottom: 1px solid var(--border-subtle);
            color: var(--text-main);
        }}

        .text-right {{ text-align: right; }}
        .font-bold {{ font-weight: 700; }}

        .cups-cell {{
            display: flex;
            flex-direction: column;
        }}

        .cups-use {{
            font-weight: 600;
            color: #ffffff;
        }}

        [data-theme="light"] .cups-use {{ color: #0f172a; }}

        .cups-id {{
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: var(--text-dim);
        }}

        .col-avg {{
            color: var(--accent-sc);
        }}

        /* Heatmap cell coloring */
        .heat-dim {{ color: var(--text-dim); }}
        .heat-cyan {{ color: var(--accent-demand); background: rgba(6, 182, 212, 0.08); border-radius: 4px; }}
        .heat-amber {{ color: var(--accent-solar); background: rgba(245, 158, 11, 0.12); border-radius: 4px; font-weight: 600; }}
        .heat-emerald {{ color: var(--accent-sc); background: rgba(16, 185, 129, 0.16); border-radius: 4px; font-weight: 700; }}

        /* Print styles */
        @media print {{
            body {{
                background: #ffffff !important;
                color: #000000 !important;
                padding: 0;
            }}
            .controls-group, .search-box, #tooltip, header .btn {{
                display: none !important;
            }}
            .section-box {{
                box-shadow: none !important;
                border: 1px solid #e2e8f0 !important;
                background: #ffffff !important;
                color: #000000 !important;
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="title-group">
                <h1 data-i18n="title">⚡ {txt_title}</h1>
                <p data-i18n="subtitle">{txt_subtitle}</p>
                <div class="badges-wrap">
                    <span class="badge badge-rd" id="badge-rd" data-i18n="badge_rd">✓ RD 244/2019</span>
                    <span class="badge badge-strat" id="badge-strat" data-strat="{opt_result.strategy.lower()}">{opt_result.strategy.upper()}</span>
                    <span class="badge" id="badge-cups">👥 {ingestion_summary.cups_count} {"Suministros (CUPS)" if is_es else "Supply Points (CUPS)"}</span>
                    <span class="badge" id="badge-period">📅 {ingestion_summary.start_time[:10]} ➔ {ingestion_summary.end_time[:10]}</span>
                    {bylaw_badge}
                </div>
            </div>
            <div class="controls-group">
                <div class="lang-switch">
                    <button type="button" class="btn-lang {"active" if is_es else ""}" id="btn-lang-es" onclick="setLang('es')">ES</button>
                    <button type="button" class="btn-lang {"active" if not is_es else ""}" id="btn-lang-en" onclick="setLang('en')">EN</button>
                </div>
                <button class="btn" id="btn-theme" onclick="toggleTheme()" data-i18n="btn_theme">{"🌗 Modo" if is_es else "🌗 Theme"}</button>
                <button class="btn" id="btn-print" onclick="window.print()" data-i18n="btn_print">{"🖨️ PDF / Imprimir" if is_es else "🖨️ Print / PDF"}</button>
            </div>
        </header>

        <!-- KPI Executive Cards -->
        <div class="kpi-grid">
            <div class="kpi-card kpi-gen">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_gen_title">🌞 {txt_total_gen}</span>
                </div>
                <div class="kpi-value">{format_kwh(tot.total_generation_kwh)}</div>
                <div class="kpi-subtitle">
                    <span><span data-i18n="kpi_gen_sub">{txt_total_surplus}</span>: {format_kwh(tot.total_surplus_kwh)}</span>
                </div>
            </div>

            <div class="kpi-card kpi-dem">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_dem_title">⚡ {txt_total_dem}</span>
                </div>
                <div class="kpi-value">{format_kwh(tot.total_consumption_kwh)}</div>
                <div class="kpi-subtitle">
                    <span><span data-i18n="kpi_dem_sub">{txt_coverage}</span>: <strong>{tot.solar_coverage_rate:.1f}%</strong></span>
                </div>
            </div>

            <div class="kpi-card kpi-sc">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_sc_title">🏆 {txt_total_sc}</span>
                    {f'<span class="gain-badge">{base_gain_str}</span>' if base_gain_str else ""}
                </div>
                <div class="kpi-value">{format_kwh(tot.total_self_consumed_kwh)}</div>
                <div class="kpi-subtitle">
                    <span><span data-i18n="kpi_sc_sub">{txt_eff}</span>: <strong>{tot.self_consumption_rate:.1f}%</strong></span>
                </div>
            </div>

            <div class="kpi-card kpi-surplus">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_sum_title">🛡️ RD 244/2019 SUM</span>
                </div>
                <div class="kpi-value">100.0%</div>
                <div class="kpi-subtitle">
                    <span data-i18n="kpi_sum_sub">{"Redondeo Exacto Hare-Niemeyer" if is_es else "Hare-Niemeyer Exact Rounding"}</span>
                </div>
            </div>
        </div>

        <!-- Monthly Trajectory SVG Chart -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title" data-i18n="chart_traj_title">📊 {txt_traj_title}</h2>
                    <p class="section-subtitle" data-i18n="chart_traj_sub">{txt_traj_sub}</p>
                </div>
            </div>
            <div class="chart-container">
                {svg_monthly_chart}
            </div>
        </div>

        <!-- Solar Efficiency Profile Section (New) -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title" data-i18n="chart_eff_title">☀️ {txt_eff_title}</h2>
                    <p class="section-subtitle" data-i18n="chart_eff_sub">{txt_eff_sub}</p>
                </div>
                <div class="eff-legend">
                    <div class="eff-legend-item"><span class="legend-line line-peak"></span> <span data-i18n="tip_eff_peak">{"Eficiencia Cenit (13:00)" if is_es else "Solar Noon Peak (13:00)"}</span></div>
                    <div class="eff-legend-item"><span class="legend-line line-avg"></span> <span data-i18n="tip_eff_avg">{"Media Diurna (08:00-18:00)" if is_es else "Daytime Avg (08:00-18:00)"}</span></div>
                </div>
            </div>
            <div class="chart-container">
                {svg_eff_chart}
            </div>
            <div class="eff-cards-grid">
                <div class="eff-card">
                    <h4 data-i18n="eff_card1_title">☁️ {"Atenuación Óptica Nubosa" if is_es else "Cloud Optical Attenuation"}</h4>
                    <p data-i18n="eff_card1_desc">{"Transmisión no lineal con retención de ~25% de irradiancia difusa incluso bajo cobertura total." if is_es else "Non-linear optical transmission retaining ~25% diffuse solar irradiance even under 100% overcast."}</p>
                </div>
                <div class="eff-card">
                    <h4 data-i18n="eff_card2_title">🌡️ {"Derating Térmico FV" if is_es else "PV Thermal Derating"}</h4>
                    <p data-i18n="eff_card2_desc">{"Coeficiente de potencia de -0,4%/°C respecto a 20°C ambiente (estándar de silicio monocristalino)." if is_es else "Power temperature derating coefficient of -0.4%/°C relative to 20°C ambient reference."}</p>
                </div>
                <div class="eff-card">
                    <h4 data-i18n="eff_card3_title">☀️ {"Elevación Estacional" if is_es else "Seasonal Declination"}</h4>
                    <p data-i18n="eff_card3_desc">{"Masa de aire y declinación solar en latitudes ibéricas, con máximo estival y mínimo invernal." if is_es else "Annual air mass and solar elevation cycle across Iberian latitudes, peaking near summer solstice."}</p>
                </div>
                <div class="eff-card">
                    <h4 data-i18n="eff_card4_title">⏱️ {"Cenit Solar Diario" if is_es else "Diurnal Solar Zenith"}</h4>
                    <p data-i18n="eff_card4_desc">{"Trayectoria horaria óptima con pérdidas de reflexión mínimas hacia el mediodía solar (13:00-14:00 h)." if is_es else "Optimal diurnal solar arc with minimal reflection losses around solar noon (13:00-14:00)."}</p>
                </div>
            </div>
        </div>

        <!-- Share Matrix Heatmap Table -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title" data-i18n="matrix_title">🗓️ {txt_matrix_title}</h2>
                    <p class="section-subtitle" data-i18n="matrix_sub">{txt_matrix_sub}</p>
                </div>
                <input type="text" id="searchInput" class="search-box" data-i18n-placeholder="search_placeholder" placeholder="{"Buscar servicio o CUPS..." if is_es else "Search service or CUPS..."}" oninput="filterTable()">
            </div>
            <div class="table-wrap">
                <table id="matrixTable">
                    <thead>
                        <tr>
                            <th data-i18n="col_cups">{txt_cups_col}</th>
                            {month_headers}
                            <th class="text-right col-avg" data-i18n="col_avg">{txt_avg_col}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(matrix_rows)}
                    </tbody>
                </table>
            </div>
        </div>

        <footer style="margin-top: 3rem; text-align: center; color: var(--text-dim); font-size: 0.8rem;">
            <span data-i18n="footer_text">{"Generado por" if is_es else "Generated by"} <strong>Electricity Share Distributor (esd) v{version}</strong> • {"Real Decreto 244/2019" if is_es else "Spanish RD 244/2019"}</span>
        </footer>
    </div>

    <!-- Tooltip Element -->
    <div id="tooltip"></div>

    <script>
        let currentLang = '{active_lang}';
        const cupsCount = {ingestion_summary.cups_count};
        const periodStart = "{ingestion_summary.start_time[:10]}";
        const periodEnd = "{ingestion_summary.end_time[:10]}";
        const appVersion = "{version}";

        const I18N = {{
            es: {{
                doc_title: "Informe Ejecutivo de Autoconsumo Colectivo — Electricity Share Distributor",
                title: "⚡ Informe Ejecutivo de Autoconsumo Colectivo",
                subtitle: "Optimización de coeficientes de reparto según Real Decreto 244/2019",
                badge_rd: "✓ RD 244/2019",
                btn_theme: "🌗 Modo",
                btn_print: "🖨️ PDF / Imprimir",
                kpi_gen_title: "🌞 Producción Solar Total",
                kpi_gen_sub: "Excedente a Red",
                kpi_dem_title: "⚡ Demanda Comunitaria",
                kpi_dem_sub: "Cobertura Solar",
                kpi_sc_title: "🏆 Energía Autoconsumida",
                kpi_sc_sub: "Aprovechamiento Solar",
                kpi_sum_title: "🛡️ RD 244/2019 SUM",
                kpi_sum_sub: "Redondeo Exacto Hare-Niemeyer",
                chart_traj_title: "📊 Trayectoria Anual de Energía (kWh)",
                chart_traj_sub: "Generación Solar (ámbar), Demanda Comunitaria (cian) y Autoconsumo Colectivo (verde)",
                chart_eff_title: "☀️ Eficiencia Solar Fotovoltaica",
                chart_eff_sub: "Índice de Eficiencia Solar (IES, 1-100) modelado con atenuación óptica nubosa, derating térmico y elevación solar estacional",
                eff_card1_title: "☁️ Atenuación Óptica Nubosa",
                eff_card1_desc: "Transmisión no lineal con retención de ~25% de irradiancia difusa incluso bajo cobertura total.",
                eff_card2_title: "🌡️ Derating Térmico FV",
                eff_card2_desc: "Coeficiente de potencia de -0,4%/°C respecto a 20°C ambiente (estándar de silicio monocristalino).",
                eff_card3_title: "☀️ Elevación Estacional",
                eff_card3_desc: "Masa de aire y declinación solar en latitudes ibéricas, con máximo estival y mínimo invernal.",
                eff_card4_title: "⏱️ Cenit Solar Diario",
                eff_card4_desc: "Trayectoria horaria óptima con pérdidas de reflexión mínimas hacia el mediodía solar (13:00-14:00 h).",
                matrix_title: "🗓️ Matriz de Coeficientes Mensuales",
                matrix_sub: "Distribución porcentual fija (βi) mensual establecida para cada servicio común bajo RD 244/2019",
                search_placeholder: "Buscar servicio o CUPS...",
                col_cups: "Suministro / CUPS",
                col_avg: "Media Anual",
                tip_gen: "Generación",
                tip_dem: "Demanda",
                tip_sc: "Autoconsumo",
                tip_surplus: "Excedente",
                tip_coverage: "Cobertura",
                tip_efficiency: "Aprovechamiento",
                tip_eff_avg: "Media Diurna (08:00-18:00)",
                tip_eff_peak: "Eficiencia Cenit (13:00)",
                tip_rating: "Calificación",
                rating_excellent: "Excelente",
                rating_good: "Favorable",
                rating_moderate: "Moderada",
                footer_text: `Generado por <strong>Electricity Share Distributor (esd) v${{appVersion}}</strong> • Real Decreto 244/2019`,
                months: {{
                    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr",
                    "05": "May", "06": "Jun", "07": "Jul", "08": "Ago",
                    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"
                }},
                months_full: {{
                    "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
                    "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
                    "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
                }}
            }},
            en: {{
                doc_title: "Executive Collective Solar Distribution Report — Electricity Share Distributor",
                title: "⚡ Executive Collective Solar Distribution Report",
                subtitle: "Optimal share coefficient allocation under Spanish RD 244/2019",
                badge_rd: "✓ RD 244/2019",
                btn_theme: "🌗 Theme",
                btn_print: "🖨️ Print / PDF",
                kpi_gen_title: "🌞 Total Solar Generation",
                kpi_gen_sub: "Solar Surplus",
                kpi_dem_title: "⚡ Collective Demand",
                kpi_dem_sub: "Solar Coverage",
                kpi_sc_title: "🏆 Self-Consumed Energy",
                kpi_sc_sub: "Solar Utilization",
                kpi_sum_title: "🛡️ RD 244/2019 SUM",
                kpi_sum_sub: "Hare-Niemeyer Exact Rounding",
                chart_traj_title: "📊 Annual Energy Trajectory (kWh)",
                chart_traj_sub: "Solar Generation (amber), Collective Demand (cyan), and Self-Consumption (green)",
                chart_eff_title: "☀️ Photovoltaic Solar Efficiency",
                chart_eff_sub: "Solar Efficiency Index (SEI, 1-100) modeled with cloud optical attenuation, thermal derating, and seasonal solar elevation",
                eff_card1_title: "☁️ Cloud Optical Attenuation",
                eff_card1_desc: "Non-linear optical transmission retaining ~25% diffuse solar irradiance even under 100% overcast.",
                eff_card2_title: "🌡️ PV Thermal Derating",
                eff_card2_desc: "Power temperature derating coefficient of -0.4%/°C relative to 20°C ambient reference.",
                eff_card3_title: "☀️ Seasonal Declination",
                eff_card3_desc: "Annual air mass and solar elevation cycle across Iberian latitudes, peaking near summer solstice.",
                eff_card4_title: "⏱️ Diurnal Solar Zenith",
                eff_card4_desc: "Optimal diurnal solar arc with minimal reflection losses around solar noon (13:00-14:00).",
                matrix_title: "🗓️ Monthly Coefficients Matrix",
                matrix_sub: "Fixed monthly percentage distribution (βi) established for each common service under RD 244/2019",
                search_placeholder: "Search service or CUPS...",
                col_cups: "Supply Point / CUPS",
                col_avg: "Annual Avg",
                tip_gen: "Generation",
                tip_dem: "Demand",
                tip_sc: "Self-Consumed",
                tip_surplus: "Surplus",
                tip_coverage: "Coverage",
                tip_efficiency: "Utilization",
                tip_eff_avg: "Daytime Avg (08:00-18:00)",
                tip_eff_peak: "Solar Noon Peak (13:00)",
                tip_rating: "Rating",
                rating_excellent: "Excellent",
                rating_good: "Good",
                rating_moderate: "Moderate",
                footer_text: `Generated by <strong>Electricity Share Distributor (esd) v${{appVersion}}</strong> • Spanish RD 244/2019`,
                months: {{
                    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
                    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
                    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
                }},
                months_full: {{
                    "01": "January", "02": "February", "03": "March", "04": "April",
                    "05": "May", "06": "June", "07": "July", "08": "August",
                    "09": "September", "10": "October", "11": "November", "12": "December"
                }}
            }}
        }};

        function setLang(lang) {{
            if (!I18N[lang]) return;
            currentLang = lang;
            document.documentElement.lang = lang;

            // Update language switcher buttons
            const btnEs = document.getElementById('btn-lang-es');
            const btnEn = document.getElementById('btn-lang-en');
            if (btnEs) btnEs.className = lang === 'es' ? 'btn-lang active' : 'btn-lang';
            if (btnEn) btnEn.className = lang === 'en' ? 'btn-lang active' : 'btn-lang';

            // Update document title
            document.title = I18N[lang].doc_title;

            // Update data-i18n text elements
            document.querySelectorAll('[data-i18n]').forEach(el => {{
                const key = el.getAttribute('data-i18n');
                if (I18N[lang][key] !== undefined) {{
                    el.innerHTML = I18N[lang][key];
                }}
            }});

            // Update placeholder attributes
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {{
                const key = el.getAttribute('data-i18n-placeholder');
                if (I18N[lang][key] !== undefined) {{
                    el.placeholder = I18N[lang][key];
                }}
            }});

            // Update month abbreviations in tables and charts
            document.querySelectorAll('[data-month]').forEach(el => {{
                const m = el.getAttribute('data-month');
                if (I18N[lang].months[m]) {{
                    el.textContent = I18N[lang].months[m];
                }}
            }});

            // Update CUPS badge text
            const cupsBadge = document.getElementById('badge-cups');
            if (cupsBadge) {{
                cupsBadge.textContent = lang === 'es'
                    ? `👥 ${{cupsCount}} Suministros (CUPS)`
                    : `👥 ${{cupsCount}} Supply Points (CUPS)`;
            }}

            // Update strategy badge if present
            const stratBadge = document.getElementById('badge-strat');
            if (stratBadge) {{
                const stratKey = stratBadge.getAttribute('data-strat');
                if (stratKey === 'optimal') stratBadge.textContent = lang === 'es' ? 'ÓPTIMO' : 'OPTIMAL';
                else if (stratKey === 'equal') stratBadge.textContent = lang === 'es' ? 'EQUITATIVO' : 'EQUAL';
                else if (stratKey === 'consumption') stratBadge.textContent = lang === 'es' ? 'CONSUMO' : 'CONSUMPTION';
            }}

            // Update bylaw badge if present
            const bylawBadge = document.getElementById('badge-bylaw');
            if (bylawBadge && bylawBadge.getAttribute('data-bylaw-active') === 'true') {{
                const minVal = bylawBadge.getAttribute('data-min');
                const maxVal = bylawBadge.getAttribute('data-max');
                const parts = [];
                if (minVal) parts.push(`Min: ${{minVal}}%`);
                if (maxVal) parts.push(`Max: ${{maxVal}}%`);
                const label = lang === 'es' ? 'Límites Estatutarios' : 'Bylaw Limits';
                bylawBadge.textContent = `⚖️ ${{label}}: ${{parts.join(' | ')}}`;
            }}
        }}

        function showTooltip(evt, el) {{
            const raw = el.getAttribute('data-tooltip');
            if (!raw) return;
            const data = JSON.parse(raw);
            const tip = document.getElementById('tooltip');
            const t = I18N[currentLang] || I18N.es;
            const mName = t.months_full[data.month_num] || data.month;
            tip.innerHTML = `
                <div style="font-weight:700; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:4px; margin-bottom:6px;">
                    📅 ${{mName}}
                </div>
                <div>🌞 ${{t.tip_gen}}: <strong>${{data.gen}}</strong></div>
                <div>⚡ ${{t.tip_dem}}: <strong>${{data.dem}}</strong></div>
                <div>🏆 ${{t.tip_sc}}: <strong style="color:var(--accent-sc);">${{data.sc}}</strong></div>
                <div>🛡️ ${{t.tip_surplus}}: <strong>${{data.surplus}}</strong></div>
                <div style="margin-top:4px; font-size:0.75rem; color:var(--text-muted);">
                    ${{t.tip_coverage}}: <strong>${{data.cov}}</strong> • ${{t.tip_efficiency}}: <strong>${{data.eff}}</strong>
                </div>
            `;
            tip.style.display = 'block';
            tip.style.left = (evt.clientX + 14) + 'px';
            tip.style.top = (evt.clientY + 14) + 'px';
        }}

        function showEffTooltip(evt, el) {{
            const raw = el.getAttribute('data-eff-tooltip');
            if (!raw) return;
            const data = JSON.parse(raw);
            const tip = document.getElementById('tooltip');
            const t = I18N[currentLang] || I18N.es;
            const mName = t.months_full[data.month_num] || data.month;
            let ratingStr = t.rating_excellent;
            let ratingColor = "var(--accent-sc)";
            if (data.avg < 65) {{
                ratingStr = t.rating_moderate;
                ratingColor = "var(--accent-solar)";
            }} else if (data.avg < 80) {{
                ratingStr = t.rating_good;
                ratingColor = "var(--accent-demand)";
            }}
            tip.innerHTML = `
                <div style="font-weight:700; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:4px; margin-bottom:6px;">
                    ☀️ ${{mName}}
                </div>
                <div>${{t.tip_eff_avg}}: <strong style="color:${{ratingColor}}; font-size:1.1em;">${{data.avg}}%</strong></div>
                <div>${{t.tip_eff_peak}}: <strong>${{data.peak}}%</strong></div>
                <div style="margin-top:4px; font-size:0.75rem; color:var(--text-muted);">
                    ${{t.tip_rating}}: <strong style="color:${{ratingColor}};">${{ratingStr}}</strong>
                </div>
            `;
            tip.style.display = 'block';
            tip.style.left = (evt.clientX + 14) + 'px';
            tip.style.top = (evt.clientY + 14) + 'px';
        }}

        function hideTooltip() {{
            const tip = document.getElementById('tooltip');
            tip.style.display = 'none';
        }}

        function filterTable() {{
            const term = document.getElementById('searchInput').value.toLowerCase().trim();
            const rows = document.querySelectorAll('.matrix-row');
            rows.forEach(row => {{
                const search = (row.getAttribute('data-search') || '').toLowerCase();
                row.style.display = search.includes(term) ? '' : 'none';
            }});
        }}

        function toggleTheme() {{
            const current = document.documentElement.getAttribute('data-theme');
            const target = current === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', target);
        }}
    </script>
</body>
</html>
"""
    return html
