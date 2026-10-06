"""Multi-format report exporters (Markdown, CSV, JSON) for optimization results."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.ingestion.schema import IngestionSummary
from src.optimization.models import OptimizationResult
from src.version import get_version

MONTH_ABBR_EN: dict[str, str] = {
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
}
MONTH_ABBR_ES: dict[str, str] = {
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
}


def get_export_timestamp() -> str:
    """Generate standardized export timestamp string: YYYYMMDD_HHMMSS."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def export_coefficients_csv(
    opt_result: OptimizationResult,
    output_dir: Path | str,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export monthly distribution coefficients and metrics per CUPS as CSV."""
    from src.config import get_precision

    prec = get_precision() if precision is None else precision
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp or get_export_timestamp()
    file_path = out_dir / f"{ts}_esd_coefficients.csv"

    rows: list[dict[str, object]] = []
    for m in opt_result.monthly_results:
        for c in m.cups_metrics:
            rows.append(
                {
                    "month": c.month,
                    "cups": c.cups,
                    "beta": f"{c.beta:.4f}",
                    "share_pct": f"{c.beta * 100:.{prec}f}",
                    "consumption_kwh": round(c.consumption_kwh, 2),
                    "generation_allocated_kwh": round(c.generation_allocated_kwh, 2),
                    "self_consumed_kwh": round(c.self_consumed_kwh, 2),
                    "surplus_kwh": round(c.surplus_kwh, 2),
                    "grid_demand_kwh": round(c.grid_demand_kwh, 2),
                    "self_consumption_rate_pct": round(c.self_consumption_rate, 2),
                    "solar_coverage_rate_pct": round(c.solar_coverage_rate, 2),
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(file_path, index=False, sep=";")
    return file_path


def export_coefficients_matrix_csv(
    opt_result: OptimizationResult,
    output_dir: Path | str,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export consolidated monthly distribution shares matrix (CUPS in Y, Months in X) as CSV."""
    from src.config import get_precision

    prec = get_precision() if precision is None else precision
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp or get_export_timestamp()
    file_path = out_dir / f"{ts}_esd_coefficients_matrix.csv"

    matrix = opt_result.build_matrix()
    rows: list[dict[str, object]] = []

    for cups in matrix.cups_list:
        row_dict: dict[str, object] = {"cups": cups}
        for m in matrix.months:
            row_dict[m] = matrix.format_cell(cups, m, precision=prec)
        row_dict["annual_average"] = matrix.format_annual(cups, precision=prec)
        rows.append(row_dict)

    # Total row
    total_dict: dict[str, object] = {"cups": "TOTAL"}
    for m in matrix.months:
        total_dict[m] = matrix.format_month_sum(m, precision=prec)
    total_dict["annual_average"] = matrix.format_annual_sum(precision=prec)
    rows.append(total_dict)

    df = pd.DataFrame(rows)
    df.to_csv(file_path, index=False, sep=";")
    return file_path


