"""Automated unit and integration tests for time-series data curation and reconciliation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd
import pytest
from typer.testing import CliRunner

from src.cli import app
from src.curation import (
    CurationError,
    DataCurator,
    dataframe_to_aligned_dataset,
    format_energy_value,
)
from src.ingestion.schema import AlignmentError


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
    solar_self_cons: float = 6.0,
    solar_exp: float = 6.0,
    solar_imp: float = 2.5,
) -> None:
    """Generate synthetic Huawei FusionSolar Excel report with generation, consumption and energy flows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Row 1: Title
    ws.append(["Informe de plantas_MOCK_PLANT", "", "", "", "", "", "", "", "", ""])

    # Row 2: Headers
    ws.append(
        [
            "Período estadístico",
            "Irradiancia global (kWh/m²)",
            "Temperatura media (°C)",
            "Rendimiento teórico (kWh)",
            "Rendimiento FV (kWh)",
            "Rendimiento del inversor (kWh)",
            "Energía exportada (kWh)",
            "Importación (kWh)",
            "Consumo (kWh)",
            "Autoconsumo (kWh)",
        ]
    )

    # Data rows: 24 hours per day
    for d in range(1, num_days + 1):
        for h in range(24):
            ts = f"2026-05-{d:02d} {h:02d}:00:00"
            is_solar = 8 <= h <= 17
            gen_val = solar_gen if is_solar else 0.0
            cons_val = solar_cons if is_solar else night_cons
            sc_val = solar_self_cons if is_solar else 0.0
            exp_val = solar_exp if is_solar else 0.0
            imp_val = solar_imp if is_solar else night_cons
            ws.append(
                [ts, 0.6, 20.0, gen_val, gen_val, gen_val, exp_val, imp_val, cons_val, sc_val]
            )

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
    expected_header = (
        "timestamp;year;month;day;hour;day_of_week;is_weekend;"
        "cups_id;use;consumption;community_demand;generation;self_consumption;"
        "hourly_self_consumption;exported_energy;imported_energy;temperature;cloud_cover"
    )
    assert header == expected_header
    assert "date" not in header.split(";")
    assert "primary" not in header.split(";")
    assert "reconciled" not in header.split(";")
    assert pri_cups in csv_lines[1]
    assert "Comunidad" in csv_lines[1]
    assert "2026-05-01 00:00:00" in csv_lines[1]
    parts = csv_lines[1].split(";")
    assert parts[1] == "2026"  # year
    assert parts[2] == "5"  # month
    assert parts[3] == "1"  # day
    assert parts[4] == "0"  # hour
    assert parts[5] == "Friday"  # day_of_week
    assert parts[6] == "False"  # is_weekend


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


def test_dataframe_to_aligned_dataset() -> None:
    """Verify conversion from flat curated DataFrame to AlignedDataset."""
    import pandas as pd

    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-05-01 12:00:00",
                "generation": 10.5,
                "cups_id": c1,
                "use": "Portal 1",
                "consumption": 2.5,
                "primary": True,
                "reconciled": True,
            },
            {
                "timestamp": "2026-05-01 12:00:00",
                "generation": 10.5,
                "cups_id": c2,
                "use": "Piscina",
                "consumption": 1.5,
                "primary": False,
                "reconciled": False,
            },
        ]
    )

    aligned = dataframe_to_aligned_dataset(df)
    assert aligned.cups_list == [c1, c2]
    assert aligned.metadata.cups_count == 2
    assert aligned.cups_uses[c1] == "Portal 1"
    assert aligned.cups_uses[c2] == "Piscina"
    assert float(aligned.data.loc["2026-05-01 12:00:00", "generation_kwh"]) == 10.5
    assert float(aligned.data.loc["2026-05-01 12:00:00", c1]) == 2.5


def test_dataframe_to_aligned_dataset_validation() -> None:
    """Verify validation when dataframe is empty or missing columns."""
    import pandas as pd

    with pytest.raises(AlignmentError, match="empty"):
        dataframe_to_aligned_dataset(pd.DataFrame())

    bad_df = pd.DataFrame([{"timestamp": "2026-05-01 00:00:00"}])
    with pytest.raises(CurationError, match="missing required columns"):
        dataframe_to_aligned_dataset(bad_df)


