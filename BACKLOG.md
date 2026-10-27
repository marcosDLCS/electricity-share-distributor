# 📋 Project Improvement Backlog

This document tracks prioritized, actionable improvement tasks for **Electricity Share Distributor (`esd`)**, formatted for autonomous AI agents to execute cleanly.

## 📐 Backlog Rules & Conventions

1. **Agent-Ready Descriptions:** Every task must have a brief, concise, and self-contained specification detailing the goal, target components, and acceptance criteria so an independent agent can pick it up immediately.
2. **Categories:** Tasks are organized into six single-word categories:
   - **`Features`** — Functional capabilities and user-facing enhancements.
   - **`Architecture`** — Structural improvements, engineering standards, and test coverage.
   - **`Cohesion`** — Codebase unification, pattern alignment, and shared abstractions.
   - **`Security`** — Privacy enforcement, vulnerability hardening, and keeping dependencies fully updated.
   - **`Documentation`** — Guides (`docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`), CLI help strings, and developer docs.
   - **`Simplicity`** — Dead code removal, complexity reduction, and waste elimination.
3. **Capacity Limit:** Maximum **2 tasks per category** at any time (fewer or zero is acceptable; never exceed 2).
4. **Prioritization:** Tasks are explicitly prioritized (e.g., `P1` High, `P2` Medium, `P3` Low) both in the summary table and within their category.
5. **Zero Completed History:** When a task is completed, it must be **removed** from both the summary table and its category section in `BACKLOG.md`.

---

## 📊 Prioritized Task Overview

| Task | Category | Priority |
| :--- | :--- | :--- |
| Extend Privacy Scanner to Inspect `.xlsx` Workbooks & `cups.json` | `Security` | `P1` |
| Extract `WeatherService` to Decouple CLI from Ingestion Layer | `Architecture` | `P2` |
| Vectorize `DatadisConsumptionLoader` Timestamp Normalization | `Architecture` | `P2` |
| Unify `SupplyPoint` and `CupsConfig` Domain Models | `Cohesion` | `P2` |
| Synchronize `README.md` and `i18n` Help with All CLI Commands & Flags | `Documentation` | `P2` |
| Centralize `cups.json` Path Discovery and Coordinate Extraction | `Cohesion` | `P3` |
| Harden `OpenMeteoWeatherDownloader` URL Scheme & Query Encoding | `Security` | `P3` |
| Localize Hardcoded CLI Prompts and Validation Errors | `Documentation` | `P3` |
| Remove Legacy `.xslx` Typo Symlink from Curated Excel Export | `Simplicity` | `P3` |
| Consolidate Month Abbreviations and Remove Redundant Export Wrappers | `Simplicity` | `P3` |

---

## 🚀 Features

*No pending tasks.*

## 🏗️ Architecture

### 1. [P2] Extract `WeatherService` to Decouple CLI from Ingestion Layer
- **Goal:** Align `esd weather` with the application service architecture used by `calculate`, `curate`, and `doctor` by moving coordinate fallback resolution (`CLI -> cups.json -> AppConfig`) and download orchestration out of `src/cli.py` into a dedicated `WeatherService`.
- **Target Files:** `src/services/weather_service.py`, `src/services/__init__.py`, `src/cli.py`, `tests/test_services.py`.
- **Acceptance Criteria:**
  - Create `WeatherRequest`, `WeatherServiceResult`, and `WeatherService.execute()` in `src/services/weather_service.py`.
  - Refactor `weather_command` in `src/cli.py` to delegate business logic to `WeatherService.execute()`.
  - Add unit tests in `tests/test_services.py` covering coordinate resolution priority and multi-location downloads.

