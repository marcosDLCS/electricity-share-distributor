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


def test_cli_calculate_skeleton() -> None:
    result = runner.invoke(app, ["calculate"])
    assert result.exit_code == 0
    assert "esd calculate" in result.output