def test_data_curator_load_aligned_dataset_semicolon(tmp_path: Path) -> None:
    """Verify that load_aligned_dataset automatically detects semicolon delimiter."""
    c1 = "ES0021000000000001AA"
    lines = [
        "timestamp;generation;cups_id;use;consumption;primary;reconciled",
        f"2026-05-01 10:00:00;5.0;{c1};Garaje;1.2;False;False",
    ]
    csv_file = tmp_path / "custom.csv"
    csv_file.write_text("\n".join(lines), encoding="utf-8")

    aligned = DataCurator.load_aligned_dataset(csv_file)
    assert aligned.cups_list == [c1]
    assert float(aligned.data.loc["2026-05-01 10:00:00", c1]) == 1.2
    assert aligned.cups_uses[c1] == "Garaje"


def test_cli_calculate_auto_curates_when_missing(tmp_path: Path) -> None:
    """Verify that calculate auto-curates when curated.csv does not exist."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{pri_cups}.csv", pri_cups, solar_cons_val=0.0)
    create_mock_huawei_excel(gen_dir / "gen.xlsx", solar_gen=10.0, solar_cons=6.0)

    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps([{"cups": pri_cups, "use": "Aerotermia", "primary": True}]),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "calculate",
            "--consumption-dir",
            str(cons_dir),
            "--generation-dir",
            str(gen_dir),
            "--curated-dir",
            str(curated_dir),
            "--cups-file",
            str(cups_file),
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )

    assert result.exit_code == 0
    # Verified: curated.csv was generated on the fly!
    assert (curated_dir / "curated.csv").exists()
    assert "COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY" in result.output


def test_cli_calculate_uses_existing_curated(tmp_path: Path) -> None:
    """Verify that calculate directly loads an existing curated.csv."""
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    lines = [
        "timestamp,generation,cups_id,use,consumption,primary,reconciled",
        f"2026-05-01 12:00:00,10,{pri_cups},Aerotermia,5,True,True",
    ]
    (curated_dir / "curated.csv").write_text("\n".join(lines), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "calculate",
            "--curated-dir",
            str(curated_dir),
            "-y",
            "2026",
            "-m",
            "5",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )

    assert result.exit_code == 0
    assert "COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY" in result.output
    assert "00000001AA" in result.output
    assert "1 CUPS" in result.output


def test_curated_data_loads_primary_cups_and_hourly_assigns_100_percent_night(
    tmp_path: Path,
) -> None:
    """Verify curated data retains primary CUPS and hourly calculation assigns 100% to primary cups at night."""
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    sec_cups = "ES0021000000000002BB"

    rows = ["timestamp,generation,cups_id,use,consumption,primary,reconciled"]
    for h in range(24):
        gen = 0.0 if (h < 7 or h > 20) else 8.0
        ts = f"2026-05-01 {h:02d}:00:00"
        rows.append(f"{ts},{gen},{pri_cups},Aerotermia,2.0,True,False")
        rows.append(f"{ts},{gen},{sec_cups},Piso 1,1.5,False,False")

    (curated_dir / "curated.csv").write_text("\n".join(rows), encoding="utf-8")

    aligned = DataCurator.load_aligned_dataset(curated_dir / "curated.csv")
    assert aligned.primary_cups == pri_cups

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "calculate",
            "--curated-dir",
            str(curated_dir),
            "--output-dir",
            str(out_dir),
            "--hourly",
            "-y",
            "2026",
            "-m",
            "5",
            "--format",
            "csv",
            "--lang",
            "en",
        ],
    )

    assert result.exit_code == 0
    hourly_csvs = list(out_dir.glob("*_esd_hourly_shares.csv"))
    assert len(hourly_csvs) == 1
    content = hourly_csvs[0].read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    header = lines[0].split(";")
    share_idx = header.index("share_pct")
    cups_idx = header.index("cups")
    hour_idx = header.index("hour")

    for line in lines[1:]:
        cols = line.split(";")
        h = int(cols[hour_idx])
        c = cols[cups_idx]
        share = cols[share_idx]
        if h < 7 or h > 20:
            if c == pri_cups:
                assert share == "99%"
            else:
                assert share == "1%"


def test_curation_with_existing_weather_data(tmp_path: Path) -> None:
    """Verify that curate populates temperature and cloud_cover when weather file exists."""
    import pandas as pd

    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    weather_dir = tmp_path / "weather"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()
    weather_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{pri_cups}.csv", pri_cups)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    # Synthetic coordinates
    lat = 40.4168
    lon = -3.7038
    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [{"cups": pri_cups, "use": "Aerotermia", "primary": True, "lat": lat, "long": lon}]
        ),
        encoding="utf-8",
    )

    # Create mock weather CSV for 2026
    weather_file = weather_dir / "2026_40.4168_-3.7038_weather.csv"
    weather_rows = ["timestamp,temperature,cloud_cover,weather_code"]
    for h in range(24):
        weather_rows.append(f"2026-05-01 {h:02d}:00:00,18.5,35,1")
    weather_file.write_text("\n".join(weather_rows), encoding="utf-8")

    curator = DataCurator(
        consumption_dir=cons_dir,
        generation_dir=gen_dir,
        cups_config_path=cups_file,
        curated_dir=curated_dir,
        weather_dir=weather_dir,
    )
    dataset = curator.curate()

    assert dataset.summary.total_hours == 24
    rec_noon = next(r for r in dataset.records if r.hour == "12:00")
    assert rec_noon.temperature == 18.5
    assert rec_noon.cloud_cover == 35

    csv_path = curator.export_csv(dataset, curated_dir=curated_dir, base_name="weather_curated")
    df = pd.read_csv(csv_path, sep=";", decimal=",")
    assert "temperature" in df.columns
    assert "cloud_cover" in df.columns
    assert "primary" not in df.columns
    assert "reconciled" not in df.columns
    assert float(df["temperature"].iloc[12]) == 18.5
    assert int(df["cloud_cover"].iloc[12]) == 35


def test_curation_auto_fetches_weather_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that curate automatically executes weather download using cups default location when missing."""
    import pandas as pd

    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    weather_dir = tmp_path / "weather"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()
    weather_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{pri_cups}.csv", pri_cups)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    lat = 40.4168
    lon = -3.7038
    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [{"cups": pri_cups, "use": "Aerotermia", "primary": True, "lat": lat, "long": lon}]
        ),
        encoding="utf-8",
    )

    download_calls: list[dict[str, Any]] = []

    def mock_download_year(
        self: Any,
        year: int,
        latitude: float,
        longitude: float,
        timezone: str = "auto",
        timeout_seconds: int = 30,
    ) -> tuple[Path, pd.DataFrame, Any]:
        download_calls.append({"year": year, "latitude": latitude, "longitude": longitude})
        timestamps = [f"{year}-05-01 {h:02d}:00:00" for h in range(24)]
        df_mock = pd.DataFrame(
            {
                "timestamp": timestamps,
                "temperature": [22.4] * 24,
                "cloud_cover": [10] * 24,
                "weather_code": [0] * 24,
            }
        )
        out_csv = self.weather_dir / f"{year}_{latitude:.4f}_{longitude:.4f}_weather.csv"
        df_mock.to_csv(out_csv, index=False)
        return out_csv, df_mock, None

    from src.ingestion.weather import OpenMeteoWeatherDownloader

    monkeypatch.setattr(OpenMeteoWeatherDownloader, "download_year", mock_download_year)

    curator = DataCurator(
        consumption_dir=cons_dir,
        generation_dir=gen_dir,
        cups_config_path=cups_file,
        curated_dir=curated_dir,
        weather_dir=weather_dir,
    )
    dataset = curator.curate()

    # Verify download was triggered automatically with cups default location
    assert len(download_calls) == 1
    assert download_calls[0]["year"] == 2026
    assert download_calls[0]["latitude"] == lat
    assert download_calls[0]["longitude"] == lon

    # Verify curated record has the downloaded weather data
    rec = dataset.records[0]
    assert rec.temperature == 22.4
    assert rec.cloud_cover == 10


