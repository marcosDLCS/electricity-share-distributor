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
    cleaned = t("cleaned_files", lang="en", count=3)
    assert "3 file(s)" in cleaned
    init_es = t("init_success", lang="es", language="Español")
    assert "Español" in init_es


def test_structured_namespaces_access() -> None:
    # Test dot-notation namespaced keys map identically to flat keys
    assert t("app.app_title", lang="en") == t("app_title", lang="en")
    assert t("cli.cmd_calculate_desc", lang="en") == t("cmd_calculate_desc", lang="en")
    assert t("doctor.doc_lbl_healthy", lang="en") == t("doc_lbl_healthy", lang="en")
    assert t("curate.title_curate_summary", lang="es") == t("title_curate_summary", lang="es")
    assert t("tables.title_community_summary", lang="es") == t("title_community_summary", lang="es")
    assert t("analytics.summary_overview_title", lang="en") == t(
        "summary_overview_title", lang="en"
    )

    # Prefix-stripped aliases are no longer generated
    assert "cli.calculate_desc" not in TRANSLATIONS["en"]
    assert "doctor.lbl_healthy" not in TRANSLATIONS["en"]
    assert "export.success_title" not in TRANSLATIONS["en"]


def test_i18n_namespace_enum() -> None:
    assert I18nNamespace.APP == "app"
    assert I18nNamespace.CLI == "cli"
    assert I18nNamespace.STATUS == "status"
    assert I18nNamespace.DOCTOR == "doctor"
    assert I18nNamespace.CURATE == "curate"
    assert I18nNamespace.WEATHER == "weather"
    assert I18nNamespace.TABLES == "tables"
    assert I18nNamespace.EXPORT == "export"
    assert I18nNamespace.ANALYTICS == "analytics"

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


def test_i18n_structured_namespace_parity_and_no_collisions() -> None:
    """Verify per-namespace EN/ES key parity, non-empty values, and exact 2x flat+namespaced sizing."""
    for ns in I18nNamespace:
        en_entries = STRUCTURED_TRANSLATIONS["en"][ns]
        es_entries = STRUCTURED_TRANSLATIONS["es"][ns]
        assert set(en_entries.keys()) == set(es_entries.keys()), (
            f"Namespace '{ns}' mismatch: EN-ES={set(en_entries) - set(es_entries)}, "
            f"ES-EN={set(es_entries) - set(en_entries)}"
        )
        for key, en_val in en_entries.items():
            assert en_val.strip(), f"Empty EN string for {ns}.{key}"
            assert es_entries[key].strip(), f"Empty ES string for {ns}.{key}"

    expected_en_count = 2 * sum(len(entries) for entries in STRUCTURED_TRANSLATIONS["en"].values())
    expected_es_count = 2 * sum(len(entries) for entries in STRUCTURED_TRANSLATIONS["es"].values())
    assert len(TRANSLATIONS["en"]) == expected_en_count
    assert len(TRANSLATIONS["es"]) == expected_es_count
