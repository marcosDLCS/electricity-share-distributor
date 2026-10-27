"""Multi-format report exporters (Markdown, CSV, JSON) and unified ReportExporter architecture."""

from __future__ import annotations

import calendar
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.ingestion.schema import AlignedDataset, IngestionSummary
from src.optimization.models import OptimizationResult
from src.presentation.views.common import format_month_abbr
from src.version import get_version

if TYPE_CHECKING:
    from src.curation.models import CuratedDataset

FORMULA_INJECTION_PREFIXES: Final[tuple[str, ...]] = ("=", "+", "-", "@", "\t", "\r")


def sanitize_formula_injection(value: Any) -> Any:
    """Neutralize spreadsheet formula injection by prefixing risky strings with a single quote.

    Prefixes string values starting with '=', '+', '-', '@', '\\t', or '\\r'
    with a single quote ('), preventing formula execution when opened in Excel/Calc.
    Non-string values or safe strings are returned unaltered.

    Args:
        value: Any cell value (string, float, int, None, etc.).

    Returns:
        Sanitized value safe for spreadsheet export.
    """
    if isinstance(value, str) and value.startswith(FORMULA_INJECTION_PREFIXES):
        return f"'{value}"
    return value


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
        if "use" in df.columns:
            df["use"] = df["use"].apply(sanitize_formula_injection)
        df.to_csv(
            csv_file,
            index=False,
            sep=self.delimiter,
            decimal=self.decimal_char,
            encoding="utf-8",
        )
        return csv_file

    def export_curated_excel(
        self,
        dataset: CuratedDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "curated",
    ) -> Path:
        """Export curated dataset to a beautifully styled Excel (.xlsx) file.

        Features:
        - Harmonious header group colors for similar semantic columns.
        - Hour-grouped zebra pattern (alternating between white and soft tint per hour block).
        - Boolean columns (is_weekend) formatted with intuitive emojis (✅ / ❌).
        - Centered, right, and left alignments per column domain.
        - Auto-fit column widths, freeze panes on header row, and native AutoFilter.
        """
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        target_dir = Path(curated_dir) if curated_dir is not None else self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        excel_file = target_dir / f"{base_name}.xlsx"

        df = dataset.to_dataframe()
        if "use" in df.columns:
            df["use"] = df["use"].apply(sanitize_formula_injection)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Curated Data"
        if ws.views.sheetView:
            ws.views.sheetView[0].showGridLines = True

        header_group_colors: dict[str, str] = {
            # 1. Temporal coordinates: Steel Slate Blue
            "timestamp": "2B4C7E",
            "year": "2B4C7E",
            "month": "2B4C7E",
            "day": "2B4C7E",
            "hour": "2B4C7E",
            "day_of_week": "2B4C7E",
            "is_weekend": "2B4C7E",
            # 2. CUPS supply point identification: Deep Petrol Teal
            "cups_id": "1A535C",
            "use": "1A535C",
            # 3. Electricity demand & community consumption: Warm Terracotta
            "consumption": "9C5B28",
            "community_demand": "9C5B28",
            # 4. Solar PV generation & balance: Solar Emerald Forest
            "generation": "2D6A4F",
            "self_consumption": "2D6A4F",
            "exported_energy": "2D6A4F",
            "imported_energy": "2D6A4F",
            # 5. Weather context: Royal Amethyst Plum
            "temperature": "5C4D7D",
            "cloud_cover": "5C4D7D",
        }

        col_widths: dict[str, int] = {
            "timestamp": 21,
            "year": 8,
            "month": 8,
            "day": 8,
            "hour": 8,
            "day_of_week": 14,
            "is_weekend": 12,
            "cups_id": 24,
            "use": 24,
            "consumption": 14,
            "community_demand": 18,
            "generation": 14,
            "self_consumption": 18,
            "exported_energy": 16,
            "imported_energy": 16,
            "temperature": 14,
            "cloud_cover": 13,
        }

        headers = list(df.columns)
        ws.append(headers)

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx)
            color = header_group_colors.get(h, "2B4C7E")
            cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = col_widths.get(h, 15)

        fill_white = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        fill_tint = PatternFill(start_color="F4F6F9", end_color="F4F6F9", fill_type="solid")
        thin_side = Side(style="thin", color="E2E8F0")
        cell_border = Border(top=thin_side, bottom=thin_side, left=thin_side, right=thin_side)
        align_center = Alignment(horizontal="center", vertical="center")

        current_hour_key: Any = None
        hour_toggle = 0
        rows_data = df.to_dict(orient="records")

        center_col_indices = {
            col_idx
            for col_idx, h in enumerate(headers, 1)
            if h
            in (
                "timestamp",
                "year",
                "month",
                "day",
                "hour",
                "day_of_week",
                "is_weekend",
                "cloud_cover",
            )
        }

        for r_idx, row in enumerate(rows_data, 2):
            h_key = row.get("timestamp")
            if h_key != current_hour_key:
                if current_hour_key is not None:
                    hour_toggle = 1 - hour_toggle
                current_hour_key = h_key

            row_fill = fill_tint if hour_toggle == 1 else fill_white

            row_vals: list[Any] = []
            for h in headers:
                val = row.get(h)
                if h == "is_weekend":
                    val = "✅" if bool(val) else "❌"
                elif pd.isna(val):
                    val = None
                elif h == "use":
                    val = sanitize_formula_injection(val)
                row_vals.append(val)

            ws.append(row_vals)

            if hour_toggle == 1:
                for c_idx in range(1, len(headers) + 1):
                    cell = ws.cell(row=r_idx, column=c_idx)
                    cell.fill = row_fill
                    cell.border = cell_border
                    if c_idx in center_col_indices:
                        cell.alignment = align_center
            else:
                for c_idx in center_col_indices:
                    ws.cell(row=r_idx, column=c_idx).alignment = align_center

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        wb.save(excel_file)

        return excel_file

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
                        "use": sanitize_formula_injection(c.use),
                        "beta": f"{c.beta:.4f}".replace(".", self.decimal_char),
                        "share_pct": f"{c.beta * 100:.{prec}f}".replace(".", self.decimal_char),
                        "consumption_kwh": round(c.consumption_kwh, 2),
                        "generation_allocated_kwh": round(c.generation_allocated_kwh, 2),
                        "self_consumed_kwh": round(c.self_consumed_kwh, 2),
                        "surplus_kwh": round(c.surplus_kwh, 2),
                        "grid_demand_kwh": round(c.grid_demand_kwh, 2),
                        "self_consumption_rate_pct": round(c.self_consumption_rate, 2),
                        "solar_coverage_rate_pct": round(c.solar_coverage_rate, 2),
                        "solar_hours_consumption_kwh": round(c.solar_hours_consumption_kwh, 2),
                        "solar_hours_coverage_rate_pct": round(c.solar_hours_coverage_rate, 2),
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
            row_dict: dict[str, object] = {
                "cups": cups,
                "use": sanitize_formula_injection(use_val),
            }
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
            if "use" in df.columns:
                df["use"] = df["use"].apply(sanitize_formula_injection)
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
            row_dict: dict[str, object] = {
                "cups": cups,
                "use": sanitize_formula_injection(use_val),
            }
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

    def export_dso_regulatory_csv(
        self,
        opt_result: OptimizationResult,
        aligned_dataset: AlignedDataset | None = None,
        consumption_dir: Path | str | None = None,
        year: int | None = None,
        hourly: bool | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export standardized annual 8,760-hour regulatory flat file (Orden TED/1247/2021).

        Generates official dynamic coefficient filing for Spanish distribution system
        operators (i-DE Iberdrola, e-distribución Endesa, UFD Naturgy, E-REDES, etc.)
        formatted with 6 decimal places (0,000000) and summing strictly to 1,000000 per hour.
        Creates both {timestamp}_esd_dso_8760h.csv and {timestamp}_esd_dso_8760h.txt companion.

        Args:
            opt_result: Solved OptimizationResult.
            aligned_dataset: Optional AlignedDataset with metadata and timestamps.
            consumption_dir: Optional path to DATADIS consumption directory for gap estimation.
            year: Calendar year for the 8,760h or 8,784h leap year schedule.
            hourly: Whether to use 24-hour diurnal profile if available.
            timestamp: Optional export timestamp override.

        Returns:
            Path to generated .csv file.
        """
        import numpy as np

        from src.optimization.engine import DistributionOptimizer

        target_year = year
        if (
            target_year is None
            and aligned_dataset is not None
            and aligned_dataset.metadata.start_time
        ):
            try:
                target_year = int(aligned_dataset.metadata.start_time[:4])
            except Exception:
                target_year = None
        if target_year is None:
            target_year = datetime.now().year

        is_leap = calendar.isleap(target_year)
        total_hours = 8784 if is_leap else 8760

        cups_list = list(opt_result.cups_list)
        if not cups_list and aligned_dataset:
            cups_list = list(aligned_dataset.cups_list)
        if not cups_list and opt_result.total_summary and opt_result.total_summary.cups_metrics:
            cups_list = [c.cups for c in opt_result.total_summary.cups_metrics]
        if not cups_list:
            for m in opt_result.monthly_results:
                if m.cups_metrics:
                    cups_list = [c.cups for c in m.cups_metrics]
                    break
        cups_list = sorted(cups_list)

        monthly_betas = DistributionOptimizer.resolve_full_year_monthly_betas(
            opt_result,
            aligned_dataset=aligned_dataset,
            consumption_dir=consumption_dir,
            target_year=target_year,
            precision=4,
        )

        use_hourly = (
            hourly
            if hourly is not None
            else (
                opt_result.hourly_result is not None
                and bool(opt_result.hourly_result.profile_matrix.matrix)
            )
        )
        hourly_matrix_6dec: dict[str, dict[str, float]] = {}
        if use_hourly and opt_result.hourly_result is not None:
            pm = opt_result.hourly_result.profile_matrix
            for h_str in pm.hours:
                raw_h = np.array([pm.matrix[c].get(h_str) or 0.0 for c in cups_list], dtype=float)
                if np.sum(raw_h) > 0:
                    rounded_h = DistributionOptimizer._round_betas(
                        raw_h,
                        precision=4,
                        cups_list=cups_list,
                        constraints=opt_result.constraints,
                    )
                    hourly_matrix_6dec[h_str] = {
                        c: float(rounded_h[i]) for i, c in enumerate(cups_list)
                    }

        lines: list[str] = ["CUPS;Hora;Coeficiente"]
        start_dt = datetime(target_year, 1, 1, 0, 0)
        for h_idx in range(1, total_hours + 1):
            dt = start_dt + timedelta(hours=h_idx - 1)
            m_str = f"{dt.month:02d}"
            h_str = f"{dt.hour:02d}"

            if use_hourly and h_str in hourly_matrix_6dec:
                betas_map = hourly_matrix_6dec[h_str]
            else:
                betas_map = monthly_betas.get(m_str, {})

            for c in cups_list:
                val = betas_map.get(c, 0.0)
                val_str = f"{val:.6f}".replace(".", ",")
                lines.append(f"{c};{h_idx};{val_str}")

        ts = timestamp or self.timestamp
        csv_file = self.output_dir / f"{ts}_esd_dso_8760h.csv"
        txt_file = self.output_dir / f"{ts}_esd_dso_8760h.txt"
        content = "\n".join(lines) + "\n"
        csv_file.write_text(content, encoding="utf-8")
        txt_file.write_text(content, encoding="utf-8")
        return csv_file

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
            "self_consumption_comparison": {
                "current_self_consumed_kwh": round(opt_result.current_self_consumed_kwh, 2),
                "current_self_consumption_rate_pct": round(
                    opt_result.current_self_consumption_rate, 2
                ),
                "monthly_share_self_consumed_kwh": round(
                    opt_result.monthly_share_self_consumed_kwh, 2
                ),
                "monthly_share_self_consumption_rate_pct": round(
                    opt_result.monthly_share_self_consumption_rate, 2
                ),
                "hourly_share_self_consumed_kwh": round(
                    opt_result.hourly_share_self_consumed_kwh, 2
                ),
                "hourly_share_self_consumption_rate_pct": round(
                    opt_result.hourly_share_self_consumption_rate, 2
                ),
            },
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
        file_suffix: str = "",
    ) -> Path:
        """Export complete human-readable optimization and coefficient report in Markdown."""
        from src.config import get_language, get_precision
        from src.i18n import t

        target_lang = lang or get_language()
        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_optimization_summary{file_suffix}.md"

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
            t(
                "md_lbl_solar_hours_gen",
                lang=target_lang,
                gen=(
                    tot.solar_hours_generation_kwh
                    if tot.solar_hours_generation_kwh > 0
                    else tot.total_generation_kwh
                ),
            ),
            t("md_lbl_total_dem", lang=target_lang, dem=tot.total_consumption_kwh),
            t("md_lbl_solar_hours_dem", lang=target_lang, dem=tot.solar_hours_consumption_kwh),
            t(
                "md_lbl_total_sc",
                lang=target_lang,
                sc=tot.total_self_consumed_kwh,
                rate=tot.self_consumption_rate,
            ),
            t("md_lbl_total_surplus", lang=target_lang, surplus=tot.total_surplus_kwh),
            t("md_lbl_solar_coverage", lang=target_lang, cov=tot.solar_coverage_rate),
            t("md_lbl_solar_hours_cov", lang=target_lang, cov=tot.solar_hours_coverage_rate),
            "",
            "---",
            "",
            t("md_sec_trajectory", lang=target_lang),
            "",
            t("md_traj_header", lang=target_lang),
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for m in opt_result.monthly_results:
            m_label = format_month_abbr(m.month, lang=target_lang)
            if m.has_data:
                lines.append(
                    f"| **{m_label}** | {m.total_generation_kwh:,.1f} | {m.total_consumption_kwh:,.1f} | "
                    f"{m.solar_hours_consumption_kwh:,.1f} | {m.total_self_consumed_kwh:,.1f} | {m.total_surplus_kwh:,.1f} | "
                    f"{m.total_grid_demand_kwh:,.1f} | {m.self_consumption_rate:.1f}% | {m.solar_coverage_rate:.1f}% |"
                )
            else:
                lines.append(f"| **{m_label}** | — | — | — | — | — | — | — | — |")

        lines.extend(
            [
                f"| **{t('lbl_total', lang=target_lang)}** | **{tot.total_generation_kwh:,.1f}** | **{tot.total_consumption_kwh:,.1f}** | "
                f"**{tot.solar_hours_consumption_kwh:,.1f}** | **{tot.total_self_consumed_kwh:,.1f}** | **{tot.total_surplus_kwh:,.1f}** | "
                f"**{tot.total_grid_demand_kwh:,.1f}** | **{tot.self_consumption_rate:.1f}%** | **{tot.solar_coverage_rate:.1f}%** |",
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

        # 3-Way Self-Consumption Progression Comparison
        mon_sc = opt_result.monthly_share_self_consumed_kwh or tot.total_self_consumed_kwh
        if (
            opt_result.current_self_consumed_kwh > 0
            or mon_sc > 0
            or opt_result.hourly_share_self_consumed_kwh > 0
        ):
            cur_sc = opt_result.current_self_consumed_kwh
            hour_sc = opt_result.hourly_share_self_consumed_kwh or mon_sc

            mon_gain = mon_sc - cur_sc
            mon_gain_pct = (mon_gain / max(cur_sc, 1e-6)) * 100.0 if cur_sc > 0 else 0.0
            mon_gain_str = (
                f"+{mon_gain:,.1f} kWh (+{mon_gain_pct:.1f}%)"
                if mon_gain > 0 and cur_sc > 0
                else "—"
            )

            hour_gain = hour_sc - cur_sc
            hour_gain_pct = (hour_gain / max(cur_sc, 1e-6)) * 100.0 if cur_sc > 0 else 0.0
            hour_gain_str = (
                f"+{hour_gain:,.1f} kWh (+{hour_gain_pct:.1f}%)"
                if hour_gain > 0 and cur_sc > 0
                else "—"
            )

            lines.extend(
                [
                    t("md_sec_sc_comparison", lang=target_lang),
                    "",
                    t("md_sc_comp_header", lang=target_lang),
                    "| :--- | :---: | :---: | :---: |",
                    f"| {t('lbl_sc_current', lang=target_lang)} | {cur_sc:,.1f} | {opt_result.current_self_consumption_rate:.1f}% | {t('lbl_baseline', lang=target_lang)} |",
                    f"| {t('lbl_sc_monthly', lang=target_lang)} | {mon_sc:,.1f} | {opt_result.monthly_share_self_consumption_rate:.1f}% | {mon_gain_str} |",
                    f"| **{t('lbl_sc_hourly', lang=target_lang)}** | **{hour_sc:,.1f}** | **{opt_result.hourly_share_self_consumption_rate:.1f}%** | **{hour_gain_str}** |",
                    "",
                    "---",
                    "",
                ]
            )

        # Consolidated Regulatory Coefficients Matrix (RD 244/2019)
        matrix = opt_result.build_matrix()
        if matrix.cups_list and matrix.months:
            lines.append(t("md_sec_coeff_matrix", lang=target_lang))
            lines.append("")
            lines.append(t("md_desc_coeff_matrix", lang=target_lang))
            lines.append("")

            month_headers = [format_month_abbr(m, lang=target_lang) for m in matrix.months]
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
            m_label = format_month_abbr(m.month, lang=target_lang)
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
        aligned_dataset: AlignedDataset | None = None,
        consumption_dir: Path | str | None = None,
        year: int | None = None,
    ) -> list[Path]:
        """Execute exports according to the specified format flag.

        Supported formats: 'all', 'table', 'csv', 'json', 'markdown', 'html', 'dso'.
        """
        fmt = formats.lower().strip()
        if fmt in ("table", "none"):
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
            if opt_result.hourly_result is not None:
                # Always generate an ES document and an EN document for hourly reports
                exported.append(
                    self.export_summary_markdown(
                        opt_result,
                        ingestion_summary,
                        lang="es",
                        precision=precision,
                        file_suffix="_es",
                    )
                )
                exported.append(
                    self.export_summary_markdown(
                        opt_result,
                        ingestion_summary,
                        lang="en",
                        precision=precision,
                        file_suffix="_en",
                    )
                )
            else:
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

        if fmt in ("all", "dso"):
            dso_csv = self.export_dso_regulatory_csv(
                opt_result,
                aligned_dataset=aligned_dataset,
                consumption_dir=consumption_dir,
                year=year,
            )
            exported.append(dso_csv)
            dso_txt = self.output_dir / f"{self.timestamp}_esd_dso_8760h.txt"
            if dso_txt.exists() and dso_txt not in exported:
                exported.append(dso_txt)

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
