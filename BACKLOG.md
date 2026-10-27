# 📋 Project Improvement Backlog

This document tracks prioritized, actionable improvement tasks for **Electricity Share Distributor (`esd`)**, formatted for autonomous AI agents to execute cleanly.

> [!IMPORTANT]
> **Core Priority Hierarchy & Performance Invariant:** Simplicity, security, architecture, and cohesion must **always** take precedence over introducing new features. Performance—low algorithmic overhead, fast execution, and a lean memory and resource footprint—is an essential invariant across all modules. Stability, security, and computational efficiency must never be compromised for feature expansion.

## 📐 Backlog Rules & Conventions

1. **Agent-Ready Descriptions:** Every task must have a brief, concise, and self-contained specification detailing the goal, target components, and acceptance criteria so an independent agent can pick it up immediately.
2. **Categories:** Tasks are organized into seven single-word categories:
   - **`Features`** — Functional capabilities and user-facing enhancements.
   - **`Architecture`** — Structural improvements, engineering standards, and test coverage.
   - **`Cohesion`** — Codebase unification, pattern alignment, and shared abstractions.
   - **`Security`** — Privacy enforcement, vulnerability hardening, and keeping dependencies fully updated.
   - **`Documentation`** — Guides (`docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`), CLI help strings, and developer docs.
   - **`Simplicity`** — Dead code removal, complexity reduction, and waste elimination.
   - **`Design`** — UX/UI ergonomics, visual polish across console outputs, reports, and documentation, adhering to best practices with modern, fresh, and cohesive aesthetics.
3. **Capacity Limit:** Maximum **2 tasks per category** at any time (fewer or zero is acceptable; never exceed 2).
4. **Prioritization:** Tasks are explicitly prioritized (e.g., `P1` High, `P2` Medium, `P3` Low) both in the summary table and within their category.
5. **Core Priority & Performance Rule:** Simplicity, security, architecture, and cohesion must always take precedence over new features. Feature proposals should be deferred whenever structural, security, performance, or simplification improvements are pending. High computational performance (e.g., efficient vectorization, fast linear programming solves, minimal I/O overhead) must be preserved across all implementations.
6. **Zero Completed History:** When a task is completed, it must be **removed** from both the summary table and its category section in `BACKLOG.md`.

---

## 📊 Prioritized Task Overview

| Priority | Category | Task | Target Components |
| :--- | :--- | :--- | :--- |
| **P2** | `Cohesion` | Propagate `primary_cups` on `OptimizationResult` to Eliminate Redundant Disk I/O | `src/optimization/models.py`, `src/optimization/engine.py`, `src/presentation/html_report.py` |
| **P2** | `Cohesion` | Unify CLI Domain Exception Handling Across All Subcommands | `src/cli.py`, `tests/test_cli.py` |
| **P2** | `Design` | Align `--curated-dir` Short Flag (`-u`) Across `esd curate` and `esd calculate` | `src/cli.py`, `tests/test_cli.py` |
| **P2** | `Design` | Add `TOTAL (RD 244/2019)` Summary Footer Row to HTML Report Matrix Table | `src/presentation/html_report.py`, `tests/test_export.py` |
| **P2** | `Documentation` | Synchronize `dso` / `html` Export Formats and 1% Minimum Floor in `README.md` and Guides | `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md` |
| **P3** | `Documentation` | Restore Missing `f_hour` Formula Block in `docs/GUIDE_ES.md` Section 4.7 | `docs/GUIDE_ES.md` |
| **P3** | `Features` | Expose `--curated-dir` (`-u`) in `esd config` and Configuration Table View | `src/cli.py`, `src/presentation/views/common.py`, `src/i18n.py` |

---

## 🚀 Features

### 1. [P3] Expose `--curated-dir` (`-u`) in `esd config` and Configuration Table View
- **Goal:** Allow viewing and persisting the existing `AppConfig.curated_dir` setting via `esd config --curated-dir / -u` and display it in `render_config_view()`.
- **Target Files:** `src/cli.py`, `src/presentation/views/common.py`, `src/i18n.py`, `tests/test_cli.py`
- **Acceptance Criteria:**
  - `esd config` accepts `--curated-dir` / `-u` and persists `curated_dir` to `.esd_config.json`.
  - `render_config_view()` displays the configured `curated_dir` path alongside `consumption_dir`, `generation_dir`, and `output_dir`.
  - Unit tests in `tests/test_cli.py` verify setting and displaying `curated_dir`.

## 🏗️ Architecture

_No pending tasks._

