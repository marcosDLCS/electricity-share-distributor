"""Interactive standalone HTML report façade for collective PV self-consumption and comparisons."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from typing import TYPE_CHECKING

from src.config import get_language
from src.i18n import get_month_name, t
from src.presentation.charts import render_community_bar_svg, render_cups_bar_svgs
from src.presentation.story_data import (
    calculate_hourly_prevision as _calculate_hourly_prevision,
)
from src.presentation.story_data import (
    calculate_monthly_efficiency as _calculate_monthly_efficiency,
)
from src.presentation.story_data import (
    parse_month_int as _parse_month_int,
)
from src.presentation.story_report import (
    build_story_i18n as _build_html_i18n,
)
from src.presentation.story_report import (
    generate_story_html_report,
)
from src.version import get_version

if TYPE_CHECKING:
    from src.analytics.models import ComparisonSummary
    from src.ingestion.schema import AlignedDataset, IngestionSummary
    from src.optimization.models import OptimizationResult
    from src.presentation.story_data import StoryReportContext

__all__ = [
    "_build_html_i18n",
    "_calculate_hourly_prevision",
    "_calculate_monthly_efficiency",
    "_parse_month_int",
    "generate_comparison_html_report",
    "generate_interactive_html_report",
]


def generate_interactive_html_report(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    lang: str | None = None,
    precision: int | None = None,
    story_context: StoryReportContext | None = None,
    aligned_dataset: AlignedDataset | None = None,
) -> str:
    """Generate self-contained, offline interactive storytelling HTML report for neighbours."""
    return generate_story_html_report(
        opt_result=opt_result,
        ingestion_summary=ingestion_summary,
        lang=lang,
        precision=precision,
        story_context=story_context,
        aligned_dataset=aligned_dataset,
    )


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
