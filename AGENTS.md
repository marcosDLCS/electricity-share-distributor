# 🤖 AGENTS.md — Autonomous AI Agent Guide

Welcome to **Electricity Share Distributor** (`esd`). This document serves as the operational manual, domain reference, and architectural blueprint for autonomous AI agents collaborating on this codebase.

---

## 1. 🎯 Project Overview & Mission

`electricity-share-distributor` (`esd`) is the **unified Python CLI platform** for residential community electricity analytics and collective photovoltaic distribution (*autoconsumo colectivo*) across shared common services in a homeowners association (*comunidad de propietarios*) in Spain (e.g. central aerothermal heating, pool, garage, elevators, general lighting) under **Real Decreto 244/2019** and **Orden TED/1247/2021**. It supports both **consumption-only analytics** (`summary`, `compare`, consumption-only `doctor`) and **full solar optimization workflows** (`calculate`, including `--curate-only` and `--refresh`). It is **not** meant to distribute private domestic apartment consumption.

### Core Capabilities:
- **📥 Unified Time-Series & Weather Ingestion:** Pre-validates (`DatadisValidator`) and recursively ingests DATADIS hourly consumption CSVs across flat and annualized (`.input/consumption/<year>/`) trees (`consumo_kWh` / `consumoKwh`), solar inverter PV generation Excel reports, and Open-Meteo hourly weather archives.
- **📊 Consumption Analytics & Fair Shares (`esd summary`):** Aggregates community consumption across months and years with an exact **100.00% fair-share invariant** (Hare-Niemeyer rounding), dominant (`★`) and inactive (`(0)`) consumer badges, and Markdown report exports.
- **📈 Multi-Year Comparison & Native SVGs (`esd compare`):** Evaluates year-over-year consumption trends using an apples-to-apples `[Inc]` calendar completeness heuristic, generating zero-dependency native SVG grouped bar charts and Markdown reports.
- **⏱️ Time-Series Alignment & Normalization:** Aligns disparate timestamps, conserving 25h autumn DST transition energy per source file, handling missing intervals, and normalizing Spanish 01:00–24:00 meter conventions.
- **🧮 Optimal $\beta_i$ Allocation Engine:** Formulates and solves monthly/fortnight LP models (RD 244/2019) and dynamic 24-hour profiles (Orden TED/1247/2021) maximizing collective self-consumption with exact per-month $1/k_m$ calendar scaling.
- **📊 Rich Terminal UI:** Renders clear tabular views, 4-way self-consumption progressions, summary metrics, and visual share bars formatted for 80-column terminals.
- **📝 Multi-Format Reporting:** Generates timestamped Markdown analytics reports, native SVG charts, interactive HTML dashboards, monthly/fortnight/hourly shares CSVs, and lite matrices in `.output/`.
- **🛡️ Privacy & Secret Guardrails:** Audits workspace files, `.xlsx` workbooks, staged diffs, and git history for real CUPS, private coordinates, local paths, and exposed secrets/credentials.
- **⚙️ Persistent Configuration:** Maintains language preferences (`en`/`es`), share precision, geographical coordinates, and directory paths in `.esd_config.json`.

---

## 2. 🧩 Architecture & Component Boundaries

