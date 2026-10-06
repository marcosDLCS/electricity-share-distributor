"""End-to-end integration tests using synthetic community datasets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.ingestion.aligner import TimeSeriesAligner
from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.generation import HuaweiGenerationLoader
from src.optimization.engine import DistributionOptimizer
from src.optimization.models import OptimizationStrategy
from src.presentation.export import export_all


def create_synthetic_environment(tmp_path: Path) -> tuple[Path, Path]:
    """Generate synthetic DATADIS CSVs and Huawei FusionSolar XLSX."""
    consumption_dir = tmp_path / "consumption"
    generation_dir = tmp_path / "generation"
    consumption_dir.mkdir(parents=True)
    generation_dir.mkdir(parents=True)

    # Generate full month of hourly data in May 2026 (744 hours)
    dates = pd.date_range("2026-05-01 00:00:00", "2026-05-31 23:00:00", freq="h")

    # 3 Synthetic CUPS:
    # CUPS 1: Diurnal consumer (offices / stores) - heavy daytime demand
    # CUPS 2: Nocturnal consumer (residents / night shift) - heavy evening demand
    # CUPS 3: Small flat - low baseline demand
    cups_definitions = [
        ("ES0021000000000001AA", "diurnal"),
        ("ES0021000000000002BB", "nocturnal"),
        ("ES0021000000000003CC", "low_constant"),
    ]

    for cups, profile in cups_definitions:
        rows = []
        for dt in dates:
            h = dt.hour  # 0 to 23
            # In DATADIS, hour 00:00-01:00 is labeled as '01:00'
            datadis_hour = f"{h + 1:02d}:00"
            date_str = dt.strftime("%Y/%m/%d")

            if profile == "diurnal":
                # High between 09:00 and 18:00
                kwh = 2.5 if 9 <= h <= 18 else 0.2
            elif profile == "nocturnal":
                # High between 20:00 and 06:00
                kwh = 3.0 if (h >= 20 or h <= 6) else 0.3
            else:
                kwh = 0.4

            # Add minor noise
            kwh_str = f"{kwh:.3f}".replace(".", ",")
            rows.append(f"{cups};{date_str};{datadis_hour};{kwh_str};IBERDROLA;R")

        csv_content = "CUPS;Fecha;Hora;Consumo_kWh;Metodo_obtencion;Tipo_lectura\n" + "\n".join(
            rows
        )
        (consumption_dir / f"{cups}.csv").write_text(csv_content, encoding="utf-8")

    # Generate Huawei FusionSolar Excel export
    # Row 1: Title, Row 2: Table headers, Row 3+: Data rows
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Informe de rendimiento FV - PLANTA SOLAR RESIDENCIAL", "", ""])
    ws.append(["Período estadístico", "Rendimiento FV (kWh)", "Rendimiento del inversor (kWh)"])

    for dt in dates:
        h = dt.hour
        if 6 <= h <= 20:
            solar_kwh = float(15.0 * np.sin(np.pi * (h - 6) / 14.0))
        else:
            solar_kwh = 0.0

        ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        ws.append([ts_str, round(solar_kwh, 3), round(solar_kwh, 3)])

    excel_path = generation_dir / "fusionsolar_export_may2026.xlsx"
    wb.save(excel_path)

    return consumption_dir, generation_dir


def test_synthetic_community_optimization(tmp_path: Path) -> None:
    c_dir, g_dir = create_synthetic_environment(tmp_path)

    # 1. Ingest
    c_loader = DatadisConsumptionLoader(c_dir)
    g_loader = HuaweiGenerationLoader(g_dir)
    c_df = c_loader.load_all()
    g_df = g_loader.load_all()

    assert len(c_loader.discover_files()) == 3
    assert len(g_loader.discover_files()) == 1

    # 2. Align
    aligner = TimeSeriesAligner(
        consumption_df=c_df,
        generation_df=g_df,
        consumption_files_loaded=3,
        generation_files_loaded=1,
    )
    aligned = aligner.align()
    assert len(aligned.data) == 744
    assert aligned.metadata.cups_count == 3

    # 3. Optimize (Optimal strategy)
    optimizer = DistributionOptimizer()
    res = optimizer.optimize_dataset(
        aligned,
        strategy=OptimizationStrategy.OPTIMAL,
        include_baselines=True,
    )

    assert len(res.monthly_results) == 12
    m = next(res_m for res_m in res.monthly_results if res_m.month == "05")
    assert m.has_data is True

    # Verify RD 244/2019 Domain Invariants
    # 1. Sum of betas <= 1.0001
    assert m.beta_sum <= 1.0001

    # 2. Optimal self-consumption >= equal allocation
    eq_res = res.baselines["equal"]
    assert m.total_self_consumed_kwh >= eq_res.total_summary.total_self_consumed_kwh

    # 3. Diurnal consumer receives highest share because generation is daytime
    c1 = next(c for c in m.cups_metrics if c.cups == "ES0021000000000001AA")
    c2 = next(c for c in m.cups_metrics if c.cups == "ES0021000000000002BB")
    assert c1.beta > c2.beta

    # 4. Conservation of energy per CUPS
    for c in m.cups_metrics:
        assert 0.0 <= c.beta <= 1.0
        # self_consumed + grid_demand == consumption (approx)
        assert abs((c.self_consumed_kwh + c.grid_demand_kwh) - c.consumption_kwh) < 1e-2
        # self_consumed + surplus == allocated_gen (approx)
        assert abs((c.self_consumed_kwh + c.surplus_kwh) - c.generation_allocated_kwh) < 1e-2

    # 4. Multi-format export (2 CSVs, 1 JSON, 1 Markdown)
    out_dir = tmp_path / "output"
    exported = export_all(res, aligned.metadata, out_dir, formats="all", lang="en")
    assert len(exported) == 4
    for p in exported:
        assert p.exists()
        assert p.stat().st_size > 0
