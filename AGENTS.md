# 🤖 AGENTS.md — Autonomous AI Agent Guide

Operational manual, domain reference, and architectural blueprint for autonomous AI agents collaborating on **Electricity Share Distributor** (`esd`).

---

## 1. 🎯 Project Overview & Mission

`electricity-share-distributor` (`esd`) is the **unified Python CLI platform** for residential community electricity analytics and collective photovoltaic distribution (*autoconsumo colectivo*) across shared common services in a homeowners association (*comunidad de propietarios*) in Spain (e.g. central aerothermal heating, pool, garage, elevators, general lighting) under **Real Decreto 244/2019** and **Orden TED/1247/2021**. It supports both **consumption-only analytics** (`summary`, `compare`, consumption-only `doctor`) and **full solar optimization workflows** (`calculate`, including `--curate-only` and `--refresh`). It is **not** meant to distribute private domestic apartment consumption.

### Core Capabilities
- **📥 Unified Time-Series & Weather Ingestion:** Pre-validates (`DatadisValidator`) and recursively ingests DATADIS hourly CSVs across flat and annualized (`.input/consumption/<year>/`) trees (`consumo_kWh`/`consumoKwh`), Huawei solar inverter Excel reports, and Open-Meteo hourly weather archives.
- **📊 Consumption Analytics & Fair Shares (`esd summary`):** Aggregates community consumption across months and years with an exact **100.00% fair-share invariant** (Hare-Niemeyer rounding), dominant (`★`) and inactive (`(0)`) consumer badges, single-CUPS trajectories, and Markdown reports.
- **📈 Multi-Year Comparison & Native SVGs (`esd compare`):** Evaluates year-over-year consumption trends using an apples-to-apples `[Inc]` calendar completeness heuristic, generating Markdown reports, zero-dependency native SVG grouped bar charts, and optional standalone HTML dashboards.
- **⏱️ Time-Series Alignment & Curation:** Aligns disparate timestamps across leap years and European DST switches (conserving 25h autumn transition energy inside each file prior to cross-file deduplication), reconciles primary CUPS fake zeros ($\max(C_{\text{DATADIS}}, C_{\text{inverter}})$), and exports CSV + streaming styled `.xlsx` datasets.
- **🧮 Optimal $\beta_i$ Allocation & Rich Terminal UI:** Solves exact RD 244/2019 monthly/fortnight models and Orden TED/1247/2021 24h diurnal profiles maximizing collective self-consumption with exact per-month $1/k_m$ calendar scaling, 80-column Rich tables, 4-way progressions, interactive HTML dashboards, and 6 `.output/` deliverables.
- **🛡️ Privacy Guardrails & Persistent Settings:** Persists `.esd_config.json` (`en`/`es`, share precision `0`/`1`/`2`, coordinates, directories) and audits workspace files, `.xlsx` workbooks, staged diffs, and git commit history for GDPR compliance.

---

## 2. 🧩 Architecture & Component Boundaries

The codebase is organized into focused, modular layers with clear separation of concerns:
- **CLI & Dispatch (`src/cli.py`):** Lazy-loaded Typer application dispatching the 7 core commands (`init`, `doctor`, `summary`, `compare`, `calculate`, `config`, `clean` + root `-V`/`--version`, `-h`/`--help`), validating parameters, and formatting domain errors cleanly.
- **Application Services (`src/services/`):** Workflow orchestrators (`CalculationService`, `ComparisonService`, `CurationService`, `DoctorService`, `SummaryService`, `WeatherService`) decoupling business workflows cleanly from CLI presentation.
- **Consumption Analytics (`src/analytics/`):** Pure consumption aggregation (`aggregate_consumption`, `CommunityConsumptionSummary`, `CupsConsumptionShare`) and apples-to-apples multi-year comparison (`compare_years`, `ComparisonSummary`).
- **Domain Core (`src/domain/`):** Pure domain models (`SupplyPoint`, `BylawConstraints`) and typed domain exceptions (`EsdError`, `IngestionError`, `ValidationError`, `AlignmentError`, `CurationError`, `OptimizationError`).
- **Configuration & Localization (`src/config.py`, `src/i18n.py`):** Settings persistence (`.esd_config.json`, `cups.json` resolution) and structured domain namespaces (`app`, `cli`, `status`, `doctor`, `curate`, `weather`, `tables`, `export`, `analytics`) with strict bilingual EN/ES parity.
- **Ingestion & Alignment (`src/ingestion/`):** `DatadisValidator`, recursive `DatadisConsumptionLoader`, streaming `HuaweiGenerationLoader`, Open-Meteo weather downloader/loader, `DataDoctor` pre-flight auditor (supporting consumption-only mode), shared `csv_utils` (`consolidate_autumn_dst`), and DST-aware `TimeSeriesAligner`.
- **Curation & Reconciliation (`src/curation/`):** 3-stage Medallion pipeline aggregating `GenerationDataset` (`generation.csv`/`.xlsx`) and `ConsumptionDataset` (`consumption.csv`/`.xlsx`), reconciling primary CUPS fake zeros, integrating weather, and exporting master `CuratedDataset` (`esd.csv`/`.xlsx`).
- **Optimization & Presentation (`src/optimization/`, `src/presentation/`):** Vectorized separable-concave water-filling solver (verified against `scipy.optimize.linprog`), 4-way progressions, Hare-Niemeyer rounding, $1/k_m$ prevision, PEP 562 lazy 80-col Rich views (`views/`), native SVG charts, interactive HTML reports, and streaming `ReportExporter`.
- **Security & Versioning (`src/security.py`, `src/version.py`):** GDPR CUPS, private coordinate, local path, and secret audit harness (`--staged`, `--files-only`, `--scan <path>`, single-pass `--history`) and automated CalVer (`YYYY.MM.NNN`) manager.