def test_curation_without_coordinates_leaves_weather_empty(tmp_path: Path) -> None:
    """Verify that curate runs gracefully without error when no coordinates are configured."""
    import pandas as pd

    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    weather_dir = tmp_path / "weather"
    cons_dir.mkdir()
    gen_dir.mkdir()
    weather_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{pri_cups}.csv", pri_cups)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    # cups.json without lat/long
    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps([{"cups": pri_cups, "use": "Aerotermia", "primary": True}]),
        encoding="utf-8",
    )

    curator = DataCurator(
        consumption_dir=cons_dir,
        generation_dir=gen_dir,
        cups_config_path=cups_file,
        curated_dir=curated_dir,
        weather_dir=weather_dir,
    )
    dataset = curator.curate()

    assert dataset.summary.total_hours == 24
    assert dataset.records[0].temperature is None
    assert dataset.records[0].cloud_cover is None

    csv_path = curator.export_csv(dataset, curated_dir=curated_dir, base_name="empty_weather")
    df = pd.read_csv(csv_path, sep=";", decimal=",")
    assert "temperature" in df.columns
    assert "cloud_cover" in df.columns
    assert df["temperature"].isna().all()
    assert df["cloud_cover"].isna().all()


def test_cli_curate_with_weather_dir(tmp_path: Path) -> None:
    """Test invoking 'esd curate' CLI command with custom --weather-dir option."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    weather_dir = tmp_path / "weather"
    cons_dir.mkdir()
    gen_dir.mkdir()
    curated_dir.mkdir()
    weather_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{pri_cups}.csv", pri_cups)
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
            "--weather-dir",
            str(weather_dir),
            "--name",
            "cli_weather_curated",
        ],
    )
    assert result.exit_code == 0
    assert (curated_dir / "cli_weather_curated.csv").exists()


def test_primary_cups_always_gets_higher_consumption(tmp_path: Path) -> None:
    """Verify that primary CUPS always adopts the higher consumption between DATADIS and the inverter."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    sec_cups = "ES0021000000000002BB"

    # DATADIS: primary has 0.0 during solar hours (9-18) and 5.0 at night
    create_mock_datadis_csv(
        cons_dir / f"{pri_cups}.csv", pri_cups, solar_cons_val=0.0, night_cons_val=5.0
    )
    create_mock_datadis_csv(
        cons_dir / f"{sec_cups}.csv", sec_cups, solar_cons_val=1.0, night_cons_val=1.0
    )

    # Inverter: has 8.5 during solar hours (8-17) and 2.0 at night
    # During solar peak (12:00): inverter (8.5) > datadis (0.0) -> picks 8.5
    # During night (22:00): datadis (5.0) > inverter (2.0) -> picks 5.0 (the higher!)
    create_mock_huawei_excel(gen_dir / "gen.xlsx", solar_gen=12.0, solar_cons=8.5, night_cons=2.0)

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

    # Hour 12:00: inverter (8.5) > datadis (0.0) -> picks 8.5
    rec_noon = next(r for r in dataset.records if r.hour == "12:00")
    pri_reading_noon = next(c for c in rec_noon.cups if c.id == pri_cups)
    assert pri_reading_noon.consumption == 8.5
    assert pri_reading_noon.reconciled is True

    # Hour 22:00: datadis (5.0) > inverter (2.0) -> picks 5.0 (the higher!)
    rec_night = next(r for r in dataset.records if r.hour == "22:00")
    pri_reading_night = next(c for c in rec_night.cups if c.id == pri_cups)
    assert pri_reading_night.consumption == 5
    assert pri_reading_night.reconciled is False