## 🔗 Cohesion

### 1. [P2] Propagate `primary_cups` on `OptimizationResult` to Eliminate Redundant Disk I/O
- **Goal:** Store `primary_cups: str | None = None` directly on `OptimizationResult` during optimization so `src/presentation/html_report.py` and `src/optimization/engine.py` no longer re-instantiate `DataCurator` to read `cups.json` from disk during report generation.
- **Target Files:** `src/optimization/models.py`, `src/optimization/engine.py`, `src/presentation/html_report.py`, `tests/test_export.py`
- **Acceptance Criteria:**
  - `OptimizationResult` in `src/optimization/models.py` includes `primary_cups: str | None = None`, populated from `aligned_dataset.primary_cups` in `DistributionOptimizer.optimize_dataset()`.
  - `HtmlReportGenerator` reads `result.primary_cups` directly (falling back to `cups.json` only if `None`), removing redundant disk reads during standard calculation workflows.
  - Existing optimization and HTML export tests pass.

### 2. [P2] Unify CLI Domain Exception Handling Across All Subcommands
- **Goal:** Standardize `EsdError` handling across `init`, `doctor`, `curate`, `weather`, `calculate`, and `config` in `src/cli.py` via a shared error-reporting helper so no subcommand leaks raw tracebacks on domain errors.
- **Target Files:** `src/cli.py`, `tests/test_cli.py`
- **Acceptance Criteria:**
  - `doctor_command` and all other CLI commands in `src/cli.py` catch `EsdError` consistently and format errors through a unified helper before raising `typer.Exit(code=1)`.
  - Unit tests in `tests/test_cli.py` verify clean CLI exit (`exit_code == 1`) when `DoctorService` raises `EsdError`.

## 🛡️ Security

_No pending tasks._

## 📚 Documentation

### 1. [P2] Synchronize `dso` / `html` Export Formats and 1% Minimum Floor in `README.md` and Guides
- **Goal:** Update `README.md` to list all 5 supported export formats (`csv`, `json`, `md`, `html`, `dso`) and update Section 4.6 of `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md` to accurately reflect the 1% minimum floor per participating CUPS during zero-generation night hours (e.g., 99% primary / 1% secondary instead of 100% / 0%).
- **Target Files:** `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`
- **Acceptance Criteria:**
  - `README.md` features and CLI examples include `html` and `dso` formats.
  - Section 4.6 in both `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md` documents the 1% (`0.01`) minimum allocation floor during zero-generation hours.

### 2. [P3] Restore Missing `f_hour` Formula Block in `docs/GUIDE_ES.md` Section 4.7
- **Goal:** Add the missing `f_hour` mathematical equation block and blank line separator at the end of Section 4.7 in `docs/GUIDE_ES.md` so it matches `docs/GUIDE_EN.md`.
- **Target Files:** `docs/GUIDE_ES.md`
- **Acceptance Criteria:**
  - Section 4.7 in `docs/GUIDE_ES.md` includes the `f_hour` display formula block and proper heading separation before `### 8. Restricciones Regulatorias`.

## 🧹 Simplicity

_No pending tasks._

## 🎨 Design

### 1. [P2] Align `--curated-dir` Short Flag (`-u`) Across `esd curate` and `esd calculate`
- **Goal:** Support the `-u` short flag for `--curated-dir` in `esd curate` (while retaining `-o` as a backward-compatible alias) so CLI flags match `esd calculate` and `README.md`.
- **Target Files:** `src/cli.py`, `tests/test_cli.py`
- **Acceptance Criteria:**
  - `curate_command` in `src/cli.py` accepts both `-u` and `-o` for `--curated-dir`.
  - CLI tests in `tests/test_cli.py` verify invoking `esd curate -u <path>`.

### 2. [P2] Add `TOTAL (RD 244/2019)` Summary Footer Row to HTML Report Matrix Table
- **Goal:** Render a `<tfoot>` summary row in the Interactive HTML Report's Monthly Coefficients Matrix table (`src/presentation/html_report.py`) displaying `matrix.format_month_sum(m)` and `matrix.format_annual_sum()`, matching the Terminal, Markdown, and CSV matrix views.
- **Target Files:** `src/presentation/html_report.py`, `tests/test_export.py`
- **Acceptance Criteria:**
  - `_build_matrix_table()` in `src/presentation/html_report.py` outputs a styled `<tfoot>` row with monthly and annual `100.00%` totals.
  - Unit tests in `tests/test_export.py` assert the presence of `<tfoot>` and `100.00%` in generated HTML reports.
