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

| Priority | Category | Task Title | Target Files |
| :--- | :--- | :--- | :--- |
| **`P2`** | `Features` | Expose Full Solar-Hours Energy Balance & 3-Way Self-Consumption KPIs in Console & HTML Reports | `src/presentation/views/summary.py`, `src/presentation/views/trajectory.py`, `src/presentation/html_report.py`, `src/i18n.py` |
| **`P2`** | `Design` | Redesign Console & HTML Executive KPI Cards for Clear Solar-Hour & Share Modality Comparison | `src/presentation/views/summary.py`, `src/presentation/html_report.py`, `src/presentation/export.py` |
| **`P3`** | `Documentation` | Synchronize Curated Dataset Schema & Energy Balance KPIs Across Bilingual Guides | `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md` |

---

## 🚀 Features

### 1. `[P2]` Expose Full Solar-Hours Energy Balance & 3-Way Self-Consumption KPIs in Console & HTML Reports
- **Goal:** Provide complete visibility in both console (`esd calculate`) and HTML reports into all six core energy balance KPIs and the three-way self-consumption comparison so users can evaluate hourly vs. monthly allocation efficiency and reduce electricity bills.
- **Target Components:** `src/presentation/views/summary.py`, `src/presentation/views/trajectory.py`, `src/presentation/html_report.py`, `src/i18n.py`, `tests/test_presentation.py`, `tests/test_html_report.py`.
- **Acceptance Criteria:**
  - Both console and HTML reports explicitly display:
    1. **Total Generation** (`total_generation_kwh`)
    2. **Total Consumption** (`total_consumption_kwh`)
    3. **Total Generation during Solar/Generation Hours** (`solar_hours_generation_kwh`, hours where $G_h > 0$)
    4. **Total Consumption during Solar/Generation Hours** (`solar_hours_consumption_kwh`, community demand during hours where $G_h > 0$)
    5. **Solar Surplus** (`total_surplus_kwh`)
    6. **Total Self-Consumption** (`total_self_consumed_kwh`)
  - Both console and HTML reports explicitly display the three-way self-consumption comparison computed directly from the curated dataset without heuristic approximations:
    1. **Current Self-Consumption** (`current_self_consumed_kwh` from the curated `self_consumption` series before collective distribution)
    2. **Estimated Self-Consumption — Monthly Share** (`monthly_share_self_consumed_kwh` under RD 244/2019 fixed monthly $\beta_{i,m}$)
    3. **Estimated Self-Consumption — Hourly Share** (`hourly_share_self_consumed_kwh` under Orden TED/1247/2021 dynamic hourly $\beta_{i,h}$)
  - Add bilingual (`en`/`es`) localization keys in `src/i18n.py` and verify via unit tests in `tests/`.

## 🏗️ Architecture

_No pending tasks._

## 🔗 Cohesion

_No pending tasks._

## 🛡️ Security

_No pending tasks._

## 📚 Documentation

### 1. `[P3]` Synchronize Curated Dataset Schema & Energy Balance KPIs Across Bilingual Guides
- **Goal:** Keep `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md` synchronized with the raw curated dataset schema and the expanded energy balance and 3-way self-consumption KPIs.
- **Target Components:** `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`.
- **Acceptance Criteria:**
  - Update the `.curated/curated.csv` column reference in both guides to reflect the plain raw/modelled schema.
  - Document the six core energy balance KPIs (including total vs. solar-hour generation and consumption) and the three self-consumption regimes (Current, Monthly Share, Hourly Share) in both English and Spanish guides.

## 🧹 Simplicity

_No pending tasks._

## 🎨 Design

### 1. `[P2]` Redesign Console & HTML Executive KPI Cards for Clear Solar-Hour & Share Modality Comparison
- **Goal:** Present the six core energy balance metrics and the 3-way self-consumption progression (Current $\rightarrow$ Monthly Share $\rightarrow$ Hourly Share) with high visual clarity on 80-column terminals and in the interactive HTML report.
- **Target Components:** `src/presentation/views/summary.py`, `src/presentation/html_report.py`, `src/presentation/export.py`.
- **Acceptance Criteria:**
  - Update the console summary KPI table (`src/presentation/views/summary.py`) to remain strictly $\le 80$ columns (`no_wrap=True` on numeric/percentage columns) while clearly pairing Total Generation / Solar-Hours Generation, Total Consumption / Solar-Hours Consumption, Solar Surplus, and the 3-way Self-Consumption comparison (Current vs. Monthly Share vs. Hourly Share with kWh and `%` deltas).
  - Update the HTML executive summary KPI grid and 3-tier self-consumption progression bars (`src/presentation/html_report.py`) and Markdown/JSON export (`src/presentation/export.py`) to display exact matching figures across all formats.
