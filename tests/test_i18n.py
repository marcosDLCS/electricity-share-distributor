"""Tests for internationalization and translation lookup."""

from __future__ import annotations

from src.i18n import t


def test_translation_english() -> None:
    msg = t("app_title", lang="en")
    assert "ELECTRICITY SHARE DISTRIBUTOR" in msg


def test_translation_spanish() -> None:
    msg = t("app_title", lang="es")
    assert "DISTRIBUIDOR DE ENERGÍA COMPARTIDA" in msg


def test_translation_fallback() -> None:
    # Non-existent key falls back to key itself
    assert t("non_existent_key_12345", lang="en") == "non_existent_key_12345"


def test_translation_interpolation() -> None:
    res = t("version_banner", lang="en", version="2026.10.001")
    assert "2026.10.001" in res
