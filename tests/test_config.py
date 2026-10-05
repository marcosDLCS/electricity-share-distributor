"""Tests for configuration, settings persistence, and language normalization."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import (
    AppConfig,
    ensure_directories,
    is_initialized,
    load_config,
    mark_initialized,
    normalize_language_code,
    set_language,
)


def test_normalize_language_code_valid() -> None:
    assert normalize_language_code("en") == "en"
    assert normalize_language_code("english") == "en"
    assert normalize_language_code("es") == "es"
    assert normalize_language_code("spanish") == "es"
    assert normalize_language_code("español") == "es"


def test_normalize_language_code_invalid() -> None:
    with pytest.raises(ValueError, match="Unsupported language"):
        normalize_language_code("fr")


def test_config_lifecycle(tmp_path: Path) -> None:
    cfg_file = tmp_path / ".esd_config.json"
    assert not is_initialized(cfg_file)

    cfg = load_config(cfg_file)
    assert cfg.language == "en"

    set_language("es", path=cfg_file)
    assert load_config(cfg_file).language == "es"

    mark_initialized(path=cfg_file, timestamp="2026-10-05T12:00:00", version="2026.10.001")
    assert is_initialized(cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.initialized_at == "2026-10-05T12:00:00"
    assert reloaded.version == "2026.10.001"


def test_ensure_directories(tmp_path: Path) -> None:
    cfg = AppConfig(
        input_dir=str(tmp_path / "in"),
        consumption_dir=str(tmp_path / "in" / "cons"),
        generation_dir=str(tmp_path / "in" / "gen"),
        output_dir=str(tmp_path / "out"),
    )
    in_p, cons_p, gen_p, out_p = ensure_directories(config=cfg)
    assert in_p.is_dir()
    assert cons_p.is_dir()
    assert gen_p.is_dir()
    assert out_p.is_dir()


def test_validate_share_precision() -> None:
    from src.config import validate_share_precision

    assert validate_share_precision(0) == 0
    assert validate_share_precision(1) == 1
    assert validate_share_precision(2) == 2

    with pytest.raises(ValueError, match="Invalid share precision"):
        validate_share_precision(-1)

    with pytest.raises(ValueError, match="Invalid share precision"):
        validate_share_precision(3)


def test_config_precision_lifecycle(tmp_path: Path) -> None:
    from src.config import get_precision, load_config, set_precision

    cfg_file = tmp_path / ".esd_config.json"
    # Default is 0
    assert get_precision(cfg_file) == 0

    # Set to 1
    set_precision(1, path=cfg_file)
    assert get_precision(cfg_file) == 1
    assert load_config(cfg_file).share_precision == 1

    # Set to 2
    set_precision(2, path=cfg_file)
    assert get_precision(cfg_file) == 2
    assert load_config(cfg_file).share_precision == 2
