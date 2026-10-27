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
| Centralize `cups.json` Path Discovery and Coordinate Extraction | `Cohesion` | `P3` |
| Harden `OpenMeteoWeatherDownloader` URL Scheme & Query Encoding | `Security` | `P3` |
| Localize Hardcoded CLI Prompts and Validation Errors | `Documentation` | `P3` |
| Remove Legacy `.xslx` Typo Symlink from Curated Excel Export | `Simplicity` | `P3` |
| Consolidate Month Abbreviations and Remove Redundant Export Wrappers | `Simplicity` | `P3` |

---

## 🚀 Features

*No pending tasks.*

## 🏗️ Architecture

*No pending tasks.*

## 🔗 Cohesion

### 1. [P3] Centralize `cups.json` Path Discovery and Coordinate Extraction
- **Goal:** Remove duplicated candidate path lists (`[.input/cups/cups.json, .input/cups.json, cups.json]`) and coordinate key parsing between `src/config.py`, `src/curation/curator.py`, and `src/ingestion/weather.py`.
- **Target Files:** `src/config.py`, `src/curation/curator.py`, `src/ingestion/weather.py`, `tests/test_curation.py`.
- **Acceptance Criteria:**
  - `DataCurator.load_cups_config()` and `DataCurator.get_default_location()` delegate file resolution to `resolve_cups_config_path()` in `src/config.py`.
  - Reuse shared coordinate parsing helpers across `weather.py` and `curator.py`.

## 🛡️ Security

### 1. [P3] Harden `OpenMeteoWeatherDownloader` URL Scheme & Query Encoding
- **Goal:** Prevent URL injection and insecure transport in `OpenMeteoWeatherDownloader` by validating that `base_url` uses `https://` and encoding query parameters with `urllib.parse.urlencode`.
- **Target Files:** `src/ingestion/weather.py`, `tests/test_weather.py`.
- **Acceptance Criteria:**
  - Validate `self.base_url.startswith("https://")` in `OpenMeteoWeatherDownloader`, raising `IngestionError` otherwise.
  - Build the request URL using `urllib.parse.urlencode` so `timezone` and coordinate parameters are safely escaped.
  - Add unit tests covering invalid URL schemes and special characters in `timezone`.

## 📚 Documentation

### 1. [P3] Localize Hardcoded CLI Prompts and Validation Errors
- **Goal:** Replace hardcoded English strings in `src/cli.py` (`init` interactive prompts, coordinate range errors, strategy/share validation errors) with localized `t(...)` lookups from `src/i18n.py`.
- **Target Files:** `src/cli.py`, `src/i18n.py`, `tests/test_cli.py`, `tests/test_i18n.py`.
- **Acceptance Criteria:**
  - All interactive prompts and validation error messages in `src/cli.py` use `t(..., lang=active_lang)`.
  - Every new key in `src/i18n.py` has matching `en` and `es` translations with identical format placeholders.
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