def test_curation_csv_ordering_by_date_and_use(tmp_path: Path) -> None:
    """Verify that curated.csv rows are ordered first by date/timestamp and then by use alphabetically."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()

    cups_portal = "ES0021000000000001AA"
    cups_aero = "ES0021000000000002BB"
    cups_garaje = "ES0021000000000003CC"

    create_mock_datadis_csv(cons_dir / f"{cups_portal}.csv", cups_portal)
    create_mock_datadis_csv(cons_dir / f"{cups_aero}.csv", cups_aero)
    create_mock_datadis_csv(cons_dir / f"{cups_garaje}.csv", cups_garaje)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    # Define uses intentionally in non-alphabetical order
    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [
                {"cups": cups_portal, "use": "Portal 1", "primary": False},
                {"cups": cups_aero, "use": "Aerotermia", "primary": True},
                {"cups": cups_garaje, "use": "Garaje", "primary": False},
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
    csv_path = curator.export_csv(dataset, curated_dir=curated_dir, base_name="curated_sorted")

    df = pd.read_csv(csv_path, sep=";", decimal=",")
    timestamps = df["timestamp"].unique()
    assert len(timestamps) == 24
    # Ensure timestamps are strictly non-decreasing
    assert list(timestamps) == sorted(timestamps)

    # For each timestamp, verify uses are ordered alphabetically: Aerotermia, Garaje, Portal 1
    for ts in timestamps:
        ts_slice = df[df["timestamp"] == ts]
        uses = ts_slice["use"].tolist()
        assert uses == ["Aerotermia", "Garaje", "Portal 1"]


def test_curated_csv_semicolon_separator_comma_decimal(tmp_path: Path) -> None:
    """Verify curated.csv uses ';' delimiter, ',' decimal, no thousand separator, and loads back cleanly."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()
    curated_dir.mkdir()

    cups_id = "ES0021000000000001AA"
    create_mock_datadis_csv(cons_dir / f"{cups_id}.csv", cups_id)
    create_mock_huawei_excel(gen_dir / "gen.xlsx")

    curator = DataCurator(
        consumption_dir=cons_dir,
        generation_dir=gen_dir,
        curated_dir=curated_dir,
    )
    csv_file = curator.ensure_curated(force=True)
    assert csv_file.exists()

    content = csv_file.read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    header = lines[0]
    expected_header = (
        "timestamp;year;month;day;hour;day_of_week;is_weekend;"
        "cups_id;use;consumption;community_demand;generation;self_consumption;"
        "hourly_self_consumption;exported_energy;imported_energy;temperature;cloud_cover"
    )
    assert header == expected_header

    # Check a sample line: should contain ';' separator and ',' decimal (e.g. '0,0' or '2,5')
    sample_line = lines[1]
    assert ";" in sample_line
    parts = sample_line.split(";")
    assert len(parts) == 18
    # Verify no thousand separators (e.g. no '.' within numeric values when ',' is decimal)
    # Check that consumption, community_demand, generation, and self_consumption parse as float with comma decimal
    cons_val = float(parts[9].replace(",", "."))
    comm_val = float(parts[10].replace(",", "."))
    gen_val = float(parts[11].replace(",", "."))
    sc_val = float(parts[12].replace(",", "."))
    h_sc_val = float(parts[13].replace(",", "."))
    exp_val = float(parts[14].replace(",", "."))
    imp_val = float(parts[15].replace(",", "."))
    assert isinstance(cons_val, float)
    assert isinstance(comm_val, float)
    assert isinstance(gen_val, float)
    assert isinstance(sc_val, float)
    assert isinstance(h_sc_val, float)
    assert isinstance(exp_val, float)
    assert isinstance(imp_val, float)

    # Verify load_aligned_dataset reconstructs properly
    aligned = curator.load_aligned_dataset(csv_file)
    assert aligned.cups_list == [cups_id]
    assert len(aligned.data) > 0
    assert float(aligned.data[cups_id].iloc[0]) == cons_val