---

## 3. 🛠️ Technology Stack & Standards

| Component | Technology | Standard / Role |
| :--- | :--- | :--- |
| **Runtime** | Python 3.14+ | Modern typing, native union syntax (`X \| Y`), dataclasses |
| **CLI & UI** | Typer & Rich | Lazy command parsing, 80-column tables, visual share bars |
| **Data & Excel** | Pandas, NumPy, Openpyxl | Vectorized time-series ingestion and streaming `write_only` Excel |
| **Optimization** | Water-Filling + SciPy (HiGHS) | Exact vectorized RD 244/2019 solver & reference verification |
| **Quality & Release** | Pytest, Ruff, Pre-commit, CalVer | Automated suite, lint/format hooks, per-commit `YYYY.MM.NNN` |

---

## 4. 📐 Domain Invariants & Regulatory Framework

1. **Real Decreto 244/2019 Coefficients:** Participating CUPS receive fraction $\beta_i$ ($0 \le \beta_i \le 1$, $\sum_i \beta_i \le 1.0000$); monthly $\beta_{i,m}$ remain fixed throughout month $m$ (fortnight fallback when active solar days `< 5`).
2. **Hourly Energy Balance:** $G_{i,h} = \beta_i \cdot G_h$, $SC_{i,h} = \min(C_{i,h}, \beta_i \cdot G_h)$, $RD_{i,h} = \max(0, C_{i,h} - \beta_i \cdot G_h)$, $Surplus_{i,h} = \max(0, \beta_i \cdot G_h - C_{i,h})$.
3. **Collective Optimization Objective:** $\max_{\beta} \sum_i \sum_{h \in m} \min(C_{i,h}, \beta_i \cdot G_h) \quad \text{s.t.} \quad \sum_i \beta_i \le 1, \; \beta_i \ge 0$.
4. **DATADIS & Inverter Conventions:** DATADIS hours 01:00–24:00 conserve 25h autumn DST transition energy inside each file prior to deduplication (`consumo_kWh`/`consumoKwh`); Huawei `.xlsx` uses `Rendimiento FV (kWh)` or `Rendimiento del inversor (kWh)` (`YYYY-MM-DD HH:MM:SS`).
5. **Consumption Analytics & Comparison Invariants (`summary` / `compare`):** Annual/monthly shares sum strictly to `100.00%` (Hare-Niemeyer); `★` marks dominant rank #1 (`> 30.0%`), `(0)` marks inactive supplies (`< 1.0 kWh`); complete months require `> 90%` observed hours past day 27 (`get_complete_months()`), else `[Inc]` excludes them from YoY totals, deltas, and variations.

---

## 5. 🤖 Directives for Autonomous AI Agents

- **🛡️ Directive 1 — Absolute GDPR Privacy:** Universal Supply Point Codes (CUPS) are legally protected under EU GDPR (2016/679) and Spanish LOPDGDD (3/2018). Never commit, log, or expose real CUPS, contracts, residential addresses, coordinates, local paths, or secrets; exclusively use synthetic mocks `ES00210000000000XXYY` (`ES0021000000000001AA`, etc.), verify with `src.security`, and rewrite local commits before pushing if anything leaks:
  ```bash
  python3 -m src.security            # Scans workspace files and entire git commit history
  python3 -m src.security --staged   # Pre-commit staged diff verification
  pre-commit run privacy-cups-checker # Pre-commit hook check
  ```
- **🌐 Directive 2 — English Codebase:** Write all code, comments, docstrings, test names, CLI text, and commit messages in **English**.
- **🎯 Directive 3 — Strict Modern Typing:** Enforce strict type hints (`X | Y` union syntax on signatures and dataclasses); avoid bare `Any`.
- **🚨 Directive 4 — Domain Exceptions:** Raise custom typed exceptions (`EsdError`, `IngestionError`, `OptimizationError`) without uncaught stack traces.
- **🖥️ Directive 5 — 80-Column Terminal Rule:** Render all Rich tables cleanly within **80 columns** (`no_wrap=True` on numeric, percentage, and CUPS columns).
- **🧪 Directive 6 — Test Completeness:** Include automated unit tests in `tests/` for all changes and run `.venv/bin/pytest` before finalizing.
- **🧹 Directive 7 — Ruff & Pre-Commit Adherence:** Pass `.venv/bin/ruff check --fix .` and `.venv/bin/ruff format .` prior to committing.
- **📝 Directive 8 — Conventional Commits & CalVer:** Use Conventional Commits (`feat:`, `fix:`, `perf:`, `refactor:`, `docs:`) and run `python3 -m src.version bump` (`check` validates sync) on every commit.
- **📚 Directive 9 — Documentation & Backlog Sync:** Update `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md` in tandem on schema, solver, presentation, or CLI changes; track future tasks in [`BACKLOG.md`](BACKLOG.md) under the 7 categories (`Features`, `Architecture`, `Cohesion`, `Security`, `Documentation`, `Simplicity`, `Design`; max 2 per category) and remove completed items.

```bash
.venv/bin/ruff check --fix . && .venv/bin/ruff format . && .venv/bin/pytest -q && python3 -m src.version check
```
