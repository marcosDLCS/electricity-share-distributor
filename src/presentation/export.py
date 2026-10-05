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
    from src.config import get_precision

    prec = get_precision() if precision is None else precision
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp or get_export_timestamp()
    file_path = out_dir / f"{ts}_esd_optimization_summary.md"

    tot = opt_result.total_summary

    lines = [
        f"# ☀️ Electricity Share Distributor (esd v{get_version()})",
        "",
        f"> **Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        "> **Regulatory Basis:** Real Decreto 244/2019 (*Autoconsumo Colectivo*, Spain)  ",
        f"> **Strategy:** `{opt_result.strategy}` (Linear Programming Max Collective Self-Consumption)  ",
        "",
        "---",
        "",
        "## 📊 Collective Community Overview",
        "",
        f"- **Participating CUPS:** {ingestion_summary.cups_count}",
        f"- **Date Range:** `{ingestion_summary.start_time}` ➔ `{ingestion_summary.end_time}`",
        f"- **Total Time Steps:** {ingestion_summary.total_hours:,} hours",
        f"- **Total Solar PV Generation:** **{tot.total_generation_kwh:,.2f} kWh**",
        f"- **Total Community Demand:** **{tot.total_consumption_kwh:,.2f} kWh**",
        f"- **Total Self-Consumed Energy:** **{tot.total_self_consumed_kwh:,.2f} kWh** ({tot.self_consumption_rate:.1f}% efficiency)",
        f"- **Total Solar Surplus Spilled:** **{tot.total_surplus_kwh:,.2f} kWh**",
        f"- **Solar Demand Coverage:** **{tot.solar_coverage_rate:.1f}%**",
        "",
        "---",
        "",
        "## 📈 Month-by-Month Energy Trajectory",
        "",
        "| Month | Solar Gen (kWh) | Demand (kWh) | Self-Consumed (kWh) | Surplus (kWh) | Grid (kWh) | Self-Cons % | Coverage % |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for m in opt_result.monthly_results:
        lines.append(
            f"| **{m.month}** | {m.total_generation_kwh:,.1f} | {m.total_consumption_kwh:,.1f} | "
            f"{m.total_self_consumed_kwh:,.1f} | {m.total_surplus_kwh:,.1f} | {m.total_grid_demand_kwh:,.1f} | "
            f"{m.self_consumption_rate:.1f}% | {m.solar_coverage_rate:.1f}% |"
        )

    lines.extend(
        [
            f"| **Total** | **{tot.total_generation_kwh:,.1f}** | **{tot.total_consumption_kwh:,.1f}** | "
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
                "## ⚖️ Allocation Strategy Comparison",
                "",
                "| Strategy | Self-Consumed (kWh) | Solar Surplus (kWh) | Efficiency % | vs Equal Gain |",
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
            f"| **Optimal (RD 244/2019 LP)** | **{tot.total_self_consumed_kwh:,.1f}** | "
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

    # Monthly breakdown tables
    lines.append("## 📅 Proposed Monthly Distribution Coefficients (β_i)")
    lines.append("")

    for m in opt_result.monthly_results:
        lines.append(f"### Month: `{m.month}` (Solar Gen: {m.total_generation_kwh:,.1f} kWh)")
        lines.append("")
        lines.append(
            "| CUPS | Beta (β) | Share % | Demand (kWh) | Allocated Solar (kWh) | Self-Consumed (kWh) | Surplus (kWh) | Grid (kWh) |",
        )
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
