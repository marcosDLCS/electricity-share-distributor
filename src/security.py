"""Security and privacy validation harness for Electricity Share Distributor (esd).

Ensures that no real Spanish Universal Supply Point Codes (CUPS), private
geographic coordinates, local filesystem paths, or exposed secrets/credentials
are committed or included in tracked repository files.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

# Standard Spanish CUPS regex pattern: 'ES' followed by 16 digits and 2 control letters
# or up to 22 characters including measurement point suffix.
CUPS_PATTERN: re.Pattern[str] = re.compile(r"\bES[0-9]{16}[A-Za-z0-9]{2,4}\b", re.IGNORECASE)

# Permitted synthetic mock CUPS regex:
# Must follow ES00210000000000XXYY format (10 consecutive zeroes).
SYNTHETIC_CUPS_PATTERN: re.Pattern[str] = re.compile(
    r"^ES00210000000000\d{2}[A-Za-z0-9]{2,4}$", re.IGNORECASE
)

# Truncated CUPS pattern (e.g. ellipsis followed by 6-14 characters)
TRUNCATED_CUPS_PATTERN: re.Pattern[str] = re.compile(
    r"(?:…|\.\.\.)([0-9A-Za-z]{6,14})\b", re.IGNORECASE
)

# Permitted synthetic truncated CUPS: must be 0-padded (e.g. '…00000001AA', '00000001AA')
SYNTHETIC_TRUNCATED_PATTERN: re.Pattern[str] = re.compile(
    r"^0{2,}\d{1,4}[A-Za-z0-9]{2,4}$", re.IGNORECASE
)

# Prohibited absolute local filesystem paths (e.g. /Users/..., /home/..., file:///...)
LOCAL_PATH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:file:///|/(?:Users|home)/[a-zA-Z0-9._-]+/)\S*", re.IGNORECASE
)

# Secret and credential patterns checked across files, Excel workbooks, and git history
SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9_\-\.]{20,}\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?token|auth[_-]?token|access[_-]?token)"
        r"\s*[:=]\s*['\"][a-zA-Z0-9_\-/.+=]{8,}['\"]"
    ),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
    re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b"),
]

# Approved public Spanish city-center coordinates for documentation and unit tests
ALLOWED_SYNTHETIC_COORDINATE_PAIRS: frozenset[tuple[float, float]] = frozenset(
    {
        (40.4168, -3.7038),  # Madrid
        (41.3851, 2.1734),  # Barcelona
        (39.4699, -0.3763),  # Valencia
        (37.3891, -5.9845),  # Seville
        (43.2630, -2.9350),  # Bilbao
    }
)

ALLOWED_SYNTHETIC_CARDINALS: frozenset[tuple[float, str]] = frozenset(
    {
        (round(abs(lat), 4), "N" if lat >= 0 else "S")
        for lat, _ in ALLOWED_SYNTHETIC_COORDINATE_PAIRS
    }
    | {
        (round(abs(lon), 4), "E" if lon >= 0 else "W")
        for _, lon in ALLOWED_SYNTHETIC_COORDINATE_PAIRS
    }
)

# Potential generic geographic coordinate patterns (decimal degrees with cardinal suffix)
GENERIC_COORDINATE_REGEX: re.Pattern[str] = re.compile(
    r"\b(-?\d{1,2}\.\d{4,6})\s*°?\s*([NSnsOEWoew])\b"
)

# Coordinate pairs in decimal degrees (e.g., latitude, longitude values)
COORDINATE_PAIR_REGEX: re.Pattern[str] = re.compile(
    r"(?<![0-9.])([+-]?\d{1,2}\.\d{4,8})\s*,\s*([+-]?\d{1,3}\.\d{4,8})(?![0-9.])"
)

# Context guards to avoid false positives inside multi-element numeric arrays (e.g. [33.33333, 16.66666, 16.66666])
_PRECEDED_BY_HIGH_PREC_FLOAT: re.Pattern[str] = re.compile(r"\d+\.\d{4,}\s*,\s*$")
_FOLLOWED_BY_HIGH_PREC_FLOAT: re.Pattern[str] = re.compile(r"^\s*,\s*[+-]?\d+\.\d{4,}")

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
    ".curated",
    "build",
    "dist",
    "electricity_share_distributor.egg-info",
}

IGNORED_EXTENSIONS: set[str] = {
    ".dylib",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".pyd",
    ".pyo",
    ".so",
    ".svg",
    ".tar",
    ".webp",
    ".xls",
    ".zip",
}

_CACHED_PRIVATE_SIGNATURES: set[str] | None = None
_CACHED_PRIVATE_COORDINATES: set[str] | None = None


def clear_private_signatures_cache() -> None:
    """Clear cached private CUPS and coordinate signatures for testing or re-evaluation."""
    global _CACHED_PRIVATE_SIGNATURES, _CACHED_PRIVATE_COORDINATES
    _CACHED_PRIVATE_SIGNATURES = None
    _CACHED_PRIVATE_COORDINATES = None


def get_known_private_signatures(repo_root: Path | str | None = None) -> set[str]:
    """Discover real CUPS suffixes from local .input/consumption and .input/cups/cups.json if present."""
    global _CACHED_PRIVATE_SIGNATURES
    if repo_root is None and _CACHED_PRIVATE_SIGNATURES is not None:
        return _CACHED_PRIVATE_SIGNATURES

    base = Path(repo_root) if repo_root else Path.cwd()
    signatures: set[str] = set()

    # 1. Discover from .input/consumption/*.csv
    input_dir = base / ".input" / "consumption"
    if input_dir.exists():
        for f in input_dir.glob("*.csv"):
            cups_part = f.stem.split("_")[0].upper()
            if cups_part.startswith("ES") and len(cups_part) >= 20:
                if not is_synthetic_cups(cups_part):
                    signatures.add(cups_part)
                    suffix = cups_part[8:]
                    if len(suffix) >= 6:
                        signatures.add(suffix)

    # 2. Discover from .input/cups/cups.json (and .input/cups.json)
    cups_candidates = [
        base / ".input" / "cups" / "cups.json",
        base / ".input" / "cups.json",
    ]
    for cups_file in cups_candidates:
        if cups_file.exists():
            try:
                content = cups_file.read_text(encoding="utf-8", errors="ignore")
                # Parse JSON structure if valid
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "cups" in item:
                                c = str(item["cups"]).strip().upper()
                                if c.startswith("ES") and len(c) >= 20 and not is_synthetic_cups(c):
                                    signatures.add(c)
                                    suffix = c[8:]
                                    if len(suffix) >= 6:
                                        signatures.add(suffix)
                    elif isinstance(data, dict):
                        for k, v in data.items():
                            for val in (k, v if isinstance(v, str) else ""):
                                if isinstance(val, str):
                                    c = val.strip().upper()
                                    if (
                                        c.startswith("ES")
                                        and len(c) >= 20
                                        and not is_synthetic_cups(c)
                                    ):
                                        signatures.add(c)
                                        suffix = c[8:]
                                        if len(suffix) >= 6:
                                            signatures.add(suffix)
                except Exception:
                    pass

                # Also regex match any CUPS patterns in the file content
                for match in CUPS_PATTERN.findall(content):
                    c = match.strip().upper()
                    if not is_synthetic_cups(c):
                        signatures.add(c)
                        suffix = c[8:]
                        if len(suffix) >= 6:
                            signatures.add(suffix)
            except Exception:
                pass

    if repo_root is None:
        _CACHED_PRIVATE_SIGNATURES = signatures
    return signatures


def is_synthetic_cups(cups: str) -> bool:
    """Check whether a given CUPS string matches the authorized synthetic mock pattern.

    Args:
        cups: CUPS identifier string.

    Returns:
        True if the CUPS is synthetic and safe to commit, False otherwise.
    """
    clean = cups.strip().upper()
    return bool(SYNTHETIC_CUPS_PATTERN.match(clean))


def find_cups_leaks(text: str, private_signatures: set[str] | None = None) -> list[str]:
    """Scan text for any CUPS identifiers that are NOT synthetic mock CUPS.

    Args:
        text: Arbitrary text to scan.
        private_signatures: Optional set of known private CUPS signatures to detect.

    Returns:
        List of prohibited (real) CUPS identifiers detected.
    """
    leaks: list[str] = []

    # 1. Full standard CUPS matches
    for match in CUPS_PATTERN.findall(text):
        if not is_synthetic_cups(match):
            leaks.append(match)

    # 2. Truncated CUPS matches (e.g. …00000001AA)
    for match in TRUNCATED_CUPS_PATTERN.findall(text):
        if not SYNTHETIC_TRUNCATED_PATTERN.match(match):
            leaks.append(f"…{match}")

    # 3. Known private signatures from .input/
    sigs = private_signatures if private_signatures is not None else get_known_private_signatures()
    text_upper = text.upper()
    for sig in sigs:
        if sig in text_upper:
            leaks.append(sig)

    return list(dict.fromkeys(leaks))


def is_synthetic_coordinate_pair(latitude: float, longitude: float) -> bool:
    """Return True if (latitude, longitude) matches an approved synthetic city-center fixture."""
    return (round(latitude, 4), round(longitude, 4)) in ALLOWED_SYNTHETIC_COORDINATE_PAIRS


def _extract_coordinate_pair(item: object) -> tuple[float, float, object, object] | None:
    """Extract (lat_float, lon_float, raw_lat, raw_lon) from a dict if valid."""
    if not isinstance(item, dict):
        return None
    raw_lat = item.get("lat")
    if raw_lat is None:
        raw_lat = item.get("latitude")
    if raw_lat is None:
        raw_lat = item.get("latitud")
    raw_lon = item.get("long")
    if raw_lon is None:
        raw_lon = item.get("lon")
    if raw_lon is None:
        raw_lon = item.get("lng")
    if raw_lon is None:
        raw_lon = item.get("longitude")
    if raw_lon is None:
        raw_lon = item.get("longitud")
    if raw_lat is None or raw_lon is None:
        return None
    if not isinstance(raw_lat, (int, float, str)) or not isinstance(raw_lon, (int, float, str)):
        return None
    if isinstance(raw_lat, bool) or isinstance(raw_lon, bool):
        return None
    try:
        lat_val = float(raw_lat)
        lon_val = float(raw_lon)
    except ValueError:
        return None
    if not (-90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0):
        return None
    return lat_val, lon_val, raw_lat, raw_lon


def _add_coordinate_signatures(
    signatures: set[str],
    lat_val: float,
    lon_val: float,
    raw_lat: object,
    raw_lon: object,
) -> None:
    """Register formatted private coordinate strings unless matching synthetic city centers."""
    if is_synthetic_coordinate_pair(lat_val, lon_val):
        return
    for num_val, raw_val in ((lat_val, raw_lat), (lon_val, raw_lon)):
        if abs(num_val) < 0.0001:
            continue
        rounded = f"{num_val:.4f}"
        signatures.add(rounded)
        stripped = rounded.rstrip("0").rstrip(".")
        if "." in stripped and len(stripped.split(".")[1]) >= 3:
            signatures.add(stripped)
        s_raw = str(raw_val).strip()
        if "." in s_raw:
            int_part, frac_part = s_raw.split(".", 1)
            if len(frac_part) >= 4:
                signatures.add(f"{int_part}.{frac_part[:4]}")


def get_known_private_coordinates(repo_root: Path | str | None = None) -> set[str]:
    """Discover private community coordinates from .input/cups/cups.json and .esd_config.json."""
    global _CACHED_PRIVATE_COORDINATES
    if repo_root is None and _CACHED_PRIVATE_COORDINATES is not None:
        return _CACHED_PRIVATE_COORDINATES

    base = Path(repo_root) if repo_root else Path.cwd()
    signatures: set[str] = set()

    candidates = [
        base / ".input" / "cups" / "cups.json",
        base / ".input" / "cups.json",
        base / ".esd_config.json",
    ]
    for cfg_file in candidates:
        if not cfg_file.is_file():
            continue
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        items: list[object] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
            items.extend(val for val in data.values() if isinstance(val, dict))

        for item in items:
            parsed = _extract_coordinate_pair(item)
            if parsed is not None:
                _add_coordinate_signatures(signatures, *parsed)

    if repo_root is None:
        _CACHED_PRIVATE_COORDINATES = signatures
    return signatures


def find_path_leaks(text: str) -> list[str]:
    """Scan text for prohibited local filesystem paths or file:/// links.

    Args:
        text: Arbitrary text to scan.

    Returns:
        List of prohibited local paths detected.
    """
    return list(dict.fromkeys(LOCAL_PATH_PATTERN.findall(text)))


def find_secret_leaks(text: str) -> list[str]:
    """Scan text for exposed private keys, bearer tokens, API secrets, or cloud tokens.

    Args:
        text: Arbitrary text to scan.

    Returns:
        List of sanitized secret violation labels detected.
    """
    leaks: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            val = match.group(0).strip()
            snippet = val[:24] + ("..." if len(val) > 24 else "")
            leaks.append(f"Secret pattern: {snippet}")
    return list(dict.fromkeys(leaks))


def find_coordinate_leaks(
    text: str,
    private_coordinates: set[str] | None = None,
) -> list[str]:
    """Scan text for private or non-synthetic geographic coordinates.

    Args:
        text: Arbitrary text to scan.
        private_coordinates: Optional set of known private coordinate signatures.

    Returns:
        List of prohibited coordinate violation descriptions.
    """
    leaks: list[str] = []

    known = (
        private_coordinates if private_coordinates is not None else get_known_private_coordinates()
    )
    for sig in known:
        if re.search(rf"(?<![0-9.]){re.escape(sig)}", text):
            leaks.append(f"Private coordinate: {sig}")

    for match in GENERIC_COORDINATE_REGEX.finditer(text):
        raw_val, cardinal = match.group(1), match.group(2).upper()
        norm_cardinal = "W" if cardinal == "O" else cardinal
        try:
            val_num = round(abs(float(raw_val)), 4)
        except ValueError:
            continue
        if (val_num, norm_cardinal) not in ALLOWED_SYNTHETIC_CARDINALS:
            leaks.append(f"Geographic coordinate: {match.group(0)}")

    for match in COORDINATE_PAIR_REGEX.finditer(text):
        if _PRECEDED_BY_HIGH_PREC_FLOAT.search(text[: match.start()]):
            continue
        if _FOLLOWED_BY_HIGH_PREC_FLOAT.match(text[match.end() :]):
            continue
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
        except ValueError:
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            continue
        if abs(lat) < 1.0 and abs(lon) < 1.0:
            continue
        if not is_synthetic_coordinate_pair(lat, lon):
            leaks.append(f"Coordinate pair: {match.group(0)}")

    return list(dict.fromkeys(leaks))


def scan_xlsx_file(
    file_source: Path | str | io.BytesIO,
    private_signatures: set[str] | None = None,
    private_coordinates: set[str] | None = None,
) -> list[tuple[int, str, str]]:
    """Scan an Excel (.xlsx) file for prohibited CUPS, paths, secrets, or coordinates.

    Args:
        file_source: File path or BytesIO buffer of an Excel workbook.
        private_signatures: Optional set of known private CUPS signatures to detect.
        private_coordinates: Optional set of known private coordinate signatures to detect.

    Returns:
        List of tuples: (row_number, leak, preview_text).
    """
    if openpyxl is None:
        return []

    if isinstance(file_source, (str, Path)):
        path = Path(file_source)
        if not path.is_file():
            return []

    findings: list[tuple[int, str, str]] = []
    wb = None
    try:
        wb = openpyxl.load_workbook(file_source, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                for cell_val in row:
                    if cell_val is None:
                        continue
                    val_str = str(cell_val)
                    leaks = (
                        find_cups_leaks(val_str, private_signatures=private_signatures)
                        + find_path_leaks(val_str)
                        + find_secret_leaks(val_str)
                        + find_coordinate_leaks(val_str, private_coordinates=private_coordinates)
                    )
                    for leak in leaks:
                        preview = f"[{sheet_name}] Row {row_idx}: {val_str.strip()}"
                        findings.append((row_idx, leak, preview))
    except Exception:
        return findings
    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception:
                pass

    return list(dict.fromkeys(findings))


def scan_file(
    file_path: Path,
    private_signatures: set[str] | None = None,
    private_coordinates: set[str] | None = None,
) -> list[tuple[int, str, str]]:
    """Scan a single file (text or .xlsx) for prohibited CUPS, paths, secrets, or coordinates.

    Args:
        file_path: Path to the file.
        private_signatures: Optional set of known private CUPS signatures to detect.
        private_coordinates: Optional set of known private coordinate signatures to detect.

    Returns:
        List of tuples (line_number, leak, line_preview).
    """
    if file_path.suffix.lower() == ".xlsx":
        return scan_xlsx_file(
            file_path,
            private_signatures=private_signatures,
            private_coordinates=private_coordinates,
        )

    findings: list[tuple[int, str, str]] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    is_sec = file_path.name in ("security.py", "test_security.py")
    for line_num, line in enumerate(content.splitlines(), start=1):
        leaks = find_cups_leaks(line, private_signatures=private_signatures)
        if not is_sec:
            leaks += find_path_leaks(line)
        leaks += find_secret_leaks(line)
        leaks += find_coordinate_leaks(line, private_coordinates=private_coordinates)
        for leak in leaks:
            findings.append((line_num, leak, line.strip()))
    return findings


def scan_directory(
    root_dir: Path | str,
    private_signatures: set[str] | None = None,
    private_coordinates: set[str] | None = None,
) -> dict[Path, list[tuple[int, str, str]]]:
    """Recursively scan a directory for prohibited CUPS, paths, secrets, and coordinates.

    Args:
        root_dir: Root directory path.
        private_signatures: Optional set of known private CUPS signatures to detect.
        private_coordinates: Optional set of known private coordinate signatures to detect.

    Returns:
        Dictionary mapping file paths to lists of findings.
    """
    root = Path(root_dir)
    sigs = (
        private_signatures if private_signatures is not None else get_known_private_signatures(root)
    )
    coords = (
        private_coordinates
        if private_coordinates is not None
        else get_known_private_coordinates(root)
    )
    results: dict[Path, list[tuple[int, str, str]]] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        # Check ignored directories
        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        if path.suffix.lower() in IGNORED_EXTENSIONS:
            continue

        findings = scan_file(
            path,
            private_signatures=sigs,
            private_coordinates=coords,
        )
        if findings:
            results[path] = findings

    return results


def scan_git_history(repo_root: Path | str | None = None) -> list[tuple[str, str, str]]:
    """Scan all git commits in repository history for prohibited real CUPS identifiers or local paths.

    Uses a single streamed ``git log --all --format=... -p`` invocation across all
    branches and commits rather than spawning per-commit subprocesses.

    Args:
        repo_root: Optional repository root path. Defaults to current working directory.

    Returns:
        List of tuples: (commit_hash, location_preview, prohibited_leak).
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    findings: list[tuple[str, str, str]] = []
    if not root.exists():
        return findings

    commit_marker = "\x1eCOMMIT:"
    end_msg_marker = "\x1eEND_MSG"
    cmd = [
        "git",
        "log",
        "--all",
        "--no-color",
        "--no-ext-diff",
        "--cc",
        "-p",
        "--format=%x1eCOMMIT:%H%n%B%n%x1eEND_MSG",
    ]

    try:
        with subprocess.Popen(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
        ) as proc:
            if proc.stdout is None:  # pragma: no cover
                return findings

            current_commit = ""
            current_diff_file = ""
            in_message = False
            message_lines: list[str] = []

            def _flush_message() -> None:
                if not current_commit or not message_lines:
                    message_lines.clear()
                    return
                msg_text = "\n".join(message_lines)
                for leak in (
                    find_cups_leaks(msg_text)
                    + find_path_leaks(msg_text)
                    + find_secret_leaks(msg_text)
                ):
                    findings.append((current_commit, "commit-message", leak))
                message_lines.clear()

            for raw_line in proc.stdout:
                line = raw_line.rstrip("\r\n")

                if line.startswith(commit_marker):
                    _flush_message()
                    current_commit = line[len(commit_marker) : len(commit_marker) + 8]
                    current_diff_file = ""
                    in_message = True
                    continue

                if in_message:
                    if line == end_msg_marker:
                        in_message = False
                        _flush_message()
                    else:
                        message_lines.append(line)
                    continue

                if line.startswith("diff --git "):
                    current_diff_file = ""
                elif line.startswith("+++ b/"):
                    current_diff_file = line[6:]
                elif line.startswith("+") and not line.startswith("+++") and current_commit:
                    is_sec = current_diff_file.endswith(
                        "security.py"
                    ) or current_diff_file.endswith("test_security.py")
                    leaks = find_cups_leaks(line) + find_secret_leaks(line)
                    if not is_sec:
                        leaks += find_path_leaks(line)
                    for leak in leaks:
                        findings.append((current_commit, line[:80].strip(), leak))

            _flush_message()
    except Exception:
        # Not a git repository or git command unavailable
        return findings

    return findings


