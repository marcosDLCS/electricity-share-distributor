"""Zero-dependency SVG chart generator for multi-year consumption comparisons."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final
from xml.sax.saxutils import escape

from src.i18n import get_month_name, t

if TYPE_CHECKING:
    from src.analytics.models import ComparisonSummary

YEAR_PALETTE: Final[tuple[str, ...]] = (
    "#2563EB",
    "#10B981",
    "#F59E0B",
    "#8B5CF6",
    "#EC4899",
    "#06B6D4",
)


def _format_kwh_compact(val: float) -> str:
    """Format energy values with thousands separators and 1 decimal place."""
    return f"{val:,.1f} kWh"


def _render_grouped_bar_svg(
    title: str,
    subtitle: str,
    month_labels: list[str],
    years: list[int],
    series_by_year: dict[int, list[float]],
    legend_labels: dict[int, str],
    x_axis_label: str,
    y_axis_label: str,
) -> str:
    """Render a clean, self-contained responsive grouped bar chart as an SVG document."""
    width = 960
    height = 440
    pad_left = 84
    pad_right = 28
    pad_top = 86
    pad_bottom = 66
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    all_vals = [val for vals in series_by_year.values() for val in vals]
    max_val = max([*all_vals, 1.0])
    y_max = max_val * 1.15

    n_months = len(month_labels)
    n_years = max(1, len(years))
    slot_w = chart_w / max(1, n_months)
    group_w = slot_w * 0.78
    bar_w = group_w / n_years

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img">',
        '<rect width="100%" height="100%" rx="12" fill="#FFFFFF" stroke="#E2E8F0"/>',
        "<style>"
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}"
        ".title{font-size:17px;font-weight:700;fill:#0F172A;}"
        ".subtitle{font-size:12px;fill:#475569;}"
        ".axis-title{font-size:12px;font-weight:600;fill:#334155;}"
        ".tick{font-size:11px;fill:#64748B;}"
        ".legend-text{font-size:11px;fill:#1E293B;font-weight:500;}"
        "</style>",
        f'<text x="{pad_left}" y="34" class="title">{escape(title)}</text>',
        f'<text x="{pad_left}" y="54" class="subtitle">{escape(subtitle)}</text>',
    ]

    # 5-tier horizontal gridlines and Y-axis tick labels
    tiers = 4
    for tier in range(tiers + 1):
        val = (y_max / tiers) * tier
        y_pos = pad_top + chart_h - (chart_h * (tier / tiers))
        stroke = "#CBD5E1" if tier == 0 else "#E2E8F0"
        dash = "" if tier == 0 else ' stroke-dasharray="4 4"'
        parts.append(
            f'<line x1="{pad_left}" y1="{y_pos:.1f}" x2="{width - pad_right}" '
            f'y2="{y_pos:.1f}" stroke="{stroke}" stroke-width="1"{dash}/>'
        )
        tick_label = f"{val:,.0f}" if val < 10000 else f"{val / 1000:,.1f}k"
        parts.append(
            f'<text x="{pad_left - 10}" y="{y_pos + 4:.1f}" text-anchor="end" '
            f'class="tick">{escape(tick_label)}</text>'
        )

    # Top-right compact legend box
    legend_x = width - pad_right - 220
    legend_y = 14
    legend_h = 14 + len(years) * 18
    parts.append(
        f'<rect x="{legend_x}" y="{legend_y}" width="220" height="{legend_h}" '
        'rx="6" fill="#F8FAFC" stroke="#CBD5E1"/>'
    )
    for idx, yr in enumerate(years):
        color = YEAR_PALETTE[idx % len(YEAR_PALETTE)]
        ly = legend_y + 18 + idx * 18
        parts.append(
            f'<rect x="{legend_x + 10}" y="{ly - 9}" width="10" height="10" rx="2" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 26}" y="{ly}" class="legend-text">'
            f"{escape(legend_labels.get(yr, str(yr)))}</text>"
        )

    # Grouped bars per month
    base_y = pad_top + chart_h
    for m_idx, m_label in enumerate(month_labels):
        cx = pad_left + m_idx * slot_w + slot_w / 2.0
        for y_idx, yr in enumerate(years):
            color = YEAR_PALETTE[y_idx % len(YEAR_PALETTE)]
            val = float(series_by_year.get(yr, [0.0] * n_months)[m_idx])
            bar_h = max(0.0, (val / y_max) * chart_h)
            x_pos = cx - (group_w / 2.0) + y_idx * bar_w + 1.0
            y_pos = base_y - bar_h
            actual_w = max(2.0, bar_w - 2.0)
            tooltip = escape(f"{yr} · {m_label}: {val:,.1f} kWh")
            parts.append(
                f'<rect x="{x_pos:.1f}" y="{y_pos:.1f}" width="{actual_w:.1f}" '
                f'height="{bar_h:.1f}" rx="3" fill="{color}" fill-opacity="0.9">'
                f"<title>{tooltip}</title></rect>"
            )

        parts.append(
            f'<text x="{cx:.1f}" y="{base_y + 20}" text-anchor="middle" '
            f'class="tick">{escape(m_label)}</text>'
        )

    # Axis titles
    parts.append(
        f'<text x="{pad_left + chart_w / 2:.1f}" y="{height - 16}" '
        f'text-anchor="middle" class="axis-title">{escape(x_axis_label)}</text>'
    )
    parts.append(
        f'<text x="22" y="{pad_top + chart_h / 2:.1f}" text-anchor="middle" '
        f'transform="rotate(-90 22 {pad_top + chart_h / 2:.1f})" '
        f'class="axis-title">{escape(y_axis_label)}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def generate_community_bar_chart(
    comparison: ComparisonSummary,
    output_dir: Path,
    lang: str = "en",
) -> Path:
    """Generate and save a grouped SVG bar chart comparing community monthly consumption."""
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    years_slug = "_".join(map(str, comparison.years))
    chart_path = charts_dir / f"community_monthly_{years_slug}.svg"

    months = list(range(1, 13))
    month_labels = [get_month_name(m, lang=lang, short=True) for m in months]
    month_map = {m.month: m for m in comparison.monthly_comparisons}

    series_by_year: dict[int, list[float]] = {}
    legend_labels: dict[int, str] = {}
    for year in comparison.years:
        series_by_year[year] = [
            float((month_map[m].yearly_kwh.get(year) if m in month_map else None) or 0.0)
            for m in months
        ]
        ann_total = comparison.annual_totals.get(year, 0.0)
        legend_labels[year] = (
            f"{year} ({t('chart_legend_total', lang=lang, total=_format_kwh_compact(ann_total))})"
        )

    years_str = " ➔ ".join(map(str, comparison.years))
    svg_text = _render_grouped_bar_svg(
        title=t("chart_community_title", lang=lang),
        subtitle=t("chart_subtitle", lang=lang, years=years_str),
        month_labels=month_labels,
        years=comparison.years,
        series_by_year=series_by_year,
        legend_labels=legend_labels,
        x_axis_label=t("chart_month_axis", lang=lang),
        y_axis_label=t("chart_kwh_axis", lang=lang),
    )
    chart_path.write_text(svg_text, encoding="utf-8")
    return chart_path


def generate_cups_bar_charts(
    comparison: ComparisonSummary,
    output_dir: Path,
    lang: str = "en",
) -> list[Path]:
    """Generate grouped SVG bar charts for each supply point (CUPS) across compared years."""
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    years_slug = "_".join(map(str, comparison.years))
    years_str = " ➔ ".join(map(str, comparison.years))

    months = list(range(1, 13))
    month_labels = [get_month_name(m, lang=lang, short=True) for m in months]

    generated_paths: list[Path] = []
    for cups_id, years_data in comparison.cups_monthly_data.items():
        chart_path = charts_dir / f"cups_{cups_id}_{years_slug}.svg"
        series_by_year: dict[int, list[float]] = {}
        legend_labels: dict[int, str] = {}

        for year in comparison.years:
            monthly_dict = years_data.get(year, {})
            vals = [float(monthly_dict.get(m, 0.0)) for m in months]
            series_by_year[year] = vals
            legend_labels[year] = (
                f"{year} ({t('chart_legend_total', lang=lang, total=_format_kwh_compact(sum(vals)))})"
            )

        use_label = comparison.cups_uses.get(cups_id, "")
        cups_display = f"{cups_id} ({use_label})" if use_label else cups_id
        svg_text = _render_grouped_bar_svg(
            title=t("chart_cups_title", lang=lang, cups=cups_display),
            subtitle=t("chart_subtitle", lang=lang, years=years_str),
            month_labels=month_labels,
            years=comparison.years,
            series_by_year=series_by_year,
            legend_labels=legend_labels,
            x_axis_label=t("chart_month_axis", lang=lang),
            y_axis_label=t("chart_kwh_axis", lang=lang),
        )
        chart_path.write_text(svg_text, encoding="utf-8")
        generated_paths.append(chart_path)

    return generated_paths


def generate_all_comparison_charts(
    comparison: ComparisonSummary,
    output_dir: Path,
    lang: str = "en",
) -> list[Path]:
    """Generate community and per-CUPS SVG comparison bar charts in output_dir/charts/."""
    community_chart = generate_community_bar_chart(comparison, output_dir, lang=lang)
    cups_charts = generate_cups_bar_charts(comparison, output_dir, lang=lang)
    return [community_chart, *cups_charts]
