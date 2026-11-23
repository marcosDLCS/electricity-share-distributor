# 📋 Project Improvement Backlog

This document tracks prioritized, actionable improvement tasks for **Electricity Share Distributor (`esd`)**, formatted for autonomous AI agents to execute cleanly.

> [!IMPORTANT]
> **Strategic Goal & Engineering Invariants:** The primary mission is migrating the core capabilities of the sibling repository `datadis-analyzer` (`da`) into `esd` so `datadis-analyzer` can be archived and both workflows are maintained in one unified CLI. Throughout this consolidation, `esd`'s core invariants must remain uncompromised: mathematical and regulatory fidelity (100.00% fair-share allocation, apples-to-apples calendar completeness, RD 244/2019 & Orden TED/1247/2021, DST energy conservation), lean zero-bloat dependencies (native SVG/HTML charts instead of `matplotlib`), vectorized data processing, architectural simplicity, codebase cohesion, and zero-leakage GDPR privacy.

## 📐 Backlog Rules & Conventions

1. **Agent-Ready Descriptions:** Every task must have a brief, concise, and self-contained specification detailing the goal, target components, and acceptance criteria so an independent agent can pick it up immediately.
2. **Categories:** Tasks are organized into seven single-word categories:
   - **`Features`** — Functional capabilities and user-facing enhancements.
   - **`Architecture`** — Structural improvements, mathematical/domain accuracy, data ingestion reliability, performance, and test coverage.
   - **`Cohesion`** — Codebase unification, pattern alignment, and shared abstractions.
   - **`Security`** — Privacy enforcement, vulnerability hardening, and keeping dependencies fully updated.
   - **`Documentation`** — Guides (`README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`), CLI help strings, and developer docs.
   - **`Simplicity`** — Dead code removal, complexity reduction, and waste elimination.
   - **`Design`** — UX/UI ergonomics, visual polish across console outputs, reports, and documentation, adhering to best practices with modern, fresh, and cohesive aesthetics.
3. **Capacity Limit:** Maximum **2 tasks per category** at any time (fewer or zero is acceptable; never exceed 2).
4. **Prioritization:** Tasks are explicitly prioritized (e.g., `P1` High, `P2` Medium, `P3` Low) both in the summary table and within their category.
5. **Core Priority & Consolidation Rule:** Migrating `datadis-analyzer` capabilities into a unified `esd` platform proceeds strictly alongside—never at the expense of—domain accuracy, ingestion reliability, security, vectorized performance, cohesion, and simplicity. New features outside the `datadis-analyzer` consolidation scope are deferred until pending accuracy, ingestion, security, simplification, and documentation work is resolved.
6. **Zero Completed History:** When a task is completed, it must be **removed** from both the summary table and its category section in `BACKLOG.md`.

---

## 📊 Prioritized Task Overview

| ID | Priority | Category | Title | Target Components |
| :--- | :---: | :--- | :--- | :--- |
| **DOC-01** | `P2` Medium | `Documentation` | Synchronize `README.md`, Bilingual Guides & CLI Help with Parameterless `calculate` & New Exports | `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/presentation/views/common.py` |
| **DOC-02** | `P2` Medium | `Documentation` | Unified Platform Documentation & `datadis-analyzer` Migration / Retirement Guide | `README.md`, `AGENTS.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/presentation/views/common.py` |
| **DES-01** | `P3` Low | `Design` | Align Interactive HTML Dashboard with 4-Way Modality Progression & Streamline Template Logic | `src/presentation/html_report.py` |
| **DES-02** | `P3` Low | `Design` | Cohesive Visual Polish for Consumption Summary & Multi-Year Comparison Views (80-Col UI & Responsive SVG/HTML) | `src/presentation/views/`, `src/presentation/charts.py`, `src/presentation/console.py` |

---

## 🚀 Features

_No pending tasks._

## 🏗️ Architecture

_No pending tasks._

## 🔗 Cohesion

_No pending tasks._

## 🛡️ Security

_No pending tasks._

## 📚 Documentation