def scan_git_staged(
    repo_root: Path | str | None = None,
    private_signatures: set[str] | None = None,
    private_coordinates: set[str] | None = None,
) -> dict[str, list[tuple[int, str, str]]]:
    """Scan git staged changes (index) for prohibited CUPS, paths, secrets, or coordinates.

    Args:
        repo_root: Optional repository root path. Defaults to current working directory.
        private_signatures: Optional set of known private CUPS signatures to detect.
        private_coordinates: Optional set of known private coordinate signatures to detect.

    Returns:
        Dictionary mapping staged file names to lists of findings (line_index, leak, preview).
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    findings: dict[str, list[tuple[int, str, str]]] = {}
    sigs = (
        private_signatures if private_signatures is not None else get_known_private_signatures(root)
    )
    coords = (
        private_coordinates
        if private_coordinates is not None
        else get_known_private_coordinates(root)
    )

    # 1. Discover all staged files (excluding deleted files)
    try:
        staged_files_res = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=d"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        staged_files = staged_files_res.stdout.splitlines()
    except Exception:
        staged_files = []

    # 2. Inspect staged .xlsx workbooks using openpyxl
    for staged_file in staged_files:
        staged_path = Path(staged_file)
        if any(part in IGNORED_DIRS for part in staged_path.parts):
            continue
        if staged_path.suffix.lower() == ".xlsx":
            show_res = subprocess.run(
                ["git", "show", f":{staged_file}"],
                cwd=root,
                capture_output=True,
                check=False,
            )
            xlsx_findings: list[tuple[int, str, str]] = []
            if show_res.returncode == 0 and show_res.stdout:
                xlsx_findings = scan_xlsx_file(
                    io.BytesIO(show_res.stdout),
                    private_signatures=sigs,
                    private_coordinates=coords,
                )
            elif (root / staged_path).is_file():
                xlsx_findings = scan_xlsx_file(
                    root / staged_path,
                    private_signatures=sigs,
                    private_coordinates=coords,
                )
            if xlsx_findings:
                findings[staged_file] = xlsx_findings

    # 3. Inspect staged text diff hunks
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
            if any(part in IGNORED_DIRS for part in Path(current_file).parts):
                current_file = ""
        elif not current_file:
            continue
        elif line.startswith("@@ "):
            # Extract hunk header line number e.g. @@ -1,4 +10,4 @@
            match = re.search(r"\+(\d+)", line)
            line_num = int(match.group(1)) if match else 1
        elif line.startswith("+") and not line.startswith("+++"):
            is_sec = current_file.endswith("security.py") or current_file.endswith(
                "test_security.py"
            )
            added = line[1:]
            leaks = find_cups_leaks(added, private_signatures=sigs)
            if not is_sec:
                leaks += find_path_leaks(added)
            leaks += find_secret_leaks(added)
            leaks += find_coordinate_leaks(added, private_coordinates=coords)
            for leak in leaks:
                findings.setdefault(current_file, []).append((line_num, leak, added.strip()))
            line_num += 1

    return findings


def check_privacy(
    include_history: bool = True,
    staged_only: bool = False,
    scan_path: Path | str | None = None,
) -> int:
    """Pre-commit hook and CLI verification entry point for repository data privacy.

    Args:
        include_history: Whether to also scan all commits in Git history.
        staged_only: If True, only inspect staged changes in the git index.
        scan_path: Optional specific file or directory path to audit directly.

    Returns:
        0 if 100% clean, 1 if any privacy/security violation is detected or path is invalid.
    """
    repo_root = Path.cwd()

    # 0. Single-path targeted scan
    if scan_path is not None:
        target = Path(scan_path)
        if not target.exists():
            print(f"Error: scan path does not exist: {scan_path}", file=sys.stderr)
            return 1

        if target.is_file():
            items = scan_file(target)
            if items:
                print(f"\n❌ [SECURITY ERROR] Privacy or secret violation detected in {target}:")
                for line_num, leak, preview in items:
                    print(f"  Line {line_num}: Prohibited '{leak}' -> {preview[:80]}")
                return 1
            print(f"✅ File '{target}' passed security & privacy audit.")
            return 0

        dir_findings = scan_directory(target)
        if dir_findings:
            print(f"\n❌ [SECURITY ERROR] Privacy or secret violations detected in {target}:")
            for file_path, items in dir_findings.items():
                try:
                    rel = file_path.relative_to(target)
                except ValueError:
                    rel = file_path
                print(f"File: {rel}")
                for line_num, leak, preview in items:
                    print(f"  Line {line_num}: Prohibited '{leak}' -> {preview[:80]}")
            return 1
        print(f"✅ Directory '{target}' passed security & privacy audit.")
        return 0

    has_violations = False

    # 1. Staged files check (if requested)
    if staged_only:
        staged_findings = scan_git_staged(repo_root)
        if staged_findings:
            print("\n❌ [SECURITY ERROR] Privacy or secret violation detected in staged changes:")
            for file_path, items in staged_findings.items():
                print(f"File: {file_path}")
                for line_num, leak, preview in items:
                    print(f"  Line ~{line_num}: Prohibited '{leak}' -> {preview[:80]}")
            return 1
        print("✅ Staged changes are 100% clean of prohibited data or secrets.")
        return 0

    # 2. Workspace files check
    file_findings = scan_directory(repo_root)
    if file_findings:
        has_violations = True
        print("\n❌ [SECURITY ERROR] Privacy or secret violations detected in repository files:")
        print(
            "Under Real Decreto 244/2019 and GDPR, real CUPS, private coordinates, local paths, "
            "and secrets must never be committed."
        )
        print(
            "Only synthetic mock CUPS ('ES00210000000000XXYY') and city-center demo coordinates "
            "are permitted.\n"
        )
        for file_path, items in file_findings.items():
            rel_path = file_path.relative_to(repo_root)
            print(f"File: {rel_path}")
            for line_num, leak, preview in items:
                print(f"  Line {line_num}: Prohibited '{leak}' -> {preview[:80]}")

    # 3. Git commit history check
    if include_history:
        history_findings = scan_git_history(repo_root)
        if history_findings:
            has_violations = True
            print("\n❌ [SECURITY ERROR] Prohibited data or secrets detected in git history:")
            print("No compromised commit may stay in git history under GDPR & LOPDGDD.")
            for commit_hash, loc, leak in history_findings:
                print(f"  Commit {commit_hash} ({loc}): Prohibited '{leak}'")

    if has_violations:
        print("\nPlease remove or anonymize all detected violations before committing.\n")
        return 1

    print("✅ Privacy & Security Check passed: Workspace files and git history are 100% clean.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for repository security audits, staged hooks, and targeted scans."""
    args = list(sys.argv[1:] if argv is None else argv)

    if any(arg in ("-h", "--help") for arg in args):
        print(
            "Electricity Share Distributor (esd) — Security & Privacy Harness\n\n"
            "Usage:\n"
            "  python -m src.security                 Audit workspace files and git history\n"
            "  python -m src.security --files-only    Audit workspace files only\n"
            "  python -m src.security --staged        Audit git staged changes (pre-commit)\n"
            "  python -m src.security --history       Audit workspace files and git history\n"
            "  python -m src.security --scan <path>   Audit a specific file or directory\n"
        )
        return 0

    scan_path: str | None = None
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg == "--scan":
            if idx + 1 >= len(args) or args[idx + 1].startswith("-"):
                print("Error: '--scan' requires a file or directory path.", file=sys.stderr)
                return 1
            scan_path = args[idx + 1]
            idx += 2
            continue
        if arg.startswith("--scan="):
            scan_path = arg.split("=", 1)[1]
            if not scan_path:
                print("Error: '--scan' requires a non-empty path.", file=sys.stderr)
                return 1
        idx += 1

    if scan_path is not None:
        return check_privacy(scan_path=scan_path)

    is_staged_only = "--staged" in args
    is_files_only = "--files-only" in args
    return check_privacy(
        include_history=not is_files_only and not is_staged_only,
        staged_only=is_staged_only,
    )


if __name__ == "__main__":
    sys.exit(main())