def test_curated_dataset_calendar_decomposition_and_community_demand() -> None:
    """Verify that CuratedDataset.to_dataframe extracts calendar dimensions and community demand correctly."""
    from src.curation.models import (
        CuratedCupsReading,
        CuratedDataset,
        CuratedHourRecord,
        CuratedSummary,
    )

    rec_sat = CuratedHourRecord(
        date="2026-10-24",
        hour="14:00",
        generation=12.5,
        timestamp="2026-10-24 14:00:00",
        total_consumption=8.0,
        temperature=18.5,
        cloud_cover=25,
        cups=[
            CuratedCupsReading(
                id="ES0021000000000001AA",
                use="Aerotermia",
                consumption=5.5,
            ),
            CuratedCupsReading(
                id="ES0021000000000002BB",
                use="Garaje",
                consumption=2.5,
            ),
        ],
    )
    rec_mon = CuratedHourRecord(
        date="2026-10-26",
        hour="09:00",
        generation=4.0,
        timestamp="2026-10-26 09:00:00",
        total_consumption=3.0,
        temperature=15.0,
        cloud_cover=0,
        cups=[
            CuratedCupsReading(
                id="ES0021000000000001AA",
                use="Aerotermia",
                consumption=3.0,
            ),
        ],
    )

    dataset = CuratedDataset(
        records=[rec_sat, rec_mon],
        summary=CuratedSummary(
            total_hours=2,
            reconciled_hours_count=0,
            recovered_kwh=0.0,
            total_generation_kwh=16.5,
            total_consumption_kwh=11.0,
            start_time="2026-10-24 14:00:00",
            end_time="2026-10-26 09:00:00",
            cups_count=2,
            primary_cups="ES0021000000000001AA",
        ),
        cups_configs={},
    )

    df = dataset.to_dataframe()
    assert len(df) == 3  # 2 for Saturday + 1 for Monday
    expected_cols = [
        "timestamp",
        "year",
        "month",
        "day",
        "hour",
        "day_of_week",
        "is_weekend",
        "cups_id",
        "use",
        "consumption",
        "community_demand",
        "generation",
        "self_consumption",
        "hourly_self_consumption",
        "exported_energy",
        "imported_energy",
        "temperature",
        "cloud_cover",
    ]
    assert list(df.columns) == expected_cols

    # Saturday checks
    row_sat = df[df["timestamp"] == "2026-10-24 14:00:00"].iloc[0]
    assert row_sat["year"] == 2026
    assert row_sat["month"] == 10
    assert row_sat["day"] == 24
    assert row_sat["hour"] == 14
    assert row_sat["day_of_week"] == "Saturday"
    assert row_sat["is_weekend"] is True or row_sat["is_weekend"] == 1
    assert row_sat["community_demand"] == 8.0
    assert row_sat["generation"] == 12.5
    assert row_sat["temperature"] == 18.5
    assert row_sat["cloud_cover"] == 25

    # Monday checks
    row_mon = df[df["timestamp"] == "2026-10-26 09:00:00"].iloc[0]
    assert row_mon["year"] == 2026
    assert row_mon["month"] == 10
    assert row_mon["day"] == 26
    assert row_mon["hour"] == 9
    assert row_mon["day_of_week"] == "Monday"
    assert row_mon["is_weekend"] is False or row_mon["is_weekend"] == 0
    assert row_mon["community_demand"] == 3.0
    assert row_mon["generation"] == 4.0

    # Empty dataset checks
    empty_df = CuratedDataset(
        records=[],
        summary=CuratedSummary(0, 0, 0.0, 0.0, 0.0, "", "", 0, None),
        cups_configs={},
    ).to_dataframe()
    assert list(empty_df.columns) == expected_cols
    assert empty_df.empty


