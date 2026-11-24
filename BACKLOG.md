# 📋 Project Improvement Backlog

This document tracks prioritized, actionable improvement tasks for **Electricity Share Distributor (`esd`)**, formatted for autonomous AI agents to execute cleanly.

> [!IMPORTANT]
> **Strategic Goal & Engineering Invariants:** Elevate `esd` into a fast, minimal, and effortless standalone CLI platform focused on three pillars: **(1) Performance** (fixing the `esd calculate` slowdown and making every command sub-second to low-second), **(2) Simplicity & Design** (trimming redundant CLI commands/flags and decluttering console outputs while preserving modern 80-column Rich craft), and **(3) Concise Documentation** (20–25% shorter bilingual guides and README with zero obsolete references). Throughout this cycle, all core invariants remain non-negotiable: mathematical and regulatory fidelity (100.00% fair-share allocation, `[Inc]` apples-to-apples calendar completeness, RD 244/2019 & Orden TED/1247/2021, 25h autumn DST energy conservation), lean zero-bloat dependencies (native SVG/HTML charts), strict Python 3.14+ typing, bilingual EN/ES parity, and zero-leakage GDPR privacy.

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
4. **Prioritization:** Tasks are explicitly prioritized (`P1` High, `P2` Medium, `P3` Low) both in the summary table and within their category.
5. **Core Priority Rule:** Performance optimization, CLI/output simplification, cohesion, and concise documentation take strict precedence over new features. New items under `Features` remain deferred until all active `P1` tasks are resolved.
6. **Zero Completed History:** When a task is completed, it must be **removed** from both the summary table and its category section in `BACKLOG.md`.

---

## 📊 Prioritized Task Overview

| ID | Priority | Category | Title | Target Components |
| :--- | :---: | :--- | :--- | :--- |
| `COH-1` | `P2` | Cohesion | Unify consumption ingestion/filtering & $O(1)$ curated cache fingerprinting | `src/ingestion/doctor.py`, `src/curation/curator.py`, `src/services/` |
| `SIMP-2` | `P2` | Simplicity | Standardize config-first CLI options & extract shared workspace resolver | `src/cli.py`, `tests/test_cli.py` |
| `DES-2` | `P2` | Design | Unify all terminal views onto the `CUSTOM_THEME` semantic design system | `src/presentation/console.py`, `src/presentation/views/` |

---

## 🚀 Features

_No pending tasks (deferred until active `P1` performance, simplicity, design, and documentation tasks are completed)._

## 🏗️ Architecture

_No pending tasks._

## 🔗 Cohesion

### `COH-1` `[P2]` — Unify Consumption Ingestion/Filtering & $O(1)$ Curated Cache Fingerprinting
- **Goal:** Eliminate duplicated DATADIS ingestion, `cups.json` filtering, and heavy CSV freshness checks across services. Currently `DataDoctor` re-implements `parse_file` + `consolidate_autumn_dst` + `cups.json` filtering inline, `DataCurator` repeats CUPS filtering across 3 methods, and `ensure_curated()` reads multi-MB CSVs and weather files just to validate freshness.
- **Target Components:**
  - `src/ingestion/doctor.py`, `src/curation/curator.py`, `src/services/summary_service.py`, `src/services/comparison_service.py`
- **Acceptance Criteria:**
  1. Extract a shared consumption + `cups.json` loading/filtering helper reused consistently by `DataDoctor`, `DataCurator`, `SummaryService`, and `ComparisonService`.
  2. Store a lightweight `.curated/.esd_manifest.json` fingerprint (input file mtimes/sizes + `cups.json` hash + schema version + weather coverage) so `DataCurator.ensure_curated(force=False)` validates cache freshness in **< 1ms** without parsing CSVs, automatically invalidating whenever any input file or `cups.json` changes.
  3. All doctor, curation, summary, comparison, and calculation tests pass.

## 🛡️ Security

_No pending tasks._

## 📚 Documentation

_No pending tasks._

## 🧹 Simplicity

### `SIMP-2` `[P2]` — Standardize Config-First CLI Options & Extract Shared Workspace Resolver
- **Goal:** Align `summary`, `compare`, `doctor`, and `clean` with `calculate`'s clean config-first model instead of duplicating 5–7 directory/config override options (`-c`, `-g`, `-w`, `-u`, `-o`, `-C`) and repeated `load_config()` / `resolve_cups_config_path()` boilerplate across every command in `src/cli.py`.
- **Target Components:**
  - `src/cli.py`, `tests/test_cli.py`
- **Acceptance Criteria:**
  1. Keep only task-specific analytical options on each command (`summary`: `--year`, `--view`, `--cups`; `compare`: `--years`, `--no-charts`, `--html`; `doctor`: `--verbose`; `calculate`: `--refresh`, `--curate-only`; `clean`: `--force`; `init`: `--lang`, `--precision`; `config`: path/lang/precision/coords setters) plus optional `-l`/`--lang` override where appropriate, delegating workspace paths to `esd config` (and keeping full path parameters on Service Request DTOs for programmatic/test isolation).
  2. Extract a single `_resolve_workspace_context()` helper in `src/cli.py` eliminating repeated config/CUPS/language resolution code and reducing `src/cli.py` length by **>= 30%**.
  3. Every command's `--help` fits cleanly within a single screen; all CLI and service tests pass.

## 🎨 Design

### `DES-2` `[P2]` — Unify All Terminal Views onto the `CUSTOM_THEME` Semantic Design System
- **Goal:** Standardize visual styling across all view modules. Currently `consumption.py` and `comparison.py` use semantic `CUSTOM_THEME` tokens (`[title]`, `[metric]`, `[dimmed]`, `[cups]`, `[panel.border]`, `[table.header]`), whereas `summary.py`, `trajectory.py`, `matrix.py`, `doctor.py`, and `common.py` hardcode raw Rich colors (`[bold yellow]`, `[bold bright_cyan]`, `border_style="cyan"`), mix `box.DOUBLE` with `box.ROUNDED`, and format CUPS inconsistently.
- **Target Components:**
  - `src/presentation/console.py`, `src/presentation/views/summary.py`, `trajectory.py`, `matrix.py`, `doctor.py`, `common.py`, `tests/test_presentation.py`
- **Acceptance Criteria:**
  1. Extend `CUSTOM_THEME` in `src/presentation/console.py` with any needed semantic tokens (e.g., `solar`, `heatmap.*`) and replace all raw color literals across `src/presentation/views/`.
  2. Use consistent `box.ROUNDED` framing (including the redesigned 7-command `render_help` and `--version` display) and unified CUPS label/number formatting helpers everywhere.
  3. All presentation tests pass in both `en` and `es`.
