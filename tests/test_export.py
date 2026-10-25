"""Unit tests for multi-format report exports."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.ingestion.schema import IngestionSummary
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    HourlyOptimizationResult,
    HourlyProfileMatrix,
    OptimizationResult,
    OptimizationStrategy,
)
from src.presentation.export import (
    ReportExporter,
    export_all,
    export_coefficients_csv,
    export_coefficients_matrix_csv,
    export_hourly_profile_matrix_csv,
    export_hourly_shares_csv,
    export_results_json,
    export_summary_markdown,
)


def create_dummy_optimization_result() -> tuple[OptimizationResult, IngestionSummary]:
    cups_list = ["ES0021000000000001AA", "ES0021000000000002BB"]
    c1 = CupsMonthlyMetrics(
        cups="ES0021000000000001AA",
        use="Aerotermia",
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
        use="Garaje",
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
        cups_uses={"ES0021000000000001AA": "Aerotermia", "ES0021000000000002BB": "Garaje"},
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

    df = pd.read_csv(csv_path, sep=";", decimal=",")
    assert len(df) == 2
    assert "month" in df.columns
    assert "cups" in df.columns
    assert "use" in df.columns
    assert "beta" in df.columns
    assert df["beta"].sum() == 1.0
    assert df.iloc[0]["use"] == "Aerotermia"
    assert df.iloc[1]["use"] == "Garaje"


def test_export_coefficients_matrix_csv(tmp_path: Path) -> None:
    opt_result, _ = create_dummy_optimization_result()
    csv_path = export_coefficients_matrix_csv(
        opt_result, tmp_path, precision=1, timestamp="20260531_120000"
    )
    assert csv_path.exists()
    assert csv_path.name == "20260531_120000_esd_coefficients_matrix.csv"

    df = pd.read_csv(csv_path, sep=";", decimal=",")
    # 2 CUPS rows + 1 TOTAL row
    assert len(df) == 3
    expected_cols = ["cups", "use"] + [f"{m:02d}" for m in range(1, 13)] + ["annual_average"]
    assert list(df.columns) == expected_cols

    # Verify CUPS rows
    assert df.iloc[0]["cups"] == "ES0021000000000001AA"
    assert df.iloc[0]["use"] == "Aerotermia"
    assert df.iloc[0]["05"] == "60,0%"
    assert df.iloc[0]["01"] == "—"
    assert df.iloc[1]["cups"] == "ES0021000000000002BB"
    assert df.iloc[1]["use"] == "Garaje"
    assert df.iloc[1]["05"] == "40,0%"
    assert df.iloc[1]["01"] == "—"

    # Verify TOTAL row
    assert df.iloc[2]["cups"] == "TOTAL"
    assert df.iloc[2]["use"] == "TOTAL"
    assert df.iloc[2]["05"] == "100,0%"
    assert df.iloc[2]["annual_average"] == "100,0%"


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


def test_export_hourly_files(tmp_path: Path) -> None:
    opt_result, meta = create_dummy_optimization_result()
    cups_list = ["ES0021000000000001AA", "ES0021000000000002BB"]
    hours = [f"{h:02d}" for h in range(24)]

    profile_matrix = HourlyProfileMatrix(
        cups_list=cups_list,
        hours=hours,
        matrix={
            cups_list[0]: dict.fromkeys(hours, 0.6),
            cups_list[1]: dict.fromkeys(hours, 0.4),
        },
        hourly_sums=dict.fromkeys(hours, 1.0),
        average_shares={cups_list[0]: 0.6, cups_list[1]: 0.4},
        average_sum=1.0,
    )
    ts_rows = []
    for h in hours:
        ts_rows.append(
            {
                "timestamp": f"2026-05-01 {h}:00:00",
                "hour": int(h),
                "cups": cups_list[0],
                "use": "Portal 1",
                "consumption_kwh": 2.4,
                "generation_kwh": 5.0,
                "share_pct": "60%",
                "estimated_share_pct": "60%",
                "solar_efficiency": 75,
            }
        )
        ts_rows.append(
            {
                "timestamp": f"2026-05-01 {h}:00:00",
                "hour": int(h),
                "cups": cups_list[1],
                "use": "Aerotermia",
                "consumption_kwh": 1.6,
                "generation_kwh": 5.0,
                "share_pct": "40%",
                "estimated_share_pct": "40%",
                "solar_efficiency": 75,
            }
        )
    ts_df = pd.DataFrame(ts_rows)
    opt_result.hourly_result = HourlyOptimizationResult(
        profile_matrix=profile_matrix,
        time_series_df=ts_df,
    )

    # Export hourly CSV files directly
    shares_path = export_hourly_shares_csv(opt_result, tmp_path, timestamp="20260531_120000")
    assert shares_path.exists()
    shares_content = shares_path.read_text(encoding="utf-8")
    assert (
        "timestamp;hour;cups;use;consumption_kwh;generation_kwh;share_pct;estimated_share_pct;solar_efficiency"
        in shares_content
    )
    assert "ES0021000000000001AA" in shares_content

    # Verify that within the same timestamp, Aerotermia appears before Portal 1
    lines = shares_content.strip().splitlines()
    assert len(lines) == 1 + (len(hours) * 2)
    # Line 1: Header, Line 2: 2026-05-01 00:00:00 with Aerotermia, Line 3: 2026-05-01 00:00:00 with Portal 1
    assert "Aerotermia" in lines[1]
    assert "Portal 1" in lines[2]

    matrix_path = export_hourly_profile_matrix_csv(
        opt_result, tmp_path, precision=0, timestamp="20260531_120000"
    )
    assert matrix_path.exists()
    matrix_content = matrix_path.read_text(encoding="utf-8")
    assert "cups;use;00;01;02" in matrix_content
    assert "TOTAL;TOTAL;100%;100%" in matrix_content

    # export_all with formats='csv' should export 4 CSVs
    exported = export_all(opt_result, meta, tmp_path, formats="csv")
    assert len(exported) == 4
    file_names = [p.name for p in exported]
    assert any("_esd_hourly_shares.csv" in n for n in file_names)
    assert any("_esd_hourly_profile_matrix.csv" in n for n in file_names)

    # export_all with json should serialize hourly profile
    json_paths = export_all(opt_result, meta, tmp_path, formats="json")
    assert len(json_paths) == 1
    with open(json_paths[0], encoding="utf-8") as f:
        data = json.load(f)
    assert "hourly_profile" in data
    assert data["hourly_profile"]["hours"] == hours

    # export_all with markdown should render hourly section in both ES and EN
    md_paths = export_all(opt_result, meta, tmp_path, formats="markdown")
    assert len(md_paths) == 2
    es_path = next(p for p in md_paths if "_es.md" in p.name)
    en_path = next(p for p in md_paths if "_en.md" in p.name)
    assert es_path.exists()
    assert en_path.exists()
    assert "Perfil Diario de Coeficientes de Reparto" in es_path.read_text(encoding="utf-8")
    assert "Diurnal Distribution Share Profile" in en_path.read_text(encoding="utf-8")


def test_export_csvs_semicolon_separator_comma_decimal(tmp_path: Path) -> None:
    """Verify that all CSV outputs use ';' as separator and ',' for decimals without thousand separators."""
    opt_result, meta = create_dummy_optimization_result()
    cups_list = ["ES0021000000000001AA", "ES0021000000000002BB"]
    hours = [f"{h:02d}" for h in range(24)]

    profile_matrix = HourlyProfileMatrix(
        cups_list=cups_list,
        hours=hours,
        matrix={
            cups_list[0]: dict.fromkeys(hours, 0.625),
            cups_list[1]: dict.fromkeys(hours, 0.375),
        },
        hourly_sums=dict.fromkeys(hours, 1.0),
        average_shares={cups_list[0]: 0.625, cups_list[1]: 0.375},
        average_sum=1.0,
    )
    ts_rows = []
    for h in hours:
        ts_rows.append(
            {
                "timestamp": f"2026-05-01 {h}:00:00",
                "hour": int(h),
                "cups": cups_list[0],
                "use": "Heating",
                "consumption_kwh": 1234.56,
                "generation_kwh": 5000.78,
                "share_pct": "62.5%",
                "estimated_share_pct": "62.5%",
                "solar_efficiency": 82,
            }
        )
    opt_result.hourly_result = HourlyOptimizationResult(
        profile_matrix=profile_matrix,
        time_series_df=pd.DataFrame(ts_rows),
    )

    csv_paths = export_all(opt_result, meta, tmp_path, formats="csv", precision=2)
    assert len(csv_paths) == 4

    for p in csv_paths:
        text = p.read_text(encoding="utf-8")
        lines = text.strip().splitlines()
        # Header has semicolon
        assert ";" in lines[0]
        # Data rows have semicolon
        for line in lines[1:]:
            assert ";" in line
            # Verify no thousand separators (e.g. no 1,234.56 or 1.234,56)
            for part in line.split(";"):
                # No 1,234 or 1.234 style thousand grouping
                assert not (part.count(",") > 1 or ("," in part and "." in part))

    # Check coefficients CSV specific values
    coeff_path = next(p for p in csv_paths if "_esd_coefficients.csv" in p.name)
    coeff_text = coeff_path.read_text(encoding="utf-8")
    assert "0,6000" in coeff_text
    assert "0,4000" in coeff_text
    assert "60,00" in coeff_text

    # Check matrix CSV specific values
    matrix_path = next(p for p in csv_paths if "_esd_coefficients_matrix.csv" in p.name)
    matrix_text = matrix_path.read_text(encoding="utf-8")
    assert "60,00%" in matrix_text
    assert "100,00%" in matrix_text

    # Check hourly shares CSV specific values
    shares_path = next(p for p in csv_paths if "_esd_hourly_shares.csv" in p.name)
    shares_text = shares_path.read_text(encoding="utf-8")
    assert "1234,56" in shares_text
    assert "5000,78" in shares_text
    assert "62,5%" in shares_text
    assert "82" in shares_text

    # Check hourly profile matrix CSV specific values
    h_matrix_path = next(p for p in csv_paths if "_esd_hourly_profile_matrix.csv" in p.name)
    h_matrix_text = h_matrix_path.read_text(encoding="utf-8")
    assert "62,50%" in h_matrix_text
    assert "37,50%" in h_matrix_text


def test_report_exporter_class(tmp_path: Path) -> None:
    opt_result, meta = create_dummy_optimization_result()
    out_dir = tmp_path / "custom_output"
    exporter = ReportExporter(
        output_dir=out_dir,
        delimiter=";",
        decimal_char=",",
        timestamp="20261025_120000",
    )
    assert exporter.output_dir == out_dir
    assert exporter.delimiter == ";"
    assert exporter.decimal_char == ","
    assert exporter.timestamp == "20261025_120000"

    # Test all exports via ReportExporter instance
    exported = exporter.export_all(opt_result, meta, formats="all", precision=1)
    assert len(exported) >= 4
    for p in exported:
        assert p.exists()
        assert p.parent == out_dir
        assert p.name.startswith("20261025_120000")