The codebase is organized into focused, modular layers with clean separation of concerns:
- **CLI & Dispatch (`src/cli.py`):** Typer application orchestrating command dispatch (`calculate`, `summary`, `compare`, `curate`, `doctor`, `weather`, `init`, `config`, `cleanup`/`clean`, `help`, `version`), parameter validation, and user workflow.
- **Application Services (`src/services/`):** Workflow orchestrators (`CalculationService`, `ComparisonService`, `CurationService`, `DoctorService`, `SummaryService`, `WeatherService`) encapsulating business processes.
- **Consumption Analytics (`src/analytics/`):** Pure consumption aggregation (`aggregate_consumption`, `CommunityConsumptionSummary`, `CupsConsumptionShare`) and apples-to-apples multi-year comparison (`compare_years`, `ComparisonSummary`).
- **Domain Core (`src/domain/`):** Pure domain models (`SupplyPoint`, `BylawConstraints`) and centralized domain exceptions (`EsdError`, `IngestionError`, `ValidationError`, `AlignmentError`, `CurationError`, `OptimizationError`).
- **Configuration & Localization (`src/config.py`, `src/i18n.py`):** Persistent settings (`.esd_config.json`) and structured domain namespaces (`app`, `cli`, `status`, `doctor`, `curate`, `weather`, `tables`, `export`, `analytics`) with strict bilingual EN/ES parity.
- **Ingestion & Alignment (`src/ingestion/`):** `DatadisValidator`, recursive `DatadisConsumptionLoader`, `HuaweiGenerationLoader`, Open-Meteo weather downloader/loader, `DataDoctor` pre-flight auditor (supporting consumption-only mode), shared `csv_utils` (including `consolidate_autumn_dst`), and DST-aware `TimeSeriesAligner`.
- **Curation & Reconciliation (`src/curation/`):** Multi-stage canonical data pipeline aggregating generation (`generation.csv` + `generation.xlsx` via `GenerationDataset`), aggregating consumption (`consumption.csv` + `consumption.xlsx` via `ConsumptionDataset`), non-destructively reconciling primary CUPS fake-zero loads ($\max(C_{\text{DATADIS}}, C_{\text{inverter}})$), integrating weather, and producing the master ESD dataset (`esd.csv` + `esd.xlsx` via `CuratedDataset`).
- **Optimization Core (`src/optimization/`):** RD 244/2019 linear programming solver (`scipy.optimize.linprog`), 4-way modality evaluations, Hare-Niemeyer exact rounding, and multi-year $1/k_m$ calendar prevision engine.
- **Presentation & Reporting (`src/presentation/`):** Rich 80-column terminal views (`src/presentation/views/`), zero-dependency SVG comparison chart generator (`src/presentation/charts.py`), two-tone heatmaps, KPI cards, and unified `ReportExporter` multi-format reporting (6 calculation CSV/HTML deliverables plus `summary`/`compare` Markdown reports).
- **Security & Versioning (`src/security.py`, `src/version.py`):** GDPR CUPS, private coordinate, path, and secret/credential audit harness (`--staged`, `--files-only`, `--scan <path>`, single-pass git history) and automated CalVer release manager.

---

## 3. 🛠️ Technology Stack & Standards

| Component | Technology | Standard / Role |
| :--- | :--- | :--- |
| **Runtime** | Python 3.14+ | Modern typing, union types (`X \| Y`), dataclasses |
| **CLI & UI** | Typer & Rich | Command parsing, 80-column tables, visual bars |
| **Data Engine** | Pandas & Openpyxl | Time-series indexing, CSV and Excel ingestion |
| **Optimization** | Scipy (`scipy.optimize.linprog`) | Linear programming solver for optimal $\beta$ coefficients |
| **Versioning** | CalVer (`YYYY.MM.NNN`) | Automated per-commit version increments |
| **Quality** | Ruff & Pre-commit | Linter, code formatter, git hook enforcement |
| **Testing** | Pytest | Unit and integration test coverage |

---

## 4. 📐 Domain Invariants & Regulatory Framework

1. **Real Decreto 244/2019 (Autoconsumo Colectivo):**
   - Participating CUPS receive a fraction $\beta_i$ of solar PV generation in each hour $h$.
   - Coefficient constraint: $0 \le \beta_i \le 1$ and $\sum_i \beta_i \le 1.0$ (or $100.00\%$).
   - Monthly coefficients $\beta_{i, m}$ remain fixed throughout month $m$.
2. **Hourly Self-Consumption & Residual Balance:**
   - Allocated Generation: $G_{i, h} = \beta_i \cdot G_h$
   - Self-Consumed Energy: $SC_{i, h} = \min(C_{i, h}, \beta_i \cdot G_h)$
   - Residual Grid Demand: $RD_{i, h} = \max(0, C_{i, h} - \beta_i \cdot G_h)$
   - Surplus / Excess Generation: $Surplus_{i, h} = \max(0, \beta_i \cdot G_h - C_{i, h})$
3. **Collective Optimization Objective:**
   $$\max_{\beta} \sum_{i} \sum_{h \in m} \min(C_{i, h}, \beta_i \cdot G_h) \quad \text{s.t.} \quad \sum_i \beta_i \le 1, \; \beta_i \ge 0$$
4. **DATADIS Time Series:**
   - Hours 01:00–24:00 (hour 01:00 = interval 00:00–01:00); autumn DST transition day preserves all 25 hours via within-file summation before deduplication.
   - Values are hourly kWh consumption per CUPS (`consumo_kWh` or `consumoKwh`).