def export_results_json(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    output_dir: Path | str,
    timestamp: str | None = None,
) -> Path:
    """Export full optimization results and metadata as JSON."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp or get_export_timestamp()
    file_path = out_dir / f"{ts}_esd_results.json"

    data = {
        "generator": "electricity-share-distributor",
        "version": get_version(),
        "exported_at": datetime.now().isoformat(),
        "ingestion_metadata": asdict(ingestion_summary),
        "primary_strategy": opt_result.strategy,
        "total_summary": asdict(opt_result.total_summary),
        "monthly_results": [asdict(m) for m in opt_result.monthly_results],
        "baselines": {k: asdict(v.total_summary) for k, v in opt_result.baselines.items()},
    }

    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return file_path


def export_summary_markdown(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    output_dir: Path | str,
    lang: str | None = None,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export complete human-readable optimization and coefficient report in Markdown."""
    from src.config import get_language, get_precision
    from src.i18n import t

    target_lang = lang or get_language()
    prec = get_precision() if precision is None else precision
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp or get_export_timestamp()
    file_path = out_dir / f"{ts}_esd_optimization_summary.md"

    tot = opt_result.total_summary

    lines = [
        t("md_report_title", lang=target_lang, version=get_version()),
        "",
        t(
            "md_meta_generated_at",
            lang=target_lang,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
        t("md_meta_regulatory", lang=target_lang),
        t("md_meta_strategy", lang=target_lang, strategy=opt_result.strategy),
        "",
        "---",
        "",
        t("md_sec_community_overview", lang=target_lang),
        "",
        t("md_lbl_participating_cups", lang=target_lang, count=ingestion_summary.cups_count),
        t(
            "md_lbl_date_range",
            lang=target_lang,
            start=ingestion_summary.start_time,
            end=ingestion_summary.end_time,
        ),
        t("md_lbl_total_hours", lang=target_lang, hours=ingestion_summary.total_hours),
        t("md_lbl_total_gen", lang=target_lang, gen=tot.total_generation_kwh),
        t("md_lbl_total_dem", lang=target_lang, dem=tot.total_consumption_kwh),
        t(
            "md_lbl_total_sc",
            lang=target_lang,
            sc=tot.total_self_consumed_kwh,
            rate=tot.self_consumption_rate,
        ),
        t("md_lbl_total_surplus", lang=target_lang, surplus=tot.total_surplus_kwh),
        t("md_lbl_solar_coverage", lang=target_lang, cov=tot.solar_coverage_rate),
        "",
        "---",
        "",
        t("md_sec_trajectory", lang=target_lang),
        "",
        t("md_traj_header", lang=target_lang),
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    abbr_map = MONTH_ABBR_ES if target_lang == "es" else MONTH_ABBR_EN
    for m in opt_result.monthly_results:
        m_label = abbr_map.get(m.month, m.month)
        if m.has_data:
            lines.append(
                f"| **{m_label}** | {m.total_generation_kwh:,.1f} | {m.total_consumption_kwh:,.1f} | "
                f"{m.total_self_consumed_kwh:,.1f} | {m.total_surplus_kwh:,.1f} | {m.total_grid_demand_kwh:,.1f} | "
                f"{m.self_consumption_rate:.1f}% | {m.solar_coverage_rate:.1f}% |"
            )
        else:
            lines.append(f"| **{m_label}** | — | — | — | — | — | — | — |")

    lines.extend(
        [
            f"| **{t('lbl_total', lang=target_lang)}** | **{tot.total_generation_kwh:,.1f}** | **{tot.total_consumption_kwh:,.1f}** | "
            f"**{tot.total_self_consumed_kwh:,.1f}** | **{tot.total_surplus_kwh:,.1f}** | **{tot.total_grid_demand_kwh:,.1f}** | "
            f"**{tot.self_consumption_rate:.1f}%** | **{tot.solar_coverage_rate:.1f}%** |",
            "",
            "---",
            "",
        ]
    )

    # Strategy comparison section if baselines exist
    if opt_result.baselines:
        lines.extend(
            [
                t("md_sec_strategy_comp", lang=target_lang),
                "",
                t("md_comp_header", lang=target_lang),
                "| :--- | :---: | :---: | :---: | :---: |",
            ]
        )
        eq_sc = (
            opt_result.baselines["equal"].total_summary.total_self_consumed_kwh
            if "equal" in opt_result.baselines
            else tot.total_self_consumed_kwh
        )

        # Optimal
        gain = tot.total_self_consumed_kwh - eq_sc
        gain_str = f"+{gain:,.1f} kWh" if gain > 0 else "0.0 kWh"
        lines.append(
            f"| {t('md_lbl_optimal_strat', lang=target_lang)} | **{tot.total_self_consumed_kwh:,.1f}** | "
            f"{tot.total_surplus_kwh:,.1f} | **{tot.self_consumption_rate:.1f}%** | **{gain_str}** |"
        )

        for b_name, b_res in opt_result.baselines.items():
            b_tot = b_res.total_summary
            b_gain = b_tot.total_self_consumed_kwh - eq_sc
            b_gain_str = f"+{b_gain:,.1f} kWh" if b_gain > 0 else f"{b_gain:,.1f} kWh"
            lines.append(
                f"| `{b_name}` | {b_tot.total_self_consumed_kwh:,.1f} | "
                f"{b_tot.total_surplus_kwh:,.1f} | {b_tot.self_consumption_rate:.1f}% | {b_gain_str} |"
            )
        lines.extend(["", "---", ""])

    # Consolidated Regulatory Coefficients Matrix (RD 244/2019)
    matrix = opt_result.build_matrix()
    if matrix.cups_list and matrix.months:
        lines.append(t("md_sec_coeff_matrix", lang=target_lang))
        lines.append("")
        lines.append(t("md_desc_coeff_matrix", lang=target_lang))
        lines.append("")

        month_headers = [abbr_map.get(m, m) for m in matrix.months]
        headers = ["CUPS", *month_headers, t("col_annual_avg", lang=target_lang)]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| :--- | " + " | ".join([":---:"] * (len(headers) - 1)) + " |")

        for cups in matrix.cups_list:
            row_cells = [f"`{cups}`"]
            for m in matrix.months:
                row_cells.append(matrix.format_cell(cups, m, precision=prec))
            row_cells.append(f"**{matrix.format_annual(cups, precision=prec)}**")
            lines.append("| " + " | ".join(row_cells) + " |")

        total_cells = [f"**{t('lbl_total_rd244', lang=target_lang)}**"]
        for m in matrix.months:
            total_cells.append(f"**{matrix.format_month_sum(m, precision=prec)}**")
        total_cells.append(f"**{matrix.format_annual_sum(precision=prec)}**")
        lines.append("| " + " | ".join(total_cells) + " |")
        lines.extend(["", "---", ""])

    # Monthly breakdown tables
    lines.append(t("md_sec_monthly_coeffs", lang=target_lang))
    lines.append("")

    for m in opt_result.monthly_results:
        if not m.has_data:
            continue
        m_label = abbr_map.get(m.month, m.month)
        lines.append(
            t(
                "md_month_header",
                lang=target_lang,
                month=m_label,
                gen=m.total_generation_kwh,
            )
        )
        lines.append("")
        lines.append(t("md_coeff_header", lang=target_lang))
        lines.append(
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        )
        for c in m.cups_metrics:
            lines.append(
                f"| `{c.cups}` | **{c.beta:.4f}** | {c.beta * 100:.{prec}f}% | "
                f"{c.consumption_kwh:,.1f} | {c.generation_allocated_kwh:,.1f} | "
                f"{c.self_consumed_kwh:,.1f} | {c.surplus_kwh:,.1f} | {c.grid_demand_kwh:,.1f} |"
            )
        lines.append("")

    lines.extend(["---", ""])

    # Community Optimization Insights & Generation Dynamics
    lines.extend(
        [
            t("md_sec_insights", lang=target_lang),
            "",
            t("md_insight_diurnal_title", lang=target_lang),
            "",
            t("md_insight_diurnal_desc", lang=target_lang),
            "",
            t("md_insight_zero_protection_title", lang=target_lang),
            "",
            t("md_insight_zero_protection_desc", lang=target_lang),
            "",
            t("md_insight_seasonal_title", lang=target_lang),
            "",
            t("md_insight_seasonal_desc", lang=target_lang),
            "",
        ]
    )

    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return file_path


def export_all(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    output_dir: Path | str,
    formats: str = "all",
    lang: str | None = None,
    precision: int | None = None,
) -> list[Path]:
    """Execute exports according to the specified format flag.

    Supported formats: 'all', 'table', 'csv', 'json', 'markdown'.
    """
    fmt = formats.lower().strip()
    if fmt == "table":
        return []

    timestamp = get_export_timestamp()
    exported: list[Path] = []

    if fmt in ("all", "csv"):
        exported.append(
            export_coefficients_csv(
                opt_result, output_dir, precision=precision, timestamp=timestamp
            )
        )
        exported.append(
            export_coefficients_matrix_csv(
                opt_result, output_dir, precision=precision, timestamp=timestamp
            )
        )

    if fmt in ("all", "json"):
        exported.append(
            export_results_json(
                opt_result,
                ingestion_summary,
                output_dir,
                timestamp=timestamp,
            )
        )

    if fmt in ("all", "markdown", "md"):
        exported.append(
            export_summary_markdown(
                opt_result,
                ingestion_summary,
                output_dir,
                lang=lang,
                precision=precision,
                timestamp=timestamp,
            )
        )

    return exported
