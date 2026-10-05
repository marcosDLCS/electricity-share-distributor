"""Tests for CalVer versioning engine and consistency checks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.version import (
    check_version_consistency,
    format_version,
    generate_next_version,
    get_version,
    parse_version,
)


def test_get_version_format() -> None:
    ver = get_version()
    year, month, seq = parse_version(ver)
    assert year >= 2025
    assert 1 <= month <= 12
    assert seq >= 1


def test_parse_invalid_version() -> None:
    with pytest.raises(ValueError, match="Invalid version format"):
        parse_version("invalid-version")


def test_format_version() -> None:
    assert format_version(2026, 10, 5) == "2026.10.005"


def test_generate_next_version_same_month() -> None:
    dt = datetime(2026, 10, 15)
    next_v = generate_next_version("2026.10.001", target_date=dt)
    assert next_v == "2026.10.002"


def test_generate_next_version_new_month() -> None:
    dt = datetime(2026, 11, 1)
    next_v = generate_next_version("2026.10.005", target_date=dt)
    assert next_v == "2026.11.001"


def test_check_version_consistency(tmp_path: Path) -> None:
    valid, msg = check_version_consistency()
    assert valid is True
    assert "is valid and consistent" in msg
