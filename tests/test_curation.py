"""Automated unit and integration tests for time-series data curation and reconciliation."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest
from typer.testing import CliRunner

from src.cli import app
from src.curation import (
    CurationError,
    DataCurator,
    format_energy_value,
)


def create_mock_datadis_csv(
    file_path: Path,
    cups: str,
    solar_cons_val: float = 0.0,
    night_cons_val: float = 2.0,
    num_days: int = 1,
) -> None:
    """Generate synthetic DATADIS hourly CSV file with authorized mock CUPS."""
    lines = ["cups;fecha;hora;consumo_kWh;metodoObtencion"]
    for d in range(1, num_days + 1):
        date_str = f"2026/05/{d:02d}"
        for h in range(1, 25):
            val = solar_cons_val if 9 <= h <= 18 else night_cons_val
            val_str = f"{val:.3f}".replace(".", ",")
            lines.append(f'"{cups}";"{date_str}";"{h:02d}:00";"{val_str}";Real')
    file_path.write_text("\n".join(lines), encoding="utf-8")


def create_mock_huawei_excel(
    file_path: Path,
    num_days: int = 1,
    solar_gen: float = 12.0,
    solar_cons: float = 8.5,
    night_cons: float = 2.0,
) -> None:
    """Generate synthetic Huawei FusionSolar Excel report with generation and consumption."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Row 1: Title
    ws.append(["Informe de plantas_MOCK_PLANT", "", "", "", "", "", ""])

    # Row 2: Headers
    ws.append(
        [
            "Período estadístico",
            "Irradiancia global (kWh/m²)",
            "Temperatura media (°C)",
            "Rendimiento teórico (kWh)",
            "Rendimiento FV (kWh)",
            "Rendimiento del inversor (kWh)",
            "Consumo (kWh)",
        ]
    )

    # Data rows: 24 hours per day
    for d in range(1, num_days + 1):
        for h in range(24):
            ts = f"2026-05-{d:02d} {h:02d}:00:00"
            is_solar = 8 <= h <= 17
            gen_val = solar_gen if is_solar else 0.0
            cons_val = solar_cons if is_solar else night_cons
            ws.append([ts, 0.6, 20.0, gen_val, gen_val, gen_val, cons_val])

    wb.save(file_path)


def test_format_energy_value() -> None:
    """Verify clean formatting: integer if exact whole number, float rounded to 3 decimals otherwise."""
    assert format_energy_value(500.0) == 500
    assert isinstance(format_energy_value(500.0), int)
    assert format_energy_value(0.0) == 0
    assert isinstance(format_energy_value(0.0), int)
    assert format_energy_value(35.250) == 35.25
    assert isinstance(format_energy_value(35.250), float)
    assert format_energy_value(0.1524) == 0.152


def test_cups_config_loading(tmp_path: Path) -> None:
    """Verify discovery and parsing of cups.json configuration file."""
    config_file = tmp_path / "cups.json"
    cups_data = [
        {"cups": "ES0021000000000001AA", "use": "piscina", "primary": False},
        {"cups": "ES0021000000000002BB", "use": "Aerotermia", "primary": True},
    ]
    config_file.write_text(json.dumps(cups_data), encoding="utf-8")

    curator = DataCurator(cups_config_path=config_file)
    configs = curator.load_cups_config()

    assert len(configs) == 2
    assert configs["ES0021000000000001AA"].use == "piscina"
    assert not configs["ES0021000000000001AA"].primary
    assert configs["ES0021000000000002BB"].use == "Aerotermia"
    assert configs["ES0021000000000002BB"].primary


def test_cups_config_missing_file(tmp_path: Path) -> None:
    """Verify empty dictionary returned when cups configuration file does not exist."""
    curator = DataCurator(cups_config_path=tmp_path / "non_existent.json")
    configs = curator.load_cups_config()
    assert configs == {}