### DOC-01 (`P2` Medium): Synchronize `README.md`, Bilingual Guides & CLI Help with Parameterless `calculate` & New Exports
- **Goal:** Align `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, and CLI help views with the simplified parameterless `esd calculate` workflow, the 6 exported `.output/` deliverables, and the expanded `esd cleanup` command.
- **Target Components:** `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/presentation/views/common.py`.
- **Acceptance Criteria:**
  1. Update `README.md` and `render_help()` in `src/presentation/views/common.py` to remove obsolete `esd calculate` flags (`--strategy`, `--year`, `--month`, `--view`, `--hourly`, `--format`, `--min-share`, `--max-share`), document the 6 `.output/` deliverables (including `*_esd_monthly_shares_lite.csv`, `*_esd_fortnight_shares.csv`, and `*_esd_fortnight_shares_lite.csv`), and reflect that `esd cleanup` cleans `.output`, `.curated`, and `.input/weather`.
  2. Document the non-destructive primary CUPS reconciliation formula (`max(datadis, inverter)`), autumn DST energy conservation, and multi-year $1/k_m$ calendar scaling in both `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md`.

### DOC-02 (`P2` Medium): Unified Platform Documentation & `datadis-analyzer` Migration / Retirement Guide
- **Goal:** Consolidate product positioning across all docs once `datadis-analyzer` capabilities are integrated so `datadis-analyzer` can be cleanly archived.
- **Target Components:** `README.md`, `AGENTS.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/presentation/views/common.py`.
- **Acceptance Criteria:**
  1. Update `README.md`, `AGENTS.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, and `render_help()` to document `esd summary`, `esd compare`, annualized `.input/consumption/<year>/` ingestion support, the 100.00% fair-share invariant, consumer classification badges (`★`, `(0)`), and the apples-to-apples calendar completeness heuristic.
  2. Replace "sibling utility to `datadis-analyzer`" positioning with unified platform framing covering both consumption-only residential analytics and collective PV optimization under RD 244/2019, and include a concise bilingual `da` ➔ `esd` command/input migration table in `README.md`, `docs/GUIDE_EN.md`, and `docs/GUIDE_ES.md`.

## 🧹 Simplicity

_No pending tasks._

## 🎨 Design

### DES-01 (`P3` Low): Align Interactive HTML Dashboard with 4-Way Modality Progression & Streamline Template Logic
- **Goal:** Bring the interactive HTML dashboard into 100% parity with the 4-way self-consumption progression (Current, Monthly RD 244/2019, Fortnight, and Dynamic Hourly Orden TED/1247/2021) while simplifying `src/presentation/html_report.py`.
- **Target Components:** `src/presentation/html_report.py`, `tests/test_export.py`.
- **Acceptance Criteria:**
  1. Refactor `_calculate_hourly_prevision()` in `src/presentation/html_report.py` to read `current_self_consumed_kwh`, `monthly_share_self_consumed_kwh`, `fortnight_share_self_consumed_kwh`, and `hourly_share_self_consumed_kwh` directly from `OptimizationResult` instead of re-parsing formatted percentage strings (`share_pct`, `estimated_share_pct`) from `time_series_df`, and display the 4-way progression in the HTML report.
  2. Consolidate scattered `if is_es else` string literals in `generate_interactive_html_report()` into a single structured bilingual dictionary.

### DES-02 (`P3` Low): Cohesive Visual Polish for Consumption Summary & Multi-Year Comparison Views (80-Col UI & Responsive SVG/HTML)
- **Goal:** Ensure the migrated `summary` and `compare` terminal views, SVG charts, and reports share `esd`'s modern visual hierarchy, palette, and 80-column clarity.
- **Target Components:** `src/presentation/views/`, `src/presentation/charts.py`, `src/presentation/console.py`, `src/presentation/html_report.py`.
- **Acceptance Criteria:**
  1. Unify 80-column Rich styling (`CUSTOM_THEME` tokens, `make_percentage_bar()`, consistent status icons, and `cups.json` `use` labels alongside masked/full CUPS) across `summary`, `compare`, and `calculate` views.
  2. Style `src/presentation/charts.py` SVGs with `esd`'s modern color palette, clean gridlines, legible value/axis typography, and accessible contrast, with optional standalone interactive HTML comparison dashboard parity (`*_esd_comparison_report.html`).
