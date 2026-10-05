"""Unit tests for the security and privacy validation harness."""

from __future__ import annotations

from pathlib import Path

from src.security import (
    find_cups_leaks,
    is_synthetic_cups,
    scan_directory,
    scan_file,
)

# Test fixture string constructed dynamically so it does not contain any real CUPS
PROHIBITED_SAMPLE_CUPS = "ES" + "9" * 16 + "ZZ"


def test_is_synthetic_cups_valid() -> None:
    assert is_synthetic_cups("ES0021000000000001AA")
    assert is_synthetic_cups("ES0021000000000002BB")
    assert is_synthetic_cups("ES0021000000000009II")
    assert is_synthetic_cups("es0021000000000001aa")


def test_is_synthetic_cups_real_detected() -> None:
    # Non-synthetic CUPS format must return False
    assert not is_synthetic_cups(PROHIBITED_SAMPLE_CUPS)
    assert not is_synthetic_cups("ES" + "1234567890123456" + "AB")


def test_find_cups_leaks_clean() -> None:
    clean_text = "Participant 1: ES0021000000000001AA, Participant 2: ES0021000000000002BB"
    assert find_cups_leaks(clean_text) == []


def test_find_cups_leaks_dirty() -> None:
    dirty_text = f"Prohibited CUPS in text: {PROHIBITED_SAMPLE_CUPS} and ES0021000000000001AA"
    leaks = find_cups_leaks(dirty_text)
    assert leaks == [PROHIBITED_SAMPLE_CUPS]


def test_scan_file(tmp_path: Path) -> None:
    file_clean = tmp_path / "clean.md"
    file_clean.write_text("All good with ES0021000000000001AA\n")
    assert scan_file(file_clean) == []

    file_dirty = tmp_path / "dirty.md"
    file_dirty.write_text(f"Header\nLeak: {PROHIBITED_SAMPLE_CUPS}\nFooter\n")
    findings = scan_file(file_dirty)
    assert len(findings) == 1
    assert findings[0][0] == 2  # Line 2
    assert findings[0][1] == PROHIBITED_SAMPLE_CUPS


def test_entire_repository_is_clean() -> None:
    """Ensure the current workspace repository is 100% free of real CUPS identifiers."""
    repo_root = Path.cwd()
    findings = scan_directory(repo_root)
    assert findings == {}, f"Prohibited CUPS found in files: {findings}"
