"""Tests for Typer CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.version import get_version

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert get_version() in result.output


def test_cli_help() -> None:
    result = runner.invoke(app, ["help", "--lang", "en"])
    assert result.exit_code == 0
    assert "ELECTRICITY SHARE DISTRIBUTOR" in result.output
    assert "AVAILABLE COMMANDS" in result.output

    result_es = runner.invoke(app, ["help", "--lang", "es"])
    assert result_es.exit_code == 0
    assert "DISTRIBUIDOR DE ENERGÍA COMPARTIDA" in result_es.output
    assert "COMANDOS DISPONIBLES" in result_es.output


def test_cli_init_english() -> None:
    result = runner.invoke(app, ["init", "--lang", "en"])
    assert result.exit_code == 0
    # Matches both "✓ Initialized Successfully" and "✓ Re-initialized Successfully"
    assert "nitialized Successfully" in result.output
    assert "Output Directory" in result.output


def test_cli_init_no_flags_uses_defaults() -> None:
    """init with no flags should succeed, defaulting to English and zero precision."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "nitialized Successfully" in result.output
    assert "English (en)" in result.output
    assert "0 decimal(s)" in result.output


def test_cli_init_precision_valid() -> None:
    result = runner.invoke(app, ["init", "--lang", "en", "--precision", "2"])
    assert result.exit_code == 0
    assert "2 decimal(s)" in result.output


def test_cli_init_precision_invalid() -> None:
    result = runner.invoke(app, ["init", "--precision", "5"])
    assert result.exit_code != 0
    assert "Invalid share precision" in result.output


def test_cli_init_spanish() -> None:
    result = runner.invoke(app, ["init", "--lang", "es", "--precision", "1"])
    assert result.exit_code == 0
    assert "inicializado" in result.output.lower()
    assert "1 decimal(es)" in result.output


def test_cli_init_clears_output(tmp_path) -> None:
    """init should always clear the .output directory contents."""
    import json

    # Create a minimal config pointing output to tmp_path
    cfg_file = tmp_path / ".esd_config.json"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "old_report.csv").write_text("data")
    (out_dir / "another.json").write_text("{}")

    cfg_data = {
        "language": "en",
        "share_precision": 0,
        "input_dir": str(tmp_path / ".input"),
        "consumption_dir": str(tmp_path / ".input/consumption"),
        "generation_dir": str(tmp_path / ".input/generation"),
        "output_dir": str(out_dir),
    }
    cfg_file.write_text(json.dumps(cfg_data))

    from src.config import clear_output_directory

    cleared = clear_output_directory(out_dir)
    assert cleared == 2
    assert not [p for p in out_dir.iterdir() if not p.name.startswith(".")]


def test_cli_calculate_default() -> None:
    result = runner.invoke(app, ["calculate", "--lang", "en", "--format", "none"])
    assert result.exit_code == 0
    assert "COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY" in result.output
    assert "CUPS" in result.output
    assert "Monthly Coefficient Proposals" not in result.output


def test_cli_calculate_month_filter() -> None:
    result = runner.invoke(
        app, ["calculate", "-y", "2026", "-m", "5", "--format", "none", "--lang", "en"]
    )
    assert result.exit_code == 0
    assert "2026-05" in result.output
    assert "Monthly Coefficient Proposals" not in result.output


def test_cli_calculate_views() -> None:
    # Test coefficients view
    result_coeff = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--view",
            "coefficients",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )
    assert result_coeff.exit_code == 0
    assert "Monthly Coefficient Proposals" in result_coeff.output
    assert "Beta" in result_coeff.output

    # Test trajectory view
    result_traj = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--view",
            "trajectory",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )
    assert result_traj.exit_code == 0
    assert "Month-by-Month Community Energy Trajectory" in result_traj.output

    # Test matrix view
    result_matrix = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--view",
            "matrix",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )
    assert result_matrix.exit_code == 0
    assert "Distribution Share" in result_matrix.output
    assert "TOTAL" in result_matrix.output
    assert "RD 244/2019" in result_matrix.output

    # Test summary view
    result_sum = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--view",
            "summary",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )
    assert result_sum.exit_code == 0
    assert "COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY" in result_sum.output
    assert "Distribution Share" in result_sum.output


def test_cli_calculate_strategies() -> None:
    for strat in ["optimal", "consumption_share", "equal"]:
        res = runner.invoke(
            app, ["calculate", "-y", "2026", "-m", "5", "--strategy", strat, "--format", "none"]
        )
        assert res.exit_code == 0


