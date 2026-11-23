"""Unit tests for application service orchestrators."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import AppConfig
from src.domain.exceptions import ValidationError
from src.ingestion.weather import WeatherDownloadResult
from src.optimization.models import OptimizationStrategy
from src.services import (
    CalculationRequest,
    CalculationService,
    CurationRequest,
    CurationService,
    DoctorRequest,
    DoctorService,
    WeatherRequest,
    WeatherService,
)


def test_doctor_service_execution() -> None:
    """Verify that DoctorService correctly audits the workspace and returns DoctorReport."""
    req = DoctorRequest(
        consumption_dir=Path(".input/consumption"),
        generation_dir=Path(".input/generation"),
        weather_dir=Path(".input/weather"),
        cups_config_path=Path(".input/cups/cups.json"),
    )
    report = DoctorService.execute(req)
    assert report is not None
    assert report.overlap.cups_count > 0


def test_curation_service_execution(tmp_path: Path) -> None:
    """Verify that CurationService correctly curates and exports time-series."""
    req = CurationRequest(
        consumption_dir=Path(".input/consumption"),
        generation_dir=Path(".input/generation"),
        curated_dir=tmp_path,
        cups_config_path=Path(".input/cups/cups.json"),
        weather_dir=Path(".input/weather"),
        year=2026,
        month=5,
    )
    res = CurationService.execute(req)
    assert res.dataset is not None
    assert res.csv_path.exists()
    assert res.csv_path.name == "esd.csv"
    assert res.excel_path is not None and res.excel_path.exists()
    assert res.excel_path.name == "esd.xlsx"
    assert res.generation_csv_path is not None and res.generation_csv_path.exists()
    assert res.generation_csv_path.name == "generation.csv"
    assert res.generation_excel_path is not None and res.generation_excel_path.exists()
    assert res.generation_excel_path.name == "generation.xlsx"
    assert res.consumption_csv_path is not None and res.consumption_csv_path.exists()
    assert res.consumption_csv_path.name == "consumption.csv"
    assert res.consumption_excel_path is not None and res.consumption_excel_path.exists()
    assert res.consumption_excel_path.name == "consumption.xlsx"
    assert res.dataset.summary.total_hours > 0


def test_calculation_service_execution(tmp_path: Path) -> None:
    """Verify that CalculationService runs end-to-end optimization and file exports."""
    req = CalculationRequest(
        consumption_dir=Path(".input/consumption"),
        generation_dir=Path(".input/generation"),
        curated_dir=Path(".curated"),
        output_dir=tmp_path,
        cups_config_path=Path(".input/cups/cups.json"),
        strategy=OptimizationStrategy.OPTIMAL,
        precision=1,
    )
    res = CalculationService.execute(req)
    assert res.opt_result is not None
    assert res.opt_result.baselines == {}
    assert res.metadata.cups_count > 0
    assert len(res.exported_paths) > 0
    assert all(p.exists() for p in res.exported_paths)


def test_calculation_service_include_baselines_on_demand(tmp_path: Path) -> None:
    """Verify CalculationService evaluates baseline strategies only when include_baselines=True."""
    curated_dir = tmp_path / "curated"
    output_dir = tmp_path / "output"
    curated_dir.mkdir()
    output_dir.mkdir()

    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    esd_csv = curated_dir / "esd.csv"
    esd_csv.write_text(
        "\n".join(
            [
                "timestamp;year;month;day;hour;day_of_week;is_weekend;cups_id;use;consumption;community_demand;generation;self_consumption;exported_energy;imported_energy;temperature;cloud_cover",
                f"2026-05-01 12:00:00;2026;5;1;12;Friday;False;{c1};Aerotermia;6,0;8,0;10,0;6,0;4,0;0,0;22,0;10",
                f"2026-05-01 12:00:00;2026;5;1;12;Friday;False;{c2};Garaje;2,0;8,0;10,0;0,0;0,0;0,0;22,0;10",
            ]
        ),
        encoding="utf-8",
    )

    req = CalculationRequest(
        consumption_dir=tmp_path / "missing_cons",
        generation_dir=tmp_path / "missing_gen",
        curated_dir=esd_csv,
        output_dir=output_dir,
        strategy=OptimizationStrategy.OPTIMAL,
        precision=0,
        include_baselines=True,
    )
    res = CalculationService.execute(req)
    assert set(res.opt_result.baselines.keys()) == {"consumption_share", "equal"}


def test_calculation_service_progress_callback(tmp_path: Path) -> None:
    """Verify that CalculationService invokes progress callback across all 4 stages."""
    steps_called: list[tuple[int, str]] = []

    def callback(step: int, msg: str) -> None:
        steps_called.append((step, msg))

    req = CalculationRequest(
        consumption_dir=Path(".input/consumption"),
        generation_dir=Path(".input/generation"),
        curated_dir=Path(".curated"),
        output_dir=tmp_path,
        cups_config_path=Path(".input/cups/cups.json"),
        strategy=OptimizationStrategy.OPTIMAL,
    )
    CalculationService.execute(req, progress_callback=callback)
    assert [step for step, _ in steps_called] == [1, 2, 3, 4]
    assert all(len(msg) > 0 for _, msg in steps_called)


def test_weather_service_coordinate_resolution_priority(tmp_path: Path) -> None:
    """Verify coordinate fallback resolution priority: CLI -> cups.json -> AppConfig."""
    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [
                {"cups": "ES0021000000000001AA", "lat": 41.6745, "long": -4.7272},
                {"cups": "ES0021000000000002BB", "lat": 40.4168, "lon": -3.7038},
            ]
        ),
        encoding="utf-8",
    )
    cfg = AppConfig(latitude=37.3891, longitude=-5.9845)

    # 1. Manual coordinates override everything
    coords_manual = WeatherService.resolve_coordinates(
        latitude=43.2630,
        longitude=-2.9350,
        cups_file=cups_file,
        config=cfg,
    )
    assert coords_manual == [(43.2630, -2.9350)]

    # 2. cups.json overrides config
    coords_cups = WeatherService.resolve_coordinates(
        latitude=None,
        longitude=None,
        cups_file=cups_file,
        config=cfg,
    )
    assert coords_cups == [(41.6745, -4.7272), (40.4168, -3.7038)]

    # 3. Config fallback when cups_file is empty/missing
    coords_cfg = WeatherService.resolve_coordinates(
        latitude=None,
        longitude=None,
        cups_file=tmp_path / "missing.json",
        config=cfg,
    )
    assert coords_cfg == [(37.3891, -5.9845)]

    # 4. Incomplete manual coordinates raise ValidationError
    with pytest.raises(ValidationError, match="Both --latitude and --longitude"):
        WeatherService.resolve_coordinates(latitude=40.0, longitude=None, config=cfg)
    with pytest.raises(ValidationError, match="Both --latitude and --longitude"):
        WeatherService.resolve_coordinates(latitude=None, longitude=-3.0, config=cfg)

    # 5. Missing coordinates raise ValidationError
    empty_cfg = AppConfig(latitude=None, longitude=None)
    with pytest.raises(ValidationError, match="Coordinates are required"):
        WeatherService.resolve_coordinates(
            latitude=None,
            longitude=None,
            cups_file=tmp_path / "missing.json",
            config=empty_cfg,
        )


def test_weather_service_execute_multi_location(tmp_path: Path) -> None:
    """Verify WeatherService.execute orchestrates downloads for all coordinates with progress reporting."""
    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [
                {"cups": "ES0021000000000001AA", "lat": 41.6745, "long": -4.7272},
                {"cups": "ES0021000000000002BB", "lat": 40.4168, "lon": -3.7038},
            ]
        ),
        encoding="utf-8",
    )

    weather_dir = tmp_path / "weather"
    calls: list[tuple[float, float, int, int]] = []

    def progress(lat: float, lon: float, idx: int, total: int) -> None:
        calls.append((lat, lon, idx, total))

    def mock_download_year(
        year: int, latitude: float, longitude: float, timezone: str
    ) -> tuple[Path, MagicMock, WeatherDownloadResult]:
        file_path = weather_dir / f"{year}_{latitude}_{longitude}.csv"
        result = WeatherDownloadResult(
            year=year,
            latitude=latitude,
            longitude=longitude,
            start_date=f"{year}-01-01",
            end_date=f"{year}-12-31",
            total_hours=8760,
            file_path=file_path,
            avg_temperature=15.0,
            min_temperature=-2.0,
            max_temperature=38.0,
            avg_cloud_cover=35.0,
            overwritten=False,
        )
        return file_path, MagicMock(), result

    with patch(
        "src.services.weather_service.OpenMeteoWeatherDownloader.download_year",
        side_effect=mock_download_year,
    ):
        req = WeatherRequest(
            year=2024,
            cups_file=cups_file,
            weather_dir=weather_dir,
            timezone="Europe/Madrid",
        )
        res = WeatherService.execute(req, progress_callback=progress)

    assert len(res.results) == 2
    assert res.results[0].latitude == 41.6745
    assert res.results[1].latitude == 40.4168
    assert calls == [
        (41.6745, -4.7272, 1, 2),
        (40.4168, -3.7038, 2, 2),
    ]


def test_unified_coordinate_resolution_prioritizes_primary_and_isolates_custom_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify primary CUPS coordinates take precedence and custom dirs ignore global AppConfig fallback."""
    from src.curation.curator import DataCurator

    cups_file = tmp_path / "cups.json"
    cups_file.write_text(
        json.dumps(
            [
                {
                    "cups": "ES0021000000000001AA",
                    "lat": 37.3891,
                    "lon": -5.9845,
                    "primary": False,
                },
                {
                    "cups": "ES0021000000000002BB",
                    "lat": 40.4168,
                    "long": -3.7038,
                    "primary": True,
                },
            ]
        ),
        encoding="utf-8",
    )

    global_cfg = AppConfig(latitude=43.2630, longitude=-2.9350)
    monkeypatch.setattr("src.curation.curator.load_config", lambda: global_cfg)

    # 1. WeatherService puts primary CUPS coordinates first
    coords = WeatherService.resolve_coordinates(cups_file=cups_file, config=global_cfg)
    assert coords == [(40.4168, -3.7038), (37.3891, -5.9845)]

    # 2. DataCurator.get_default_location picks primary CUPS coordinate
    custom_cons = tmp_path / "custom_cons"
    custom_cons.mkdir()
    curator = DataCurator(consumption_dir=custom_cons, cups_config_path=cups_file)
    assert curator.get_default_location() == (40.4168, -3.7038)

    # 3. Custom consumption_dir in a workspace without cups.json must NOT inherit global AppConfig coordinates
    isolated_cons = tmp_path / "isolated" / "consumption"
    isolated_cons.mkdir(parents=True)
    curator_isolated = DataCurator(consumption_dir=isolated_cons)
    assert curator_isolated.get_default_location() is None
