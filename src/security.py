"""Security and privacy validation harness for Electricity Share Distributor (esd).

Ensures that no real Spanish Universal Supply Point Codes (CUPS) or personally
identifiable energy data are committed or included in tracked repository files.
"""

from __future__ import annotations

import re
import subprocess
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


def scan_git_history(repo_root: Path | str | None = None) -> list[tuple[str, str, str]]:
    """Scan all git commits in repository history for prohibited real CUPS identifiers.

    Args:
        repo_root: Optional repository root path. Defaults to current working directory.

    Returns:
        List of tuples: (commit_hash, location_preview, prohibited_cups).
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    findings: list[tuple[str, str, str]] = []

    try:
        res = subprocess.run(
            ["git", "rev-list", "--all"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        commits = res.stdout.strip().split()
    except Exception:
        # Not a git repository or git command unavailable
        return findings

    for commit in commits:
        # 1. Scan commit message
        msg_res = subprocess.run(
            ["git", "log", "-1", "--format=%B", commit],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if msg_res.returncode == 0:
            for leak in find_cups_leaks(msg_res.stdout):
                findings.append((commit[:8], "commit-message", leak))

        # 2. Scan commit diff additions
        diff_res = subprocess.run(
            ["git", "show", "--format=", commit],
            cwd=root,
            capture_output=True,
            text=True,
            errors="ignore",
        )
        if diff_res.returncode == 0:
            for line in diff_res.stdout.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    for leak in find_cups_leaks(line):
                        findings.append((commit[:8], line[:80].strip(), leak))

    return findings


def scan_git_staged(repo_root: Path | str | None = None) -> dict[str, list[tuple[int, str, str]]]:
    """Scan git staged changes (index) for prohibited real CUPS identifiers before commit.

    Args:
        repo_root: Optional repository root path. Defaults to current working directory.

    Returns:
        Dictionary mapping staged file names to lists of findings (line_index, cups, preview).
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    findings: dict[str, list[tuple[int, str, str]]] = {}

    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "-U0"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return findings

    current_file = ""
    line_num = 0

    for line in res.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("@@ "):
            # Extract hunk header line number e.g. @@ -1,4 +10,4 @@
            match = re.search(r"\+(\d+)", line)
            line_num = int(match.group(1)) if match else 1
        elif line.startswith("+") and not line.startswith("+++"):
            leaks = find_cups_leaks(line[1:])
            for leak in leaks:
                findings.setdefault(current_file, []).append((line_num, leak, line[1:].strip()))
            line_num += 1

    return findings


def check_privacy(include_history: bool = True, staged_only: bool = False) -> int:
    """Pre-commit hook and CLI verification entry point for repository data privacy.

    Args:
        include_history: Whether to also scan all commits in Git history.
        staged_only: If True, only inspect staged changes in the git index.

    Returns:
        0 if 100% clean, 1 if any prohibited CUPS identifiers are detected.
    """
    repo_root = Path.cwd()
    has_violations = False

    # 1. Staged files check (if requested)
    if staged_only:
        staged_findings = scan_git_staged(repo_root)
        if staged_findings:
            print("\n❌ [SECURITY ERROR] Real CUPS detected in staged git changes:")
            for file_path, items in staged_findings.items():
                print(f"File: {file_path}")
                for line_num, cups, preview in items:
                    print(f"  Line ~{line_num}: Prohibited CUPS '{cups}' -> {preview[:80]}")
            return 1
        print("✅ Staged changes are 100% clean of prohibited CUPS.")
        return 0

    # 2. Workspace text files check
    file_findings = scan_directory(repo_root)
    if file_findings:
        has_violations = True
        print("\n❌ [SECURITY ERROR] Real / Non-synthetic CUPS detected in repository files:")
        print(
            "Under Real Decreto 244/2019 and GDPR, CUPS numbers are private residential identifiers."
        )
        print(
            "Only synthetic mock CUPS adhering to pattern 'ES00210000000000XXYY' are permitted.\n"
        )
        for file_path, items in file_findings.items():
            rel_path = file_path.relative_to(repo_root)
            print(f"File: {rel_path}")
            for line_num, cups, preview in items:
                print(f"  Line {line_num}: Prohibited CUPS '{cups}' -> {preview[:80]}")

    # 3. Git commit history check
    if include_history:
        history_findings = scan_git_history(repo_root)
        if history_findings:
            has_violations = True
            print("\n❌ [SECURITY ERROR] Real CUPS detected in git commit history:")
            print("No compromised commit may stay in git history under GDPR & LOPDGDD.")
            for commit_hash, loc, cups in history_findings:
                print(f"  Commit {commit_hash} ({loc}): Prohibited CUPS '{cups}'")

    if has_violations:
        print(
            "\nPlease replace these real identifiers with synthetic mock CUPS before committing.\n"
        )
        return 1

    print("✅ Privacy & Security Check passed: Workspace files and git history are 100% clean.")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    is_staged_only = "--staged" in args
    is_files_only = "--files-only" in args
    exit_code = check_privacy(
        include_history=not is_files_only and not is_staged_only,
        staged_only=is_staged_only,
    )
    sys.exit(exit_code)