### 2. [P2] Vectorize `DatadisConsumptionLoader` Timestamp Normalization
- **Goal:** Replace the Python `groupby("fecha")` + `iterrows()` loop in `DatadisConsumptionLoader.parse_file()` with vectorized Pandas string/integer operations to speed up ingestion of multi-CUPS annual datasets while preserving Spanish 01:00–24:00 billing hour and 23h/25h DST conventions.
- **Target Files:** `src/ingestion/consumption.py`, `tests/test_ingestion.py`.
- **Acceptance Criteria:**
  - Eliminate `.iterrows()` in `DatadisConsumptionLoader.parse_file()`.
  - Preserve identical timestamp output for standard 24-hour days, 23-hour spring DST transitions, and 25-hour autumn DST transitions.
  - All existing ingestion and alignment tests pass without regressions.

## 🔗 Cohesion

### 1. [P2] Unify `SupplyPoint` and `CupsConfig` Domain Models
- **Goal:** Eliminate duplication between `SupplyPoint` (`src/domain/models.py`) and `CupsConfig` (`src/curation/models.py`), which define the exact same 7 attributes (`cups`, `use`, `primary`, `latitude`, `longitude`, `min_share`, `max_share`).
- **Target Files:** `src/domain/models.py`, `src/curation/models.py`, `src/curation/curator.py`, `tests/test_domain.py`, `tests/test_curation.py`.
- **Acceptance Criteria:**
  - Use `SupplyPoint` as the single canonical model for CUPS configuration and metadata across `domain`, `curation`, and `services` (aliasing `CupsConfig = SupplyPoint` in `src/curation/models.py` if needed for compatibility).
  - Ensure CUPS format validation and share bound validation are consistently applied when loading `cups.json`.

### 2. [P3] Centralize `cups.json` Path Discovery and Coordinate Extraction
- **Goal:** Remove duplicated candidate path lists (`[.input/cups/cups.json, .input/cups.json, cups.json]`) and coordinate key parsing between `src/config.py`, `src/curation/curator.py`, and `src/ingestion/weather.py`.
- **Target Files:** `src/config.py`, `src/curation/curator.py`, `src/ingestion/weather.py`, `tests/test_curation.py`.
- **Acceptance Criteria:**
  - `DataCurator.load_cups_config()` and `DataCurator.get_default_location()` delegate file resolution to `resolve_cups_config_path()` in `src/config.py`.
  - Reuse shared coordinate parsing helpers across `weather.py` and `curator.py`.

## 🛡️ Security

### 1. [P1] Extend Privacy Scanner to Inspect `.xlsx` Workbooks & `cups.json`
- **Goal:** Strengthen GDPR / LOPDGDD zero-leakage guarantees in `src/security.py` by extracting local private signatures from `.input/cups/cups.json` (in addition to `.input/consumption/*.csv`) and scanning tracked/staged `.xlsx` files for non-synthetic CUPS.
- **Target Files:** `src/security.py`, `tests/test_security.py`.
- **Acceptance Criteria:**
  - `get_known_private_signatures()` reads `.input/cups/cups.json` (if present) to register real CUPS suffixes as prohibited signatures.
  - `scan_directory()` and `scan_git_staged()` inspect cell values in tracked/staged `.xlsx` files (outside `.input/`, `.output/`, `.curated/`) using `openpyxl` read-only mode.
  - Add unit tests in `tests/test_security.py` verifying detection of non-synthetic CUPS inside mock `.xlsx` files and `cups.json`.

### 2. [P3] Harden `OpenMeteoWeatherDownloader` URL Scheme & Query Encoding
- **Goal:** Prevent URL injection and insecure transport in `OpenMeteoWeatherDownloader` by validating that `base_url` uses `https://` and encoding query parameters with `urllib.parse.urlencode`.
- **Target Files:** `src/ingestion/weather.py`, `tests/test_weather.py`.
- **Acceptance Criteria:**
  - Validate `self.base_url.startswith("https://")` in `OpenMeteoWeatherDownloader`, raising `IngestionError` otherwise.
  - Build the request URL using `urllib.parse.urlencode` so `timezone` and coordinate parameters are safely escaped.
  - Add unit tests covering invalid URL schemes and special characters in `timezone`.

