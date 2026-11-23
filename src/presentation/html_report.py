"""Interactive standalone HTML report generator for collective PV self-consumption (RD 244/2019)."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from typing import TYPE_CHECKING, Any

from src.config import get_language
from src.i18n import get_month_name, t
from src.optimization.efficiency import calculate_solar_efficiency
from src.presentation.charts import render_community_bar_svg, render_cups_bar_svgs
from src.presentation.console import format_kwh
from src.presentation.views.common import MONTH_ABBR_EN, MONTH_ABBR_ES
from src.version import get_version

if TYPE_CHECKING:
    from src.analytics.models import ComparisonSummary
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
        '    <stop offset="0%" stop-color="#f59e0b" stop-opacity="0.95"/>',
        '    <stop offset="100%" stop-color="#d97706" stop-opacity="0.45"/>',
        "  </linearGradient>",
        '  <linearGradient id="gradDem" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#06b6d4" stop-opacity="0.95"/>',
        '    <stop offset="100%" stop-color="#0284c7" stop-opacity="0.45"/>',
        "  </linearGradient>",
        '  <linearGradient id="gradSc" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#10b981" stop-opacity="0.98"/>',
        '    <stop offset="100%" stop-color="#059669" stop-opacity="0.55"/>',
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
                "solar_dem": f"{m.solar_hours_consumption_kwh:,.1f} kWh",
                "solar_cov": f"{m.solar_hours_coverage_rate:.1f}%",
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


def _calculate_hourly_prevision(opt_result: OptimizationResult) -> dict[str, Any]:
    """Read 4-way self-consumption progression metrics directly from OptimizationResult.

    Covers all four operational modalities without re-parsing time-series DataFrames:
    1. Current Self-Consumption (single CUPS tied behind inverter meter)
    2. Fixed Monthly Share (Real Decreto 244/2019)
    3. Fortnight Share (24 half-month periods)
    4. Dynamic Hourly Share (Orden TED/1247/2021)
    """
    tot = opt_result.total_summary
    tot_gen = tot.total_generation_kwh
    tot_dem = tot.total_consumption_kwh
    monthly_sc = (
        opt_result.monthly_share_self_consumed_kwh
        if opt_result.monthly_share_self_consumed_kwh > 0
        else tot.total_self_consumed_kwh
    )

    # 1. Identify primary supply point directly from OptimizationResult
    primary_cups: str | None = opt_result.primary_cups
    if primary_cups and opt_result.cups_list and primary_cups not in opt_result.cups_list:
        primary_cups = None
    if not primary_cups and opt_result.cups_list:
        primary_cups = opt_result.cups_list[0]
    primary_name: str = opt_result.cups_uses.get(primary_cups, "") if primary_cups else ""

    # 2. Current / No Collective Share (solely tied to primary CUPS)
    if opt_result.current_self_consumed_kwh > 0:
        single_sc_val = opt_result.current_self_consumed_kwh
    else:
        pri_metric = (
            next((c for c in tot.cups_metrics if c.cups == primary_cups), None)
            if primary_cups
            else None
        )
        single_sc_val = float(pri_metric.self_consumed_kwh) if pri_metric else 0.0
    single_sc = round(max(0.0, min(monthly_sc, single_sc_val)), 1)

    # 3. Fortnight Share (24 half-month periods)
    has_fortnight = opt_result.fortnight_share_self_consumed_kwh > 0
    if has_fortnight:
        fortnight_sc = round(
            max(0.0, min(tot_gen, min(tot_dem, opt_result.fortnight_share_self_consumed_kwh))),
            1,
        )
    else:
        fortnight_sc = round(max(0.0, min(tot_gen, min(tot_dem, monthly_sc))), 1)

    # 4. Dynamic Hourly Share (Orden TED/1247/2021)
    is_simulated = opt_result.hourly_share_self_consumed_kwh > 0
    if is_simulated:
        hourly_sc = round(
            max(0.0, min(tot_gen, min(tot_dem, opt_result.hourly_share_self_consumed_kwh))),
            1,
        )
    else:
        hourly_sc = round(max(0.0, min(tot_gen, min(tot_dem, max(monthly_sc, fortnight_sc)))), 1)

    # Self-consumption rates, surpluses, and solar coverages
    single_sc_rate = (single_sc / max(tot_gen, 1e-6)) * 100.0
    single_surplus_kwh = max(0.0, tot_gen - single_sc)
    single_cov_rate = (single_sc / max(tot_dem, 1e-6)) * 100.0

    monthly_sc_rate = (
        (monthly_sc / max(tot_gen, 1e-6)) * 100.0 if tot_gen > 0 else tot.self_consumption_rate
    )
    monthly_surplus_kwh = max(0.0, tot_gen - monthly_sc) if tot_gen > 0 else tot.total_surplus_kwh
    monthly_cov_rate = (
        (monthly_sc / max(tot_dem, 1e-6)) * 100.0 if tot_dem > 0 else tot.solar_coverage_rate
    )

    fortnight_sc_rate = (fortnight_sc / max(tot_gen, 1e-6)) * 100.0
    fortnight_surplus_kwh = max(0.0, tot_gen - fortnight_sc)
    fortnight_cov_rate = (fortnight_sc / max(tot_dem, 1e-6)) * 100.0

    hourly_sc_rate = (hourly_sc / max(tot_gen, 1e-6)) * 100.0
    hourly_surplus_kwh = max(0.0, tot_gen - hourly_sc)
    hourly_cov_rate = (hourly_sc / max(tot_dem, 1e-6)) * 100.0

    # Step-by-step and cumulative uplift vs baseline
    gain_monthly_kwh = max(0.0, monthly_sc - single_sc)
    gain_monthly_pct = (gain_monthly_kwh / max(single_sc, 1e-6)) * 100.0

    gain_fortnight_kwh = max(0.0, fortnight_sc - single_sc)
    gain_fortnight_pct = (gain_fortnight_kwh / max(single_sc, 1e-6)) * 100.0

    gain_fortnight_vs_monthly_kwh = max(0.0, fortnight_sc - monthly_sc)
    gain_fortnight_vs_monthly_pct = (gain_fortnight_vs_monthly_kwh / max(monthly_sc, 1e-6)) * 100.0

    gain_hourly_kwh = max(0.0, hourly_sc - monthly_sc)
    gain_hourly_pct = (gain_hourly_kwh / max(monthly_sc, 1e-6)) * 100.0

    gain_total_kwh = max(0.0, hourly_sc - single_sc)
    gain_total_pct = (gain_total_kwh / max(single_sc, 1e-6)) * 100.0

    return {
        "primary_cups": primary_cups or "",
        "primary_name": primary_name or "Primary CUPS",
        # Scenario 1: Single CUPS (No Collective Share)
        "single_sc_kwh": single_sc,
        "single_sc_rate": round(single_sc_rate, 1),
        "single_surplus_kwh": round(single_surplus_kwh, 1),
        "single_cov_rate": round(single_cov_rate, 1),
        # Scenario 2: Monthly Share (RD 244/2019)
        "monthly_sc_kwh": round(monthly_sc, 1),
        "monthly_sc_rate": round(monthly_sc_rate, 1),
        "monthly_surplus_kwh": round(monthly_surplus_kwh, 1),
        "monthly_cov_rate": round(monthly_cov_rate, 1),
        "gain_monthly_kwh": round(gain_monthly_kwh, 1),
        "gain_monthly_pct": round(gain_monthly_pct, 1),
        # Scenario 3: Fortnight Share (24 Half-Month Periods)
        "has_fortnight": has_fortnight,
        "fortnight_sc_kwh": fortnight_sc,
        "fortnight_sc_rate": round(fortnight_sc_rate, 1),
        "fortnight_surplus_kwh": round(fortnight_surplus_kwh, 1),
        "fortnight_cov_rate": round(fortnight_cov_rate, 1),
        "gain_fortnight_kwh": round(gain_fortnight_kwh, 1),
        "gain_fortnight_pct": round(gain_fortnight_pct, 1),
        "gain_fortnight_vs_monthly_kwh": round(gain_fortnight_vs_monthly_kwh, 1),
        "gain_fortnight_vs_monthly_pct": round(gain_fortnight_vs_monthly_pct, 1),
        # Scenario 4: Dynamic Hourly Share (Orden TED/1247/2021)
        "hourly_sc_kwh": hourly_sc,
        "hourly_sc_rate": round(hourly_sc_rate, 1),
        "hourly_surplus_kwh": round(hourly_surplus_kwh, 1),
        "hourly_cov_rate": round(hourly_cov_rate, 1),
        "gain_hourly_kwh": round(gain_hourly_kwh, 1),
        "gain_hourly_pct": round(gain_hourly_pct, 1),
        # Total Uplift vs Single CUPS
        "gain_total_kwh": round(gain_total_kwh, 1),
        "gain_total_pct": round(gain_total_pct, 1),
        "is_simulated": is_simulated,
        # Backward compatibility aliases
        "gain_kwh": round(gain_hourly_kwh, 1),
        "gain_pct": round(gain_hourly_pct, 1),
    }


def _build_html_i18n(version: str = "dev") -> dict[str, dict[str, Any]]:
    """Build unified bilingual (ES/EN) UI dictionary shared by HTML SSR and JS runtime."""
    return {
        "es": {
            "doc_title": "Informe Ejecutivo de Autoconsumo Colectivo — Electricity Share Distributor",
            "title": "⚡ Informe Ejecutivo de Autoconsumo Colectivo",
            "subtitle": "Optimización de coeficientes de reparto según Real Decreto 244/2019",
            "badge_rd": "✓ RD 244/2019",
            "cups_label": "Suministros (CUPS)",
            "bylaw_label": "Límites Estatutarios",
            "mode_simulated": "Simulación Horaria Diurna",
            "mode_modeled": "Previsión Diurna Modelada",
            "strat_optimal": "ÓPTIMO",
            "strat_equal": "EQUITATIVO",
            "strat_consumption_share": "CONSUMO",
            "strat_consumption": "CONSUMO",
            "default_service": "Servicio",
            "btn_theme": "🌗 Modo",
            "btn_print": "🖨️ PDF / Imprimir",
            "kpi_gen_title": "🌞 Producción Solar Total",
            "kpi_dem_title": "⚡ Demanda Comunitaria",
            "kpi_surplus_title": "🛡️ Excedente a Red",
            "kpi_sc_title": "🏆 Energía Autoconsumida",
            "kpi_solar_hours_gen": "Horas de Sol",
            "kpi_solar_hours_dem": "Horas de Sol",
            "kpi_surplus_rate": "Vertido a Red",
            "kpi_sc_rate": "Aprovechamiento",
            "kpi_cov_rate": "Cobertura",
            "prev_box_title": "⚡ Previsión y Comparativa de Autoconsumo",
            "prev_box_sub": "Progresión comparativa en 4 modalidades: Sin reparto colectivo (1 solo CUPS), Reparto Mensual Fijo (RD 244/2019), Reparto Quincenal (24 quincenas) y Reparto Horario Dinámico (Orden TED/1247/2021)",
            "hourly_badge_ted": "📜 Orden TED/1247/2021",
            "prev_card1_title": "Sin Reparto (1 solo CUPS)",
            "prev_card1_sub": "Aprovechamiento",
            "prev_card1_tag": "Línea Base",
            "prev_card2_title": "Reparto Mensual (RD 244/2019)",
            "prev_card2_vs": "vs 1 CUPS",
            "prev_card_fortnight_title": "Reparto Quincenal (24 Quincenas)",
            "prev_card_fortnight_vs": "vs 1 CUPS",
            "prev_card3_title": "Reparto Horario (Orden TED)",
            "prev_card3_vs": "vs mensual",
            "prev_card4_title": "Ganancia Colectiva Total",
            "prev_card4_sub": "sobre 1 CUPS",
            "prev_comp_single": "Sin Reparto Colectivo (1 solo CUPS)",
            "prev_comp_monthly": "Reparto Mensual Fijo (RD 244/2019)",
            "prev_comp_fortnight": "Reparto Quincenal (24 Quincenas)",
            "prev_comp_hourly": "Reparto Horario Dinámico (Orden TED/1247/2021)",
            "prev_note": "Al pasar del autoconsumo individual en 1 solo CUPS al reparto mensual fijo bajo <strong>RD 244/2019</strong> o al reparto quincenal por medias lunas, la comunidad captura la simultaneidad estacional entre servicios comunes. La adopción de coeficientes horarios dinámicos según la <strong>Orden TED/1247/2021</strong> maximiza el aprovechamiento solar y minimiza el excedente vertido a red sin inversión adicional en hardware.",
            "chart_traj_title": "📊 Trayectoria Anual de Energía (kWh)",
            "chart_traj_sub": "Generación Solar (ámbar), Demanda Comunitaria (cian) y Autoconsumo Colectivo (verde)",
            "chart_eff_title": "☀️ Eficiencia Solar Fotovoltaica",
            "chart_eff_sub": "Índice de Eficiencia Solar (IES, 1-100) modelado con atenuación óptica nubosa, derating térmico y elevación solar estacional",
            "eff_card1_title": "☁️ Atenuación Óptica Nubosa",
            "eff_card1_desc": "Transmisión no lineal con retención de ~25% de irradiancia difusa incluso bajo cobertura total.",
            "eff_card2_title": "🌡️ Derating Térmico FV",
            "eff_card2_desc": "Coeficiente de potencia de -0,4%/°C respecto a 20°C ambiente (estándar de silicio monocristalino).",
            "eff_card3_title": "☀️ Elevación Estacional",
            "eff_card3_desc": "Masa de aire y declinación solar en latitudes ibéricas, con máximo estival y mínimo invernal.",
            "eff_card4_title": "⏱️ Cenit Solar Diario",
            "eff_card4_desc": "Trayectoria horaria óptima con pérdidas de reflexión mínimas hacia el mediodía solar (13:00-14:00 h).",
            "matrix_title": "🗓️ Matriz de Coeficientes Mensuales",
            "matrix_sub": "Distribución porcentual fija (βi) mensual establecida para cada servicio común bajo RD 244/2019",
            "search_placeholder": "Buscar servicio o CUPS...",
            "col_cups": "Suministro / CUPS",
            "col_avg": "Media Anual",
            "lbl_total_rd244": "TOTAL (RD 244/2019)",
            "tip_gen": "Generación",
            "tip_dem": "Demanda",
            "tip_solar_dem": "Demanda Horas Sol",
            "tip_solar_cov": "Cobertura Horas Sol",
            "tip_sc": "Autoconsumo",
            "tip_surplus": "Excedente",
            "tip_coverage": "Cobertura",
            "tip_efficiency": "Aprovechamiento",
            "tip_eff_avg": "Media Diurna (08:00-18:00)",
            "tip_eff_peak": "Eficiencia Cenit (13:00)",
            "tip_rating": "Calificación",
            "rating_excellent": "Excelente",
            "rating_good": "Favorable",
            "rating_moderate": "Moderada",
            "footer_text": f"Generado por <strong>Electricity Share Distributor (esd) v{version}</strong> • Real Decreto 244/2019",
            "months": {
                "01": "Ene",
                "02": "Feb",
                "03": "Mar",
                "04": "Abr",
                "05": "May",
                "06": "Jun",
                "07": "Jul",
                "08": "Ago",
                "09": "Sep",
                "10": "Oct",
                "11": "Nov",
                "12": "Dic",
            },
            "months_full": {
                "01": "Enero",
                "02": "Febrero",
                "03": "Marzo",
                "04": "Abril",
                "05": "Mayo",
                "06": "Junio",
                "07": "Julio",
                "08": "Agosto",
                "09": "Septiembre",
                "10": "Octubre",
                "11": "Noviembre",
                "12": "Diciembre",
            },
        },
        "en": {
            "doc_title": "Executive Collective Solar Distribution Report — Electricity Share Distributor",
            "title": "⚡ Executive Collective Solar Distribution Report",
            "subtitle": "Optimal share coefficient allocation under Spanish RD 244/2019",
            "badge_rd": "✓ RD 244/2019",
            "cups_label": "Supply Points (CUPS)",
            "bylaw_label": "Bylaw Limits",
            "mode_simulated": "Hourly Diurnal Simulation",
            "mode_modeled": "Modeled Diurnal Prevision",
            "strat_optimal": "OPTIMAL",
            "strat_equal": "EQUAL",
            "strat_consumption_share": "CONSUMPTION",
            "strat_consumption": "CONSUMPTION",
            "default_service": "Service",
            "btn_theme": "🌗 Theme",
            "btn_print": "🖨️ Print / PDF",
            "kpi_gen_title": "🌞 Total Solar Generation",
            "kpi_dem_title": "⚡ Collective Demand",
            "kpi_surplus_title": "🛡️ Solar Surplus (Grid)",
            "kpi_sc_title": "🏆 Self-Consumed Energy",
            "kpi_solar_hours_gen": "Solar Hours",
            "kpi_solar_hours_dem": "Solar Hours",
            "kpi_surplus_rate": "Spilled to Grid",
            "kpi_sc_rate": "Efficiency",
            "kpi_cov_rate": "Coverage",
            "prev_box_title": "⚡ Self-Consumption Prevision & Comparison",
            "prev_box_sub": "4-way comparative solar utilization: No collective share (single CUPS), Fixed Monthly Share (RD 244/2019), Fortnight Share (24 half-month periods), and Dynamic Hourly Share (Order TED/1247/2021)",
            "hourly_badge_ted": "📜 Spanish Order TED/1247/2021",
            "prev_card1_title": "No Share (Single CUPS)",
            "prev_card1_sub": "Utilization",
            "prev_card1_tag": "Baseline",
            "prev_card2_title": "Monthly Share (RD 244/2019)",
            "prev_card2_vs": "vs single CUPS",
            "prev_card_fortnight_title": "Fortnight Share (24 Periods)",
            "prev_card_fortnight_vs": "vs single CUPS",
            "prev_card3_title": "Hourly Share (Order TED)",
            "prev_card3_vs": "vs monthly",
            "prev_card4_title": "Total Collective Uplift",
            "prev_card4_sub": "over single CUPS",
            "prev_comp_single": "No Collective Share (Single CUPS)",
            "prev_comp_monthly": "Fixed Monthly Share (RD 244/2019)",
            "prev_comp_fortnight": "Fortnight Share (24 Half-Month Periods)",
            "prev_comp_hourly": "Dynamic Hourly Share (Orden TED/1247/2021)",
            "prev_note": "Moving from single-meter self-consumption to fixed monthly (<strong>RD 244/2019</strong>) or fortnight (half-month) collective shares captures seasonal concurrency across common services. Transitioning further to dynamic hourly schedules under Spanish <strong>Order TED/1247/2021</strong> maximizes solar harvesting and minimizes spilled grid surplus with zero additional hardware costs.",
            "chart_traj_title": "📊 Annual Energy Trajectory (kWh)",
            "chart_traj_sub": "Solar Generation (amber), Collective Demand (cyan), and Self-Consumption (green)",
            "chart_eff_title": "☀️ Photovoltaic Solar Efficiency",
            "chart_eff_sub": "Solar Efficiency Index (SEI, 1-100) modeled with cloud optical attenuation, thermal derating, and seasonal solar elevation",
            "eff_card1_title": "☁️ Cloud Optical Attenuation",
            "eff_card1_desc": "Non-linear optical transmission retaining ~25% diffuse solar irradiance even under 100% overcast.",
            "eff_card2_title": "🌡️ PV Thermal Derating",
            "eff_card2_desc": "Power temperature derating coefficient of -0.4%/°C relative to 20°C ambient reference.",
            "eff_card3_title": "☀️ Seasonal Declination",
            "eff_card3_desc": "Annual air mass and solar elevation cycle across Iberian latitudes, peaking near summer solstice.",
            "eff_card4_title": "⏱️ Diurnal Solar Zenith",
            "eff_card4_desc": "Optimal diurnal solar arc with minimal reflection losses around solar noon (13:00-14:00).",
            "matrix_title": "🗓️ Monthly Coefficients Matrix",
            "matrix_sub": "Fixed monthly percentage distribution (βi) established for each common service under RD 244/2019",
            "search_placeholder": "Search service or CUPS...",
            "col_cups": "Supply Point / CUPS",
            "col_avg": "Annual Avg",
            "lbl_total_rd244": "TOTAL (RD 244/2019)",
            "tip_gen": "Generation",
            "tip_dem": "Demand",
            "tip_solar_dem": "Solar Hours Demand",
            "tip_solar_cov": "Solar Hours Coverage",
            "tip_sc": "Self-Consumed",
            "tip_surplus": "Surplus",
            "tip_coverage": "Coverage",
            "tip_efficiency": "Utilization",
            "tip_eff_avg": "Daytime Avg (08:00-18:00)",
            "tip_eff_peak": "Solar Noon Peak (13:00)",
            "tip_rating": "Rating",
            "rating_excellent": "Excellent",
            "rating_good": "Good",
            "rating_moderate": "Moderate",
            "footer_text": f"Generated by <strong>Electricity Share Distributor (esd) v{version}</strong> • Spanish RD 244/2019",
            "months": {
                "01": "Jan",
                "02": "Feb",
                "03": "Mar",
                "04": "Apr",
                "05": "May",
                "06": "Jun",
                "07": "Jul",
                "08": "Aug",
                "09": "Sep",
                "10": "Oct",
                "11": "Nov",
                "12": "Dec",
            },
            "months_full": {
                "01": "January",
                "02": "February",
                "03": "March",
                "04": "April",
                "05": "May",
                "06": "June",
                "07": "July",
                "08": "August",
                "09": "September",
                "10": "October",
                "11": "November",
                "12": "December",
            },
        },
    }


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

    active_lang = "es" if (lang or get_language() or "en").lower().startswith("es") else "en"
    is_es = active_lang == "es"
    prec = get_precision() if precision is None else precision
    version = get_version()

    i18n_catalog = _build_html_i18n(version)
    ui = i18n_catalog[active_lang]

    tot = opt_result.total_summary
    matrix = opt_result.build_matrix()
    abbr_map = MONTH_ABBR_ES if is_es else MONTH_ABBR_EN

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
        bylaw_badge = (
            f'<span class="badge badge-bylaw" id="badge-bylaw" data-bylaw-active="true" '
            f'data-min="{bylaw_min_str}" data-max="{bylaw_max_str}">⚖️ {ui["bylaw_label"]}: {" | ".join(parts)}</span>'
        )

    # Compute 4-way comparative prevision directly from OptimizationResult
    h_prev = _calculate_hourly_prevision(opt_result)
    hourly_mode_badge_text = ui["mode_simulated"] if h_prev["is_simulated"] else ui["mode_modeled"]
    strat_badge_text = ui.get(f"strat_{opt_result.strategy.lower()}", opt_result.strategy.upper())

    svg_monthly_chart = _generate_svg_monthly_chart(opt_result, is_es)
    svg_eff_chart = _generate_svg_efficiency_chart(opt_result, is_es)

    # Stacked meter widths for Bar 3 (Fortnight) and Bar 4 (Hourly)
    monthly_rate = h_prev["monthly_sc_rate"]
    fortnight_rate = h_prev["fortnight_sc_rate"]
    hourly_rate = h_prev["hourly_sc_rate"]
    bar3_base_w = min(monthly_rate, fortnight_rate)
    bar3_fort_w = max(0.0, fortnight_rate - bar3_base_w)
    bar4_base_w = min(monthly_rate, hourly_rate)
    bar4_fort_w = max(0.0, min(fortnight_rate, hourly_rate) - bar4_base_w)
    bar4_hour_w = max(0.0, hourly_rate - bar4_base_w - bar4_fort_w)

    # Build matrix table rows
    matrix_rows: list[str] = []
    for cups in matrix.cups_list:
        use_val = matrix.cups_uses.get(cups, "")
        label_html = (
            f"<div class='cups-cell'><span class='cups-use'>{use_val or ui['default_service']}</span>"
            f"<span class='cups-id'>…{cups[-8:]}</span></div>"
        )
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

    # Build matrix table footer (TOTAL row)
    total_cells = [
        f"<td><span class='total-label' data-i18n='lbl_total_rd244'>{t('lbl_total_rd244', lang=active_lang)}</span></td>"
    ]
    for m in matrix.months:
        month_sum_fmt = matrix.format_month_sum(m, precision=prec)
        total_cells.append(f"<td class='text-right font-bold total-val'>{month_sum_fmt}</td>")
    annual_sum_fmt = matrix.format_annual_sum(precision=prec)
    total_cells.append(f"<td class='text-right font-bold total-val col-avg'>{annual_sum_fmt}</td>")
    matrix_footer = f"<tfoot><tr>{''.join(total_cells)}</tr></tfoot>"

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
    <title>{ui["doc_title"]}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-surface: #0f172a;
            --bg-card: rgba(15, 23, 42, 0.78);
            --bg-card-hover: rgba(30, 41, 59, 0.88);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(16, 185, 129, 0.35);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
            --accent-solar: #f59e0b;
            --accent-solar-glow: rgba(245, 158, 11, 0.25);
            --accent-demand: #06b6d4;
            --accent-demand-glow: rgba(6, 182, 212, 0.25);
            --accent-sc: #10b981;
            --accent-sc-glow: rgba(16, 185, 129, 0.25);
            --accent-purple: #a855f7;
            --accent-purple-glow: rgba(168, 85, 247, 0.25);
            --accent-danger: #ef4444;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 20px;
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
            padding: 2.25rem 1.75rem 4.5rem;
            min-height: 100vh;
            background-image:
                radial-gradient(circle at 10% 8%, rgba(245, 158, 11, 0.08) 0%, transparent 45%),
                radial-gradient(circle at 90% 12%, rgba(6, 182, 212, 0.08) 0%, transparent 45%),
                radial-gradient(circle at 50% 90%, rgba(16, 185, 129, 0.08) 0%, transparent 50%);
            background-attachment: fixed;
        }}

        .container {{
            max-width: 1200px;
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
            padding-bottom: 1.75rem;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .title-group h1 {{
            font-size: 1.95rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            background: linear-gradient(135deg, #ffffff 30%, var(--accent-solar) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.35rem;
        }}

        [data-theme="light"] .title-group h1 {{
            background: linear-gradient(135deg, #0f172a 35%, #d97706 100%);
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
            margin-top: 0.85rem;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.7rem;
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
            border-color: rgba(16, 185, 129, 0.35);
        }}

        .badge-strat {{
            background: rgba(6, 182, 212, 0.15);
            color: var(--accent-demand);
            border-color: rgba(6, 182, 212, 0.35);
        }}

        .badge-bylaw {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-solar);
            border-color: rgba(245, 158, 11, 0.35);
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
            padding: 0.4rem 0.8rem;
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
            box-shadow: 0 2px 10px rgba(16, 185, 129, 0.4);
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

        /* Four Executive KPI Cards (Production, Demand, Surplus, Autoconsumption) */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2.5rem;
        }}

        .kpi-card {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 1.45rem 1.65rem;
            position: relative;
            overflow: hidden;
            transition: all 0.25s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-3px);
            border-color: var(--text-dim);
            box-shadow: 0 16px 32px -8px rgba(0, 0, 0, 0.4), 0 0 1px 1px rgba(255, 255, 255, 0.08);
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
        }}

        .kpi-gen::before {{ background: linear-gradient(90deg, #f59e0b, #d97706); }}
        .kpi-dem::before {{ background: linear-gradient(90deg, #06b6d4, #0284c7); }}
        .kpi-surplus::before {{ background: linear-gradient(90deg, #a855f7, #6366f1); }}
        .kpi-sc::before {{ background: linear-gradient(90deg, #10b981, #059669); }}

        .kpi-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.65rem;
        }}

        .kpi-title {{
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}

        .kpi-value {{
            font-size: 2.15rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            margin-bottom: 0;
            line-height: 1.15;
            font-family: var(--font-sans);
        }}

        .kpi-meta {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.45rem;
            line-height: 1.4;
        }}

        .kpi-meta strong {{
            color: var(--text-main);
        }}

        .text-amber {{ color: var(--accent-solar); }}
        .text-cyan {{ color: var(--accent-demand); }}
        .text-purple {{ color: var(--accent-purple); }}
        .text-emerald {{ color: var(--accent-sc); }}
        .text-dim-blue {{ color: #94a3b8; }}

        /* Section Layouts */
        .section-box {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-xl);
            padding: 1.85rem;
            margin-bottom: 2.5rem;
            position: relative;
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
            font-size: 1.3rem;
            font-weight: 700;
            letter-spacing: -0.015em;
        }}

        .section-subtitle {{
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }}

        /* Dynamic Hourly Prevision Showcase Box */
        .section-hourly-prevision {{
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.08) 0%, rgba(16, 185, 129, 0.08) 100%), var(--bg-card);
            border: 1px solid rgba(6, 182, 212, 0.28);
            box-shadow: 0 14px 40px -10px rgba(6, 182, 212, 0.15);
            overflow: hidden;
        }}

        .section-hourly-prevision::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, #06b6d4, #10b981, #f59e0b);
        }}

        .title-with-pill {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.65rem;
        }}

        .badge-ted {{
            background: rgba(6, 182, 212, 0.15);
            color: var(--accent-demand);
            border-color: rgba(6, 182, 212, 0.35);
            font-weight: 700;
        }}

        .badge-mode {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-sc);
            border-color: rgba(16, 185, 129, 0.35);
            font-weight: 600;
        }}

        .hourly-kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(195px, 1fr));
            gap: 1.05rem;
            margin: 1.25rem 0 1.6rem;
        }}

        .hourly-kpi-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1.2rem 1.35rem;
            transition: all 0.25s ease;
        }}

        .hourly-kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--text-dim);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}

        .card-highlight {{
            border-color: rgba(245, 158, 11, 0.35);
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, var(--bg-surface) 100%);
        }}

        .hourly-kpi-label {{
            font-size: 0.775rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            display: block;
            margin-bottom: 0.35rem;
        }}

        .hourly-kpi-val {{
            font-size: 1.6rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 0.25rem;
        }}

        .hourly-kpi-sub {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .pill-uplift {{
            background: rgba(245, 158, 11, 0.22);
            color: var(--accent-solar);
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            font-weight: 800;
        }}

        /* Comparison Dual Meter Bar */
        .comparison-bar-container {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1.35rem 1.5rem;
            margin-bottom: 1.25rem;
        }}

        .comp-bar-row {{
            margin-bottom: 1.15rem;
        }}

        .comp-bar-row:last-child {{
            margin-bottom: 0;
        }}

        .comp-bar-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            margin-bottom: 0.45rem;
        }}

        .comp-bar-name {{
            font-weight: 600;
            color: var(--text-main);
        }}

        .comp-bar-val {{
            font-family: var(--font-mono);
        }}

        .comp-bar-track {{
            width: 100%;
            height: 14px;
            background: rgba(255, 255, 255, 0.06);
            border-radius: 9999px;
            display: flex;
            overflow: hidden;
        }}

        .fill-single {{
            height: 100%;
            background: linear-gradient(90deg, #475569, #64748b);
        }}

        [data-theme="light"] .fill-single {{
            background: linear-gradient(90deg, #94a3b8, #64748b);
        }}

        .fill-monthly {{
            height: 100%;
            background: linear-gradient(90deg, #059669, #10b981);
        }}

        .fill-fortnight {{
            height: 100%;
            background: linear-gradient(90deg, #0891b2, #06b6d4);
        }}

        .fill-uplift {{
            height: 100%;
            background: repeating-linear-gradient(
                45deg,
                #f59e0b,
                #f59e0b 8px,
                #d97706 8px,
                #d97706 16px
            );
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.5);
        }}

        .pill-dim {{
            background: rgba(148, 163, 184, 0.15);
            color: #94a3b8;
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.75rem;
        }}

        .pill-uplift-green {{
            background: rgba(16, 185, 129, 0.2);
            color: var(--accent-sc);
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            font-weight: 800;
            font-size: 0.75rem;
        }}

        .pill-fortnight {{
            background: rgba(6, 182, 212, 0.2);
            color: var(--accent-demand);
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            font-weight: 800;
            font-size: 0.75rem;
        }}

        .pill-cyan {{
            background: rgba(6, 182, 212, 0.2);
            color: var(--accent-demand);
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            font-weight: 800;
            font-size: 0.75rem;
        }}

        .regulatory-callout {{
            display: flex;
            align-items: flex-start;
            gap: 0.85rem;
            background: rgba(6, 182, 212, 0.06);
            border: 1px solid rgba(6, 182, 212, 0.2);
            border-radius: var(--radius-md);
            padding: 0.95rem 1.25rem;
            font-size: 0.825rem;
            color: var(--text-muted);
            line-height: 1.55;
        }}

        .callout-icon {{
            font-size: 1.2rem;
            line-height: 1;
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

        tfoot td {{
            padding: 0.75rem 0.65rem;
            font-weight: 700;
            border-top: 2px solid var(--border-subtle);
            border-bottom: none;
            background: rgba(255, 255, 255, 0.02);
        }}

        [data-theme="light"] tfoot td {{
            background: rgba(0, 0, 0, 0.02);
        }}

        .total-label {{
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 0.02em;
        }}

        [data-theme="light"] .total-label {{
            color: #0f172a;
        }}

        .total-val {{
            color: var(--accent-sc);
            font-family: var(--font-mono);
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
                <h1 data-i18n="title">{ui["title"]}</h1>
                <p data-i18n="subtitle">{ui["subtitle"]}</p>
                <div class="badges-wrap">
                    <span class="badge badge-rd" id="badge-rd" data-i18n="badge_rd">{ui["badge_rd"]}</span>
                    <span class="badge badge-strat" id="badge-strat" data-strat="{opt_result.strategy.lower()}">{strat_badge_text}</span>
                    <span class="badge" id="badge-cups">👥 {ingestion_summary.cups_count} {ui["cups_label"]}</span>
                    <span class="badge" id="badge-period">📅 {ingestion_summary.start_time[:10]} ➔ {ingestion_summary.end_time[:10]}</span>
                    {bylaw_badge}
                </div>
            </div>
            <div class="controls-group">
                <div class="lang-switch">
                    <button type="button" class="btn-lang {"active" if is_es else ""}" id="btn-lang-es" onclick="setLang('es')">ES</button>
                    <button type="button" class="btn-lang {"active" if not is_es else ""}" id="btn-lang-en" onclick="setLang('en')">EN</button>
                </div>
                <button class="btn" id="btn-theme" onclick="toggleTheme()" data-i18n="btn_theme">{ui["btn_theme"]}</button>
                <button class="btn" id="btn-print" onclick="window.print()" data-i18n="btn_print">{ui["btn_print"]}</button>
            </div>
        </header>

        <!-- Four Executive KPI Cards: Production, Demand, Surplus, and Autoconsumption -->
        <div class="kpi-grid">
            <!-- Box 1: Production -->
            <div class="kpi-card kpi-gen">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_gen_title">{ui["kpi_gen_title"]}</span>
                </div>
                <div class="kpi-value text-amber">{format_kwh(tot.total_generation_kwh)}</div>
                <div class="kpi-meta"><span data-i18n="kpi_solar_hours_gen">{ui["kpi_solar_hours_gen"]}</span>: <strong>{format_kwh(tot.solar_hours_generation_kwh if tot.solar_hours_generation_kwh > 0 else tot.total_generation_kwh)}</strong></div>
            </div>

            <!-- Box 2: Demand -->
            <div class="kpi-card kpi-dem">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_dem_title">{ui["kpi_dem_title"]}</span>
                </div>
                <div class="kpi-value text-cyan">{format_kwh(tot.total_consumption_kwh)}</div>
                <div class="kpi-meta"><span data-i18n="kpi_solar_hours_dem">{ui["kpi_solar_hours_dem"]}</span>: <strong>{format_kwh(tot.solar_hours_consumption_kwh)}</strong> ({tot.solar_hours_coverage_rate:.1f}% cov)</div>
            </div>

            <!-- Box 3: Surplus -->
            <div class="kpi-card kpi-surplus">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_surplus_title">{ui["kpi_surplus_title"]}</span>
                </div>
                <div class="kpi-value text-purple">{format_kwh(tot.total_surplus_kwh)}</div>
                <div class="kpi-meta"><span data-i18n="kpi_surplus_rate">{ui["kpi_surplus_rate"]}</span>: <strong>{tot.total_surplus_kwh / max(tot.total_generation_kwh, 1e-6) * 100:.1f}%</strong></div>
            </div>

            <!-- Box 4: Autoconsumption -->
            <div class="kpi-card kpi-sc">
                <div class="kpi-header">
                    <span class="kpi-title" data-i18n="kpi_sc_title">{ui["kpi_sc_title"]}</span>
                </div>
                <div class="kpi-value text-emerald">{format_kwh(tot.total_self_consumed_kwh)}</div>
                <div class="kpi-meta"><span data-i18n="kpi_sc_rate">{ui["kpi_sc_rate"]}</span>: <strong>{tot.self_consumption_rate:.1f}%</strong> • <span data-i18n="kpi_cov_rate">{ui["kpi_cov_rate"]}</span>: <strong>{tot.solar_coverage_rate:.1f}%</strong></div>
            </div>
        </div>

        <!-- Dynamic Prevision & 4-Way Comparative Showcase Box -->
        <div class="section-box section-hourly-prevision">
            <div class="section-header">
                <div>
                    <div class="title-with-pill">
                        <h2 class="section-title" data-i18n="prev_box_title">{ui["prev_box_title"]}</h2>
                        <span class="badge badge-ted" data-i18n="hourly_badge_ted">{ui["hourly_badge_ted"]}</span>
                        <span class="badge badge-mode" id="badge-hourly-mode" data-simulated="{"true" if h_prev["is_simulated"] else "false"}">{hourly_mode_badge_text}</span>
                    </div>
                    <p class="section-subtitle" data-i18n="prev_box_sub">{ui["prev_box_sub"]}</p>
                </div>
            </div>

            <div class="hourly-kpi-grid">
                <!-- Scenario 1: No Share (Single CUPS) -->
                <div class="hourly-kpi-card">
                    <span class="hourly-kpi-label" data-i18n="prev_card1_title">{ui["prev_card1_title"]}</span>
                    <div class="hourly-kpi-val text-dim-blue">{format_kwh(h_prev["single_sc_kwh"])}</div>
                    <span class="hourly-kpi-sub"><span data-i18n="prev_card1_sub">{ui["prev_card1_sub"]}</span>: <strong>{h_prev["single_sc_rate"]:.1f}%</strong> • <span class="pill-dim" data-i18n="prev_card1_tag">{ui["prev_card1_tag"]}</span></span>
                </div>

                <!-- Scenario 2: Monthly Share (RD 244/2019) -->
                <div class="hourly-kpi-card">
                    <span class="hourly-kpi-label" data-i18n="prev_card2_title">{ui["prev_card2_title"]}</span>
                    <div class="hourly-kpi-val text-emerald">{format_kwh(h_prev["monthly_sc_kwh"])}</div>
                    <span class="hourly-kpi-sub"><strong>{h_prev["monthly_sc_rate"]:.1f}%</strong> • <span class="pill-uplift-green">+{h_prev["gain_monthly_pct"]:.1f}% <span data-i18n="prev_card2_vs">{ui["prev_card2_vs"]}</span></span></span>
                </div>

                <!-- Scenario 3: Fortnight Share (24 Half-Month Periods) -->
                <div class="hourly-kpi-card">
                    <span class="hourly-kpi-label" data-i18n="prev_card_fortnight_title">{ui["prev_card_fortnight_title"]}</span>
                    <div class="hourly-kpi-val text-cyan">{format_kwh(h_prev["fortnight_sc_kwh"])}</div>
                    <span class="hourly-kpi-sub"><strong>{h_prev["fortnight_sc_rate"]:.1f}%</strong> • <span class="pill-fortnight">+{h_prev["gain_fortnight_pct"]:.1f}% <span data-i18n="prev_card_fortnight_vs">{ui["prev_card_fortnight_vs"]}</span></span></span>
                </div>

                <!-- Scenario 4: Hourly Share (Orden TED/1247/2021) -->
                <div class="hourly-kpi-card card-highlight">
                    <span class="hourly-kpi-label" data-i18n="prev_card3_title">{ui["prev_card3_title"]}</span>
                    <div class="hourly-kpi-val text-amber">{format_kwh(h_prev["hourly_sc_kwh"])}</div>
                    <span class="hourly-kpi-sub"><strong>{h_prev["hourly_sc_rate"]:.1f}%</strong> • <span class="pill-uplift">+{h_prev["gain_hourly_pct"]:.1f}% <span data-i18n="prev_card3_vs">{ui["prev_card3_vs"]}</span></span></span>
                </div>

                <!-- Total Collective Uplift -->
                <div class="hourly-kpi-card">
                    <span class="hourly-kpi-label" data-i18n="prev_card4_title">{ui["prev_card4_title"]}</span>
                    <div class="hourly-kpi-val text-cyan">+{h_prev["gain_total_kwh"]:,.1f} kWh</div>
                    <span class="hourly-kpi-sub"><span class="pill-cyan">+{h_prev["gain_total_pct"]:.1f}%</span> <span data-i18n="prev_card4_sub">{ui["prev_card4_sub"]}</span></span>
                </div>
            </div>

            <!-- Comparison 4-Way Meter Bar -->
            <div class="comparison-bar-container">
                <!-- Bar 1: Single CUPS -->
                <div class="comp-bar-row">
                    <div class="comp-bar-meta">
                        <span class="comp-bar-name" data-i18n="prev_comp_single">{ui["prev_comp_single"]}</span>
                        <span class="comp-bar-val">{format_kwh(h_prev["single_sc_kwh"])} ({h_prev["single_sc_rate"]:.1f}%)</span>
                    </div>
                    <div class="comp-bar-track">
                        <div class="comp-bar-fill fill-single" style="width: {h_prev["single_sc_rate"]:.1f}%;"></div>
                    </div>
                </div>

                <!-- Bar 2: Fixed Monthly Share (RD 244/2019) -->
                <div class="comp-bar-row">
                    <div class="comp-bar-meta">
                        <span class="comp-bar-name" data-i18n="prev_comp_monthly">{ui["prev_comp_monthly"]}</span>
                        <span class="comp-bar-val">{format_kwh(h_prev["monthly_sc_kwh"])} ({h_prev["monthly_sc_rate"]:.1f}%)</span>
                    </div>
                    <div class="comp-bar-track">
                        <div class="comp-bar-fill fill-monthly" style="width: {h_prev["monthly_sc_rate"]:.1f}%;"></div>
                    </div>
                </div>

                <!-- Bar 3: Fortnight Share (24 Half-Month Periods) -->
                <div class="comp-bar-row">
                    <div class="comp-bar-meta">
                        <span class="comp-bar-name text-cyan" data-i18n="prev_comp_fortnight">{ui["prev_comp_fortnight"]}</span>
                        <span class="comp-bar-val text-cyan">{format_kwh(h_prev["fortnight_sc_kwh"])} ({h_prev["fortnight_sc_rate"]:.1f}%)</span>
                    </div>
                    <div class="comp-bar-track">
                        <div class="comp-bar-fill fill-monthly" style="width: {bar3_base_w:.1f}%;"></div>
                        <div class="comp-bar-fill fill-fortnight" style="width: {bar3_fort_w:.1f}%;"></div>
                    </div>
                </div>

                <!-- Bar 4: Dynamic Hourly Share (Orden TED/1247/2021) -->
                <div class="comp-bar-row">
                    <div class="comp-bar-meta">
                        <span class="comp-bar-name font-bold text-amber" data-i18n="prev_comp_hourly">{ui["prev_comp_hourly"]}</span>
                        <span class="comp-bar-val font-bold text-emerald">{format_kwh(h_prev["hourly_sc_kwh"])} ({h_prev["hourly_sc_rate"]:.1f}%)</span>
                    </div>
                    <div class="comp-bar-track">
                        <div class="comp-bar-fill fill-monthly" style="width: {bar4_base_w:.1f}%;"></div>
                        <div class="comp-bar-fill fill-fortnight" style="width: {bar4_fort_w:.1f}%;"></div>
                        <div class="comp-bar-fill fill-uplift" style="width: {bar4_hour_w:.1f}%;"></div>
                    </div>
                </div>
            </div>

            <div class="regulatory-callout">
                <span class="callout-icon">💡</span>
                <p data-i18n="prev_note">{ui["prev_note"]}</p>
            </div>
        </div>

        <!-- Monthly Trajectory SVG Chart -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title" data-i18n="chart_traj_title">{ui["chart_traj_title"]}</h2>
                    <p class="section-subtitle" data-i18n="chart_traj_sub">{ui["chart_traj_sub"]}</p>
                </div>
            </div>
            <div class="chart-container">
                {svg_monthly_chart}
            </div>
        </div>

        <!-- Solar Efficiency Profile Section -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title" data-i18n="chart_eff_title">{ui["chart_eff_title"]}</h2>
                    <p class="section-subtitle" data-i18n="chart_eff_sub">{ui["chart_eff_sub"]}</p>
                </div>
                <div class="eff-legend">
                    <div class="eff-legend-item"><span class="legend-line line-peak"></span> <span data-i18n="tip_eff_peak">{ui["tip_eff_peak"]}</span></div>
                    <div class="eff-legend-item"><span class="legend-line line-avg"></span> <span data-i18n="tip_eff_avg">{ui["tip_eff_avg"]}</span></div>
                </div>
            </div>
            <div class="chart-container">
                {svg_eff_chart}
            </div>
            <div class="eff-cards-grid">
                <div class="eff-card">
                    <h4 data-i18n="eff_card1_title">{ui["eff_card1_title"]}</h4>
                    <p data-i18n="eff_card1_desc">{ui["eff_card1_desc"]}</p>
                </div>
                <div class="eff-card">
                    <h4 data-i18n="eff_card2_title">{ui["eff_card2_title"]}</h4>
                    <p data-i18n="eff_card2_desc">{ui["eff_card2_desc"]}</p>
                </div>
                <div class="eff-card">
                    <h4 data-i18n="eff_card3_title">{ui["eff_card3_title"]}</h4>
                    <p data-i18n="eff_card3_desc">{ui["eff_card3_desc"]}</p>
                </div>
                <div class="eff-card">
                    <h4 data-i18n="eff_card4_title">{ui["eff_card4_title"]}</h4>
                    <p data-i18n="eff_card4_desc">{ui["eff_card4_desc"]}</p>
                </div>
            </div>
        </div>

        <!-- Share Matrix Heatmap Table -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title" data-i18n="matrix_title">{ui["matrix_title"]}</h2>
                    <p class="section-subtitle" data-i18n="matrix_sub">{ui["matrix_sub"]}</p>
                </div>
                <input type="text" id="searchInput" class="search-box" data-i18n-placeholder="search_placeholder" placeholder="{ui["search_placeholder"]}" oninput="filterTable()">
            </div>
            <div class="table-wrap">
                <table id="matrixTable">
                    <thead>
                        <tr>
                            <th data-i18n="col_cups">{ui["col_cups"]}</th>
                            {month_headers}
                            <th class="text-right col-avg" data-i18n="col_avg">{ui["col_avg"]}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(matrix_rows)}
                    </tbody>
                    {matrix_footer}
                </table>
            </div>
        </div>

        <footer style="margin-top: 3rem; text-align: center; color: var(--text-dim); font-size: 0.8rem;">
            <span data-i18n="footer_text">{ui["footer_text"]}</span>
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

        const I18N = {json.dumps(i18n_catalog, ensure_ascii=False)};

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
                cupsBadge.textContent = `👥 ${{cupsCount}} ${{I18N[lang].cups_label}}`;
            }}

            // Update hourly simulation badge
            const hourlyModeBadge = document.getElementById('badge-hourly-mode');
            if (hourlyModeBadge) {{
                const isSim = hourlyModeBadge.getAttribute('data-simulated') === 'true';
                hourlyModeBadge.textContent = isSim ? I18N[lang].mode_simulated : I18N[lang].mode_modeled;
            }}

            // Update strategy badge if present
            const stratBadge = document.getElementById('badge-strat');
            if (stratBadge) {{
                const stratKey = stratBadge.getAttribute('data-strat');
                const translatedStrat = I18N[lang][`strat_${{stratKey}}`];
                if (translatedStrat) stratBadge.textContent = translatedStrat;
            }}

            // Update bylaw badge if present
            const bylawBadge = document.getElementById('badge-bylaw');
            if (bylawBadge && bylawBadge.getAttribute('data-bylaw-active') === 'true') {{
                const minVal = bylawBadge.getAttribute('data-min');
                const maxVal = bylawBadge.getAttribute('data-max');
                const parts = [];
                if (minVal) parts.push(`Min: ${{minVal}}%`);
                if (maxVal) parts.push(`Max: ${{maxVal}}%`);
                bylawBadge.textContent = `⚖️ ${{I18N[lang].bylaw_label}}: ${{parts.join(' | ')}}`;
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
                ${{data.solar_dem ? `<div>☀️ ${{t.tip_solar_dem}}: <strong>${{data.solar_dem}}</strong> <span style="font-size:0.75rem; color:var(--text-muted);">(${{data.solar_cov}} ${{t.tip_coverage.toLowerCase()}})</span></div>` : ''}}
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


def _build_comparison_html_i18n(version: str) -> dict[str, dict[str, str]]:
    """Build synchronized bilingual EN/ES string dictionary for comparison HTML reports."""
    return {
        "en": {
            "page_title": "Electricity Share Distributor — Multi-Year Comparison",
            "header_badge": f"MULTI-YEAR COMPARISON v{version}",
            "header_subtitle": "Community Electricity Consumption · Year-over-Year Analytics",
            "btn_lang": "ES / EN",
            "btn_theme": "Theme",
            "btn_print": "Print",
            "kpi_years": "Compared Years",
            "kpi_comparable": "Comparable Period",
            "kpi_diff": "Comparable Variation",
            "kpi_top_saver": "Top Saving CUPS",
            "sec_community_chart": "Community Monthly Trajectory",
            "sec_monthly_table": "Month-by-Month Breakdown",
            "sec_cups_table": "Supply Points (CUPS) Shift",
            "sec_cups_charts": "Per-CUPS Monthly Charts",
            "search_placeholder": "Filter CUPS or community use...",
            "col_month": "Month",
            "col_diff": "Diff (kWh)",
            "col_var": "Var (%)",
            "col_trend": "Trend",
            "col_cups": "CUPS",
            "col_use": "Use",
            "badge_inc": "[Inc]",
            "inc_legend": "* [Inc] Incomplete or missing calendar months are excluded from comparable totals.",
            "no_results": "No CUPS match the active filter.",
            "footer_brand": f"Electricity Share Distributor · Multi-Year Comparison v{version}",
        },
        "es": {
            "page_title": "Electricity Share Distributor — Comparativa Interanual",
            "header_badge": f"COMPARATIVA INTERANUAL v{version}",
            "header_subtitle": "Consumo Eléctrico Comunitario · Análisis Interanual",
            "btn_lang": "ES / EN",
            "btn_theme": "Tema",
            "btn_print": "Imprimir",
            "kpi_years": "Años Comparados",
            "kpi_comparable": "Periodo Comparable",
            "kpi_diff": "Variación Comparable",
            "kpi_top_saver": "CUPS con Mayor Ahorro",
            "sec_community_chart": "Evolución Mensual Comunitaria",
            "sec_monthly_table": "Desglose Mes a Mes",
            "sec_cups_table": "Variación por Punto de Suministro (CUPS)",
            "sec_cups_charts": "Gráficos Mensuales por CUPS",
            "search_placeholder": "Filtrar CUPS o uso comunitario...",
            "col_month": "Mes",
            "col_diff": "Dif. (kWh)",
            "col_var": "Var (%)",
            "col_trend": "Tendencia",
            "col_cups": "CUPS",
            "col_use": "Uso",
            "badge_inc": "[Inc]",
            "inc_legend": "* [Inc] Los meses incompletos o sin datos se excluyen del total comparable.",
            "no_results": "Ningún CUPS coincide con el filtro.",
            "footer_brand": f"Electricity Share Distributor · Informe Interanual v{version}",
        },
    }


def generate_comparison_html_report(
    comparison: ComparisonSummary,
    lang: str | None = None,
) -> str:
    """Generate a standalone offline interactive HTML report for multi-year consumption comparison."""
    active_lang = (lang or get_language()).lower()
    if active_lang not in ("en", "es"):
        active_lang = "en"

    version = get_version()
    i18n_data = _build_comparison_html_i18n(version)
    ui = i18n_data[active_lang]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    years = list(comparison.years)
    years_str = " ➔ ".join(map(str, years))
    earliest_y = years[0]
    latest_y = years[-1]

    comp_months = list(comparison.comparable_months)
    if comp_months:
        comp_start_en = get_month_name(min(comp_months), lang="en", short=True)
        comp_end_en = get_month_name(max(comp_months), lang="en", short=True)
        comp_start_es = get_month_name(min(comp_months), lang="es", short=True)
        comp_end_es = get_month_name(max(comp_months), lang="es", short=True)
        comp_range_en = f"{comp_start_en} - {comp_end_en}"
        comp_range_es = f"{comp_start_es} - {comp_end_es}"
    else:
        comp_range_en = "No overlapping complete months"
        comp_range_es = "Sin meses completos comparables"

    comp_range_cur = comp_range_en if active_lang == "en" else comp_range_es

    diff_tot = comparison.total_diff_kwh
    pct_tot = comparison.total_pct_change
    if diff_tot is not None and pct_tot is not None:
        if diff_tot < 0:
            diff_class = "delta-saving"
            diff_val_html = f"-{abs(diff_tot):,.2f} kWh"
            pct_sub_html = f"▼ {pct_tot:.2f}%"
        elif diff_tot > 0:
            diff_class = "delta-increase"
            diff_val_html = f"+{diff_tot:,.2f} kWh"
            pct_sub_html = f"▲ +{pct_tot:.2f}%"
        else:
            diff_class = "delta-neutral"
            diff_val_html = "0.00 kWh"
            pct_sub_html = "— 0.00%"
    else:
        diff_class = "delta-neutral"
        diff_val_html = "—"
        pct_sub_html = "—"

    top_saver = comparison.top_saving_cups
    if top_saver is not None:
        saver_title = escape(top_saver.cups)
        saver_sub = escape(top_saver.use or f"-{abs(top_saver.diff_kwh):,.2f} kWh")
        if top_saver.use:
            saver_sub = f"{escape(top_saver.use)} · -{abs(top_saver.diff_kwh):,.2f} kWh"
    else:
        saver_title = "—"
        saver_sub = "—"

    year_headers = "".join(f'<th class="num">{y} (kWh)</th>' for y in years)

    monthly_rows: list[str] = []
    for m in comparison.monthly_comparisons:
        m_en = escape(get_month_name(m.month, lang="en"))
        m_es = escape(get_month_name(m.month, lang="es"))
        m_cur = m_en if active_lang == "en" else m_es

        year_cells: list[str] = []
        for y in years:
            status = m.year_status.get(y, "complete")
            val = m.yearly_kwh.get(y)
            if status == "no_data" or val is None:
                year_cells.append(
                    f'<td class="num muted"><span class="badge-inc">{escape(ui["badge_inc"])}</span></td>'
                )
            elif status == "incomplete":
                year_cells.append(
                    f'<td class="num">{val:,.2f}* <span class="badge-inc">{escape(ui["badge_inc"])}</span></td>'
                )
            else:
                year_cells.append(f'<td class="num">{val:,.2f}</td>')

        if m.diff_kwh is not None:
            if m.diff_kwh < 0:
                m_diff_cls = "delta-saving"
                m_diff_str = f"-{abs(m.diff_kwh):,.2f}"
            elif m.diff_kwh > 0:
                m_diff_cls = "delta-increase"
                m_diff_str = f"+{m.diff_kwh:,.2f}"
            else:
                m_diff_cls = "delta-neutral"
                m_diff_str = "0.00"
        else:
            m_diff_cls = "delta-neutral"
            m_diff_str = "—"

        if m.pct_change is not None:
            if m.pct_change < 0:
                m_var_cls = "delta-saving"
                m_var_str = f"▼ {m.pct_change:.1f}%"
                tr_en = t("compare_trend_reduced", lang="en")
                tr_es = t("compare_trend_reduced", lang="es")
            elif m.pct_change > 0:
                m_var_cls = "delta-increase"
                m_var_str = f"▲ +{m.pct_change:.1f}%"
                tr_en = t("compare_trend_increased", lang="en")
                tr_es = t("compare_trend_increased", lang="es")
            else:
                m_var_cls = "delta-neutral"
                m_var_str = "— 0.0%"
                tr_en = t("compare_trend_equal", lang="en")
                tr_es = t("compare_trend_equal", lang="es")
            tr_cur = tr_en if active_lang == "en" else tr_es
            trend_html = (
                f'<span class="dyn-text {m_var_cls}" '
                f'data-en="{escape(tr_en)}" data-es="{escape(tr_es)}">{escape(tr_cur)}</span>'
            )
        else:
            m_var_cls = "delta-neutral"
            m_var_str = "—"
            trend_html = (
                f'<span class="badge-inc">{escape(ui["badge_inc"])}</span>'
                if not m.is_complete
                else '<span class="muted">—</span>'
            )

        monthly_rows.append(
            "<tr>"
            f'<td><strong class="dyn-text" data-en="{m_en}" data-es="{m_es}">{m_cur}</strong></td>'
            f"{''.join(year_cells)}"
            f'<td class="num {m_diff_cls}">{m_diff_str}</td>'
            f'<td class="num {m_var_cls}">{m_var_str}</td>'
            f'<td class="center">{trend_html}</td>'
            "</tr>"
        )

    if comp_months:
        tot_en = f"Total ({comp_range_en})" if len(comp_months) < 12 else "Total"
        tot_es = f"Total ({comp_range_es})" if len(comp_months) < 12 else "Total"
        tot_cur = tot_en if active_lang == "en" else tot_es
        tot_year_cells = "".join(
            f'<td class="num">{comparison.comparable_annual_totals[y]:,.2f}</td>' for y in years
        )
        t_diff_str = diff_val_html.replace(" kWh", "")
        t_pct_str = pct_sub_html
        tot_trend = (
            t(
                "compare_trend_reduced"
                if (diff_tot or 0.0) < 0
                else (
                    "compare_trend_increased" if (diff_tot or 0.0) > 0 else "compare_trend_equal"
                ),
                lang=active_lang,
            )
            if diff_tot is not None
            else "—"
        )
        tfoot_html = (
            "<tfoot><tr>"
            f'<td><strong class="dyn-text" data-en="{escape(tot_en)}" data-es="{escape(tot_es)}">{escape(tot_cur)}</strong></td>'
            f"{tot_year_cells}"
            f'<td class="num {diff_class}">{t_diff_str}</td>'
            f'<td class="num {diff_class}">{t_pct_str}</td>'
            f'<td class="center {diff_class}">{escape(tot_trend)}</td>'
            "</tr></tfoot>"
        )
    else:
        raw_cells = "".join(
            f'<td class="num">{comparison.annual_totals[y]:,.2f}</td>' for y in years
        )
        tfoot_html = (
            f"<tfoot><tr><td><strong>Total</strong></td>{raw_cells}"
            '<td class="num muted">—</td><td class="num muted">—</td><td class="center muted">—</td></tr></tfoot>'
        )

    cups_rows: list[str] = []
    for idx, c in enumerate(comparison.cups_comparisons, start=1):
        base_val = c.yearly_kwh.get(earliest_y, 0.0)
        target_val = c.yearly_kwh.get(latest_y, 0.0)
        if c.diff_kwh < 0:
            c_cls = "delta-saving"
            c_diff = f"-{abs(c.diff_kwh):,.2f}"
        elif c.diff_kwh > 0:
            c_cls = "delta-increase"
            c_diff = f"+{c.diff_kwh:,.2f}"
        else:
            c_cls = "delta-neutral"
            c_diff = "0.00"

        if c.pct_change is not None:
            if c.pct_change < 0:
                c_var = f"▼ {c.pct_change:.1f}%"
            elif c.pct_change > 0:
                c_var = f"▲ +{c.pct_change:.1f}%"
            else:
                c_var = "— 0.0%"
        else:
            c_var = "N/A"

        search_key = escape(f"{c.cups} {c.use}".lower())
        cups_rows.append(
            f'<tr data-search="{search_key}">'
            f'<td class="num muted">{idx}</td>'
            f'<td><code class="cups-code">{escape(c.cups)}</code></td>'
            f'<td class="use-cell">{escape(c.use or "—")}</td>'
            f'<td class="num">{base_val:,.2f}</td>'
            f'<td class="num">{target_val:,.2f}</td>'
            f'<td class="num {c_cls}">{c_diff}</td>'
            f'<td class="num {c_cls}">{c_var}</td>'
            "</tr>"
        )

    community_svg = render_community_bar_svg(comparison, lang=active_lang, id_prefix="community")
    cups_svgs = render_cups_bar_svgs(comparison, lang=active_lang)
    cups_cards_html = "".join(
        f'<article class="chart-card"><div class="svg-wrap">{svg_doc}</div></article>'
        for _cups_id, svg_doc in cups_svgs
    )

    ann_summary_bits = " · ".join(f"{y}: {comparison.annual_totals[y]:,.0f} kWh" for y in years)

    css_styles = """
        :root {
            --bg-base: #0b0f19;
            --bg-card: rgba(17, 24, 39, 0.82);
            --bg-subtle: rgba(30, 41, 59, 0.58);
            --border-subtle: rgba(148, 163, 184, 0.16);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-solar: #f59e0b;
            --accent-demand: #38bdf8;
            --accent-sc: #10b981;
            --accent-danger: #f43f5e;
            --accent-warn: #f59e0b;
        }
        [data-theme="light"] {
            --bg-base: #f8fafc;
            --bg-card: rgba(255, 255, 255, 0.94);
            --bg-subtle: #f1f5f9;
            --border-subtle: rgba(15, 23, 42, 0.12);
            --text-primary: #0f172a;
            --text-secondary: #475569;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-base);
            color: var(--text-primary);
            line-height: 1.5;
            padding: 28px 20px 48px;
        }
        .container { max-width: 1200px; margin: 0 auto; display: grid; gap: 22px; }
        .topbar {
            display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
            gap: 14px; padding: 20px 24px; border-radius: 16px;
            background: var(--bg-card); border: 1px solid var(--border-subtle);
        }
        .badge {
            display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
            color: #064e3b; background: #10b981; padding: 4px 10px; border-radius: 999px;
            margin-bottom: 8px;
        }
        .title-main { font-size: 1.45rem; font-weight: 700; }
        .subtitle { color: var(--text-secondary); font-size: 0.92rem; }
        .controls { display: flex; flex-wrap: wrap; gap: 8px; }
        .btn {
            cursor: pointer; border: 1px solid var(--border-subtle); background: var(--bg-subtle);
            color: var(--text-primary); padding: 8px 13px; border-radius: 10px;
            font-size: 0.85rem; font-weight: 600;
        }
        .btn:hover { border-color: var(--accent-demand); }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
        .kpi-card {
            background: var(--bg-card); border: 1px solid var(--border-subtle);
            border-radius: 14px; padding: 18px 20px; position: relative; overflow: hidden;
        }
        .kpi-card::before {
            content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, var(--accent-sc), var(--accent-demand));
        }
        .kpi-label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-secondary); }
        .kpi-value { font-size: 1.45rem; font-weight: 700; margin: 6px 0 4px; font-family: 'JetBrains Mono', ui-monospace, monospace; }
        .kpi-sub { font-size: 0.82rem; color: var(--text-secondary); }
        .panel {
            background: var(--bg-card); border: 1px solid var(--border-subtle);
            border-radius: 16px; padding: 20px 22px; overflow: hidden;
        }
        .panel-head {
            display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
            gap: 12px; margin-bottom: 16px;
        }
        .panel-title { font-size: 1.05rem; font-weight: 700; }
        .search-box {
            padding: 8px 12px; border-radius: 10px; border: 1px solid var(--border-subtle);
            background: var(--bg-subtle); color: var(--text-primary); min-width: 240px;
            font-size: 0.88rem;
        }
        .table-wrap { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
        th, td { padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); text-align: left; }
        th { color: var(--text-secondary); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }
        tfoot td { font-weight: 700; border-top: 2px solid var(--border-subtle); background: var(--bg-subtle); }
        .num { text-align: right; font-family: 'JetBrains Mono', ui-monospace, monospace; white-space: nowrap; }
        .center { text-align: center; }
        .muted { color: var(--text-secondary); }
        .delta-saving { color: var(--accent-sc); font-weight: 600; }
        .delta-increase { color: var(--accent-danger); font-weight: 600; }
        .delta-neutral { color: var(--text-secondary); }
        .badge-inc {
            display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 2px 6px;
            border-radius: 6px; background: rgba(245, 158, 11, 0.16); color: var(--accent-warn);
        }
        .cups-code { font-family: 'JetBrains Mono', ui-monospace, monospace; font-weight: 600; }
        .use-cell { color: var(--accent-demand); }
        .svg-wrap { width: 100%; overflow: hidden; border-radius: 12px; }
        .svg-wrap svg { width: 100%; height: auto; display: block; }
        .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 18px; }
        .chart-card {
            background: var(--bg-subtle); border: 1px solid var(--border-subtle);
            border-radius: 12px; padding: 10px;
        }
        .legend-note { margin-top: 12px; font-size: 0.82rem; color: var(--text-secondary); }
        .footer {
            display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px;
            color: var(--text-secondary); font-size: 0.82rem; padding: 6px 4px;
        }
        @media (max-width: 640px) {
            .charts-grid { grid-template-columns: 1fr; }
        }
        @media print {
            body { background: #ffffff; color: #0f172a; padding: 0; }
            .no-print { display: none !important; }
            .panel, .kpi-card, .chart-card { break-inside: avoid; border-color: #cbd5e1; background: #ffffff; }
        }
    """

    i18n_json = json.dumps(i18n_data, ensure_ascii=False)
    active_lang_json = json.dumps(active_lang)
    script_body = f"""
        const I18N = {i18n_json};
        let activeLang = {active_lang_json};

        function setLang(lang) {{
            activeLang = I18N[lang] ? lang : 'en';
            const dict = I18N[activeLang];
            document.documentElement.lang = activeLang;
            document.title = dict.page_title;
            document.querySelectorAll('[data-i18n]').forEach(el => {{
                const key = el.getAttribute('data-i18n');
                if (key && dict[key]) el.textContent = dict[key];
            }});
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {{
                const key = el.getAttribute('data-i18n-placeholder');
                if (key && dict[key]) el.setAttribute('placeholder', dict[key]);
            }});
            document.querySelectorAll('.dyn-text').forEach(el => {{
                const txt = el.getAttribute('data-' + activeLang);
                if (txt) el.textContent = txt;
            }});
        }}

        function toggleLang() {{
            setLang(activeLang === 'en' ? 'es' : 'en');
        }}

        function toggleTheme() {{
            const current = document.documentElement.getAttribute('data-theme');
            document.documentElement.setAttribute('data-theme', current === 'light' ? 'dark' : 'light');
        }}

        const searchInput = document.getElementById('cups-search');
        const noResultsEl = document.getElementById('no-results');
        if (searchInput) {{
            searchInput.addEventListener('input', () => {{
                const query = searchInput.value.trim().toLowerCase();
                const rows = document.querySelectorAll('#cups-table tbody tr');
                let visible = 0;
                rows.forEach(row => {{
                    const haystack = row.getAttribute('data-search') || '';
                    const match = !query || haystack.includes(query);
                    row.style.display = match ? '' : 'none';
                    if (match) visible += 1;
                }});
                if (noResultsEl) {{
                    noResultsEl.style.display = visible === 0 ? 'block' : 'none';
                }}
            }});
        }}

        setLang(activeLang);
    """

    return f"""<!DOCTYPE html>
<html lang="{active_lang}" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(ui["page_title"])}</title>
    <style>{css_styles}</style>