def test_cli_calculate_export_formats(tmp_path) -> None:
    out_dir = tmp_path / "out"
    res = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--format",
            "all",
            "--output-dir",
            str(out_dir),
            "--lang",
            "en",
        ],
    )
    assert res.exit_code == 0
    csv_files = list(out_dir.glob("*.csv"))
    html_files = list(out_dir.glob("*.html"))
    json_files = list(out_dir.glob("*.json"))
    md_files = list(out_dir.glob("*.md"))
    # Two CSVs exported (monthly_shares and hourly_shares) plus one interactive HTML report
    assert len(csv_files) == 2
    assert len(html_files) == 1
    assert len(json_files) == 0
    assert len(md_files) == 0
    csv_names = [f.name for f in csv_files]
    assert any("_esd_monthly_shares.csv" in n for n in csv_names)
    assert any("_esd_hourly_shares.csv" in n for n in csv_names)
    assert html_files[0].name.endswith("_esd_interactive_report.html")


def test_cli_calculate_missing_directory(tmp_path) -> None:
    empty_dir = tmp_path / "nonexistent"
    res = runner.invoke(app, ["calculate", "--consumption-dir", str(empty_dir)])
    assert res.exit_code != 0


def test_cli_config_display() -> None:
    res = runner.invoke(app, ["config"])
    assert res.exit_code == 0
    assert "Active Configuration" in res.output or "Configuración Activa" in res.output


def test_cli_config_modify_lang() -> None:
    res = runner.invoke(app, ["config", "--lang", "es"])
    assert res.exit_code == 0
    assert "es" in res.output

    # Reset back to en
    res_en = runner.invoke(app, ["config", "--lang", "en"])
    assert res_en.exit_code == 0


def test_cli_config_modify_precision() -> None:
    res = runner.invoke(app, ["config", "--precision", "2"])
    assert res.exit_code == 0
    assert "2 decimal(s)" in res.output

    # Invalid precision
    res_err = runner.invoke(app, ["config", "--precision", "4"])
    assert res_err.exit_code != 0
    assert "Invalid share precision" in res_err.output

    # Reset back to 0
    res_reset = runner.invoke(app, ["config", "--precision", "0"])
    assert res_reset.exit_code == 0


def test_cli_calculate_precision_flag() -> None:
    res0 = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--precision",
            "0",
            "--view",
            "coefficients",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )
    assert res0.exit_code == 0

    res2 = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--precision",
            "2",
            "--view",
            "coefficients",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )
    assert res2.exit_code == 0

    res_inv = runner.invoke(app, ["calculate", "--precision", "9"])
    assert res_inv.exit_code != 0
    assert "Invalid share precision" in res_inv.output


def test_cli_cleanup_force(tmp_path) -> None:
    # Create fake files in dummy output dir
    dummy_out = tmp_path / "dummy_out"
    dummy_out.mkdir()
    (dummy_out / "test.csv").write_text("dummy")

    # Override config or pass custom
    res = runner.invoke(app, ["cleanup", "--force"])
    assert res.exit_code == 0


def test_cli_init_interactive_prompts() -> None:
    """Ensure init interactive prompts accept language and precision inputs."""
    result = runner.invoke(app, ["init"], input="es\n2\n")
    assert result.exit_code == 0
    assert "inicializado" in result.output.lower()
    assert "2 decimal(es)" in result.output


def test_cli_init_interactive_prompts_defaults() -> None:
    """Ensure init interactive prompts default to English and zero precision when Enter is pressed."""
    from src.config import get_language, get_precision, set_language, set_precision

    set_language("es")
    set_precision(2)
    assert get_language() == "es"
    assert get_precision() == 2

    # User presses Enter on both prompts (empty inputs)
    result = runner.invoke(app, ["init"], input="\n\n")
    assert result.exit_code == 0
    assert "nitialized Successfully" in result.output
    assert "English (en)" in result.output
    assert "0 decimal(s)" in result.output
    assert get_language() == "en"
    assert get_precision() == 0


def test_cli_calculate_spanish() -> None:
    """Ensure calculate outputs Spanish console view when --lang es is passed."""
    result = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--lang",
            "es",
            "--format",
            "none",
            "--view",
            "summary",
        ],
    )
    assert result.exit_code == 0
    assert "RESUMEN DE LA COMUNIDAD DE AUTOCONSUMO COLECTIVO" in result.output
    assert "Trayectoria Energética Mensual" in result.output
    assert "Comparativa de Eficiencia según Estrategia de Reparto" not in result.output
    assert "Propuesta de Coeficientes Mensuales" not in result.output


def test_cli_doctor_spanish() -> None:
    """Ensure doctor outputs Spanish diagnostic report when --lang es is passed."""
    result = runner.invoke(app, ["doctor", "--lang", "es"])
    # Should contain Spanish report title and headers
    assert "INFORME DE DIAGNÓSTICO ESD DATA DOCTOR" in result.output
    assert "Puntos Suministro:" in result.output
    assert "Estado de Datos de Consumo" in result.output


