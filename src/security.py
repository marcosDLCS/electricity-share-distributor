"""Security and privacy validation harness for Electricity Share Distributor (esd).

Ensures that no real Spanish Universal Supply Point Codes (CUPS) or personally
identifiable energy data are committed or included in tracked repository files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Standard Spanish CUPS regex pattern: 'ES' followed by 16 digits and 2 control letters
# or up to 22 characters including measurement point suffix.
CUPS_PATTERN: re.Pattern[str] = re.compile(r"\bES[0-9]{16}[A-Za-z0-9]{2,4}\b", re.IGNORECASE)

# Permitted synthetic mock CUPS regex:
# Must follow ES00210000000000XXYY format (10 consecutive zeroes).
SYNTHETIC_CUPS_PATTERN: re.Pattern[str] = re.compile(
    r"^ES00210000000000\d{2}[A-Za-z0-9]{2,4}$", re.IGNORECASE
)

# File patterns or paths ignored from scanning (e.g. git internals, venv, caches, local inputs)
IGNORED_DIRS: set[str] = {
    ".git",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".input",
    ".output",
    "build",
    "dist",
    "electricity_share_distributor.egg-info",
}

IGNORED_EXTENSIONS: set[str] = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".xlsx",
    ".xls",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".pdf",
}


def is_synthetic_cups(cups: str) -> bool:
    """Check whether a given CUPS string matches the authorized synthetic mock pattern.

    Args:
        cups: CUPS identifier string.

    Returns:
        True if the CUPS is synthetic and safe to commit, False otherwise.
    """
    clean = cups.strip().upper()
    return bool(SYNTHETIC_CUPS_PATTERN.match(clean))


def find_cups_leaks(text: str) -> list[str]:
    """Scan text for any CUPS identifiers that are NOT synthetic mock CUPS.

    Args:
        text: Arbitrary text to scan.

    Returns:
        List of prohibited (real) CUPS identifiers detected.
    """
    matches = CUPS_PATTERN.findall(text)
    leaks: list[str] = []
    for match in matches:
        if not is_synthetic_cups(match):
            leaks.append(match)
    return leaks


def scan_file(file_path: Path) -> list[tuple[int, str, str]]:
    """Scan a single text file for prohibited real CUPS identifiers.

    Args:
        file_path: Path to the file.

    Returns:
        List of tuples (line_number, cups, line_preview).
    """
    findings: list[tuple[int, str, str]] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    for line_num, line in enumerate(content.splitlines(), start=1):
        leaks = find_cups_leaks(line)
        for leak in leaks:
            findings.append((line_num, leak, line.strip()))
    return findings


def scan_directory(root_dir: Path | str) -> dict[Path, list[tuple[int, str, str]]]:
    """Recursively scan a directory for prohibited real CUPS identifiers.

    Args:
        root_dir: Root directory path.

    Returns:
        Dictionary mapping file paths to lists of findings.
    """
    root = Path(root_dir)
    results: dict[Path, list[tuple[int, str, str]]] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        # Check ignored directories
        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        if path.suffix.lower() in IGNORED_EXTENSIONS:
            continue

        findings = scan_file(path)
        if findings:
            results[path] = findings

    return results


def check_privacy() -> int:
    """Pre-commit hook entry point to verify repository data privacy."""
    repo_root = Path.cwd()
    findings = scan_directory(repo_root)

    if not findings:
        return 0

    print("\n❌ [SECURITY ERROR] Real / Non-synthetic CUPS detected in repository files:")
    print("Under Real Decreto 244/2019 and GDPR, CUPS numbers are private residential identifiers.")
    print("Only synthetic mock CUPS adhering to pattern 'ES00210000000000XXYY' are permitted.\n")

    for file_path, items in findings.items():
        rel_path = file_path.relative_to(repo_root)
        print(f"File: {rel_path}")
        for line_num, cups, preview in items:
            print(f"  Line {line_num}: Prohibited CUPS '{cups}' -> {preview[:80]}")

    print("\nPlease replace these real identifiers with synthetic mock CUPS before committing.\n")
    return 1


if __name__ == "__main__":
    sys.exit(check_privacy())
