"""Application service for pre-flight data health audits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.ingestion.doctor import DataDoctor, DoctorReport


@dataclass(frozen=True)
class DoctorRequest:
    """Request DTO for running pre-flight data doctor audit."""

    consumption_dir: Path
    generation_dir: Path
    weather_dir: Path
    cups_config_path: Path | None = None


class DoctorService:
    """Orchestrates pre-flight data gap detection, CUPS enrichment, and overlap checks."""

    @staticmethod
    def execute(request: DoctorRequest) -> DoctorReport:
        """Run diagnosis on input datasets and return consolidated health report."""
        doctor = DataDoctor(
            consumption_dir=request.consumption_dir,
            generation_dir=request.generation_dir,
            weather_dir=request.weather_dir,
            cups_config_path=request.cups_config_path,
        )
        return doctor.diagnose()
