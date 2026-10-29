"""Report exporters (CSV, Excel, HTML) and unified ReportExporter architecture."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.ingestion.schema import AlignedDataset, IngestionSummary
from src.optimization.models import OptimizationResult

if TYPE_CHECKING:
    from src.curation.models import ConsumptionDataset, CuratedDataset, GenerationDataset

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
    """Unified exporter for calculation shares, interactive HTML reports, and curated datasets.

    Encapsulates output directory management, timestamp formatting, delimiter conventions (';' or ','),
    decimal formatting, and artifact generation across CSV, Excel, and HTML formats.
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

    def _export_dataframe_csv(
        self,
        df: pd.DataFrame,
        target_dir: Path | str | None,
        base_name: str,
    ) -> Path:
        """Write a canonical DataFrame to CSV with formula injection sanitization."""
        out_dir = Path(target_dir) if target_dir is not None else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_file = out_dir / f"{base_name}.csv"
        df_out = df.copy()
        if "use" in df_out.columns:
            df_out["use"] = df_out["use"].apply(sanitize_formula_injection)
        df_out.to_csv(
            csv_file,
            index=False,
            sep=self.delimiter,
            decimal=self.decimal_char,
            encoding="utf-8",
        )
        return csv_file

    def _export_styled_dataframe_excel(
        self,
        df: pd.DataFrame,
        target_dir: Path | str | None,
        base_name: str,
        sheet_title: str,
    ) -> Path:
        """Export a canonical time-series DataFrame to a styled Excel (.xlsx) workbook.

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

        out_dir = Path(target_dir) if target_dir is not None else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        excel_file = out_dir / f"{base_name}.xlsx"

        df_out = df.copy()
        if "use" in df_out.columns:
            df_out["use"] = df_out["use"].apply(sanitize_formula_injection)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_title
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

        headers = list(df_out.columns)
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
        rows_data = df_out.to_dict(orient="records")

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

    def export_generation_dataset(
        self,
        dataset: GenerationDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "generation",
    ) -> Path:
        """Export aggregated canonical generation dataset to a clean CSV file."""
        return self._export_dataframe_csv(
            df=dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
        )

    def export_generation_excel(
        self,
        dataset: GenerationDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "generation",
    ) -> Path:
        """Export aggregated canonical generation dataset to a styled Excel (.xlsx) file."""
        return self._export_styled_dataframe_excel(
            df=dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
            sheet_title="Generation Data",
        )

    def export_consumption_dataset(
        self,
        dataset: ConsumptionDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "consumption",
    ) -> Path:
        """Export aggregated canonical consumption dataset to a clean CSV file."""
        return self._export_dataframe_csv(
            df=dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
        )

    def export_consumption_excel(
        self,
        dataset: ConsumptionDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "consumption",
    ) -> Path:
        """Export aggregated canonical consumption dataset to a styled Excel (.xlsx) file."""
        return self._export_styled_dataframe_excel(
            df=dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
            sheet_title="Consumption Data",
        )

    def export_curated_dataset(
        self,
        dataset: CuratedDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "esd",
    ) -> Path:
        """Export master ESD curated dataset to a clean CSV file."""
        return self._export_dataframe_csv(
            df=dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
        )

    def export_curated_excel(
        self,
        dataset: CuratedDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "esd",
    ) -> Path:
        """Export master ESD curated dataset to a beautifully styled Excel (.xlsx) file."""
        return self._export_styled_dataframe_excel(
            df=dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
            sheet_title="ESD Data",
        )

    def export_monthly_shares_csv(
        self,
        opt_result: OptimizationResult,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export monthly distribution shares and energy balance per CUPS as CSV."""
        from src.config import get_precision

        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_monthly_shares.csv"

        rows: list[dict[str, object]] = []
        for m in opt_result.monthly_results:
            if not m.has_data:
                continue
            for c in m.cups_metrics:
                use_val = c.use or opt_result.cups_uses.get(c.cups, "")
                rows.append(
                    {
                        "month": c.month,
                        "cups": c.cups,
                        "use": sanitize_formula_injection(use_val),
                        "consumption_kwh": round(c.consumption_kwh, 2),
                        "generation_kwh": round(m.total_generation_kwh, 2),
                        "share_pct": f"{c.beta * 100:.{prec}f}%".replace(".", self.decimal_char),
                        "self_consumed_kwh": round(c.self_consumed_kwh, 2),
                        "surplus_kwh": round(c.surplus_kwh, 2),
                        "grid_demand_kwh": round(c.grid_demand_kwh, 2),
                    }
                )

        columns = [
            "month",
            "cups",
            "use",
            "consumption_kwh",
            "generation_kwh",
            "share_pct",
            "self_consumed_kwh",
            "surplus_kwh",
            "grid_demand_kwh",
        ]
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            sort_cols = [col for col in ["month", "use", "cups"] if col in df.columns]
            df = df.sort_values(
                by=sort_cols,
                key=lambda col: col.astype(str).str.lower() if col.name in ("use", "cups") else col,
                ascending=[True] * len(sort_cols),
            ).reset_index(drop=True)

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

    def export_all(
        self,
        opt_result: OptimizationResult,
        ingestion_summary: IngestionSummary,
        formats: str = "all",
        lang: str | None = None,
        precision: int | None = None,
        aligned_dataset: AlignedDataset | None = None,
    ) -> list[Path]:
        """Execute exports according to the specified format flag.

        Supported formats: 'all', 'table', 'csv', 'html'.
        """
        fmt = formats.lower().strip()
        if fmt in ("table", "none"):
            return []

        exported: list[Path] = []

        if fmt in ("all", "csv"):
            exported.append(self.export_monthly_shares_csv(opt_result, precision=precision))
            if opt_result.hourly_result is None and aligned_dataset is not None:
                from src.optimization.engine import DistributionOptimizer
                from src.optimization.models import OptimizationStrategy

                opt_result.hourly_result = DistributionOptimizer.compute_hourly_optimization(
                    aligned_dataset=aligned_dataset,
                    strategy=OptimizationStrategy(opt_result.strategy),
                    precision=precision or 0,
                    primary_cups=opt_result.primary_cups,
                    constraints=opt_result.constraints,
                )
            if (
                opt_result.hourly_result is not None
                and not opt_result.hourly_result.time_series_df.empty
            ):
                exported.append(self.export_hourly_shares_csv(opt_result))

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
