"""Automated tests for DATADIS consumption and Huawei generation data ingestion."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from src.ingestion.consumption import DatadisConsumptionLoader, DatadisValidator
from src.ingestion.csv_utils import clean_numeric_series, sniff_csv_delimiter
from src.ingestion.generation import HuaweiGenerationLoader
from src.ingestion.schema import IngestionError, ValidationError, ValidationResult
from src.ingestion.weather import (
    ALLOWED_WEATHER_HOST,
    MAX_RESPONSE_BYTES,
    OpenMeteoWeatherDownloader,
)


def create_mock_datadis_csv(
    file_path: Path,
    cups: str = "ES0021000000000001AA",
    delimiter: str = ";",
    decimal_sep: str = ",",
    encoding: str = "utf-8",
    num_days: int = 2,
    include_spring_dst: bool = False,
    include_autumn_dst: bool = False,
) -> None:
    """Helper to generate synthetic mock DATADIS consumption CSV files."""
    lines = [f"cups{delimiter}fecha{delimiter}hora{delimiter}consumo_kWh{delimiter}metodoObtencion"]
    for d in range(1, num_days + 1):
        month = "10" if include_autumn_dst else "03"
        date_str = f"2026/{month}/{d:02d}"
        if include_spring_dst and d == 29:
            # 23 hours on spring DST day (02:00 skipped)
            hours = [f"{h:02d}:00" for h in range(1, 25) if h != 2]
        elif include_autumn_dst and d == 25:
            # 25 hours on autumn DST day (25 sequential intervals with repeated 02:00)
            hours = [f"{h:02d}:00" for h in range(1, 26)]
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


def test_consumption_autumn_dst_transition(tmp_path: Path) -> None:
    csv_file = tmp_path / "dst_autumn.csv"
    create_mock_datadis_csv(csv_file, num_days=25, include_autumn_dst=True)

    loader = DatadisConsumptionLoader(tmp_path)
    df = loader.parse_file(csv_file)

    # October 25 should have 25 readings
    oct25 = df[df["timestamp"].str.startswith("2026-10-25")]
    assert len(oct25) == 25
    ts_list = oct25["timestamp"].tolist()
    assert ts_list[0] == "2026-10-25 00:00:00"
    assert ts_list[1] == "2026-10-25 01:00:00"
    assert ts_list[2] == "2026-10-25 02:00:00"
    assert ts_list[3] == "2026-10-25 02:00:00"
    assert ts_list[4] == "2026-10-25 03:00:00"
    assert ts_list[24] == "2026-10-25 23:00:00"


def test_consumption_unparseable_hora_fallback(tmp_path: Path) -> None:
    csv_file = tmp_path / "unparseable_hora.csv"
    # Create CSV where hora has malformed strings like 'invalid' or '??'
    lines = [
        "cups;fecha;hora;consumo_kWh;metodoObtencion",
        "ES0021000000000001AA;2026/04/01;invalid;0,150;Real",
        "ES0021000000000001AA;2026/04/01;02:00;0,150;Real",
        "ES0021000000000001AA;2026/04/01;??;0,150;Real",
    ]
    csv_file.write_text("\n".join(lines), encoding="utf-8")

    loader = DatadisConsumptionLoader(tmp_path)
    df = loader.parse_file(csv_file)
    assert len(df) == 3
    # idx 0 fallback: h = idx + 1 = 1 -> 00:00:00
    # idx 1: h = 2 -> 01:00:00
    # idx 2 fallback: h = idx + 1 = 3 -> 02:00:00
    assert df["timestamp"].tolist() == [
        "2026-04-01 00:00:00",
        "2026-04-01 01:00:00",
        "2026-04-01 02:00:00",
    ]


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


def test_generation_loader_with_autoconsumo(tmp_path: Path) -> None:
    xlsx_file = tmp_path / "Informe_planta_autoconsumo.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Informe de plantas_TEST", "", "", "", "", "", ""])
    ws.append(
        [
            "Período estadístico",
            "Rendimiento FV (kWh)",
            "Consumo (kWh)",
            "Autoconsumo (kWh)",
            "Energía exportada (kWh)",
            "Importación (kWh)",
        ]
    )
    ws.append(["2026-06-01 12:00:00", 10.5, 8.0, 7.5, 3.0, 0.5])
    wb.save(xlsx_file)

    loader = HuaweiGenerationLoader(tmp_path)
    df = loader.load_all()

    assert not df.empty
    assert "generation_kwh" in df.columns
    assert "consumption_kwh" in df.columns
    assert "self_consumption_kwh" in df.columns
    assert "exported_energy_kwh" in df.columns
    assert "imported_energy_kwh" in df.columns
    assert df["self_consumption_kwh"].iloc[0] == 7.5
    assert df["exported_energy_kwh"].iloc[0] == 3.0
    assert df["imported_energy_kwh"].iloc[0] == 0.5


def test_weather_downloader_security_host_and_payload_limits(tmp_path: Path) -> None:
    """OpenMeteoWeatherDownloader enforces HTTPS, trusted hostname, and 10 MB payload limits."""
    from unittest.mock import MagicMock, patch

    # Insecure scheme rejected
    with pytest.raises(IngestionError, match="Only HTTPS is permitted"):
        OpenMeteoWeatherDownloader.validate_url("http://archive-api.open-meteo.com/v1/archive")

    # SSRF untrusted host rejected
    with pytest.raises(IngestionError, match=r"Untrusted host 'attacker\.com'"):
        OpenMeteoWeatherDownloader(weather_dir=tmp_path, base_url="https://attacker.com/v1/archive")

    # Official endpoint accepted
    OpenMeteoWeatherDownloader.validate_url(
        f"https://{ALLOWED_WEATHER_HOST}/v1/archive?latitude=40.4&longitude=-3.7"
    )

    # Oversized payload rejected (> 10 MB)
    downloader = OpenMeteoWeatherDownloader(weather_dir=tmp_path)
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"A" * (MAX_RESPONSE_BYTES + 1)
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(IngestionError, match="exceeded maximum allowable size"):
            downloader.download_year(year=2024, latitude=40.4168, longitude=-3.7038)


def test_consumption_loader_spanish_date_formats(tmp_path: Path) -> None:
    """Verify that Spanish DD/MM/YYYY and DD-MM-YYYY dates parse into identical timestamps as YYYY/MM/DD and YYYY-MM-DD."""
    cups = "ES0021000000000001AA"
    hours = ["01:00", "02:00", "12:00", "24:00"]
    expected_ts = [
        "2026-03-15 00:00:00",
        "2026-03-15 01:00:00",
        "2026-03-15 11:00:00",
        "2026-03-15 23:00:00",
    ]

    formats = {
        "slash_dmy": "15/03/2026",
        "dash_dmy": "15-03-2026",
        "slash_ymd": "2026/03/15",
        "dash_ymd": "2026-03-15",
    }

    loader = DatadisConsumptionLoader(tmp_path)

    for fmt_name, date_str in formats.items():
        file_p = tmp_path / f"test_{fmt_name}.csv"
        lines = ["cups;fecha;hora;consumo_kWh;metodoObtencion"]
        for h in hours:
            lines.append(f'"{cups}";"{date_str}";"{h}";"0,250";Real')
        file_p.write_text("\n".join(lines), encoding="utf-8")

        parsed_df = loader.parse_file(file_p)
        assert len(parsed_df) == 4
        assert parsed_df["timestamp"].tolist() == expected_ts
        assert parsed_df["cups"].tolist() == [cups] * 4
        assert parsed_df["consumption_kwh"].tolist() == [0.25] * 4


def test_consumption_loader_single_digit_spanish_dates(tmp_path: Path) -> None:
    """Verify that single-digit day and month in Spanish formats are normalized with leading zeros."""
    cups = "ES0021000000000001AA"
    loader = DatadisConsumptionLoader(tmp_path)

    cases = [
        ("5/4/2026", "2026-04-05 00:00:00"),
        ("5-4-2026", "2026-04-05 00:00:00"),
        ("2026-4-5", "2026-04-05 00:00:00"),
        ("2026/4/5", "2026-04-05 00:00:00"),
    ]

    for i, (date_str, expected_ts) in enumerate(cases):
        file_p = tmp_path / f"single_{i}.csv"
        lines = [
            "cups;fecha;hora;consumo_kWh;metodoObtencion",
            f'"{cups}";"{date_str}";"01:00";"0,500";Real',
        ]
        file_p.write_text("\n".join(lines), encoding="utf-8")
        parsed = loader.parse_file(file_p)
        assert parsed["timestamp"].iloc[0] == expected_ts


def test_generation_loader_sanitizes_corrupted_partial_outage_hours(tmp_path: Path) -> None:
    """Verify corrupted hours where reported PV generation < exported energy are sanitized."""
    xlsx_file = tmp_path / "Informe_planta_partial_outage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Informe de plantas_TEST", "", "", "", "", ""])
    ws.append(
        [
            "Período estadístico",
            "Rendimiento FV (kWh)",
            "Consumo (kWh)",
            "Autoconsumo (kWh)",
            "Energía exportada (kWh)",
            "Importación (kWh)",
        ]
    )
    # Hour 15:00: partial reconnect where FV (27.84) < Exported (49.74) and Consumo was clamped to 0.0
    ws.append(["2026-09-01 15:00:00", 27.84, 0.0, 0.0, 49.74, 0.0])
    # Hour 16:00: normal full hour where FV (56.33) >= Exported (38.69) and Consumo is 17.64
    ws.append(["2026-09-01 16:00:00", 56.33, 17.64, 17.64, 38.69, 0.0])
    wb.save(xlsx_file)

    df = HuaweiGenerationLoader.parse_file(xlsx_file)
    assert len(df) == 2
    # Corrupted hour 15:00 has generation zeroed and consumption set to NaN
    assert df["generation_kwh"].iloc[0] == 0.0
    assert df["consumption_kwh"].isna().iloc[0]
    # Valid hour 16:00 is preserved intact
    assert df["generation_kwh"].iloc[1] == 56.33
    assert df["consumption_kwh"].iloc[1] == 17.64


def test_consumption_loader_recursive_annualized_discovery(tmp_path: Path) -> None:
    """Discover flat and annualized .input/consumption/<year>/*.csv while skipping hidden items."""
    base_dir = tmp_path / ".input" / "consumption"
    dir_2024 = base_dir / "2024"
    dir_2025 = base_dir / "2025"
    hidden_dir = base_dir / ".archive"
    dir_2024.mkdir(parents=True)
    dir_2025.mkdir(parents=True)
    hidden_dir.mkdir(parents=True)

    f_2024 = dir_2024 / "ES0021000000000001AA_2024.csv"
    f_2025 = dir_2025 / "ES0021000000000001AA_2025.csv"
    f_flat = base_dir / "ES0021000000000002BB_flat.csv"
    f_hidden_file = dir_2024 / ".backup.csv"
    f_hidden_sub = hidden_dir / "ignored.csv"

    f_2024.write_text(
        "cups;fecha;hora;consumo_kWh\nES0021000000000001AA;2024/05/01;01:00;1,250\n",
        encoding="utf-8",
    )
    f_2025.write_text(
        "cups;fecha;hora;consumo_kWh\nES0021000000000001AA;2025/05/01;01:00;2,500\n",
        encoding="utf-8",
    )
    f_flat.write_text(
        "cups;fecha;hora;consumo_kWh\nES0021000000000002BB;2026/05/01;01:00;3,750\n",
        encoding="utf-8",
    )
    f_hidden_file.write_text("cups;fecha;hora;consumo_kWh\n", encoding="utf-8")
    f_hidden_sub.write_text("cups;fecha;hora;consumo_kWh\n", encoding="utf-8")

    loader = DatadisConsumptionLoader(base_dir)
    all_files = loader.discover_files()
    assert all_files == sorted([f_2024, f_2025, f_flat])

    # Specific year directory hit
    files_2024 = loader.discover_files(year=2024)
    assert files_2024 == [f_2024]

    # Fallback when year directory does not exist returns non-hidden recursive CSVs
    files_2026 = loader.discover_files(year=2026)
    assert files_2026 == sorted([f_2024, f_2025, f_flat])

    df_2026 = loader.load_all(year=2026)
    assert len(df_2026) == 1
    assert df_2026["cups"].iloc[0] == "ES0021000000000002BB"
    assert df_2026["consumption_kwh"].iloc[0] == 3.75


def test_consumption_loader_consumokwh_alias_and_utf8_bom(tmp_path: Path) -> None:
    """Accept camelCase consumoKwh header alias and UTF-8 BOM-encoded CSV files."""
    bom_csv = tmp_path / "bom_alias.csv"
    content = (
        "cups;fecha;hora;consumoKwh;metodoObtencion\n"
        '"ES0021000000000001AA";"2026/05/01";"01:00";"0,450";Real\n'
        '"ES0021000000000001AA";"2026/05/01";"02:00";"0,550";Real\n'
    )
    bom_csv.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

    assert DatadisValidator.detect_encoding(bom_csv) == "utf-8-sig"
    val = DatadisValidator.validate_file(bom_csv)
    assert val.is_valid is True
    assert val.total_rows == 2
    assert val.detected_columns[0] == "cups"

    df = DatadisConsumptionLoader.parse_file(bom_csv)
    assert len(df) == 2
    assert df["consumption_kwh"].tolist() == [0.45, 0.55]
    assert df["timestamp"].tolist() == ["2026-05-01 00:00:00", "2026-05-01 01:00:00"]


def test_datadis_validator_file_checks(tmp_path: Path) -> None:
    """Validate missing, empty, header-only, missing-column, and valid CSV files."""
    missing_file = tmp_path / "does_not_exist.csv"
    res_missing = DatadisValidator.validate_file(missing_file)
    assert isinstance(res_missing, ValidationResult)
    assert res_missing.is_valid is False
    assert "not found" in (res_missing.error_message or "").lower()

    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")
    res_empty = DatadisValidator.validate_file(empty_file)
    assert res_empty.is_valid is False
    assert "empty" in (res_empty.error_message or "").lower()

    header_only = tmp_path / "header_only.csv"
    header_only.write_text("cups;fecha;hora;consumo_kWh\n   \n", encoding="utf-8")
    res_header_only = DatadisValidator.validate_file(header_only)
    assert res_header_only.is_valid is False
    assert res_header_only.total_rows == 0
    assert "zero data rows" in (res_header_only.error_message or "").lower()

    missing_col = tmp_path / "missing_col.csv"
    missing_col.write_text("cups;fecha;hora\nES0021000000000001AA;2026/05/01;01:00\n")
    res_missing_col = DatadisValidator.validate_file(missing_col)
    assert res_missing_col.is_valid is False
    assert res_missing_col.missing_columns == ["consumo_kWh"]

    valid_file = tmp_path / "valid_alias.csv"
    valid_file.write_text(
        "cups,fecha,hora,consumoKwh\nES0021000000000001AA,2026-05-01,01:00,1.25\n",
        encoding="utf-8",
    )
    res_valid = DatadisValidator.validate_file(valid_file)
    assert res_valid.is_valid is True
    assert res_valid.delimiter == ","
    assert res_valid.total_rows == 1


def test_consumption_loader_load_all_with_validation_skips_invalid(tmp_path: Path) -> None:
    """Skip empty or malformed CSVs cleanly and raise IngestionError if all fail."""
    valid_csv = tmp_path / "a_valid.csv"
    create_mock_datadis_csv(valid_csv, cups="ES0021000000000001AA", num_days=1)

    empty_csv = tmp_path / "b_empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    bad_col_csv = tmp_path / "c_bad_col.csv"
    bad_col_csv.write_text("fecha;hora;consumo_kWh\n2026/05/01;01:00;0,5\n", encoding="utf-8")

    loader = DatadisConsumptionLoader(tmp_path)
    df, results = loader.load_all_with_validation()

    assert len(df) == 24
    assert len(results) == 3
    assert sum(1 for r in results if r.is_valid) == 1
    assert sum(1 for r in results if not r.is_valid) == 2

    df_non_strict = loader.load_all(strict=False)
    assert len(df_non_strict) == 24

    # All-invalid directory raises IngestionError
    invalid_only_dir = tmp_path / "invalid_only"
    invalid_only_dir.mkdir()
    (invalid_only_dir / "empty.csv").write_text("", encoding="utf-8")
    (invalid_only_dir / "bad.csv").write_text("a;b\n1;2\n", encoding="utf-8")

    with pytest.raises(IngestionError, match="none could be loaded"):
        DatadisConsumptionLoader(invalid_only_dir).load_all_with_validation()


def test_clean_numeric_series_and_sniff_csv_delimiter(tmp_path: Path) -> None:
    """Verify shared numeric normalization and CSV delimiter sniffing across formats."""
    str_series = pd.Series([' "1,250" ', " 0,500 ", "'2 500,5'", "bad", None])
    parsed = clean_numeric_series(str_series)
    assert parsed.iloc[0] == 1.25
    assert parsed.iloc[1] == 0.5
    assert parsed.iloc[2] == 2500.5
    assert pd.isna(parsed.iloc[3])
    assert pd.isna(parsed.iloc[4])

    filled = clean_numeric_series(str_series, fill_na=0.0)
    assert filled.iloc[3] == 0.0
    assert filled.iloc[4] == 0.0

    num_series = pd.Series([1.5, None, 3.0])
    assert clean_numeric_series(num_series, fill_na=0.0).tolist() == [1.5, 0.0, 3.0]

    semicolon_csv = tmp_path / "semi.csv"
    semicolon_csv.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    comma_csv = tmp_path / "comma.csv"
    comma_csv.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    tab_csv = tmp_path / "tab.csv"
    tab_csv.write_text("a\tb\tc\n1\t2\t3\n", encoding="utf-8")

    assert sniff_csv_delimiter(semicolon_csv) == ";"
    assert sniff_csv_delimiter(comma_csv) == ","
    assert sniff_csv_delimiter(tab_csv) == "\t"
