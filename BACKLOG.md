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
| `DES-1` | `P1` | Design | Declutter default console outputs (`summary`, `doctor`, `calculate`, `compare`) | `src/presentation/views/consumption.py`, `doctor.py`, `summary.py`, `comparison.py`, `common.py` |
| `DOC-1` | `P1` | Documentation | Purge all `datadis-analyzer` references across docs, guides & codebase | `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `AGENTS.md`, `src/security.py` |
| `DOC-2` | `P1` | Documentation | Condense `README.md`, bilingual guides & `AGENTS.md` by 20–25% | `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `AGENTS.md` |
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

### `DOC-1` `[P1]` — Purge All `datadis-analyzer` References Across Docs, Guides & Codebase
- **Goal:** Remove every mention, link, migration table, legacy alias note, and code comment referencing `datadis-analyzer` (`da`) now that the external repository is being deleted, making `esd` read as a clean standalone platform.
- **Target Components:**
  - `README.md` (intro, `clean` alias comment, migration section)
  - `docs/GUIDE_EN.md` & `docs/GUIDE_ES.md` (Section 1 intro, Section 6 guarantees intro, Section 8 migration table & section renumbering)
  - `AGENTS.md` (Project Overview)
  - `src/security.py` (line 47 comment)
- **Acceptance Criteria:**
  1. All `datadis-analyzer` / `da` migration sections, links, and comments are removed cleanly and section numbering in `GUIDE_EN.md` and `GUIDE_ES.md` is updated symmetrically.
  2. `git grep -i "datadis.analyzer\|datadis_analyzer\|former da\|legacy da"` returns **zero matches** across the entire tracked repository (once this task is completed and removed from `BACKLOG.md`).
  3. `python3 -m src.security` passes with zero violations.

### `DOC-2` `[P1]` — Condense `README.md`, Bilingual Guides & `AGENTS.md` by 20–25%
- **Goal:** Tighten all user and developer documentation by **20–25%** without losing any relevant domain formula, regulatory invariant, CLI capability, deliverable specification, or architecture reference. Current baselines: `README.md` (401 lines / 3,248 words), `docs/GUIDE_EN.md` (315 lines / 4,585 words), `docs/GUIDE_ES.md` (315 lines / 5,073 words), `AGENTS.md` (100 lines / 1,488 words).
- **Target Components:**
  - `README.md` (target: ~300–320 lines / ~2,435–2,600 words)
  - `docs/GUIDE_EN.md` (target: ~235–252 lines / ~3,440–3,670 words)
  - `docs/GUIDE_ES.md` (target: ~235–252 lines / ~3,800–4,060 words)
  - `AGENTS.md` (target: ~75–85 lines / ~1,120–1,200 words)
- **Acceptance Criteria:**
  1. Replace the stale 48-line terminal preview in `README.md` with a compact (~20-line) accurate preview of the current redesigned CLI output; collapse repeated per-command flag tables and synchronize commands with `SIMP-1` / `SIMP-2`.
  2. Deduplicate repeated prose across Sections 3, 4, 5, and 7 of `GUIDE_EN.md` and `GUIDE_ES.md` in strict bilingual parity while preserving every mathematical formula (RD 244/2019, SEI, Hare-Niemeyer, $1/k_m$, DST conservation, `[Inc]`), both Mermaid diagrams, the `.output/` deliverables table, and the Code Map.
  3. Combined length of `README.md`, `docs/GUIDE_EN.md`, and `docs/GUIDE_ES.md` drops by **20–25%** (verified via `wc -l -w`), with zero broken markdown links and clean `python3 -m src.security` verification.

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

### `DES-1` `[P1]` — Declutter Default Console Outputs (`summary`, `doctor`, `calculate`, `compare`)
- **Goal:** Simplify terminal outputs across all core commands so every screen is tight, scannable, and clutter-free on 80-column terminals **without losing Rich visual polish, color hierarchy, KPI cards, heatmaps, or share bars**:
  - **`esd summary`:** Default view currently prints up to 24 separate monthly CUPS tables (~350+ lines) plus 4 stacked boxes in `render_consumption_overview`. Change default view to show a single unified overview card, annual ranked table(s), compact monthly timeline, and insights — reserving per-month CUPS breakdown tables for `--view monthly` (full breakdown always remains in the exported `.md`).
  - **`esd doctor`:** Collapse the 6 separate panels/tables (including separate single-row Generation and Weather tables and a broken 12-char truncated `Diagnosis` column) into 2–3 crisp blocks: status header, CUPS health table, and a unified Data Sources table (Generation + Weather) + concise non-repetitive advice footer.
  - **`esd calculate`:** Eliminate double-boxed nesting inside `render_community_summary` (replace nested inner KPI `Panel` borders with a sleek borderless metric strip inside one outer card) while keeping the 4-way modality progression, monthly trajectory, and signature $\beta_i$ heatmap matrix.
  - **`esd compare`:** Drop the redundant `Trend` text column (already encoded via colored `▼`/`▲` in `Variation`), keep CUPS labels single-line, and merge `.md` + `.svg` + `.html` export notices into one unified compact footer.
  - **All commands:** Replace bulky boxed `render_export_success` panels with a sleek 1–2 line `✔ Exported ...` footer component.
- **Target Components:**
  - `src/presentation/views/consumption.py`, `src/presentation/views/doctor.py`, `src/presentation/views/summary.py`, `src/presentation/views/comparison.py`, `src/presentation/views/common.py`, `src/cli.py`, `tests/test_presentation.py`
- **Acceptance Criteria:**
  1. Default terminal output height drops by **>= 30%** on `calculate`/`doctor`/`compare` and **>= 60%** on multi-year `summary` with zero loss of decision-critical KPIs or visual richness.
  2. Strict 80-column compliance with zero 12-char diagnosis truncation or double-boxed borders across both `en` and `es`.
  3. Updated presentation and CLI tests verify every redesigned view and pass cleanly.

### `DES-2` `[P2]` — Unify All Terminal Views onto the `CUSTOM_THEME` Semantic Design System
- **Goal:** Standardize visual styling across all view modules. Currently `consumption.py` and `comparison.py` use semantic `CUSTOM_THEME` tokens (`[title]`, `[metric]`, `[dimmed]`, `[cups]`, `[panel.border]`, `[table.header]`), whereas `summary.py`, `trajectory.py`, `matrix.py`, `doctor.py`, and `common.py` hardcode raw Rich colors (`[bold yellow]`, `[bold bright_cyan]`, `border_style="cyan"`), mix `box.DOUBLE` with `box.ROUNDED`, and format CUPS inconsistently.
- **Target Components:**
  - `src/presentation/console.py`, `src/presentation/views/summary.py`, `trajectory.py`, `matrix.py`, `doctor.py`, `common.py`, `tests/test_presentation.py`
- **Acceptance Criteria:**
  1. Extend `CUSTOM_THEME` in `src/presentation/console.py` with any needed semantic tokens (e.g., `solar`, `heatmap.*`) and replace all raw color literals across `src/presentation/views/`.
  2. Use consistent `box.ROUNDED` framing (including the redesigned 7-command `render_help` and `--version` display) and unified CUPS label/number formatting helpers everywhere.
  3. All presentation tests pass in both `en` and `es`.
