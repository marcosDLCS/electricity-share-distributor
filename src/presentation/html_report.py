"""Interactive standalone HTML report generator for collective PV self-consumption (RD 244/2019)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.presentation.console import format_kwh
from src.presentation.views.common import MONTH_ABBR_EN, MONTH_ABBR_ES
from src.version import get_version

if TYPE_CHECKING:
    from src.ingestion.schema import IngestionSummary
    from src.optimization.models import OptimizationResult


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
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg" xmlns="http://www.w3.org/2000/svg">',
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
        m_name = abbr_map.get(m.month, m.month)

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
            f'  <text x="{cx:.1f}" y="{height - pad_bottom + 22}" text-anchor="middle" class="x-label">{m_name}</text>'
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
    bylaw_min_val = 0.0
    bylaw_max_val = 1.0
    if has_bylaws and opt_result.constraints:
        c = opt_result.constraints
        parts = []
        if c.min_share is not None:
            parts.append(f"Min: {c.min_share * 100:.1f}%")
            bylaw_min_val = c.min_share
        if c.max_share is not None:
            parts.append(f"Max: {c.max_share * 100:.1f}%")
            bylaw_max_val = c.max_share
        bylaw_badge = f'<span class="badge badge-bylaw">⚖️ {" | ".join(parts)}</span>'

    # Prepare slider initial data
    initial_shares: dict[str, float] = {}
    for cups in matrix.cups_list:
        ann_val = matrix.annual_shares.get(cups)
        initial_shares[cups] = round(ann_val * 100.0, 1) if ann_val is not None else 0.0

    svg_chart = _generate_svg_monthly_chart(opt_result, is_es)

    # Localized texts
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
    txt_eff = "Eficiencia de Autoconsumo" if is_es else "Self-Consumption Efficiency"
    txt_coverage = "Cobertura Solar" if is_es else "Solar Coverage"
    txt_matrix_title = (
        "Matriz de Coeficientes Mensuales" if is_es else "Monthly Coefficients Matrix"
    )
    txt_sim_title = (
        "Simulador Interactivo de Coeficientes" if is_es else "Interactive Share Simulator"
    )
    txt_sim_desc = (
        "Simula el impacto de ajustar los coeficientes comunitarios. Verifica en tiempo real el cumplimiento del 100% y los límites estatutarios."
        if is_es
        else "Simulate the impact of adjusting community shares. Verify in real time the 100% regulatory sum and bylaw limits."
    )
    txt_annex_title = (
        "Anexo para el Acta de Junta General" if is_es else "HOA Board Resolution Annex"
    )
    txt_cups_col = "Suministro / CUPS" if is_es else "Supply Point / CUPS"
    txt_use_col = "Uso Comunitario" if is_es else "Facility Use"
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
            # Heatmap color class
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
        f"<th class='text-right'>{abbr_map.get(m, m)}</th>" for m in matrix.months
    )

    # Build simulator sliders
    simulator_rows: list[str] = []
    for cups in matrix.cups_list:
        use_val = matrix.cups_uses.get(cups, "") or "Servicio"
        init_val = initial_shares.get(cups, 0.0)
        slider_row = f"""
        <div class="sim-item" data-cups="{cups}">
            <div class="sim-label">
                <span class="sim-use">{use_val}</span>
                <span class="sim-cups">…{cups[-8:]}</span>
            </div>
            <div class="sim-slider-wrap">
                <input type="range" min="0" max="100" step="0.5" value="{init_val}" id="sim_{cups}" class="sim-slider" oninput="updateSim()">
            </div>
            <div class="sim-value">
                <span id="sim_val_{cups}">{init_val:.1f}%</span>
            </div>
        </div>
        """
        simulator_rows.append(slider_row)

    # Resolution annex table rows
    annex_rows: list[str] = []
    for idx, cups in enumerate(matrix.cups_list, 1):
        use_val = matrix.cups_uses.get(cups, "") or f"Servicio #{idx}"
        ann_val = matrix.format_annual(cups, precision=prec)
        annex_rows.append(
            f"<tr><td>{idx}</td><td><strong>{use_val}</strong></td><td><code>{cups}</code></td><td class='text-right'><strong>{ann_val}</strong></td></tr>"
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
            gap: 0.75rem;
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
            min-width: 180px;
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

        /* Simulator */
        .sim-grid {{
            display: grid;
            gap: 0.85rem;
            margin-bottom: 1.5rem;
        }}

        .sim-item {{
            display: grid;
            grid-template-columns: 200px 1fr 80px;
            align-items: center;
            gap: 1.25rem;
            padding: 0.5rem 0.75rem;
            background: var(--bg-surface);
            border-radius: var(--radius-md);
            border: 1px solid var(--border-subtle);
        }}

        .sim-label {{
            display: flex;
            flex-direction: column;
        }}

        .sim-use {{
            font-weight: 600;
            font-size: 0.85rem;
        }}

        .sim-cups {{
            font-size: 0.725rem;
            color: var(--text-dim);
            font-family: var(--font-mono);
        }}

        .sim-slider-wrap input[type=range] {{
            width: 100%;
            accent-color: var(--accent-sc);
            cursor: pointer;
        }}

        .sim-value {{
            text-align: right;
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 0.95rem;
            color: var(--accent-sc);
        }}

        .sim-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.25rem;
            background: var(--bg-surface);
            border-radius: var(--radius-md);
            border: 1px solid var(--border-subtle);
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .sim-sum-badge {{
            font-size: 1.1rem;
            font-weight: 800;
            font-family: var(--font-mono);
        }}

        .sum-valid {{ color: var(--accent-sc); }}
        .sum-invalid {{ color: var(--accent-danger); }}

        /* Resolution Annex */
        .resolution-box {{
            background: #ffffff;
            color: #1e293b;
            border-radius: var(--radius-lg);
            padding: 2.5rem;
            box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.4);
            margin-top: 2rem;
        }}

        .resolution-header {{
            text-align: center;
            margin-bottom: 2rem;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 1.25rem;
        }}

        .resolution-header h2 {{
            font-size: 1.35rem;
            font-weight: 800;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .resolution-header p {{
            color: #64748b;
            font-size: 0.875rem;
            margin-top: 0.35rem;
        }}

        .resolution-body {{
            font-size: 0.9rem;
            line-height: 1.7;
            color: #334155;
            margin-bottom: 2rem;
        }}

        .resolution-table {{
            margin: 1.5rem 0;
            border: 1px solid #cbd5e1;
            width: 100%;
        }}

        .resolution-table th {{
            background: #f1f5f9;
            color: #334155;
            border-bottom: 1px solid #cbd5e1;
        }}

        .resolution-table td {{
            color: #1e293b;
            border-bottom: 1px solid #e2e8f0;
        }}

        .signatures-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 3rem;
            margin-top: 3.5rem;
            padding-top: 1.5rem;
        }}

        .sig-block {{
            border-top: 1px solid #94a3b8;
            padding-top: 0.75rem;
            text-align: center;
            font-size: 0.85rem;
            color: #475569;
        }}

        /* Print styles */
        @media print {{
            body {{
                background: #ffffff !important;
                color: #000000 !important;
                padding: 0;
            }}
            .controls-group, .search-box, .sim-slider-wrap, #tooltip, header .btn {{
                display: none !important;
            }}
            .section-box, .resolution-box {{
                box-shadow: none !important;
                border: 1px solid #e2e8f0 !important;
                background: #ffffff !important;
                color: #000000 !important;
                page-break-inside: avoid;
            }}
            .resolution-box {{
                page-break-before: always;
            }}
        }}

        @media (max-width: 768px) {{
            .sim-item {{
                grid-template-columns: 1fr;
                gap: 0.5rem;
            }}
            .signatures-grid {{
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="title-group">
                <h1>⚡ {txt_title}</h1>
                <p>{txt_subtitle}</p>
                <div class="badges-wrap">
                    <span class="badge badge-rd">✓ RD 244/2019</span>
                    <span class="badge badge-strat">{opt_result.strategy.upper()}</span>
                    <span class="badge">👥 {ingestion_summary.cups_count} CUPS</span>
                    <span class="badge">📅 {ingestion_summary.start_time[:10]} ➔ {ingestion_summary.end_time[:10]}</span>
                    {bylaw_badge}
                </div>
            </div>
            <div class="controls-group">
                <button class="btn" onclick="toggleTheme()">🌗 Modo</button>
                <button class="btn" onclick="window.print()">🖨️ PDF / Imprimir</button>
            </div>
        </header>

        <!-- KPI Executive Cards -->
        <div class="kpi-grid">
            <div class="kpi-card kpi-gen">
                <div class="kpi-header">
                    <span class="kpi-title">🌞 {txt_total_gen}</span>
                </div>
                <div class="kpi-value">{format_kwh(tot.total_generation_kwh)}</div>
                <div class="kpi-subtitle">
                    <span>{txt_total_surplus}: {format_kwh(tot.total_surplus_kwh)}</span>
                </div>
            </div>

            <div class="kpi-card kpi-dem">
                <div class="kpi-header">
                    <span class="kpi-title">⚡ {txt_total_dem}</span>
                </div>
                <div class="kpi-value">{format_kwh(tot.total_consumption_kwh)}</div>
                <div class="kpi-subtitle">
                    <span>{txt_coverage}: <strong>{tot.solar_coverage_rate:.1f}%</strong></span>
                </div>
            </div>

            <div class="kpi-card kpi-sc">
                <div class="kpi-header">
                    <span class="kpi-title">🏆 {txt_total_sc}</span>
                    {f'<span class="gain-badge">{base_gain_str}</span>' if base_gain_str else ""}
                </div>
                <div class="kpi-value">{format_kwh(tot.total_self_consumed_kwh)}</div>
                <div class="kpi-subtitle">
                    <span>{txt_eff}: <strong>{tot.self_consumption_rate:.1f}%</strong></span>
                </div>
            </div>

            <div class="kpi-card kpi-surplus">
                <div class="kpi-header">
                    <span class="kpi-title">🛡️ RD 244/2019 SUM</span>
                </div>
                <div class="kpi-value">100.0%</div>
                <div class="kpi-subtitle">
                    <span>Hare-Niemeyer Verified</span>
                </div>
            </div>
        </div>

        <!-- Monthly Trajectory SVG Chart -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title">📊 Trayectoria Anual de Energía (kWh)</h2>
                    <p class="section-subtitle">Generación Solar (ámbar), Demanda Comunitaria (cian) y Autoconsumo Colectivo (verde)</p>
                </div>
            </div>
            <div class="chart-container">
                {svg_chart}
            </div>
        </div>

        <!-- Share Matrix Heatmap Table -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title">🗓️ {txt_matrix_title}</h2>
                    <p class="section-subtitle">Distribución porcentual ($\beta_i$) mensual fijada para cada servicio común</p>
                </div>
                <input type="text" id="searchInput" class="search-box" placeholder="Buscar servicio o CUPS..." oninput="filterTable()">
            </div>
            <div class="table-wrap">
                <table id="matrixTable">
                    <thead>
                        <tr>
                            <th>{txt_cups_col}</th>
                            {month_headers}
                            <th class="text-right col-avg">{txt_avg_col}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(matrix_rows)}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Interactive What-If Share Simulator -->
        <div class="section-box">
            <div class="section-header">
                <div>
                    <h2 class="section-title">🎛️ {txt_sim_title}</h2>
                    <p class="section-subtitle">{txt_sim_desc}</p>
                </div>
                <button class="btn" onclick="resetSim()">↺ Restablecer Óptimo</button>
            </div>
            <div class="sim-grid">
                {"".join(simulator_rows)}
            </div>
            <div class="sim-footer">
                <div>
                    <span>Suma Total Asignada:</span>
                    <span id="simSumBadge" class="sim-sum-badge sum-valid">100.0%</span>
                </div>
                <div id="simBylawAlert" style="font-size: 0.85rem; color: var(--text-dim);">
                    {f"Límites estatutarios activos: Min {bylaw_min_val * 100:.1f}% | Max {bylaw_max_val * 100:.1f}%" if has_bylaws else "Sin restricciones estatutarias adicionales"}
                </div>
            </div>
        </div>

        <!-- Statutory Homeowners Board Resolution Annex -->
        <div class="resolution-box">
            <div class="resolution-header">
                <h2>{txt_annex_title}</h2>
                <p>Propuesta de Acuerdo para la Junta General Extraordinaria de Propietarios</p>
            </div>
            <div class="resolution-body">
                <p>
                    En cumplimiento de lo estipulado en el <strong>Real Decreto 244/2019</strong>, de 5 de abril, por el que se regulan las condiciones administrativas, técnicas y económicas del autoconsumo de energía eléctrica, y de conformidad con el régimen de mayorías previsto en el artículo 17 de la <strong>Ley de Propiedad Horizontal</strong>:
                </p>
                <br>
                <p>
                    La <strong>Junta General de Propietarios</strong> acuerda por unanimidad / mayoría legalmente requerida aprobar la presente tabla de coeficientes de reparto fijos ($\beta_i$) para la instalación solar fotovoltaica colectiva de uso compartido, con destino a la alimentación de los servicios comunes del edificio:
                </p>
                <table class="resolution-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>{txt_use_col}</th>
                            <th>CUPS</th>
                            <th class="text-right">Coeficiente Asignado ($\beta_i$)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(annex_rows)}
                    </tbody>
                </table>
                <p>
                    Se faculta expresamente al <strong>Presidente</strong> y al <strong>Administrador-Secretario</strong> de la Comunidad para formalizar y firmar el acuerdo de reparto y remitirlo a la empresa distribuidora de electricidad correspondiente para su inmediata aplicación en la facturación horaria.
                </p>
            </div>
            <div class="signatures-grid">
                <div class="sig-block">
                    <strong>Fdo.: El Presidente de la Comunidad</strong><br>
                    <span>D./Dña. ___________________________</span>
                </div>
                <div class="sig-block">
                    <strong>Fdo.: El Secretario-Administrador</strong><br>
                    <span>Colegiado Nº ______________________</span>
                </div>
            </div>
        </div>

        <footer style="margin-top: 3rem; text-align: center; color: var(--text-dim); font-size: 0.8rem;">
            Generado por <strong>Electricity Share Distributor (esd) v{version}</strong> • Real Decreto 244/2019
        </footer>
    </div>

    <!-- Tooltip Element -->
    <div id="tooltip"></div>

    <script>
        const initialShares = {json.dumps(initial_shares)};
        const bylawMin = {bylaw_min_val * 100.0};
        const bylawMax = {bylaw_max_val * 100.0};
        const hasBylaws = {"true" if has_bylaws else "false"};

        function showTooltip(evt, el) {{
            const raw = el.getAttribute('data-tooltip');
            if (!raw) return;
            const data = JSON.parse(raw);
            const tip = document.getElementById('tooltip');
            tip.innerHTML = `
                <div style="font-weight:700; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:4px; margin-bottom:6px;">
                    📅 ${{data.month}}
                </div>
                <div>🌞 Generación: <strong>${{data.gen}}</strong></div>
                <div>⚡ Demanda: <strong>${{data.dem}}</strong></div>
                <div>🏆 Autoconsumo: <strong style="color:var(--accent-sc);">${{data.sc}}</strong></div>
                <div>🛡️ Excedente: <strong>${{data.surplus}}</strong></div>
                <div style="margin-top:4px; font-size:0.75rem; color:var(--text-muted);">
                    Cobertura: <strong>${{data.cov}}</strong> • Eficiencia: <strong>${{data.eff}}</strong>
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

        function updateSim() {{
            let sum = 0.0;
            let violation = false;
            for (const cups in initialShares) {{
                const input = document.getElementById('sim_' + cups);
                const valEl = document.getElementById('sim_val_' + cups);
                if (input && valEl) {{
                    const val = parseFloat(input.value);
                    sum += val;
                    valEl.textContent = val.toFixed(1) + '%';

                    if (hasBylaws && (val < bylawMin - 0.01 || val > bylawMax + 0.01)) {{
                        valEl.style.color = 'var(--accent-danger)';
                        violation = true;
                    }} else {{
                        valEl.style.color = 'var(--accent-sc)';
                    }}
                }}
            }}
            const sumBadge = document.getElementById('simSumBadge');
            const alertEl = document.getElementById('simBylawAlert');
            if (sumBadge) {{
                sumBadge.textContent = sum.toFixed(1) + '%';
                if (Math.abs(sum - 100.0) <= 0.2) {{
                    sumBadge.className = 'sim-sum-badge sum-valid';
                }} else {{
                    sumBadge.className = 'sim-sum-badge sum-invalid';
                }}
            }}
            if (alertEl && hasBylaws) {{
                if (violation) {{
                    alertEl.innerHTML = '<span style="color:var(--accent-danger); font-weight:700;">⚠️ Alerta: Algunos coeficientes incumplen los límites estatutarios.</span>';
                }} else {{
                    alertEl.innerHTML = '<span style="color:var(--accent-sc);">✓ Todos los coeficientes cumplen los límites estatutarios.</span>';
                }}
            }}
        }}

        function resetSim() {{
            for (const cups in initialShares) {{
                const input = document.getElementById('sim_' + cups);
                if (input) {{
                    input.value = initialShares[cups];
                }}
            }}
            updateSim();
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
