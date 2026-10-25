"""Multi-format report exporters (Markdown, CSV, JSON) and unified ReportExporter architecture."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from src.ingestion.schema import IngestionSummary
from src.optimization.models import OptimizationResult
from src.version import get_version

if TYPE_CHECKING:
    from src.curation.models import CuratedDataset

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


class ReportExporter:
    """Unified exporter for calculation results, matrix profiles, and curated datasets.

    Encapsulates output directory management, timestamp formatting, delimiter conventions (';' or ','),
    decimal formatting, and artifact generation across CSV, JSON, and Markdown formats.
    """

    def __init__(
        self,
        output_dir: Path | str,
        delimiter: str = ";",
        decimal_char: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.delimiter = delimiter
        self.decimal_char = (
            decimal_char if decimal_char is not None else ("," if delimiter == ";" else ".")
        )
        self.timestamp = timestamp or get_export_timestamp()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_curated_dataset(
        self,
        dataset: CuratedDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "curated",
    ) -> Path:
        """Export curated dataset to a clean CSV file."""
        target_dir = Path(curated_dir) if curated_dir is not None else self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        csv_file = target_dir / f"{base_name}.csv"
        df = dataset.to_dataframe()
        df.to_csv(
            csv_file,
            index=False,
            sep=self.delimiter,
            decimal=self.decimal_char,
            encoding="utf-8",
        )
        return csv_file

    def export_coefficients_csv(
        self,
        opt_result: OptimizationResult,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export monthly distribution coefficients and metrics per CUPS as CSV."""
        from src.config import get_precision

        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_coefficients.csv"

        rows: list[dict[str, object]] = []
        for m in opt_result.monthly_results:
            for c in m.cups_metrics:
                rows.append(
                    {
                        "month": c.month,
                        "cups": c.cups,
                        "use": c.use,
                        "beta": f"{c.beta:.4f}".replace(".", self.decimal_char),
                        "share_pct": f"{c.beta * 100:.{prec}f}".replace(".", self.decimal_char),
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
        df.to_csv(file_path, index=False, sep=self.delimiter, decimal=self.decimal_char)
        return file_path

    def export_coefficients_matrix_csv(
        self,
        opt_result: OptimizationResult,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export consolidated monthly distribution shares matrix (CUPS in Y, Months in X) as CSV."""
        from src.config import get_precision

        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_coefficients_matrix.csv"

        matrix = opt_result.build_matrix()
        rows: list[dict[str, object]] = []

        for cups in matrix.cups_list:
            use_val = matrix.cups_uses.get(cups, "") if hasattr(matrix, "cups_uses") else ""
            row_dict: dict[str, object] = {"cups": cups, "use": use_val}
            for m in matrix.months:
                row_dict[m] = matrix.format_cell(cups, m, precision=prec).replace(
                    ".", self.decimal_char
                )
            row_dict["annual_average"] = matrix.format_annual(cups, precision=prec).replace(
                ".", self.decimal_char
            )
            rows.append(row_dict)

        # Total row
        total_dict: dict[str, object] = {"cups": "TOTAL", "use": "TOTAL"}
        for m in matrix.months:
            total_dict[m] = matrix.format_month_sum(m, precision=prec).replace(
                ".", self.decimal_char
            )
        total_dict["annual_average"] = matrix.format_annual_sum(precision=prec).replace(
            ".", self.decimal_char
        )
        rows.append(total_dict)

        df = pd.DataFrame(rows)
        df.to_csv(file_path, index=False, sep=self.delimiter, decimal=self.decimal_char)
        return file_path

    def export_hourly_shares_csv(
        self,
        opt_result: OptimizationResult,
        timestamp: str | None = None,
    ) -> Path:
        """Export full hourly time-series distribution coefficients and energy balance as CSV."""
        if opt_result.hourly_result is None or opt_result.hourly_result.time_series_df.empty:
            raise ValueError("No hourly results available for export.")

        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_hourly_shares.csv"

        df = opt_result.hourly_result.time_series_df.copy()
        if not df.empty:
            sort_cols = [c for c in ["timestamp", "use", "cups"] if c in df.columns]
            df = df.sort_values(
                by=sort_cols,
                key=lambda col: col.astype(str).str.lower() if col.name in ("use", "cups") else col,
                ascending=[True] * len(sort_cols),
            ).reset_index(drop=True)

            for col in ["share_pct", "estimated_share_pct"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(".", self.decimal_char, regex=False)

        df.to_csv(file_path, index=False, sep=self.delimiter, decimal=self.decimal_char)
        return file_path

    def export_hourly_profile_matrix_csv(
        self,
        opt_result: OptimizationResult,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export 24-hour diurnal distribution profile matrix (CUPS in Y, Hours 00..23 in X) as CSV."""
        from src.config import get_precision

        if opt_result.hourly_result is None:
            raise ValueError("No hourly results available for export.")

        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_hourly_profile_matrix.csv"

        matrix = opt_result.hourly_result.profile_matrix
        rows: list[dict[str, object]] = []

        for cups in matrix.cups_list:
            use_val = matrix.cups_uses.get(cups, "") if hasattr(matrix, "cups_uses") else ""
            row_dict: dict[str, object] = {"cups": cups, "use": use_val}
            for h_str in matrix.hours:
                row_dict[h_str] = matrix.format_cell(cups, h_str, precision=prec).replace(
                    ".", self.decimal_char
                )
            row_dict["average"] = matrix.format_average(cups, precision=prec).replace(
                ".", self.decimal_char
            )
            rows.append(row_dict)

        # Total row
        total_dict: dict[str, object] = {"cups": "TOTAL", "use": "TOTAL"}
        for h_str in matrix.hours:
            total_dict[h_str] = matrix.format_hour_sum(h_str, precision=prec).replace(
                ".", self.decimal_char
            )
        total_dict["average"] = matrix.format_average_sum(precision=prec).replace(
            ".", self.decimal_char
        )
        rows.append(total_dict)

        df = pd.DataFrame(rows)
        df.to_csv(file_path, index=False, sep=self.delimiter, decimal=self.decimal_char)
        return file_path

    def export_results_json(
        self,
        opt_result: OptimizationResult,
        ingestion_summary: IngestionSummary,
        timestamp: str | None = None,
    ) -> Path:
        """Export full optimization results and metadata as JSON."""
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_results.json"

        data = {
            "generator": "electricity-share-distributor",
            "version": get_version(),
            "exported_at": datetime.now().isoformat(),
            "ingestion_metadata": asdict(ingestion_summary),
            "primary_strategy": opt_result.strategy,
            "total_summary": asdict(opt_result.total_summary),
            "monthly_results": [asdict(m) for m in opt_result.monthly_results],
            "baselines": {k: asdict(v.total_summary) for k, v in opt_result.baselines.items()},
            "cups_uses": opt_result.cups_uses,
        }

        if opt_result.hourly_result is not None:
            h_matrix = opt_result.hourly_result.profile_matrix
            data["hourly_profile"] = {
                "hours": h_matrix.hours,
                "matrix": h_matrix.matrix,
                "hourly_sums": h_matrix.hourly_sums,
                "average_shares": h_matrix.average_shares,
                "average_sum": h_matrix.average_sum,
                "cups_uses": h_matrix.cups_uses,
            }

        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return file_path

    def export_summary_markdown(
        self,
        opt_result: OptimizationResult,
        ingestion_summary: IngestionSummary,
        lang: str | None = None,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export complete human-readable optimization and coefficient report in Markdown."""
        from src.config import get_language, get_precision
        from src.i18n import t

        target_lang = lang or get_language()
        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_optimization_summary.md"

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
            headers = [
                "CUPS",
                t("col_use", lang=target_lang),
                *month_headers,
                t("col_annual_avg", lang=target_lang),
            ]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| :--- | :--- | " + " | ".join([":---:"] * (len(headers) - 2)) + " |")

            for cups in matrix.cups_list:
                use_val = matrix.cups_uses.get(cups, "") if hasattr(matrix, "cups_uses") else ""
                row_cells = [f"`{cups}`", use_val]
                for m in matrix.months:
                    row_cells.append(matrix.format_cell(cups, m, precision=prec))
                row_cells.append(f"**{matrix.format_annual(cups, precision=prec)}**")
                lines.append("| " + " | ".join(row_cells) + " |")

            total_cells = [f"**{t('lbl_total_rd244', lang=target_lang)}**", ""]
            for m in matrix.months:
                total_cells.append(f"**{matrix.format_month_sum(m, precision=prec)}**")
            total_cells.append(f"**{matrix.format_annual_sum(precision=prec)}**")
            lines.append("| " + " | ".join(total_cells) + " |")
            lines.extend(["", "---", ""])

        # Diurnal Distribution Share Profile (24-Hour Profile)
        if opt_result.hourly_result is not None:
            h_matrix = opt_result.hourly_result.profile_matrix
            if h_matrix.cups_list and h_matrix.hours:
                lines.append(t("md_sec_hourly_profile", lang=target_lang))
                lines.append("")
                lines.append(t("md_desc_hourly_profile", lang=target_lang))
                lines.append("")

                hour_headers = [f"{h}h" for h in h_matrix.hours]
                h_headers = [
                    "CUPS",
                    t("col_use", lang=target_lang),
                    *hour_headers,
                    t("col_hourly_avg", lang=target_lang),
                ]
                lines.append("| " + " | ".join(h_headers) + " |")
                lines.append(
                    "| :--- | :--- | " + " | ".join([":---:"] * (len(h_headers) - 2)) + " |"
                )

                for cups in h_matrix.cups_list:
                    h_use = (
                        h_matrix.cups_uses.get(cups, "") if hasattr(h_matrix, "cups_uses") else ""
                    )
                    h_row = [f"`{cups}`", h_use]
                    for h in h_matrix.hours:
                        h_row.append(h_matrix.format_cell(cups, h, precision=prec))
                    h_row.append(f"**{h_matrix.format_average(cups, precision=prec)}**")
                    lines.append("| " + " | ".join(h_row) + " |")

                total_h_cells = [f"**{t('lbl_total_rd244', lang=target_lang)}**", ""]
                for h in h_matrix.hours:
                    total_h_cells.append(f"**{h_matrix.format_hour_sum(h, precision=prec)}**")
                total_h_cells.append(f"**{h_matrix.format_average_sum(precision=prec)}**")
                lines.append("| " + " | ".join(total_h_cells) + " |")
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
                "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            )
            for c in m.cups_metrics:
                lines.append(
                    f"| `{c.cups}` | {c.use} | **{c.beta:.4f}** | {c.beta * 100:.{prec}f}% | "
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
        self,
        opt_result: OptimizationResult,
        ingestion_summary: IngestionSummary,
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

        exported: list[Path] = []

        if fmt in ("all", "csv"):
            exported.append(self.export_coefficients_csv(opt_result, precision=precision))
            exported.append(self.export_coefficients_matrix_csv(opt_result, precision=precision))
            if opt_result.hourly_result is not None:
                exported.append(self.export_hourly_shares_csv(opt_result))
                exported.append(
                    self.export_hourly_profile_matrix_csv(opt_result, precision=precision)
                )

        if fmt in ("all", "json"):
            exported.append(self.export_results_json(opt_result, ingestion_summary))

        if fmt in ("all", "markdown", "md"):
            exported.append(
                self.export_summary_markdown(
                    opt_result,
                    ingestion_summary,
                    lang=lang,
                    precision=precision,
                )
            )

        if fmt in ("all", "html"):
            exported.append(
                self.export_interactive_html(
                    opt_result,
                    ingestion_summary,
                    lang=lang,
                    precision=precision,
                )
            )

        return exported

    def export_interactive_html(
        self,
        opt_result: OptimizationResult,
        ingestion_summary: IngestionSummary,
        lang: str | None = None,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export standalone offline interactive HTML report."""
        from src.presentation.html_report import generate_interactive_html_report

        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_interactive_report.html"
        html_content = generate_interactive_html_report(
            opt_result,
            ingestion_summary,
            lang=lang,
            precision=precision,
        )
        file_path.write_text(html_content, encoding="utf-8")
        return file_path


# -------------------------------------------------------------------------
# Standalone functions preserving exact backward-compatible API
# -------------------------------------------------------------------------


def export_coefficients_csv(
    opt_result: OptimizationResult,
    output_dir: Path | str,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export monthly distribution coefficients and metrics per CUPS as CSV."""
    exporter = ReportExporter(output_dir=output_dir, timestamp=timestamp)
    return exporter.export_coefficients_csv(opt_result, precision=precision)


def export_coefficients_matrix_csv(
    opt_result: OptimizationResult,
    output_dir: Path | str,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export consolidated monthly distribution shares matrix (CUPS in Y, Months in X) as CSV."""
    exporter = ReportExporter(output_dir=output_dir, timestamp=timestamp)
    return exporter.export_coefficients_matrix_csv(opt_result, precision=precision)


def export_hourly_shares_csv(
    opt_result: OptimizationResult,
    output_dir: Path | str,
    timestamp: str | None = None,
) -> Path:
    """Export full hourly time-series distribution coefficients and energy balance as CSV."""
    exporter = ReportExporter(output_dir=output_dir, timestamp=timestamp)
    return exporter.export_hourly_shares_csv(opt_result)


def export_hourly_profile_matrix_csv(
    opt_result: OptimizationResult,
    output_dir: Path | str,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export 24-hour diurnal distribution profile matrix (CUPS in Y, Hours 00..23 in X) as CSV."""
    exporter = ReportExporter(output_dir=output_dir, timestamp=timestamp)
    return exporter.export_hourly_profile_matrix_csv(opt_result, precision=precision)


def export_results_json(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    output_dir: Path | str,
    timestamp: str | None = None,
) -> Path:
    """Export full optimization results and metadata as JSON."""
    exporter = ReportExporter(output_dir=output_dir, timestamp=timestamp)
    return exporter.export_results_json(opt_result, ingestion_summary)


def export_summary_markdown(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    output_dir: Path | str,
    lang: str | None = None,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export complete human-readable optimization and coefficient report in Markdown."""
    exporter = ReportExporter(output_dir=output_dir, timestamp=timestamp)
    return exporter.export_summary_markdown(
        opt_result, ingestion_summary, lang=lang, precision=precision
    )


def export_all(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    output_dir: Path | str,
    formats: str = "all",
    lang: str | None = None,
    precision: int | None = None,
) -> list[Path]:
    """Execute exports according to the specified format flag."""
    exporter = ReportExporter(output_dir=output_dir)
    return exporter.export_all(
        opt_result,
        ingestion_summary,
        formats=formats,
        lang=lang,
        precision=precision,
    )


def export_interactive_html(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    output_dir: Path | str,
    lang: str | None = None,
    precision: int | None = None,
    timestamp: str | None = None,
) -> Path:
    """Export standalone offline interactive HTML report."""
    exporter = ReportExporter(output_dir=output_dir, timestamp=timestamp)
    return exporter.export_interactive_html(
        opt_result, ingestion_summary, lang=lang, precision=precision
    )