def test_cli_calculate_hourly_flag() -> None:
    """Ensure calculate --hourly performs calculation without dumping the diurnal profile in console."""
    result = runner.invoke(
        app,
        ["calculate", "-y", "2026", "-m", "5", "--hourly", "--format", "none", "--lang", "en"],
    )
    assert result.exit_code == 0
    assert "Diurnal Distribution Share Profile" not in result.output
    assert "Allocation Strategy Efficiency Comparison" not in result.output


def test_cli_calculate_hourly_short_flag() -> None:
    """Ensure calculate -H performs calculation without dumping the diurnal profile in console."""
    result = runner.invoke(
        app,
        ["calculate", "-y", "2026", "-m", "5", "-H", "--format", "none", "--lang", "en"],
    )
    assert result.exit_code == 0
    assert "Diurnal Distribution Share Profile" not in result.output
    assert "Allocation Strategy Efficiency Comparison" not in result.output


def test_cli_calculate_view_hourly() -> None:
    """Ensure calculate --view hourly displays only the hourly profile table."""
    result = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--view",
            "hourly",
            "--format",
            "none",
            "--lang",
            "en",
        ],
    )
    assert result.exit_code == 0
    assert "Diurnal Distribution Share Profile" in result.output
    assert "COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY" not in result.output


def test_cli_calculate_hourly_export_csv(tmp_path: Path) -> None:
    """Ensure calculate --hourly exports monthly and hourly shares CSV files."""
    result = runner.invoke(
        app,
        [
            "calculate",
            "-y",
            "2026",
            "-m",
            "5",
            "--hourly",
            "--output-dir",
            str(tmp_path),
            "--format",
            "csv",
        ],
    )
    assert result.exit_code == 0
    exported_files = list(tmp_path.glob("*.csv"))
    file_names = [f.name for f in exported_files]
    assert any("_esd_monthly_shares.csv" in n for n in file_names)
    assert any("_esd_hourly_shares.csv" in n for n in file_names)