def test_cups_config_invalid_json(tmp_path: Path) -> None:
    """Verify CurationError raised when cups config contains invalid JSON or non-list."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"not": "a list"}', encoding="utf-8")
    curator = DataCurator(cups_config_path=bad_file)
    with pytest.raises(CurationError, match="expected JSON array"):
        curator.load_cups_config()


def test_curation_reconciliation_fake_zeros(tmp_path: Path) -> None:
    """Verify data reconciliation: primary CUPS fake zero readings are corrected from Huawei."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    sec_cups = "ES0021000000000002BB"

    # Primary CUPS has 0.0 in DATADIS during solar hours (fake zero from behind-the-meter PV)
    create_mock_datadis_csv(
        cons_dir / f"{pri_cups}.csv", pri_cups, solar_cons_val=0.0, night_cons_val=2.0
    )
    # Secondary CUPS has steady 1.0 kWh
    create_mock_datadis_csv(
        cons_dir / f"{sec_cups}.csv", sec_cups, solar_cons_val=1.0, night_cons_val=1.0
    )

    # Huawei FusionSolar records solar generation 12.0 kWh and plant consumption 8.5 kWh
    create_mock_huawei_excel(gen_dir / "gen.xlsx", solar_gen=12.0, solar_cons=8.5, night_cons=2.0)

    # Setup cups.json designating pri_cups as primary
    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [
                {"cups": pri_cups, "use": "Aerotermia", "primary": True},
                {"cups": sec_cups, "use": "piscina", "primary": False},
            ]
        ),
        encoding="utf-8",
    )

    curator = DataCurator(
        consumption_dir=cons_dir,
        generation_dir=gen_dir,
        cups_config_path=cups_file,
        curated_dir=curated_dir,
    )
    dataset = curator.curate()

    assert dataset.summary.total_hours == 24
    assert dataset.summary.cups_count == 2
    assert dataset.summary.reconciled_hours_count > 0
    assert dataset.summary.recovered_kwh > 0

    # Check a solar hour (e.g. 12:00)
    solar_records = [r for r in dataset.records if r.hour == "12:00"]
    assert len(solar_records) == 1
    rec = solar_records[0]
    assert rec.generation == 12

    pri_reading = next(c for c in rec.cups if c.id == pri_cups)
    sec_reading = next(c for c in rec.cups if c.id == sec_cups)

    # Primary reading was fake zero (0.0 in DATADIS) -> reconciled to 8.5 from Huawei!
    assert pri_reading.consumption == 8.5
    assert pri_reading.primary is True
    assert pri_reading.reconciled is True
    assert pri_reading.use == "Aerotermia"

    # Secondary reading was 1.0 -> stays 1.0, reconciled is False
    assert sec_reading.consumption == 1
    assert sec_reading.primary is False
    assert sec_reading.reconciled is False
    assert sec_reading.use == "piscina"

    # Hourly community totals
    assert rec.total_consumption == 9.5
    assert rec.solar_surplus == 2.5
    assert rec.net_grid_demand == 0


def test_curation_exports_csv(tmp_path: Path) -> None:
    """Verify that export_csv writes clean CSV with timestamp and without date/hour columns."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{pri_cups}.csv", pri_cups)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps([{"cups": pri_cups, "use": "Comunidad", "primary": True}]),
        encoding="utf-8",
    )

    curator = DataCurator(
        consumption_dir=cons_dir,
        generation_dir=gen_dir,
        cups_config_path=cups_file,
        curated_dir=curated_dir,
    )
    dataset = curator.curate()
    csv_path = curator.export_csv(dataset, curated_dir=curated_dir, base_name="reconciliation")

    assert csv_path.exists()
    assert csv_path.name == "reconciliation.csv"
    assert not (curated_dir / "reconciliation.json").exists()

    # Validate compatible CSV header and contents
    csv_lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(csv_lines) == 25  # 1 header + 24 rows
    header = csv_lines[0]
    assert header == "timestamp,generation,cups_id,use,consumption,primary,reconciled"
    assert "date" not in header.split(",")
    assert "hour" not in header.split(",")
    assert pri_cups in csv_lines[1]
    assert "Comunidad" in csv_lines[1]
    assert "2026-05-01 00:00:00" in csv_lines[1]


def test_cli_curate_command(tmp_path: Path) -> None:
    """Test invoking 'esd curate' CLI command through Typer CliRunner."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()

    cups_id = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{cups_id}.csv", cups_id)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "curate",
            "--consumption-dir",
            str(cons_dir),
            "--generation-dir",
            str(gen_dir),
            "--curated-dir",
            str(curated_dir),
            "--name",
            "test_curated",
            "--lang",
            "en",
        ],
    )

    assert result.exit_code == 0
    assert "DATA RECONCILIATION" in result.output
    assert (curated_dir / "test_curated.csv").exists()
    assert not (curated_dir / "test_curated.json").exists()


def test_cli_curate_spanish_lang(tmp_path: Path) -> None:
    """Test invoking 'esd curate' CLI with Spanish language override."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()

    cups_id = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{cups_id}.csv", cups_id)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "curate",
            "--consumption-dir",
            str(cons_dir),
            "--generation-dir",
            str(gen_dir),
            "--curated-dir",
            str(curated_dir),
            "--lang",
            "es",
        ],
    )

    assert result.exit_code == 0
    assert "RECONCILIACIÓN" in result.output
    assert (curated_dir / "curated.csv").exists()
    assert not (curated_dir / "curated.json").exists()
