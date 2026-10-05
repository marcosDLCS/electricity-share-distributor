"""Global configuration, schema constants, and persistent settings for Electricity Share Distributor."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

# Default paths
DEFAULT_INPUT_DIR: Final[Path] = Path(".input")
DEFAULT_CONSUMPTION_DIR: Final[Path] = Path(".input/consumption")
DEFAULT_GENERATION_DIR: Final[Path] = Path(".input/generation")
DEFAULT_OUTPUT_DIR: Final[Path] = Path(".output")
CONFIG_FILE_PATH: Final[Path] = Path(".esd_config.json")

# Required DATADIS CSV columns (case-insensitive)
REQUIRED_CONSUMPTION_COLUMNS: Final[list[str]] = [
    "cups",
    "fecha",
    "hora",
    "consumo_kWh",
]

# Standard normalized column names used internally
COL_CUPS: Final[str] = "cups"
COL_TIMESTAMP: Final[str] = "timestamp"
COL_DATE: Final[str] = "date"
COL_TIME: Final[str] = "time"
COL_YEAR: Final[str] = "year"
COL_MONTH: Final[str] = "month"
COL_CONSUMPTION_KWH: Final[str] = "consumption_kwh"
COL_GENERATION_KWH: Final[str] = "generation_kwh"

# Delimiters and encodings commonly encountered in DATADIS exports
SUPPORTED_DELIMITERS: Final[list[str]] = [";", ",", "\t"]
SUPPORTED_ENCODINGS: Final[list[str]] = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

# Supported date string patterns
DATE_FORMATS: Final[list[str]] = [
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
]

# Supported application languages
SUPPORTED_LANGUAGES: Final[dict[str, str]] = {
    "en": "English",
    "english": "English",
    "es": "Español",
    "spanish": "Español",
    "español": "Español",
    "espanol": "Español",
}


@dataclass
class AppConfig:
    """Persistent user and application settings.

    Attributes:
        language: Active output language ('en' for English, 'es' for Spanish).
        input_dir: Base input folder path.
        consumption_dir: Folder containing DATADIS hourly consumption CSVs.
        generation_dir: Folder containing Huawei/FusionSolar generation Excel reports.
        output_dir: Folder for output reports, exports, and visualizations.
        initialized_at: ISO timestamp recording when 'esd init' was successfully run.
        version: Application version recorded at initialization time (CalVer YYYY.MM.NNN).
    """

    language: str = "en"
    input_dir: str = ".input"
    consumption_dir: str = ".input/consumption"
    generation_dir: str = ".input/generation"
    output_dir: str = ".output"
    initialized_at: str | None = None
    version: str | None = None


def normalize_language_code(lang_raw: str) -> str:
    """Normalize input language string to standard two-letter ISO code ('en' or 'es').

    Raises:
        ValueError: If the language is not supported.
    """
    clean = lang_raw.strip().lower()
    if clean in ("en", "english"):
        return "en"
    if clean in ("es", "spanish", "español", "espanol"):
        return "es"
    raise ValueError(
        f"Unsupported language '{lang_raw}'. Supported options: 'en' (English), 'es' (Spanish)."
    )


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from disk, returning default settings if the file does not exist."""
    target_path = path or CONFIG_FILE_PATH
    if not target_path.exists():
        return AppConfig()

    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
        lang = data.get("language", "en")
        try:
            normalized_lang = normalize_language_code(lang)
        except ValueError:
            normalized_lang = "en"

        return AppConfig(
            language=normalized_lang,
            input_dir=data.get("input_dir", ".input"),
            consumption_dir=data.get("consumption_dir", ".input/consumption"),
            generation_dir=data.get("generation_dir", ".input/generation"),
            output_dir=data.get("output_dir", ".output"),
            initialized_at=data.get("initialized_at"),
            version=data.get("version"),
        )
    except Exception:
        return AppConfig()


def is_initialized(path: Path | None = None) -> bool:
    """Check whether the workspace configuration has been initialized via 'esd init'."""
    target_path = path or CONFIG_FILE_PATH
    if not target_path.exists():
        return False
    cfg = load_config(target_path)
    return bool(cfg.initialized_at)


def mark_initialized(
    path: Path | None = None,
    timestamp: str | None = None,
    version: str | None = None,
) -> str:
    """Record and persist an initialization timestamp and version in settings.

    Returns:
        The persisted ISO datetime string.
    """
    from datetime import datetime

    from src.version import get_version

    target_path = path or CONFIG_FILE_PATH
    cfg = load_config(target_path)
    ts = timestamp or datetime.now().isoformat()
    cfg.initialized_at = ts
    cfg.version = version or cfg.version or get_version()
    save_config(cfg, target_path)
    return ts


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Persist application configuration to disk as JSON."""
    target_path = path or CONFIG_FILE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")


def set_language(language: str, path: Path | None = None) -> str:
    """Update and persist the active language setting.

    Returns:
        The normalized two-letter language code ('en' or 'es').
    """
    code = normalize_language_code(language)
    cfg = load_config(path)
    cfg.language = code
    save_config(cfg, path)
    return code


def get_language(path: Path | None = None) -> str:
    """Retrieve the currently configured language code ('en' or 'es')."""
    return load_config(path).language


def ensure_directories(
    config: AppConfig | None = None,
    config_path: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Ensure that the input, consumption, generation, and output directories exist on disk.

    Returns:
        Tuple of (input_dir, consumption_dir, generation_dir, output_dir).
    """
    cfg = config or load_config(config_path)
    input_path = Path(cfg.input_dir)
    consumption_path = Path(cfg.consumption_dir)
    generation_path = Path(cfg.generation_dir)
    output_path = Path(cfg.output_dir)

    input_path.mkdir(parents=True, exist_ok=True)
    consumption_path.mkdir(parents=True, exist_ok=True)
    generation_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)

    return input_path, consumption_path, generation_path, output_path
