"""Report exporters (CSV, Excel, HTML) and unified ReportExporter architecture."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.i18n import get_month_name, t
from src.ingestion.schema import AlignedDataset, IngestionSummary
from src.optimization.models import OptimizationResult
from src.presentation.console import format_kwh, format_pct
from src.version import get_version

if TYPE_CHECKING:
    from src.analytics.models import (
        CommunityConsumptionSummary,
        ComparisonSummary,
        CupsConsumptionShare,
    )
    from src.curation.models import ConsumptionDataset, CuratedDataset, GenerationDataset
    from src.presentation.story_data import StoryReportContext

FORMULA_INJECTION_PREFIXES: Final[tuple[str, ...]] = ("=", "+", "-", "@", "\t", "\r")


def sanitize_formula_injection(value: Any) -> Any:
    """Neutralize spreadsheet formula injection by prefixing risky strings with a single quote.

    Prefixes string values starting with '=', '+', '-', '@', '\\t', or '\\r'
    (either directly or after leading whitespace) with a single quote ('),
    preventing formula execution when opened in Excel/Calc. Non-string values
    or safe strings are returned unaltered.

    Args:
        value: Any cell value (string, float, int, None, etc.).

    Returns:
        Sanitized value safe for spreadsheet export.
    """
    if isinstance(value, str) and (
        value.startswith(FORMULA_INJECTION_PREFIXES)
        or value.lstrip().startswith(FORMULA_INJECTION_PREFIXES)
    ):
        return f"'{value}"
    return value


def _sanitize_dataframe_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Neutralize spreadsheet formula injection across all string/object columns."""
    df_out = df.copy()
    if df_out.empty:
        return df_out

    formula_pattern = r"^(?:[=+\-@\t\r]|\s+[=+\-@])"
    for col in df_out.columns:
        series = df_out[col]
        dtype = series.dtype
        if pd.api.types.is_object_dtype(dtype):
            as_str = series.astype("string")
            risky = as_str.str.contains(formula_pattern, regex=True, na=False)
            if not bool(risky.any()):
                continue
            # Only escape actual str elements; keep numeric values like -3.5 intact.
            is_str_val = series.loc[risky].map(lambda v: isinstance(v, str))
            risky_str_idx = is_str_val[is_str_val].index
            if len(risky_str_idx) > 0:
                df_out.loc[risky_str_idx, col] = "'" + series.loc[risky_str_idx].astype(str)
        elif pd.api.types.is_string_dtype(dtype):
            as_str = series.astype("string")
            risky = as_str.str.contains(formula_pattern, regex=True, na=False)
            if bool(risky.any()):
                df_out.loc[risky, col] = "'" + series.loc[risky].astype(str)
    return df_out


def get_export_timestamp() -> str:
    """Generate standardized export timestamp string: YYYYMMDD_HHMMSS."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _make_ascii_bar(pct: float, width: int = 12) -> str:
    """Create a plain-text block bar suitable for Markdown table cells."""
    pct_clamped = max(0.0, min(100.0, pct))
    filled_len = round((pct_clamped / 100.0) * width)
    empty_len = width - filled_len
    return "`" + "█" * filled_len + "░" * empty_len + "`"


def _strip_rich_markup(text: str) -> str:
    """Remove Rich console markup tags (e.g. [bold], [/]) from localized strings."""
    return re.sub(r"\[/?[^\]]+\]", "", text)


def _format_signed_kwh(diff: float, include_unit: bool = False) -> str:
    """Format a signed kWh delta with optional unit."""
    if diff > 0.0:
        core = f"+{diff:,.2f}"
    elif diff < 0.0:
        core = f"-{abs(diff):,.2f}"
    else:
        core = "0.00"
    return f"{core} kWh" if include_unit else core


def _format_signed_pct(pct: float | None, decimals: int = 1) -> str:
    """Format a signed percentage delta, returning 'N/A' when undefined."""
    if pct is None:
        return "N/A"
    return f"+{pct:.{decimals}f}%" if pct > 0.0 else f"{pct:.{decimals}f}%"


def _append_markdown_shares_table(
    lines: list[str],
    shares: list[CupsConsumptionShare],
    total_kwh: float,
    include_use: bool,
    lang: str | None,
) -> None:
    """Append a Markdown ranked CUPS share table for an annual or monthly period."""
    if include_use:
        lines.append(
            f"| {t('summary_col_rank', lang=lang)} | {t('summary_col_cups', lang=lang)} | "
            f"{t('summary_col_use', lang=lang)} | {t('summary_col_consumption', lang=lang)} | "
            f"{t('summary_col_share', lang=lang)} | {t('summary_col_distribution', lang=lang)} |"
        )
        lines.append("| :---: | :--- | :--- | :---: | :---: | :--- |")
    else:
        lines.append(
            f"| {t('summary_col_rank', lang=lang)} | {t('summary_col_cups', lang=lang)} | "
            f"{t('summary_col_consumption', lang=lang)} | {t('summary_col_share', lang=lang)} | "
            f"{t('summary_col_distribution', lang=lang)} |"
        )
        lines.append("| :---: | :--- | :---: | :---: | :--- |")

    for idx, item in enumerate(shares, start=1):
        badge = ""
        if idx == 1 and item.share_pct > 30.0:
            badge = " ★"
        elif item.consumption_kwh < 1.0:
            badge = " (0)"

        if include_use:
            use_val = item.use or "—"
            lines.append(
                f"| {idx} | `{item.cups}`{badge} | {use_val} | {format_kwh(item.consumption_kwh)} | "
                f"{format_pct(item.share_pct)} | {_make_ascii_bar(item.share_pct)} |"
            )
        else:
            lines.append(
                f"| {idx} | `{item.cups}`{badge} | {format_kwh(item.consumption_kwh)} | "
                f"{format_pct(item.share_pct)} | {_make_ascii_bar(item.share_pct)} |"
            )

    total_pct = "100.00%" if total_kwh > 0.0 else "0.00%"
    if include_use:
        lines.append(
            f"| | **{t('summary_col_total', lang=lang)}** | | **{format_kwh(total_kwh)}** | **{total_pct}** | |"
        )
    else:
        lines.append(
            f"| | **{t('summary_col_total', lang=lang)}** | **{format_kwh(total_kwh)}** | **{total_pct}** | |"
        )
    lines.append("")


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
        df_out = _sanitize_dataframe_strings(df)
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
        from openpyxl.cell import WriteOnlyCell
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        out_dir = Path(target_dir) if target_dir is not None else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        excel_file = out_dir / f"{base_name}.xlsx"

        df_out = _sanitize_dataframe_strings(df)
        if "is_weekend" in df_out.columns:
            df_out["is_weekend"] = df_out["is_weekend"].astype(bool).map({True: "✅", False: "❌"})

        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet(title=sheet_title)
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
        ws.freeze_panes = "A2"
        for col_idx, h in enumerate(headers, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(h, 15)
        if headers:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(df_out) + 1}"

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_align = Alignment(horizontal="center", vertical="center")
        header_fills: dict[str, PatternFill] = {}
        header_cells: list[WriteOnlyCell] = []
        for h in headers:
            color = header_group_colors.get(h, "2B4C7E")
            fill = header_fills.get(color)
            if fill is None:
                fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
                header_fills[color] = fill
            cell = WriteOnlyCell(ws, value=h)
            cell.fill = fill
            cell.font = header_font
            cell.alignment = header_align
            header_cells.append(cell)
        ws.append(header_cells)

        fill_tint = PatternFill(start_color="F4F6F9", end_color="F4F6F9", fill_type="solid")
        thin_side = Side(style="thin", color="E2E8F0")
        cell_border = Border(top=thin_side, bottom=thin_side, left=thin_side, right=thin_side)
        align_center = Alignment(horizontal="center", vertical="center")

        center_col_mask = tuple(
            h
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
            for h in headers
        )

        ts_idx = headers.index("timestamp") if "timestamp" in headers else None
        df_clean = df_out.astype(object).where(pd.notna(df_out), None)

        current_hour_key: Any = None
        hour_toggle = 0
        for row_vals in df_clean.itertuples(index=False, name=None):
            h_key = row_vals[ts_idx] if ts_idx is not None else None
            if h_key != current_hour_key:
                if current_hour_key is not None:
                    hour_toggle = 1 - hour_toggle
                current_hour_key = h_key

            if hour_toggle == 1:
                row_cells: list[WriteOnlyCell] = []
                for val, is_center in zip(row_vals, center_col_mask, strict=True):
                    cell = WriteOnlyCell(ws, value=val)
                    cell.fill = fill_tint
                    cell.border = cell_border
                    if is_center:
                        cell.alignment = align_center
                    row_cells.append(cell)
                ws.append(row_cells)
            else:
                ws.append(row_vals)

        wb.save(excel_file)
        return excel_file

    def export_generation_dataset(
        self,
        dataset: GenerationDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "generation",
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export aggregated canonical generation dataset to a clean CSV file."""
        return self._export_dataframe_csv(
            df=df if df is not None else dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
        )

    def export_generation_excel(
        self,
        dataset: GenerationDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "generation",
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export aggregated canonical generation dataset to a styled Excel (.xlsx) file."""
        return self._export_styled_dataframe_excel(
            df=df if df is not None else dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
            sheet_title="Generation Data",
        )

    def export_consumption_dataset(
        self,
        dataset: ConsumptionDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "consumption",
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export aggregated canonical consumption dataset to a clean CSV file."""
        return self._export_dataframe_csv(
            df=df if df is not None else dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
        )

    def export_consumption_excel(
        self,
        dataset: ConsumptionDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "consumption",
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export aggregated canonical consumption dataset to a styled Excel (.xlsx) file."""
        return self._export_styled_dataframe_excel(
            df=df if df is not None else dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
            sheet_title="Consumption Data",
        )

    def export_curated_dataset(
        self,
        dataset: CuratedDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "esd",
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export master ESD curated dataset to a clean CSV file."""
        return self._export_dataframe_csv(
            df=df if df is not None else dataset.to_dataframe(),
            target_dir=curated_dir,
            base_name=base_name,
        )

    def export_curated_excel(
        self,
        dataset: CuratedDataset,
        curated_dir: Path | str | None = None,
        base_name: str = "esd",
        df: pd.DataFrame | None = None,
    ) -> Path:
        """Export master ESD curated dataset to a beautifully styled Excel (.xlsx) file."""
        return self._export_styled_dataframe_excel(
            df=df if df is not None else dataset.to_dataframe(),
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
                        "use": use_val,
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

        df = _sanitize_dataframe_strings(df)
        df.to_csv(file_path, index=False, sep=self.delimiter, decimal=self.decimal_char)
        return file_path

    def export_monthly_shares_lite_csv(
        self,
        opt_result: OptimizationResult,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export lite monthly distribution shares matrix (CUPS in Y, Months 01..12 in X) as CSV."""
        from src.config import get_precision

        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_monthly_shares_lite.csv"

        calendar_months = [f"{m:02d}" for m in range(1, 13)]
        cups_set: list[str] = list(opt_result.cups_list)
        if not cups_set:
            seen: set[str] = set()
            for m in opt_result.monthly_results:
                for cm in m.cups_metrics:
                    if cm.cups not in seen:
                        seen.add(cm.cups)
                        cups_set.append(cm.cups)

        uses_map: dict[str, str] = dict(opt_result.cups_uses)
        share_lookup: dict[tuple[str, str], str] = {}
        for m in opt_result.monthly_results:
            if not m.has_data:
                continue
            m_key = m.month[-2:] if len(m.month) >= 2 else f"{int(m.month):02d}"
            for cm in m.cups_metrics:
                if cm.use and not uses_map.get(cm.cups):
                    uses_map[cm.cups] = cm.use
                share_lookup[(cm.cups, m_key)] = f"{cm.beta * 100:.{prec}f}%".replace(
                    ".", self.decimal_char
                )

        rows: list[dict[str, object]] = []
        for cups_id in cups_set:
            use_val = uses_map.get(cups_id, "")
            row: dict[str, object] = {
                "cups": cups_id,
                "use": use_val,
            }
            for m_str in calendar_months:
                row[m_str] = share_lookup.get((cups_id, m_str), "")
            rows.append(row)

        columns = ["cups", "use", *calendar_months]
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df = df.sort_values(
                by=["use", "cups"],
                key=lambda col: col.astype(str).str.lower(),
                ascending=[True, True],
            ).reset_index(drop=True)

        df = _sanitize_dataframe_strings(df)
        df.to_csv(file_path, index=False, sep=self.delimiter, decimal=self.decimal_char)
        return file_path

    def export_fortnight_shares_csv(
        self,
        opt_result: OptimizationResult,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export fortnight (half-month) distribution shares and energy balance per CUPS as CSV."""
        from src.config import get_precision

        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_fortnight_shares.csv"

        rows: list[dict[str, object]] = []
        source_results = (
            opt_result.fortnight_results
            if opt_result.fortnight_results
            else opt_result.monthly_results
        )
        for f_res in source_results:
            if not f_res.has_data:
                continue
            raw_period = str(f_res.month)
            if "-" in raw_period:
                parts = raw_period.split("-")
                if len(parts) == 2 and len(parts[0]) == 2:
                    month_val = parts[0]
                    try:
                        fortnight_val: int | str = int(parts[1].lstrip("Ff"))
                    except ValueError:
                        fortnight_val = parts[1]
                elif len(parts) >= 3:
                    month_val = f"{parts[0]}-{parts[1]}"
                    try:
                        fortnight_val = int(parts[2].lstrip("Ff"))
                    except ValueError:
                        fortnight_val = parts[2]
                else:
                    month_val = raw_period
                    fortnight_val = 1
            else:
                month_val = raw_period
                fortnight_val = 1

            for c in f_res.cups_metrics:
                use_val = c.use or opt_result.cups_uses.get(c.cups, "")
                rows.append(
                    {
                        "month": month_val,
                        "fortnight": fortnight_val,
                        "cups": c.cups,
                        "use": use_val,
                        "consumption_kwh": round(c.consumption_kwh, 2),
                        "generation_kwh": round(f_res.total_generation_kwh, 2),
                        "share_pct": f"{c.beta * 100:.{prec}f}%".replace(".", self.decimal_char),
                        "self_consumed_kwh": round(c.self_consumed_kwh, 2),
                        "surplus_kwh": round(c.surplus_kwh, 2),
                        "grid_demand_kwh": round(c.grid_demand_kwh, 2),
                    }
                )

        columns = [
            "month",
            "fortnight",
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
            sort_cols = [col for col in ["month", "fortnight", "use", "cups"] if col in df.columns]
            df = df.sort_values(
                by=sort_cols,
                key=lambda col: col.astype(str).str.lower() if col.name in ("use", "cups") else col,
                ascending=[True] * len(sort_cols),
            ).reset_index(drop=True)

        df = _sanitize_dataframe_strings(df)
        df.to_csv(file_path, index=False, sep=self.delimiter, decimal=self.decimal_char)
        return file_path

    def export_fortnight_shares_lite_csv(
        self,
        opt_result: OptimizationResult,
        precision: int | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export lite fortnight distribution shares matrix (CUPS in Y, Fortnights 01-1..12-2 in X) as CSV."""
        from src.config import get_precision

        prec = get_precision() if precision is None else precision
        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_fortnight_shares_lite.csv"

        calendar_fortnights = [f"{m:02d}-{f}" for m in range(1, 13) for f in (1, 2)]
        source_results = (
            opt_result.fortnight_results
            if opt_result.fortnight_results
            else opt_result.monthly_results
        )

        cups_set: list[str] = list(opt_result.cups_list)
        if not cups_set:
            seen: set[str] = set()
            for f_res in source_results:
                for cm in f_res.cups_metrics:
                    if cm.cups not in seen:
                        seen.add(cm.cups)
                        cups_set.append(cm.cups)

        uses_map: dict[str, str] = dict(opt_result.cups_uses)
        share_lookup: dict[tuple[str, str], str] = {}
        for f_res in source_results:
            if not f_res.has_data:
                continue
            raw_period = str(f_res.month)
            if "-" in raw_period:
                parts = raw_period.split("-")
                if len(parts) == 2 and len(parts[0]) == 2:
                    f_keys = [f"{parts[0]}-{parts[1].lstrip('Ff')}"]
                elif len(parts) >= 3:
                    f_keys = [f"{parts[1]}-{parts[2].lstrip('Ff')}"]
                else:
                    m_two = raw_period[-2:] if len(raw_period) >= 2 else f"{int(raw_period):02d}"
                    f_keys = [f"{m_two}-1", f"{m_two}-2"]
            else:
                m_two = raw_period[-2:] if len(raw_period) >= 2 else f"{int(raw_period):02d}"
                f_keys = [f"{m_two}-1", f"{m_two}-2"]

            for cm in f_res.cups_metrics:
                if cm.use and not uses_map.get(cm.cups):
                    uses_map[cm.cups] = cm.use
                formatted_pct = f"{cm.beta * 100:.{prec}f}%".replace(".", self.decimal_char)
                for fk in f_keys:
                    share_lookup[(cm.cups, fk)] = formatted_pct

        rows: list[dict[str, object]] = []
        for cups_id in cups_set:
            use_val = uses_map.get(cups_id, "")
            row: dict[str, object] = {
                "cups": cups_id,
                "use": use_val,
            }
            for f_str in calendar_fortnights:
                row[f_str] = share_lookup.get((cups_id, f_str), "")
            rows.append(row)

        columns = ["cups", "use", *calendar_fortnights]
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df = df.sort_values(
                by=["use", "cups"],
                key=lambda col: col.astype(str).str.lower(),
                ascending=[True, True],
            ).reset_index(drop=True)

        df = _sanitize_dataframe_strings(df)
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
            if not df.attrs.get("_sorted_ts_use_cups"):
                sort_cols = [c for c in ["timestamp", "use", "cups"] if c in df.columns]
                df = df.sort_values(
                    by=sort_cols,
                    key=lambda col: (
                        col.map({v: str(v).lower() for v in col.unique()})
                        if col.name in ("use", "cups")
                        else col
                    ),
                    ascending=[True] * len(sort_cols),
                ).reset_index(drop=True)

            if self.decimal_char != ".":
                for col in ["share_pct", "estimated_share_pct"]:
                    if col in df.columns:
                        df[col] = (
                            df[col].astype(str).str.replace(".", self.decimal_char, regex=False)
                        )

        df = _sanitize_dataframe_strings(df)
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
        story_context: StoryReportContext | None = None,
    ) -> list[Path]:
        """Execute exports according to the specified format flag.

        Supported formats: 'all', 'table', 'csv', 'html'.
        """
        fmt = formats.lower().strip()
        if fmt in ("table", "none"):
            return []

        exported: list[Path] = []

        if fmt in ("all", "csv", "html") and (
            not opt_result.fortnight_results and aligned_dataset is not None
        ):
            from src.optimization.engine import DistributionOptimizer
            from src.optimization.models import OptimizationStrategy

            opt_result.fortnight_results = DistributionOptimizer._evaluate_calendar_fortnights(
                aligned_dataset=aligned_dataset,
                cups_list=aligned_dataset.cups_list,
                strategy=OptimizationStrategy(opt_result.strategy),
                precision=precision or 0,
                cups_uses=opt_result.cups_uses,
                constraints=opt_result.constraints,
            )

        if fmt in ("all", "csv"):
            exported.append(self.export_monthly_shares_csv(opt_result, precision=precision))
            exported.append(self.export_monthly_shares_lite_csv(opt_result, precision=precision))
            exported.append(self.export_fortnight_shares_csv(opt_result, precision=precision))
            exported.append(self.export_fortnight_shares_lite_csv(opt_result, precision=precision))
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
                    story_context=story_context,
                    aligned_dataset=aligned_dataset,
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
        story_context: StoryReportContext | None = None,
        aligned_dataset: AlignedDataset | None = None,
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
            story_context=story_context,
            aligned_dataset=aligned_dataset,
        )
        file_path.write_text(html_content, encoding="utf-8")
        return file_path

    def export_consumption_summary_markdown(
        self,
        summary: CommunityConsumptionSummary,
        lang: str | None = None,
        year_filter: int | None = None,
        cups_filter: str | None = None,
        view_mode: str = "all",
        timestamp: str | None = None,
    ) -> Path:
        """Export a timestamped Markdown report for community consumption and fair-share analytics."""
        ts = timestamp or self.timestamp
        if year_filter is not None:
            filename = f"{ts}_summary_{year_filter}.md"
        elif cups_filter:
            filename = f"{ts}_summary_{cups_filter}.md"
        else:
            filename = f"{ts}_community_summary.md"

        report_path = self.output_dir / filename
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app_version = get_version()
        include_use = any(s.use for s in summary.overall_cups_shares) or any(
            bool(v) for v in summary.cups_uses.values()
        )

        lines: list[str] = [
            t("summary_md_doc_title", lang=lang),
            "",
            f"> {t('summary_md_generated_at', lang=lang, datetime=generated_at)} | "
            f"**{t('summary_md_version_label', lang=lang)}:** `{app_version}`",
            "",
            t("summary_md_section_overview", lang=lang),
            "",
            f"| {t('summary_md_metric_col', lang=lang)} | {t('summary_md_value_col', lang=lang)} |",
            "| :--- | :--- |",
            f"| {t('summary_md_version_label', lang=lang)} | `{app_version}` |",
            f"| {t('summary_total_consumption', lang=lang).rstrip(':')} | **{format_kwh(summary.total_community_kwh)}** |",
            f"| {t('summary_active_cups', lang=lang).rstrip(':')} | {summary.unique_cups_count} |",
            f"| {t('summary_date_range', lang=lang).rstrip(':')} | {summary.date_min} to {summary.date_max} |",
            f"| {t('summary_peak_month', lang=lang).rstrip(':')} | {summary.peak_month_label} ({format_kwh(summary.peak_month_kwh)}) |",
            f"| {t('summary_total_readings', lang=lang).rstrip(':')} | {summary.total_readings:,} |",
            "",
        ]

        if view_mode in ("all", "annual") and not cups_filter:
            lines.append(t("summary_md_section_annual", lang=lang))
            lines.append("")
            years_to_display = (
                [year_filter]
                if year_filter is not None and year_filter in summary.annual_summaries
                else sorted(summary.annual_summaries.keys())
            )
            for year in years_to_display:
                annual = summary.annual_summaries[year]
                lines.append(f"### {t('summary_annual_title', lang=lang, year=year)}")
                lines.append(
                    f"*{t('summary_community_total_label', lang=lang, total=format_kwh(annual.community_total_kwh))}*"
                )
                lines.append("")
                _append_markdown_shares_table(
                    lines=lines,
                    shares=annual.cups_shares,
                    total_kwh=annual.community_total_kwh,
                    include_use=include_use,
                    lang=lang,
                )

        filtered_months = summary.monthly_summaries
        if year_filter is not None:
            filtered_months = [m for m in filtered_months if m.year == year_filter]

        if view_mode in ("all", "monthly") and not cups_filter and filtered_months:
            lines.append(t("summary_md_section_timeline", lang=lang))
            lines.append("")
            lines.append(
                f"| {t('summary_col_period', lang=lang)} | {t('summary_col_community_total', lang=lang)} | "
                f"{t('summary_col_top_cups', lang=lang)} | {t('summary_col_top_share', lang=lang)} | "
                f"{t('summary_col_distribution', lang=lang)} |"
            )
            lines.append("| :---: | :---: | :--- | :---: | :--- |")
            for month_data in filtered_months:
                top = month_data.top_consumer
                lines.append(
                    f"| {month_data.period_label} | {format_kwh(month_data.community_total_kwh)} | "
                    f"`{top.cups}` | {format_pct(top.share_pct)} | {_make_ascii_bar(top.share_pct)} |"
                )
            lines.append("")

            lines.append(t("summary_md_section_monthly", lang=lang))
            lines.append("")
            for month_data in filtered_months:
                lines.append(
                    f"### {t('summary_period_title', lang=lang, period=month_data.period_label)}"
                )
                lines.append(
                    f"*{t('summary_community_total_label', lang=lang, total=format_kwh(month_data.community_total_kwh))}*"
                )
                lines.append("")
                _append_markdown_shares_table(
                    lines=lines,
                    shares=month_data.cups_shares,
                    total_kwh=month_data.community_total_kwh,
                    include_use=include_use,
                    lang=lang,
                )

        if cups_filter:
            use_label = summary.cups_uses.get(cups_filter, "")
            title_cups = f"{cups_filter} ({use_label})" if use_label else cups_filter
            lines.append(f"## {t('summary_cups_trajectory_title', lang=lang, cups=title_cups)}")
            lines.append("")
            lines.append(
                f"| {t('summary_col_period', lang=lang)} | {t('summary_col_cups_kwh', lang=lang)} | "
                f"{t('summary_col_community_kwh', lang=lang)} | {t('summary_col_share', lang=lang)} | "
                f"{t('summary_col_distribution', lang=lang)} |"
            )
            lines.append("| :---: | :---: | :---: | :---: | :--- |")
            total_c = 0.0
            total_comm = 0.0
            for month_data in filtered_months:
                match = next((s for s in month_data.cups_shares if s.cups == cups_filter), None)
                if match:
                    total_c += match.consumption_kwh
                    total_comm += month_data.community_total_kwh
                    lines.append(
                        f"| {month_data.period_label} | {format_kwh(match.consumption_kwh)} | "
                        f"{format_kwh(month_data.community_total_kwh)} | {format_pct(match.share_pct)} | "
                        f"{_make_ascii_bar(match.share_pct)} |"
                    )
            ov_share = (total_c / total_comm * 100.0) if total_comm > 0.0 else 0.0
            lines.append(
                f"| **{t('summary_col_total', lang=lang)}** | **{format_kwh(total_c)}** | "
                f"**{format_kwh(total_comm)}** | **{format_pct(ov_share)}** | |"
            )
            lines.append("")

        lines.append(t("summary_md_section_insights", lang=lang))
        lines.append("")
        top_overall = summary.overall_cups_shares[0] if summary.overall_cups_shares else None
        zero_consumers = [s.cups for s in summary.overall_cups_shares if s.consumption_kwh < 1.0]

        if top_overall and top_overall.share_pct > 50.0:
            clean_dom = _strip_rich_markup(
                t(
                    "summary_dominant_insight",
                    lang=lang,
                    cups=top_overall.cups,
                    pct=f"{top_overall.share_pct:.2f}",
                    kwh=format_kwh(top_overall.consumption_kwh),
                )
            ).lstrip("• ")
            lines.append(f"- {clean_dom}")
        if zero_consumers:
            clean_zero = _strip_rich_markup(
                t(
                    "summary_zero_insight",
                    lang=lang,
                    count=len(zero_consumers),
                    cups=", ".join(zero_consumers),
                )
            ).lstrip("• ")
            lines.append(f"- {clean_zero}")
        clean_season = _strip_rich_markup(
            t(
                "summary_seasonality_insight",
                lang=lang,
                peak_month=summary.peak_month_label,
                peak_kwh=format_kwh(summary.peak_month_kwh),
                lowest_month=summary.lowest_month_label,
                lowest_kwh=format_kwh(summary.lowest_month_kwh),
            )
        ).lstrip("• ")
        lines.append(f"- {clean_season}")
        lines.append("")

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path

    def export_comparison_markdown(
        self,
        comparison: ComparisonSummary,
        lang: str | None = None,
        chart_paths: list[Path] | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export a timestamped multi-year comparison Markdown report with SVG chart links."""
        ts = timestamp or self.timestamp
        years_slug = "_".join(map(str, comparison.years))
        report_path = self.output_dir / f"{ts}_comparison_{years_slug}.md"

        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app_version = get_version()
        years_title = " vs ".join(map(str, comparison.years))

        lines: list[str] = [
            t("compare_md_title", lang=lang, years=years_title),
            "",
            f"> {t('summary_md_generated_at', lang=lang, datetime=generated_at)} | "
            f"**{t('summary_md_version_label', lang=lang)}:** `{app_version}`",
            "",
            t("compare_md_overview", lang=lang),
            "",
            f"| {t('summary_md_metric_col', lang=lang)} | {t('summary_md_value_col', lang=lang)} |",
            "| :--- | :--- |",
            f"| {t('summary_md_version_label', lang=lang)} | `{app_version}` |",
            f"| {t('compare_years_label', lang=lang).rstrip(':')} | **{', '.join(map(str, comparison.years))}** |",
        ]

        if comparison.comparable_months:
            first_m = get_month_name(min(comparison.comparable_months), lang=lang, short=True)
            last_m = get_month_name(max(comparison.comparable_months), lang=lang, short=True)
            period_str = f"{first_m} - {last_m}"
            lines.append(
                f"| {t('compare_comparable_period_note', lang=lang, period=period_str, months=len(comparison.comparable_months)).split(':')[0]} | "
                f"**{period_str} ({len(comparison.comparable_months)} {t('compare_month_col', lang=lang).lower()})** |"
            )

        for year in comparison.years:
            raw_kwh = comparison.annual_totals[year]
            comp_kwh = comparison.comparable_annual_totals.get(year, raw_kwh)
            metric_lbl = t("compare_md_community_consumption", lang=lang, year=year)
            if comparison.excluded_months and comp_kwh != raw_kwh:
                full_note = t("compare_md_full_year_suffix", lang=lang, total=format_kwh(raw_kwh))
                lines.append(f"| {metric_lbl} | **{format_kwh(comp_kwh)}** ({full_note}) |")
            else:
                lines.append(f"| {metric_lbl} | **{format_kwh(raw_kwh)}** |")

        if comparison.total_diff_kwh is not None and comparison.total_pct_change is not None:
            lines.append(
                f"| {t('compare_overall_change', lang=lang).rstrip(':')} | "
                f"**{_format_signed_kwh(comparison.total_diff_kwh, include_unit=True)} "
                f"({_format_signed_pct(comparison.total_pct_change, decimals=2)})** |"
            )
        lines.append("")

        charts_dir = self.output_dir / "charts"
        chart_set = {Path(p).resolve() for p in chart_paths} if chart_paths else None

        comm_chart = charts_dir / f"community_monthly_{years_slug}.svg"
        if comm_chart.exists() and (chart_set is None or comm_chart.resolve() in chart_set):
            lines.append(
                f"![{t('chart_community_title', lang=lang)}](charts/community_monthly_{years_slug}.svg)"
            )
            lines.append("")

        # Section 2: Month-by-Month Comparison Table
        lines.append(t("compare_md_monthly", lang=lang))
        lines.append("")
        year_headers = " | ".join(f"{y} (kWh)" for y in comparison.years)
        lines.append(
            f"| {t('compare_month_col', lang=lang)} | {year_headers} | "
            f"{t('compare_diff_col', lang=lang)} | {t('compare_var_col', lang=lang)} | "
            f"{t('compare_trend_col', lang=lang)} |"
        )
        col_dashes = " | ".join(
            ":---:" if idx == 0 else "---:" for idx in range(len(comparison.years) + 4)
        )
        lines.append(f"| {col_dashes} |")

        for m in comparison.monthly_comparisons:
            m_name = get_month_name(m.month, lang=lang, short=True)
            year_vals: list[str] = []
            for year in comparison.years:
                val = m.yearly_kwh.get(year)
                status = m.year_status.get(year, "complete")
                if status == "no_data" or val is None:
                    year_vals.append(t("compare_no_data", lang=lang))
                elif status == "incomplete":
                    year_vals.append(f"{val:,.2f}*")
                else:
                    year_vals.append(f"{val:,.2f}")

            if m.diff_kwh is not None:
                m_diff = _format_signed_kwh(m.diff_kwh)
                m_pct = _format_signed_pct(m.pct_change, decimals=1)
                m_trend = (
                    t("compare_trend_reduced", lang=lang)
                    if (m.pct_change is not None and m.pct_change < 0.0)
                    else t("compare_trend_increased", lang=lang)
                    if (m.pct_change is not None and m.pct_change > 0.0)
                    else t("compare_trend_equal", lang=lang)
                )
            else:
                m_diff = "—"
                m_pct = "—"
                m_trend = t("compare_no_data", lang=lang) if not m.is_complete else "—"

            lines.append(f"| {m_name} | {' | '.join(year_vals)} | {m_diff} | {m_pct} | {m_trend} |")

        if comparison.comparable_months:
            first_m = get_month_name(min(comparison.comparable_months), lang=lang, short=True)
            last_m = get_month_name(max(comparison.comparable_months), lang=lang, short=True)
            tot_label = (
                f"**Total ({first_m}-{last_m})**"
                if len(comparison.comparable_months) < 12
                else "**Total**"
            )
            total_vals = " | ".join(
                f"**{comparison.comparable_annual_totals[y]:,.2f}**" for y in comparison.years
            )
            tot_diff_str = (
                f"**{_format_signed_kwh(comparison.total_diff_kwh, include_unit=True)}**"
                if comparison.total_diff_kwh is not None
                else "**—**"
            )
            tot_pct_str = (
                f"**{_format_signed_pct(comparison.total_pct_change, decimals=2)}**"
                if comparison.total_pct_change is not None
                else "**—**"
            )
            lines.append(f"| {tot_label} | {total_vals} | {tot_diff_str} | {tot_pct_str} | |")
        lines.append("")

        # Section 3: Individual CUPS Evolution
        if comparison.cups_comparisons:
            lines.append(t("compare_md_cups", lang=lang))
            lines.append("")
            earliest_y = comparison.years[0]
            latest_y = comparison.years[-1]
            include_use = any(bool(c.use) for c in comparison.cups_comparisons)
            if include_use:
                lines.append(
                    f"| {t('summary_col_rank', lang=lang)} | {t('compare_cups_col', lang=lang)} | "
                    f"{t('summary_col_use', lang=lang)} | {earliest_y} (kWh) | {latest_y} (kWh) | "
                    f"{t('compare_diff_col', lang=lang)} | {t('compare_var_col', lang=lang)} |"
                )
                lines.append("| ---: | :--- | :--- | ---: | ---: | ---: | ---: |")
            else:
                lines.append(
                    f"| {t('summary_col_rank', lang=lang)} | {t('compare_cups_col', lang=lang)} | "
                    f"{earliest_y} (kWh) | {latest_y} (kWh) | "
                    f"{t('compare_diff_col', lang=lang)} | {t('compare_var_col', lang=lang)} |"
                )
                lines.append("| ---: | :--- | ---: | ---: | ---: | ---: |")

            for idx, c in enumerate(comparison.cups_comparisons, start=1):
                c_base = c.yearly_kwh.get(earliest_y, 0.0)
                c_target = c.yearly_kwh.get(latest_y, 0.0)
                c_diff = _format_signed_kwh(c.diff_kwh)
                c_pct = _format_signed_pct(c.pct_change, decimals=1)
                if include_use:
                    lines.append(
                        f"| {idx} | `{c.cups}` | {c.use or '—'} | {c_base:,.2f} | {c_target:,.2f} | {c_diff} | {c_pct} |"
                    )
                else:
                    lines.append(
                        f"| {idx} | `{c.cups}` | {c_base:,.2f} | {c_target:,.2f} | {c_diff} | {c_pct} |"
                    )
            lines.append("")

        # Section 4: Visual Monthly Trajectories by CUPS
        cups_charts = [
            (cups_id, charts_dir / f"cups_{cups_id}_{years_slug}.svg")
            for cups_id in comparison.cups_monthly_data
            if (charts_dir / f"cups_{cups_id}_{years_slug}.svg").exists()
            and (
                chart_set is None
                or (charts_dir / f"cups_{cups_id}_{years_slug}.svg").resolve() in chart_set
            )
        ]
        if cups_charts:
            lines.append(t("compare_md_charts", lang=lang))
            lines.append("")
            for cups_id, chart_file in cups_charts:
                use_val = comparison.cups_uses.get(cups_id, "")
                heading = f"`{cups_id}` ({use_val})" if use_val else f"`{cups_id}`"
                lines.append(f"### {heading}")
                lines.append("")
                lines.append(f"![{cups_id} Monthly Comparison](charts/{chart_file.name})")
                lines.append("")

        # Section 5: Key Insights
        lines.append(t("compare_md_insights", lang=lang))
        lines.append("")
        if comparison.max_decrease_month and comparison.max_decrease_month.diff_kwh is not None:
            m_name = get_month_name(comparison.max_decrease_month.month, lang=lang)
            pct_val = abs(comparison.max_decrease_month.pct_change or 0.0)
            lines.append(
                f"- **{t('compare_max_decrease', lang=lang).rstrip(':')}:** {m_name} "
                f"(-{pct_val:.1f}% / -{format_kwh(abs(comparison.max_decrease_month.diff_kwh))})"
            )
        if comparison.max_increase_month and comparison.max_increase_month.diff_kwh is not None:
            m_name = get_month_name(comparison.max_increase_month.month, lang=lang)
            pct_val = comparison.max_increase_month.pct_change or 0.0
            lines.append(
                f"- **{t('compare_max_increase', lang=lang).rstrip(':')}:** {m_name} "
                f"(+{pct_val:.1f}% / +{format_kwh(comparison.max_increase_month.diff_kwh)})"
            )
        if comparison.top_saving_cups:
            saver = comparison.top_saving_cups
            saver_lbl = f"`{saver.cups}` ({saver.use})" if saver.use else f"`{saver.cups}`"
            lines.append(
                f"- **{t('compare_top_saver', lang=lang).rstrip(':')}:** {saver_lbl} "
                f"(-{format_kwh(abs(saver.diff_kwh))})"
            )
        if comparison.top_increasing_cups:
            inc = comparison.top_increasing_cups
            inc_lbl = f"`{inc.cups}` ({inc.use})" if inc.use else f"`{inc.cups}`"
            lines.append(
                f"- **{t('compare_top_increaser', lang=lang).rstrip(':')}:** {inc_lbl} "
                f"(+{format_kwh(inc.diff_kwh)})"
            )
        if comparison.excluded_months:
            ex_names = ", ".join(
                get_month_name(m, lang=lang, short=True) for m in comparison.excluded_months
            )
            lines.append(
                f"- **{t('compare_no_data', lang=lang)}:** "
                f"{t('compare_excluded_months_note', lang=lang, count=len(comparison.excluded_months), months=ex_names)}"
            )
        lines.append("")

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path

    def export_comparison_html(
        self,
        comparison: ComparisonSummary,
        lang: str | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Export standalone interactive HTML report for multi-year consumption comparison."""
        from src.presentation.html_report import generate_comparison_html_report

        ts = timestamp or self.timestamp
        file_path = self.output_dir / f"{ts}_esd_comparison_report.html"
        html_content = generate_comparison_html_report(comparison, lang=lang)
        file_path.write_text(html_content, encoding="utf-8")
        return file_path
