"""Tests for internationalization, structured namespaces, and translation parity."""

from __future__ import annotations

import re

from src.i18n import STRUCTURED_TRANSLATIONS, TRANSLATIONS, I18nNamespace, t


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


def test_structured_namespaces_access() -> None:
    # Test dot-notation namespaced keys
    assert t("app.app_title", lang="en") == t("app_title", lang="en")
    assert t("cli.cmd_calculate_desc", lang="en") == t("cmd_calculate_desc", lang="en")
    assert t("doctor.doc_lbl_healthy", lang="en") == t("doc_lbl_healthy", lang="en")
    assert t("curate.title_curate_summary", lang="es") == t("title_curate_summary", lang="es")
    assert t("tables.title_community_summary", lang="es") == t("title_community_summary", lang="es")

    # Test clean prefix aliases
    assert t("cli.calculate_desc", lang="en") == t("cmd_calculate_desc", lang="en")
    assert t("doctor.lbl_healthy", lang="en") == t("doc_lbl_healthy", lang="en")
    assert t("export.report_title", lang="en") == t("md_report_title", lang="en")


def test_i18n_namespace_enum() -> None:
    assert I18nNamespace.APP == "app"
    assert I18nNamespace.CLI == "cli"
    assert I18nNamespace.STATUS == "status"
    assert I18nNamespace.DOCTOR == "doctor"
    assert I18nNamespace.CURATE == "curate"
    assert I18nNamespace.WEATHER == "weather"
    assert I18nNamespace.TABLES == "tables"
    assert I18nNamespace.EXPORT == "export"

    for ns in I18nNamespace:
        assert ns in STRUCTURED_TRANSLATIONS["en"]
        assert ns in STRUCTURED_TRANSLATIONS["es"]


def test_i18n_key_parity() -> None:
    en_keys = set(TRANSLATIONS["en"].keys())
    es_keys = set(TRANSLATIONS["es"].keys())
    assert en_keys == es_keys, f"Key mismatch: EN-ES={en_keys - es_keys}, ES-EN={es_keys - en_keys}"


def test_i18n_placeholder_parity() -> None:
    pattern = re.compile(r"\{([a-zA-Z0-9_]+)\}")
    en = TRANSLATIONS["en"]
    es = TRANSLATIONS["es"]

    for key in en:
        en_placeholders = set(pattern.findall(en[key]))
        es_placeholders = set(pattern.findall(es[key]))
        assert en_placeholders == es_placeholders, (
            f"Placeholder mismatch for '{key}': EN={en_placeholders}, ES={es_placeholders}"
        )


def test_i18n_cli_option_keys() -> None:
    """Verify newly added CLI option keys and html export format in i18n catalog."""
    for lang in ("en", "es"):
        assert "html" in t("opt_format", lang=lang)
        assert len(t("opt_min_share", lang=lang)) > 0
        assert len(t("opt_max_share", lang=lang)) > 0
        assert len(t("opt_precision", lang=lang)) > 0
        assert len(t("opt_strategy", lang=lang)) > 0
        assert len(t("opt_verbose", lang=lang)) > 0