5. **Solar Inverter Generation:**
   - Timestamps `YYYY-MM-DD HH:MM:SS`. Column `Rendimiento FV (kWh)` or `Rendimiento del inversor (kWh)`.
6. **Consumption Analytics & Comparison Invariants (`esd summary` / `esd compare`):**
   - **100.00% Fair-Share Invariant:** Annual and monthly consumption shares sum strictly to `100.00%` whenever total consumption > 0 (via Hare-Niemeyer rounding at 2 decimals).
   - **Consumer Classification Badges:** `★` marks a dominant consumer (`share_pct > 30.0%` at rank #1); `(0)` marks an inactive/negligible consumer (`consumption_kwh < 1.0`).
   - **Apples-to-Apples Completeness Heuristic:** A calendar month is complete only when observed hours exceed 90% of expected calendar hours and span past the 27th day (`get_complete_months()`); incomplete months are flagged `[Inc]` and excluded from year-over-year totals, deltas, and percentage variations.

---

## 5. 🤖 Directives for Autonomous AI Agents

- **🛡️ Directive 1: Anonymization & Data Privacy is Absolute.** Universal Supply Point Codes (CUPS) are legally protected residential identifiers under European GDPR (Regulation EU 2016/679) and Spanish Organic Law 3/2018 (LOPDGDD).
  - **Zero Real Data Policy:** Never commit, log, or include real DATADIS CUPS, contract numbers, residential addresses, customer names, or real customer consumption datasets in the codebase, tests, documentation, or commit messages.
  - **Synthetic Mock Specification:** Exclusively use authorized synthetic mock identifiers adhering strictly to pattern `ES00210000000000XXYY` (e.g., `ES0021000000000001AA`, `ES0021000000000002BB`, etc.).
  - **Automated Verification Harness:** Enforce zero-leakage via the security harness:
    ```bash
    python3 -m src.security            # Scans workspace files and entire git commit history
    python3 -m src.security --history  # Explicit git history scan across all commit blobs and messages
    pre-commit run privacy-cups-checker # Pre-commit hook enforcement
    ```
  - **Git History Invariant:** No commit containing real CUPS or private data may ever exist in Github history. If real data is ever detected in local commits before pushing, you must amend or rewrite commits prior to sharing.
- **🌐 Directive 2: Universal English Codebase.** Write all code, comments, docstrings, test names, CLI messages, and commit messages entirely in **English**.
- **🎯 Directive 3: Strict Modern Typing.** Use strict type hints (`typing`, native union syntax `X | Y`) on all function signatures, dataclasses, and class methods. Avoid bare `Any`.
- **🚨 Directive 4: Domain Exceptions.** Use custom domain exceptions (`EsdError`, `IngestionError`, `OptimizationError`). Handle errors gracefully without uncaught stack traces.
- **🖥️ Directive 5: The 80-Column Terminal Rule.** Rich tables must render cleanly on standard **80-column terminals**. Set `no_wrap=True` on numeric, percentage, and CUPS columns.
- **🧪 Directive 6: Test Completeness.** Any new calculation logic, CLI flag, or parser must include automated unit tests in `tests/`. Always run `pytest` before finalizing tasks.
- **🧹 Directive 7: Ruff & Pre-Commit Adherence.** Run `ruff check --fix .` and `ruff format .` before committing changes.
- **📝 Directive 8: Conventional Commits.** Adhere strictly to Conventional Commits (`feat:`, `fix:`, `chore:`, etc.).
- **🏷️ Directive 9: CalVer Increments on Every Commit.** Every commit must increment the CalVer sequence (`python -m src.version bump`).
- **📚 Directive 10: Documentation Synchronization.** Whenever modifying data schemas, optimization algorithms, presentation views, or CLI commands, you must update both English and Spanish documentation guides (`docs/GUIDE_EN.md` and `docs/GUIDE_ES.md`) in tandem.
- **📋 Directive 11: Backlog Management (`BACKLOG.md`).** Future improvements are tracked in [`BACKLOG.md`](BACKLOG.md) under seven single-word categories (`Features`, `Architecture`, `Cohesion`, `Security`, `Documentation`, `Simplicity`, `Design`), capped at a maximum of 2 tasks per category and summarized in a prioritized overview table. When completing a backlog task, remove it from `BACKLOG.md`.
