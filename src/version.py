"""Application version management and CalVer enforcement for Electricity Share Distributor."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

__version__ = "2026.10.004"

VERSION_PATTERN = re.compile(r"^(\d{4})\.(\d{2})\.(\d{3})$")


def get_version() -> str:
    """Return the active Electricity Share Distributor version string."""
    return __version__


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a CalVer version string formatted as YYYY.MM.NNN into (year, month, sequence).

    Raises:
        ValueError: If version_str does not match YYYY.MM.NNN format.
    """
    clean = version_str.strip()
    match = VERSION_PATTERN.match(clean)
    if not match:
        raise ValueError(
            f"Invalid version format '{version_str}'. Expected format: YYYY.MM.NNN (e.g. 2026.10.001)"
        )
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_version(year: int, month: int, sequence: int) -> str:
    """Format year, month, and sequence into a standard CalVer string."""
    return f"{year:04d}.{month:02d}.{sequence:03d}"


def generate_next_version(
    current_version: str | None = None,
    target_date: datetime | None = None,
) -> str:
    """Calculate the next CalVer version string based on date and previous version.

    Pattern: <year>.<month>.<sequence:03d>
    If target_date falls within the same year and month as current_version:
        increments the sequence by 1 (e.g. 2026.10.001 -> 2026.10.002).
    If target_date represents a new year or month:
        resets sequence to 001 (e.g. 2026.11.001).
    """
    now = target_date or datetime.now()
    curr_year = now.year
    curr_month = now.month

    if current_version:
        try:
            v_year, v_month, v_seq = parse_version(current_version)
            if v_year == curr_year and v_month == curr_month:
                return format_version(curr_year, curr_month, v_seq + 1)
        except ValueError:
            pass

    return format_version(curr_year, curr_month, 1)


def find_repo_root(start_path: Path | None = None) -> Path:
    """Locate the repository root containing pyproject.toml."""
    current = (start_path or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / "pyproject.toml").is_file():
            return directory
    return current


def update_pyproject_version(pyproject_path: Path, new_version: str) -> None:
    """Update version field in pyproject.toml."""
    content = pyproject_path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(version\s*=\s*")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
        content,
        count=1,
    )
    if count == 0:
        raise ValueError(f"Could not find 'version = ...' line in {pyproject_path}")
    pyproject_path.write_text(updated, encoding="utf-8")


def update_version_py(version_file_path: Path, new_version: str) -> None:
    """Update __version__ field in src/version.py."""
    content = version_file_path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(__version__\s*=\s*")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
        content,
        count=1,
    )
    if count == 0:
        raise ValueError(f"Could not find '__version__ = ...' line in {version_file_path}")
    version_file_path.write_text(updated, encoding="utf-8")


def bump_version_files(
    repo_root: Path | None = None,
    target_date: datetime | None = None,
) -> str:
    """Calculate and write the next CalVer version across repository files.

    Returns:
        The newly generated version string.
    """
    root = find_repo_root(repo_root)
    pyproject = root / "pyproject.toml"
    version_file = root / "src" / "version.py"

    current: str | None = None
    if version_file.is_file():
        ver_content = version_file.read_text(encoding="utf-8")
        ver_match = re.search(r'__version__\s*=\s*"([^"]+)"', ver_content)
        if ver_match:
            current = ver_match.group(1)
    if current is None:
        current = get_version()

    new_version = generate_next_version(current, target_date=target_date)

    if version_file.is_file():
        update_version_py(version_file, new_version)
    if pyproject.is_file():
        update_pyproject_version(pyproject, new_version)

    return new_version


def check_version_consistency(repo_root: Path | None = None) -> tuple[bool, str]:
    """Verify that src/version.py and pyproject.toml have matching, valid CalVer versions."""
    root = find_repo_root(repo_root)
    pyproject = root / "pyproject.toml"
    version_file = root / "src" / "version.py"

    if not version_file.is_file():
        return False, f"Missing version file at {version_file}"
    if not pyproject.is_file():
        return False, f"Missing pyproject.toml at {pyproject}"

    ver_content = version_file.read_text(encoding="utf-8")
    ver_match = re.search(r'__version__\s*=\s*"([^"]+)"', ver_content)
    if not ver_match:
        return False, f"Cannot parse __version__ in {version_file}"
    src_ver = ver_match.group(1)

    try:
        parse_version(src_ver)
    except ValueError as exc:
        return False, f"Invalid format in {version_file}: {exc}"

    pyproj_content = pyproject.read_text(encoding="utf-8")
    proj_match = re.search(r'version\s*=\s*"([^"]+)"', pyproj_content)
    if not proj_match:
        return False, f"Cannot parse version in {pyproject}"
    proj_ver = proj_match.group(1)

    if src_ver != proj_ver:
        return (
            False,
            f"Version mismatch between src/version.py ({src_ver}) and pyproject.toml ({proj_ver})",
        )

    return True, f"Version {src_ver} is valid and consistent."


def check_commit_version_bump(repo_root: Path | None = None) -> int:
    """Pre-commit check: ensure that staged commits either bumped version or auto-bump if needed."""
    root = find_repo_root(repo_root)
    valid, msg = check_version_consistency(root)
    if not valid:
        print(f"[ERROR] Version consistency check failed: {msg}", file=sys.stderr)
        return 1

    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        staged_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        return 0

    if not staged_files:
        return 0

    version_changed = any(f in staged_files for f in ("src/version.py", "pyproject.toml"))

    if not version_changed:
        new_version = bump_version_files(repo_root=root)
        try:
            subprocess.run(
                ["git", "add", "src/version.py", "pyproject.toml"],
                cwd=str(root),
                check=True,
            )
            print(
                f"[CalVer] Auto-bumped version to {new_version} and staged version files. Please re-run git commit.",
                file=sys.stderr,
            )
            return 1
        except Exception as exc:
            print(f"[CalVer] Failed to auto-stage bumped version: {exc}", file=sys.stderr)
            return 1

    return 0


def main() -> None:
    """Command-line utility interface for version management."""
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "get"

    if action == "get":
        print(get_version())
    elif action == "bump":
        new_v = bump_version_files()
        print(f"Bumped version to {new_v}")
    elif action == "check":
        valid, msg = check_version_consistency()
        print(msg)
        sys.exit(0 if valid else 1)
    elif action == "hook":
        code = check_commit_version_bump()
        sys.exit(code)
    else:
        print(f"Unknown action '{action}'. Valid options: get, bump, check, hook", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