def test_cli_calculate_dynamic_defaults_from_config(tmp_path: Path, monkeypatch) -> None:
    """Ensure calculate command dynamically picks up directories from config."""
    from src.config import AppConfig

    custom_out = tmp_path / "custom_output"
    custom_out.mkdir()

    cfg = AppConfig(
        output_dir=str(custom_out),
    )
    monkeypatch.setattr("src.cli.load_config", lambda: cfg)

    result = runner.invoke(
        app,
        [
            "calculate",
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
    exported = list(custom_out.glob("*.csv"))
    assert len(exported) > 0


def test_cli_cleanup_with_output_dir_override(tmp_path: Path) -> None:
    """Ensure cleanup --output-dir cleans the overridden directory."""
    test_dir = tmp_path / "clean_me"
    test_dir.mkdir()
    (test_dir / "temp_file.csv").write_text("dummy")

    result = runner.invoke(app, ["cleanup", "-o", str(test_dir), "--force"])
    assert result.exit_code == 0
    assert not (test_dir / "temp_file.csv").exists()


def test_cli_config_invalid_coordinates_localized() -> None:
    """Test localized error messages for out-of-range coordinates in config command."""
    res_en_lat = runner.invoke(app, ["config", "--lat", "95.0", "--lang", "en"])
    assert res_en_lat.exit_code != 0
    assert "Latitude must be between -90.0 and 90.0 (got 95.0)." in res_en_lat.output

    res_es_lat = runner.invoke(app, ["config", "--lat", "-95.0", "--lang", "es"])
    assert res_es_lat.exit_code != 0
    assert "La latitud debe estar entre -90.0 y 90.0 (valor recibido: -95.0)." in res_es_lat.output

    res_en_lon = runner.invoke(app, ["config", "--lon", "190.0", "--lang", "en"])
    assert res_en_lon.exit_code != 0
    assert "Longitude must be between -180.0 and 180.0 (got 190.0)." in res_en_lon.output

    res_es_lon = runner.invoke(app, ["config", "--lon", "-190.0", "--lang", "es"])
    assert res_es_lon.exit_code != 0
    assert (
        "La longitud debe estar entre -180.0 y 180.0 (valor recibido: -190.0)." in res_es_lon.output
    )


def test_cli_calculate_invalid_strategy_and_share_localized() -> None:
    """Test localized error messages for invalid strategy and share bounds."""
    res_en_strat = runner.invoke(app, ["calculate", "--strategy", "invalid_strat", "--lang", "en"])
    assert res_en_strat.exit_code != 0
    assert "Invalid strategy 'invalid_strat'." in res_en_strat.output

    res_es_strat = runner.invoke(app, ["calculate", "--strategy", "invalid_strat", "--lang", "es"])
    assert res_es_strat.exit_code != 0
    assert "Estrategia no válida 'invalid_strat'." in res_es_strat.output

    res_en_share = runner.invoke(app, ["calculate", "--min-share", "150", "--lang", "en"])
    assert res_en_share.exit_code != 0
    assert "--min-share must be between 0% and 100%. Got 150.0." in res_en_share.output

    res_es_share = runner.invoke(app, ["calculate", "--max-share", "-5", "--lang", "es"])
    assert res_es_share.exit_code != 0
    assert "--max-share debe estar entre 0% y 100%. Valor recibido: -5.0." in res_es_share.output


def test_cli_doctor_handles_esd_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure doctor command cleanly catches EsdError and exits with code 1 without traceback."""
    from src.domain.exceptions import IngestionError
    from src.services.doctor_service import DoctorService

    def mock_execute(*args: Any, **kwargs: Any) -> Any:
        raise IngestionError("Simulated ingestion error in DoctorService")

    monkeypatch.setattr(DoctorService, "execute", mock_execute)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Simulated ingestion error in DoctorService" in result.output
    assert "Traceback" not in result.output


def test_cli_subcommands_unified_esd_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure curate, weather, and calculate cleanly catch EsdError and exit with code 1."""
    from src.domain.exceptions import CurationError, OptimizationError, ValidationError
    from src.services.calculation_service import CalculationService
    from src.services.curation_service import CurationService
    from src.services.weather_service import WeatherService

    def mock_curation_execute(*args: Any, **kwargs: Any) -> Any:
        raise CurationError("Mock curation failure")

    def mock_weather_execute(*args: Any, **kwargs: Any) -> Any:
        raise ValidationError("Mock weather failure")

    def mock_calc_execute(*args: Any, **kwargs: Any) -> Any:
        raise OptimizationError("Mock calculation failure")

    monkeypatch.setattr(CurationService, "execute", mock_curation_execute)
    res_curate = runner.invoke(app, ["curate"])
    assert res_curate.exit_code == 1
    assert "Mock curation failure" in res_curate.output
    assert "Traceback" not in res_curate.output

    monkeypatch.setattr(WeatherService, "execute", mock_weather_execute)
    res_weather = runner.invoke(app, ["weather", "--year", "2024"])
    assert res_weather.exit_code == 1
    assert "Mock weather failure" in res_weather.output
    assert "Traceback" not in res_weather.output

    monkeypatch.setattr(CalculationService, "execute", mock_calc_execute)
    res_calc = runner.invoke(app, ["calculate", "-y", "2026", "-m", "5", "--format", "none"])
    assert res_calc.exit_code == 1
    assert "Mock calculation failure" in res_calc.output
    assert "Traceback" not in res_calc.output


def test_cli_curate_short_flag_u_and_o(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure esd curate accepts both -u and -o for --curated-dir."""
    from unittest.mock import MagicMock

    import src.cli as cli_mod
    from src.services.curation_service import CurationRequest, CurationService

    captured_requests: list[CurationRequest] = []

    def mock_curation_execute(req: CurationRequest) -> MagicMock:
        captured_requests.append(req)
        mock_res = MagicMock()
        mock_res.csv_path = req.curated_dir / "curated.csv"
        mock_res.excel_path = req.curated_dir / "curated.xlsx"
        return mock_res

    monkeypatch.setattr(CurationService, "execute", mock_curation_execute)
    monkeypatch.setattr(cli_mod, "render_curate_summary", lambda **kwargs: None)

    custom_dir_u = tmp_path / "curated_u"
    res_u = runner.invoke(app, ["curate", "-u", str(custom_dir_u)])
    assert res_u.exit_code == 0
    assert captured_requests[-1].curated_dir == custom_dir_u

    custom_dir_o = tmp_path / "curated_o"
    res_o = runner.invoke(app, ["curate", "-o", str(custom_dir_o)])
    assert res_o.exit_code == 0
    assert captured_requests[-1].curated_dir == custom_dir_o


def test_cli_config_modify_curated_dir(tmp_path: Path) -> None:
    """Ensure esd config accepts --curated-dir / -u and persists curated_dir."""
    from src.config import load_config

    custom_dir = tmp_path / "test_curated"
    res = runner.invoke(app, ["config", "-u", str(custom_dir)])
    assert res.exit_code == 0
    assert "curated_dir" in res.output
    assert load_config().curated_dir == str(custom_dir)

    # Reset back to default .curated
    res_reset = runner.invoke(app, ["config", "--curated-dir", ".curated"])
    assert res_reset.exit_code == 0
    assert load_config().curated_dir == ".curated"


def test_cli_config_display_includes_curated_dir() -> None:
    """Ensure render_config_view displays curated_dir."""
    res = runner.invoke(app, ["config"])
    assert res.exit_code == 0
    assert "curated_dir" in res.output
