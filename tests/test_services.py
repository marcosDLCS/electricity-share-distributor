"""Unit tests for application service orchestrators."""

from __future__ import annotations

from pathlib import Path

from src.optimization.models import OptimizationStrategy
from src.services import (
    CalculationRequest,
    CalculationService,
    CurationRequest,
    CurationService,
    DoctorRequest,
    DoctorService,
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
    assert res.dataset.summary.total_hours > 0


def test_calculation_service_execution(tmp_path: Path) -> None:
    """Verify that CalculationService runs end-to-end optimization and file exports."""
    req = CalculationRequest(
        consumption_dir=Path(".input/consumption"),
        generation_dir=Path(".input/generation"),
        curated_dir=Path(".curated"),
        output_dir=tmp_path,
        cups_config_path=Path(".input/cups/cups.json"),
        year=2026,
        month=5,
        strategy=OptimizationStrategy.OPTIMAL,
        precision=1,
        export_format="csv",
    )
    res = CalculationService.execute(req)
    assert res.opt_result is not None
    assert res.metadata.cups_count > 0
    assert len(res.exported_paths) > 0
    assert all(p.exists() for p in res.exported_paths)


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
        year=2026,
        month=5,
        strategy=OptimizationStrategy.OPTIMAL,
        export_format="csv",
    )
    CalculationService.execute(req, progress_callback=callback)
    assert [step for step, _ in steps_called] == [1, 2, 3, 4]
    assert all(len(msg) > 0 for _, msg in steps_called)
