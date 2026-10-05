"""Automated tests for DATADIS consumption and Huawei generation data ingestion."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from src.ingestion.consumption import DatadisConsumptionLoader
from src.ingestion.generation import HuaweiGenerationLoader
from src.ingestion.schema import IngestionError, ValidationError


def create_mock_datadis_csv(
    file_path: Path,
    cups: str = "ES0021000000000001AA",
    delimiter: str = ";",
    decimal_sep: str = ",",
    encoding: str = "utf-8",
    num_days: int = 2,
    include_spring_dst: bool = False,
) -> None:
    """Helper to generate synthetic mock DATADIS consumption CSV files."""
    lines = [f"cups{delimiter}fecha{delimiter}hora{delimiter}consumo_kWh{delimiter}metodoObtencion"]
    for d in range(1, num_days + 1):
        date_str = f"2026/03/{d:02d}"
        if include_spring_dst and d == 29:
            # 23 hours on spring DST day (02:00 skipped)
            hours = [f"{h:02d}:00" for h in range(1, 25) if h != 2]
        else:
            hours = [f"{h:02d}:00" for h in range(1, 25)]

        for h in hours:
            val_str = f"0{decimal_sep}150"
            lines.append(
                f'"{cups}"{delimiter}"{date_str}"{delimiter}"{h}"{delimiter}"{val_str}"{delimiter}Real'
            )

    file_path.write_text("\n".join(lines), encoding=encoding)


def create_mock_huawei_excel(
    file_path: Path,
    num_days: int = 2,
    include_dst: bool = False,
) -> None:
    """Helper to generate synthetic mock Huawei FusionSolar Excel reports."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Row 1: Title
    ws.append(["Informe de plantas_MOCK INSTALLATION", "", "", "", "", ""])

    # Row 2: Headers
    ws.append(
        [
            "Período estadístico",
            "Irradiancia global (kWh/m²)",
            "Temperatura media (°C)",
            "Rendimiento teórico (kWh)",
            "Rendimiento FV (kWh)",
            "Rendimiento del inversor (kWh)",
        ]
    )

    # Data rows
    for d in range(1, num_days + 1):
        for h in range(24):
            dst_suffix = " DST" if include_dst else ""
            ts = f"2026-03-{d:02d} {h:02d}:00:00{dst_suffix}"
            gen_val = 5.5 if 9 <= h <= 17 else 0.0
            ws.append([ts, 0.5, 18.0, 6.0, gen_val, gen_val])

    wb.save(file_path)


def test_consumption_loader_directory_not_found(tmp_path: Path) -> None:
    loader = DatadisConsumptionLoader(tmp_path / "non_existent")
    with pytest.raises(IngestionError, match="not found"):
        loader.discover_files()


def test_consumption_loader_empty_directory(tmp_path: Path) -> None:
    loader = DatadisConsumptionLoader(tmp_path)
    with pytest.raises(IngestionError, match="No CSV files found"):
        loader.discover_files()


def test_consumption_loader_valid_files(tmp_path: Path) -> None:
    csv_file = tmp_path / "sample.csv"
    create_mock_datadis_csv(csv_file, delimiter=";", decimal_sep=",")

    loader = DatadisConsumptionLoader(tmp_path)
    df = loader.load_all()

    assert not df.empty
    assert len(df) == 48
    assert "cups" in df.columns
    assert "timestamp" in df.columns
    assert "consumption_kwh" in df.columns
    assert df["cups"].iloc[0] == "ES0021000000000001AA"
    assert df["consumption_kwh"].iloc[0] == 0.15


def test_consumption_loader_different_delimiters_and_encodings(tmp_path: Path) -> None:
    csv1 = tmp_path / "comma_dot.csv"
    create_mock_datadis_csv(
        csv1,
        cups="ES0021000000000001AA",
        delimiter=",",
        decimal_sep=".",
        encoding="latin-1",
    )

    loader = DatadisConsumptionLoader(tmp_path)
    df = loader.load_all()
    assert len(df) == 48
    assert df["consumption_kwh"].iloc[0] == 0.15


def test_consumption_loader_missing_required_column(tmp_path: Path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("fecha;hora;consumo_kWh\n2026/03/01;01:00;0.1", encoding="utf-8")

    loader = DatadisConsumptionLoader(tmp_path)
    with pytest.raises(ValidationError, match="missing required DATADIS column: 'cups'"):
        loader.parse_file(bad_csv)


def test_consumption_spring_dst_transition(tmp_path: Path) -> None:
    csv_file = tmp_path / "dst.csv"
    create_mock_datadis_csv(csv_file, num_days=29, include_spring_dst=True)

    loader = DatadisConsumptionLoader(tmp_path)
    df = loader.parse_file(csv_file)

    # March 29 should have 23 readings
    m29 = df[df["timestamp"].str.startswith("2026-03-29")]
    assert len(m29) == 23
    # Check that timestamps map 00:00:00, 01:00:00, 03:00:00, etc.
    ts_list = m29["timestamp"].tolist()
    assert ts_list[0] == "2026-03-29 00:00:00"
    assert ts_list[1] == "2026-03-29 01:00:00"
    assert ts_list[2] == "2026-03-29 03:00:00"


def test_generation_loader_valid(tmp_path: Path) -> None:
    xlsx_file = tmp_path / "Informe_planta_test.xlsx"
    create_mock_huawei_excel(xlsx_file, num_days=2, include_dst=True)

    loader = HuaweiGenerationLoader(tmp_path)
    df = loader.load_all()

    assert not df.empty
    assert len(df) == 48
    assert "timestamp" in df.columns
    assert "generation_kwh" in df.columns
    # Ensure DST suffix is removed
    assert not df["timestamp"].str.contains("DST").any()
    assert df["generation_kwh"].max() == 5.5


def test_generation_loader_missing_columns(tmp_path: Path) -> None:
    bad_xlsx = tmp_path / "bad_gen.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Title"])
    ws.append(["Fecha", "Otra columna"])
    ws.append(["2026-01-01 00:00:00", 123])
    wb.save(bad_xlsx)

    loader = HuaweiGenerationLoader(tmp_path)
    with pytest.raises(ValidationError, match="does not contain 'Rendimiento FV'"):
        loader.parse_file(bad_xlsx)