</head>
<body>
    <main class="container">
        <header class="topbar">
            <div>
                <span class="badge" data-i18n="header_badge">{escape(ui["header_badge"])}</span>
                <h1 class="title-main">⚡ {escape(years_str)}</h1>
                <p class="subtitle" data-i18n="header_subtitle">{escape(ui["header_subtitle"])}</p>
            </div>
            <div class="controls no-print">
                <button class="btn" type="button" onclick="toggleLang()" data-i18n="btn_lang">{escape(ui["btn_lang"])}</button>
                <button class="btn" type="button" onclick="toggleTheme()" data-i18n="btn_theme">{escape(ui["btn_theme"])}</button>
                <button class="btn" type="button" onclick="window.print()" data-i18n="btn_print">{escape(ui["btn_print"])}</button>
            </div>
        </header>

        <section class="kpi-grid">
            <article class="kpi-card">
                <div class="kpi-label" data-i18n="kpi_years">{escape(ui["kpi_years"])}</div>
                <div class="kpi-value">{escape(years_str)}</div>
                <div class="kpi-sub">{escape(ann_summary_bits)}</div>
            </article>
            <article class="kpi-card">
                <div class="kpi-label" data-i18n="kpi_comparable">{escape(ui["kpi_comparable"])}</div>
                <div class="kpi-value">{len(comp_months)} / 12</div>
                <div class="kpi-sub dyn-text" data-en="{escape(comp_range_en)}" data-es="{escape(comp_range_es)}">{escape(comp_range_cur)}</div>
            </article>
            <article class="kpi-card">
                <div class="kpi-label" data-i18n="kpi_diff">{escape(ui["kpi_diff"])}</div>
                <div class="kpi-value {diff_class}">{escape(diff_val_html)}</div>
                <div class="kpi-sub {diff_class}">{escape(pct_sub_html)}</div>
            </article>
            <article class="kpi-card">
                <div class="kpi-label" data-i18n="kpi_top_saver">{escape(ui["kpi_top_saver"])}</div>
                <div class="kpi-value" style="font-size: 1.05rem;">{saver_title}</div>
                <div class="kpi-sub delta-saving">{saver_sub}</div>
            </article>
        </section>

        <section class="panel">
            <div class="panel-head">
                <h2 class="panel-title" data-i18n="sec_community_chart">{escape(ui["sec_community_chart"])}</h2>
            </div>
            <div class="svg-wrap">{community_svg}</div>
        </section>

        <section class="panel">
            <div class="panel-head">
                <h2 class="panel-title" data-i18n="sec_monthly_table">{escape(ui["sec_monthly_table"])}</h2>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th data-i18n="col_month">{escape(ui["col_month"])}</th>
                            {year_headers}
                            <th class="num" data-i18n="col_diff">{escape(ui["col_diff"])}</th>
                            <th class="num" data-i18n="col_var">{escape(ui["col_var"])}</th>
                            <th class="center" data-i18n="col_trend">{escape(ui["col_trend"])}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(monthly_rows)}
                    </tbody>
                    {tfoot_html}
                </table>
            </div>
            <p class="legend-note" data-i18n="inc_legend">{escape(ui["inc_legend"])}</p>
        </section>

        <section class="panel">
            <div class="panel-head">
                <h2 class="panel-title" data-i18n="sec_cups_table">{escape(ui["sec_cups_table"])}</h2>
                <input id="cups-search" class="search-box no-print" type="search"
                       data-i18n-placeholder="search_placeholder"
                       placeholder="{escape(ui["search_placeholder"])}">
            </div>
            <div class="table-wrap">
                <table id="cups-table">
                    <thead>
                        <tr>
                            <th class="num">#</th>
                            <th data-i18n="col_cups">{escape(ui["col_cups"])}</th>
                            <th data-i18n="col_use">{escape(ui["col_use"])}</th>
                            <th class="num">{earliest_y} (kWh)</th>
                            <th class="num">{latest_y} (kWh)</th>
                            <th class="num" data-i18n="col_diff">{escape(ui["col_diff"])}</th>
                            <th class="num" data-i18n="col_var">{escape(ui["col_var"])}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(cups_rows)}
                    </tbody>
                </table>
                <p id="no-results" class="legend-note" style="display:none;" data-i18n="no_results">{escape(ui["no_results"])}</p>
            </div>
        </section>

        <section class="panel">
            <div class="panel-head">
                <h2 class="panel-title" data-i18n="sec_cups_charts">{escape(ui["sec_cups_charts"])}</h2>
            </div>
            <div class="charts-grid">{cups_cards_html}</div>
        </section>

        <footer class="footer">
            <span data-i18n="footer_brand">{escape(ui["footer_brand"])}</span>
            <span>{escape(generated_at)}</span>
        </footer>
    </main>
    <script>{script_body}</script>
</body>
</html>"""
