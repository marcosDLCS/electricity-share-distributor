"""Tests for Typer CLI commands."""

from __future__ import annotations

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
    assert "Initialized" in result.output or "Already Initialized" in result.output


def test_cli_init_spanish() -> None:
    result = runner.invoke(app, ["init", "--lang", "es"])
    assert result.exit_code == 0
    assert "inicializado" in result.output.lower()


def test_cli_calculate_default() -> None:
    result = runner.invoke(app, ["calculate", "--lang", "en", "--format", "none"])
    assert result.exit_code == 0
    assert "COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY" in result.output
    assert "CUPS" in result.output


def test_cli_calculate_month_filter() -> None:
    result = runner.invoke(
        app, ["calculate", "-y", "2026", "-m", "5", "--format", "none", "--lang", "en"]
    )
    assert result.exit_code == 0
    assert "2026-05" in result.output


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
    json_files = list(out_dir.glob("*.json"))
    md_files = list(out_dir.glob("*.md"))
    assert len(csv_files) == 1
    assert len(json_files) == 1
    assert len(md_files) == 1


def test_cli_calculate_missing_directory(tmp_path) -> None:
    empty_dir = tmp_path / "nonexistent"
    res = runner.invoke(app, ["calculate", "--consumption-dir", str(empty_dir)])
    assert res.exit_code != 0