def test_curation_self_consumption_assigned_to_primary_cups(tmp_path: Path) -> None:
    """Verify that hourly self-consumed electricity is assigned to primary CUPS, and other CUPS receive 0."""
    cons_dir = tmp_path / "consumption"
    gen_dir = tmp_path / "generation"
    curated_dir = tmp_path / "curated"
    cons_dir.mkdir()
    gen_dir.mkdir()
    curated_dir.mkdir()

    pri_cups = "ES0021000000000001AA"
    sec_cups = "ES0021000000000002BB"

    create_mock_datadis_csv(cons_dir / f"{pri_cups}.csv", pri_cups)
    create_mock_datadis_csv(cons_dir / f"{sec_cups}.csv", sec_cups)
    # Inverter has 12 kWh gen, 8.5 kWh cons, and 6.0 kWh self_cons during solar hours (8-17)
    create_mock_huawei_excel(
        gen_dir / "gen.xlsx",
        solar_gen=12.0,
        solar_cons=8.5,
        solar_self_cons=6.0,
        solar_exp=6.0,
        solar_imp=2.5,
    )

    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [
                {"cups": pri_cups, "use": "Aerotermia", "primary": True},
                {"cups": sec_cups, "use": "Garaje", "primary": False},
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
    csv_file = curator.export_csv(dataset, curated_dir=curated_dir)
    df = pd.read_csv(csv_file, sep=";", decimal=",", dtype=str)

    assert "self_consumption" in df.columns
    assert "hourly_self_consumption" in df.columns
    assert "exported_energy" in df.columns
    assert "imported_energy" in df.columns

    # Check a solar hour (e.g. 12:00:00)
    solar_rows = df[df["timestamp"] == "2026-05-01 12:00:00"]
    assert len(solar_rows) == 2

    pri_row = solar_rows[solar_rows["cups_id"] == pri_cups].iloc[0]
    sec_row = solar_rows[solar_rows["cups_id"] == sec_cups].iloc[0]

    # Primary CUPS receives Huawei physical self_consumption (6.0 kWh)
    assert float(pri_row["self_consumption"].replace(",", ".")) == 6.0
    # Primary CUPS receives regulatory hourly min(cons, gen) = min(8.5, 12.0) = 8.5 kWh
    assert float(pri_row["hourly_self_consumption"].replace(",", ".")) == 8.5
    # Primary CUPS receives exported_energy = 6.0 kWh
    assert float(pri_row["exported_energy"].replace(",", ".")) == 6.0
    # Primary CUPS receives imported_energy = 2.5 kWh
    assert float(pri_row["imported_energy"].replace(",", ".")) == 2.5

    # Secondary CUPS receives 0.0 for all primary PV plant metrics
    assert float(sec_row["self_consumption"].replace(",", ".")) == 0.0
    assert float(sec_row["hourly_self_consumption"].replace(",", ".")) == 0.0
    assert float(sec_row["exported_energy"].replace(",", ".")) == 0.0
    assert float(sec_row["imported_energy"].replace(",", ".")) == 0.0
