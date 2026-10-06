"""Unit tests for multi-format report exports."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.ingestion.schema import IngestionSummary
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    OptimizationResult,
    OptimizationStrategy,
)
from src.presentation.export import (
    export_all,
    export_coefficients_csv,
    export_coefficients_matrix_csv,
    export_results_json,
    export_summary_markdown,
)


def create_dummy_optimization_result() -> tuple[OptimizationResult, IngestionSummary]:
    cups_list = ["ES0021000000000001AA", "ES0021000000000002BB"]
    c1 = CupsMonthlyMetrics(
        cups="ES0021000000000001AA",
        month="2026-05",
        beta=0.6,
        consumption_kwh=500.0,
        generation_allocated_kwh=600.0,
        self_consumed_kwh=480.0,
        surplus_kwh=120.0,
        grid_demand_kwh=20.0,
        self_consumption_rate=80.0,
        solar_coverage_rate=96.0,
    )
    c2 = CupsMonthlyMetrics(
        cups="ES0021000000000002BB",
        month="2026-05",
        beta=0.4,
        consumption_kwh=300.0,
        generation_allocated_kwh=400.0,
        self_consumed_kwh=270.0,
        surplus_kwh=130.0,
        grid_demand_kwh=30.0,
        self_consumption_rate=67.5,
        solar_coverage_rate=90.0,
    )
    m1 = CommunityMonthlyMetrics(
        month="2026-05",
        strategy=OptimizationStrategy.OPTIMAL,
        total_generation_kwh=1000.0,
        total_consumption_kwh=800.0,
        total_self_consumed_kwh=750.0,
        total_surplus_kwh=250.0,
        total_grid_demand_kwh=50.0,
        self_consumption_rate=75.0,
        solar_coverage_rate=93.75,
        beta_sum=1.0,
        cups_metrics=[c1, c2],
    )

    result = OptimizationResult(
        strategy=OptimizationStrategy.OPTIMAL,
        monthly_results=[m1],
        total_summary=m1,
        baselines={},
    )

    summary = IngestionSummary(
        cups_count=2,
        cups_list=cups_list,
        start_time="2026-05-01 00:00:00",
        end_time="2026-05-31 23:00:00",
        total_hours=744,
        consumption_files_loaded=2,
        generation_files_loaded=1,
    )

    return result, summary


def test_export_csv(tmp_path: Path) -> None:
    opt_result, _ = create_dummy_optimization_result()
    csv_path = export_coefficients_csv(opt_result, tmp_path, timestamp="20260531_120000")
    assert csv_path.exists()

    df = pd.read_csv(csv_path, sep=";")
    assert len(df) == 2
    assert "month" in df.columns
    assert "cups" in df.columns
    assert "beta" in df.columns
    assert df["beta"].sum() == 1.0


def test_export_coefficients_matrix_csv(tmp_path: Path) -> None:
    opt_result, _ = create_dummy_optimization_result()
    csv_path = export_coefficients_matrix_csv(
        opt_result, tmp_path, precision=1, timestamp="20260531_120000"
    )
    assert csv_path.exists()
    assert csv_path.name == "20260531_120000_esd_coefficients_matrix.csv"

    df = pd.read_csv(csv_path, sep=";")
    # 2 CUPS rows + 1 TOTAL row
    assert len(df) == 3
    expected_cols = ["cups"] + [f"{m:02d}" for m in range(1, 13)] + ["annual_average"]
    assert list(df.columns) == expected_cols

    # Verify CUPS rows
    assert df.iloc[0]["cups"] == "ES0021000000000001AA"
    assert df.iloc[0]["05"] == "60.0%"
    assert df.iloc[0]["01"] == "—"
    assert df.iloc[1]["cups"] == "ES0021000000000002BB"
    assert df.iloc[1]["05"] == "40.0%"
    assert df.iloc[1]["01"] == "—"

    # Verify TOTAL row
    assert df.iloc[2]["cups"] == "TOTAL"
    assert df.iloc[2]["05"] == "100.0%"
    assert df.iloc[2]["annual_average"] == "100.0%"


def test_export_json(tmp_path: Path) -> None:
    opt_result, meta = create_dummy_optimization_result()
    json_path = export_results_json(opt_result, meta, tmp_path, timestamp="20260531_120000")
    assert json_path.exists()

    with open(json_path) as f:
        data = json.load(f)

    assert data["primary_strategy"] == "optimal"
    assert data["ingestion_metadata"]["cups_count"] == 2
    assert len(data["monthly_results"]) == 1
    assert data["monthly_results"][0]["month"] == "2026-05"


def test_export_markdown_english(tmp_path: Path) -> None:
    opt_result, meta = create_dummy_optimization_result()
    md_path = export_summary_markdown(
        opt_result, meta, tmp_path, lang="en", precision=1, timestamp="20260531_120000"
    )
    assert md_path.exists()

    content = md_path.read_text(encoding="utf-8")
    assert "Electricity Share Distributor" in content
    assert "Collective Community Overview" in content
    assert "Month-by-Month Energy Trajectory" in content
    assert "Regulatory Distribution Coefficients Matrix (RD 244/2019)" in content
    assert "Community Optimization Insights & Generation Dynamics" in content
    assert "Diurnal Alignment" in content
    assert "Proposed Monthly Distribution Coefficients" in content
    assert "Participating CUPS" in content
    assert "ES0021000000000001AA" in content
    assert "TOTAL (RD 244/2019)" in content
    assert "100.0%" in content


def test_export_markdown_spanish(tmp_path: Path) -> None:
    opt_result, meta = create_dummy_optimization_result()
    md_path = export_summary_markdown(
        opt_result, meta, tmp_path, lang="es", precision=1, timestamp="20260531_120000"
    )
    assert md_path.exists()

    content = md_path.read_text(encoding="utf-8")
    assert "Distribuidor de Energía Compartida" in content
    assert "Resumen de la Comunidad de Autoconsumo Colectivo" in content
    assert "Trayectoria Energética Mensual" in content
    assert "Matriz Regulatoria de Coeficientes de Reparto (RD 244/2019)" in content
    assert "Análisis de Rendimiento y Dinámica de Generación" in content
    assert "Coincidencia Diurna" in content
    assert "Propuesta de Coeficientes de Reparto Mensuales" in content
    assert "Puntos de Suministro (CUPS)" in content
    assert "ES0021000000000001AA" in content
    assert "TOTAL (RD 244/2019)" in content
    assert "100.0%" in content


def test_export_all_filtering(tmp_path: Path) -> None:
    opt_result, meta = create_dummy_optimization_result()

    # CSV exports both detailed metrics and consolidated matrix CSV
    paths_csv = export_all(opt_result, meta, tmp_path, formats="csv")
    assert len(paths_csv) == 2
    assert all(p.suffix == ".csv" for p in paths_csv)
    file_names = [p.name for p in paths_csv]
    assert any("_esd_coefficients.csv" in n for n in file_names)
    assert any("_esd_coefficients_matrix.csv" in n for n in file_names)

    # None
    paths_none = export_all(opt_result, meta, tmp_path, formats="table")
    assert len(paths_none) == 0