## 📚 Documentation

### 1. [P2] Synchronize `README.md` and `i18n` Help with All CLI Commands & Flags
- **Goal:** Bring `README.md` and CLI localization strings into 100% parity with `src/cli.py` by documenting `esd curate` and all missing `esd calculate` options (`--hourly` / `-H`, `--min-share`, `--max-share`, `--precision` / `-p`, `--force-curate`, `--curated-dir` / `-u`, `--cups-file` / `-C`, and `--format html`).
- **Target Files:** `README.md`, `src/i18n.py`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `tests/test_i18n.py`.
- **Acceptance Criteria:**
  - Add `### esd curate` section and complete option tables in `README.md`.
  - Update `opt_format` in `src/i18n.py` (both `en` and `es`) to include `'html'`.
  - Verify `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md` reflect all current flags.

### 2. [P3] Localize Hardcoded CLI Prompts and Validation Errors
- **Goal:** Replace hardcoded English strings in `src/cli.py` (`init` interactive prompts, coordinate range errors, strategy/share validation errors) with localized `t(...)` lookups from `src/i18n.py`.
- **Target Files:** `src/cli.py`, `src/i18n.py`, `tests/test_cli.py`, `tests/test_i18n.py`.
- **Acceptance Criteria:**
  - All interactive prompts and validation error messages in `src/cli.py` use `t(..., lang=active_lang)`.
  - Every new key in `src/i18n.py` has matching `en` and `es` translations with identical format placeholders.

## 🧹 Simplicity

### 1. [P3] Remove Legacy `.xslx` Typo Symlink from Curated Excel Export
- **Goal:** Eliminate the creation of the misspelled `{base_name}.xslx` symlink in `ReportExporter.export_curated_excel()` so `.curated/` only contains clean `curated.csv` and `curated.xlsx` artifacts.
- **Target Files:** `src/presentation/export.py`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `tests/test_curation.py`.
- **Acceptance Criteria:**
  - Remove `.xslx` symlink creation from `ReportExporter.export_curated_excel()`.
  - Remove references to `curated.xslx` from `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, and tests.

### 2. [P3] Consolidate Month Abbreviations and Remove Redundant Export Wrappers
- **Goal:** Deduplicate `MONTH_ABBR_EN` / `MONTH_ABBR_ES` across `src/presentation/export.py` and `src/presentation/views/common.py` (removing hardcoded `"2026-01"`..`"2026-12"` entries), and remove the 8 redundant standalone wrapper functions at the bottom of `src/presentation/export.py`.
- **Target Files:** `src/presentation/export.py`, `src/presentation/views/common.py`, `src/presentation/__init__.py`, `tests/test_export.py`.
- **Acceptance Criteria:**
  - Single source of truth for `MONTH_ABBR_EN` and `MONTH_ABBR_ES` with keys `"01"`..`"12"`.
  - Migrate any remaining test/internal callers to `ReportExporter` methods and delete the module-level wrapper functions in `src/presentation/export.py`.

### 2. [P3] Consolidate Month Abbreviations and Remove Redundant Export Wrappers
- **Goal:** Deduplicate `MONTH_ABBR_EN` / `MONTH_ABBR_ES` across `src/presentation/export.py` and `src/presentation/views/common.py` (removing hardcoded `"2026-01"`..`"2026-12"` entries), and remove the 8 redundant standalone wrapper functions at the bottom of `src/presentation/export.py`.
- **Target Files:** `src/presentation/export.py`, `src/presentation/views/common.py`, `src/presentation/__init__.py`, `tests/test_export.py`.
- **Acceptance Criteria:**
  - Single source of truth for `MONTH_ABBR_EN` and `MONTH_ABBR_ES` with keys `"01"`..`"12"`.
  - Migrate any remaining test/internal callers to `ReportExporter` methods and delete the module-level wrapper functions in `src/presentation/export.py`.

