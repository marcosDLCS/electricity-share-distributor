# 📋 Project Improvement Backlog

This document tracks prioritized, actionable improvement tasks for **Electricity Share Distributor (`esd`)**, formatted for autonomous AI agents to execute cleanly.

> [!IMPORTANT]
> **Core Priority Hierarchy & Performance Invariant:** Simplicity, domain accuracy, data ingestion reliability, security, architecture, and cohesion must **always** take precedence over introducing new features ("do less, but do better"). Performance—low algorithmic overhead, vectorized data processing, fast linear programming solves, and a lean memory and I/O footprint—is an essential invariant across all modules. Stability, mathematical accuracy, regulatory fidelity (RD 244/2019 & Orden TED/1247/2021), and computational efficiency must never be compromised for feature expansion.

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
5. **Core Priority & Performance Rule:** Simplicity, domain accuracy, data ingestion, security, architecture, and cohesion must always take precedence over new features. Feature proposals should be deferred whenever structural, accuracy, ingestion, security, performance, or simplification improvements are pending.
6. **Zero Completed History:** When a task is completed, it must be **removed** from both the summary table and its category section in `BACKLOG.md`.

---

## 📊 Prioritized Task Overview

| ID | Priority | Category | Title | Target Components |
| :--- | :---: | :--- | :--- | :--- |
| **ARCH-01** | `P1` High | `Architecture` | Domain & Ingestion Accuracy: Multi-Year Scaling, Primary Reconciliation, DST & Doctor Audit | `src/optimization/engine.py`, `src/curation/curator.py`, `src/ingestion/` |
| **ARCH-02** | `P1` High | `Architecture` | Performance Vectorization: Curation Pipeline, 2D Rounding, Solver Baselines & Excel Export | `src/curation/`, `src/optimization/`, `src/presentation/export.py` |
| **SIMP-01** | `P1` High | `Simplicity` | Prune Dead Calculation Options, Unreferenced Views, Legacy Fallbacks & Unused Domain Models | `src/domain/`, `src/curation/`, `src/services/`, `src/presentation/views/` |
| **SIMP-02** | `P1` High | `Simplicity` | Prune Orphaned Localization Keys & Simplify Translation Catalog Builder | `src/i18n.py`, `tests/` |
| **COH-01** | `P2` Medium | `Cohesion` | Unify `cups.json` Configuration, Primary Supply Point & Coordinate Resolution | `src/curation/curator.py`, `src/services/weather_service.py`, `src/optimization/engine.py`, `src/presentation/html_report.py` |
| **COH-02** | `P2` Medium | `Cohesion` | Centralize Ingestion & Curation CSV Reader, Delimiter Sniffing & Numeric Normalization | `src/curation/`, `src/ingestion/`, `src/presentation/html_report.py` |
| **SEC-01** | `P2` Medium | `Security` | Harden Formula Injection Sanitization & Streamline Git History Privacy Audit | `src/presentation/export.py`, `src/security.py` |
| **DOC-01** | `P2` Medium | `Documentation` | Synchronize `README.md`, Bilingual Guides & CLI Help with Parameterless `calculate` & New Exports | `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/cli.py` |
| **DES-01** | `P3` Low | `Design` | Align Interactive HTML Dashboard with 4-Way Modality Progression & Streamline Template Logic | `src/presentation/html_report.py` |

---

## 🚀 Features

_No pending tasks. New feature proposals are intentionally deferred in favor of simplicity, domain accuracy, data ingestion reliability, and performance ("do less, but do better")._

## 🏗️ Architecture

### ARCH-01 (`P1` High): Domain & Ingestion Accuracy: Multi-Year Scaling, Primary Reconciliation, DST & Doctor Audit
- **Goal:** Guarantee strict mathematical, physical, and regulatory accuracy across multi-year datasets, behind-the-meter primary CUPS reconciliation, 25-hour autumn DST transitions, and `DataDoctor` pre-flight diagnostics.
- **Target Components:** `src/optimization/engine.py`, `src/curation/curator.py`, `src/ingestion/consumption.py`, `src/ingestion/generation.py`, `src/ingestion/doctor.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Multi-Year Modality Scaling & Fortnight Completeness:** In `DistributionOptimizer.optimize_dataset()` and `evaluate_hourly_self_consumption()`, scale `current_self_consumed_kwh` (physical no-share baseline) and `hourly_share_self_consumed_kwh` (Orden TED/1247/2021) using the exact same per-calendar-month $1/k_m$ multi-year pooling and completeness filtering applied in `_evaluate_calendar_months()`. In `_evaluate_calendar_fortnights()`, validate half-month completeness ($\ge 90\%$ of expected hours in the fortnight when `require_full_month=True`). Guarantee the domain invariant $0 \le \text{Current SC} \le \text{Monthly SC} \le \text{Fortnight SC} \le \text{Hourly SC} \le G_{\text{total}}$.
  2. **Primary Self-Consumption Bounding:** In `DataCurator.curate()`, bound hourly `self_consumption` on the primary CUPS by $\min(\text{generation}, \text{final\_cons})$ so physical behind-the-meter self-consumption never exceeds hourly solar generation or demand.
  3. **Autumn DST Energy Conservation:** In `DatadisConsumptionLoader` (`src/ingestion/consumption.py`) and `HuaweiGenerationLoader` (`src/ingestion/generation.py`), preserve the full 25 hours of energy during the October autumn DST transition (summing the repeated `02:00:00` / `02:00:00 DST` transition hour energy instead of dropping the first hour via `drop_duplicates` or discarding load via `max`), ensuring daily kWh totals match fiscal meters.
  4. **Accurate `DataDoctor` Pre-Flight Diagnostics:** In `DataDoctor.diagnose()` (`src/ingestion/doctor.py`), filter consumption series to the active CUPS in `cups.json` (reporting any unconfigured CUPS in a diagnostic note), count raw duplicate timestamps before deduplication so `duplicate_records` is accurately reported, and handle empty input directories cleanly without uncaught `IngestionError`.

### ARCH-02 (`P1` High): Performance Vectorization: Curation Pipeline, 2D Rounding, Solver Baselines & Excel Export
- **Goal:** Eliminate tens of thousands of Python loop iterations and redundant LP/heuristic solves across time-series curation, hourly share optimization, solar efficiency calculation, and styled Excel generation.
- **Target Components:** `src/curation/curator.py`, `src/curation/models.py`, `src/optimization/engine.py`, `src/optimization/efficiency.py`, `src/presentation/export.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Vectorized Curation & DataFrame Construction:** Replace the nested Python loop (`for ts in aligned.data.index` with `aligned.data.loc[ts, ...]`) in `DataCurator.curate()` and per-record `extract_temporal_features()` calls in `CuratedDataset.to_dataframe()` with vectorized Pandas/NumPy operations.
  2. **Vectorized 2D Hare-Niemeyer Rounding & Solar Efficiency:** Vectorize `DistributionOptimizer._round_betas()` and `calculate_solar_efficiency()` to operate on 2D/1D NumPy arrays across all $T$ timestamps simultaneously in `compute_hourly_optimization()` and `evaluate_hourly_self_consumption()`.
  3. **On-Demand Baseline Evaluation:** Default `include_baselines=False` in `CalculationService.execute()` so `esd calculate` does not run 24 extra monthly solves, 48 extra fortnight solves, and 2 extra full-year hourly evaluations for unused `consumption_share` and `equal` baselines unless explicitly requested.
  4. **Fast Openpyxl Styling:** Optimize `ReportExporter._export_styled_dataframe_excel()` to write DataFrame rows directly without `df_out.to_dict(orient="records")` and skip redundant per-cell `ws.cell()` styling on default white-background rows.

## 🔗 Cohesion

### COH-01 (`P2` Medium): Unify `cups.json` Configuration, Primary Supply Point & Coordinate Resolution
- **Goal:** Eliminate duplicated `cups.json` loading, primary CUPS discovery, and geographical coordinate fallback chains scattered across curation, ingestion, services, optimization, and HTML reporting.
- **Target Components:** `src/curation/curator.py`, `src/services/weather_service.py`, `src/ingestion/doctor.py`, `src/optimization/engine.py`, `src/presentation/html_report.py`.
- **Acceptance Criteria:**
  1. Ensure `AlignedDataset` and `OptimizationResult` always carry pre-resolved `primary_cups` and `cups_uses` from `cups.json`, removing fallback `DataCurator().load_cups_config()` calls and brittle use-name keyword heuristics (`["aerotermia", "principal", ...]`) from `DistributionOptimizer` and `html_report.py`.
  2. Consolidate coordinate resolution (`DataCurator.get_default_location()` and `WeatherService.resolve_coordinates()`) into a single shared resolution helper following the deterministic priority order: explicit CLI coordinates $\rightarrow$ primary CUPS in `cups.json` $\rightarrow$ participating CUPS in `cups.json` $\rightarrow$ persistent `AppConfig` (isolated from custom test directories).

### COH-02 (`P2` Medium): Centralize Ingestion & Curation CSV Reader, Delimiter Sniffing & Numeric Normalization
- **Goal:** Unify CSV delimiter/decimal auto-detection and comma-decimal string cleaning into shared helpers across ingestion, curation, and reporting.
- **Target Components:** `src/curation/curator.py`, `src/curation/models.py`, `src/ingestion/consumption.py`, `src/ingestion/generation.py`, `src/presentation/html_report.py`.
- **Acceptance Criteria:**
  1. Extract a single reusable CSV reader helper for curated datasets (`load_generation_dataset`, `load_consumption_dataset`, `load_aligned_dataset`) that encapsulates header delimiter sniffing (`;` vs `,`), decimal character selection, and `CurationError` wrapping.
  2. Expose and reuse `clean_numeric_series()` across `dataframe_to_aligned_dataset()`, `HuaweiGenerationLoader`, `DatadisConsumptionLoader`, and `html_report.py` instead of repeating inline `.astype(str).str.replace(",", ".")` chains.

## 🛡️ Security

### SEC-01 (`P2` Medium): Harden Formula Injection Sanitization & Streamline Git History Privacy Audit
- **Goal:** Ensure spreadsheet formula sanitization protects all string columns (including leading-whitespace payloads and lite matrix exports) and optimize `scan_git_history()` to execute in a single streamed `git log` pass.
- **Target Components:** `src/presentation/export.py`, `src/security.py`, `tests/test_security.py`.
- **Acceptance Criteria:**
  1. Update `sanitize_formula_injection()` in `src/presentation/export.py` to detect dangerous spreadsheet prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) even after leading whitespace (`value.lstrip().startswith(...)`) and apply it consistently across all string columns in CSV and Excel exports.
  2. Refactor `scan_git_history()` in `src/security.py` to replace the per-commit `git log -1` and `git show` subprocess loop ($2 \times N_{\text{commits}}$ processes) with a single `git log --all --format=... -p` stream parser, maintaining 100% detection parity in `tests/test_security.py` while cutting execution time by >90%.

## 📚 Documentation

### DOC-01 (`P2` Medium): Synchronize `README.md`, Bilingual Guides & CLI Help with Parameterless `calculate` & New Exports
- **Goal:** Align `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, and CLI help views with the simplified parameterless `esd calculate` workflow, the 6 exported `.output/` deliverables, and the expanded `esd cleanup` command.
- **Target Components:** `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/presentation/views/common.py`.
- **Acceptance Criteria:**
  1. Update `README.md` and `render_help()` in `src/presentation/views/common.py` to remove obsolete `esd calculate` flags (`--strategy`, `--year`, `--month`, `--view`, `--hourly`, `--format`, `--min-share`, `--max-share`), document the 6 `.output/` deliverables (including `*_esd_monthly_shares_lite.csv`, `*_esd_fortnight_shares.csv`, and `*_esd_fortnight_shares_lite.csv`), and reflect that `esd cleanup` cleans `.output`, `.curated`, and `.input/weather`.
  2. Document the non-destructive primary CUPS reconciliation formula (`max(datadis, inverter)`), autumn DST energy conservation, and multi-year $1/k_m$ calendar scaling in both `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md`.

## 🧹 Simplicity

### SIMP-01 (`P1` High): Prune Dead Calculation Options, Unreferenced Views, Legacy Fallbacks & Unused Domain Models
- **Goal:** Remove dead domain classes, unreferenced terminal views, obsolete `CalculationRequest` fields, legacy `curated.csv` fallbacks, and redundant attributes in curation models.
- **Target Components:** `src/domain/models.py`, `src/domain/__init__.py`, `src/curation/models.py`, `src/curation/curator.py`, `src/services/calculation_service.py`, `src/presentation/views/matrix.py`, `src/presentation/views/trajectory.py`, `src/presentation/views/__init__.py`.
- **Acceptance Criteria:**
  1. Remove unused `ShareAllocation` and `EnergyBalance` classes from `src/domain/models.py` and `src/domain/__init__.py`.
  2. Remove unreferenced terminal table renderers (`render_monthly_coefficients_table`, `render_hourly_profile_table`, `render_strategy_comparison_table`) and dead sparkline helpers (`_coverage_sparkline`, `SPARK_BLOCKS`) along with their orphaned exports in `src/presentation/views/`.
  3. Simplify `CalculationRequest` and `CalculationService.execute()` by removing obsolete fields (`force_curate`, `is_custom_input`, `is_custom_curated`, `year`, `month`, `export_format`, `min_share`, `max_share`) and legacy `curated.csv` fallback checks in `DataCurator.load_aligned_dataset()` and `CalculationService.execute()`.
  4. Simplify `CuratedHourRecord` and `CuratedCupsReading` by removing unused attributes (`date`, `hour`, `solar_surplus`, `net_grid_demand`), eliminating duplicated `self_consumption`, `exported_energy`, and `imported_energy` storage across parent and child records, and deleting unused `.to_dict()` / `.to_json()` methods and aliases (`CupsConfig`, `SolarGenerationLoader`).

### SIMP-02 (`P1` High): Prune Orphaned Localization Keys & Simplify Translation Catalog Builder
- **Goal:** Delete ~55 orphaned translation keys from `src/i18n.py` and remove unnecessary prefix-stripping key multiplication in `_build_translation_catalog()`.
- **Target Components:** `src/i18n.py`, `tests/`.
- **Acceptance Criteria:**
  1. Remove all unused translation keys (including obsolete `opt_*` CLI option strings, unreferenced view titles/columns, and dead status messages) from both `"en"` and `"es"` dictionaries in `STRUCTURED_TRANSLATIONS`.
  2. Simplify `_build_translation_catalog()` to index only `f"{ns}.{key}"` and flat `key`, removing the unused prefix-stripping loop.
  3. Verify 100% EN/ES key and format-placeholder parity in `tests/`.

## 🎨 Design

### DES-01 (`P3` Low): Align Interactive HTML Dashboard with 4-Way Modality Progression & Streamline Template Logic
- **Goal:** Bring the interactive HTML dashboard into 100% parity with the 4-way self-consumption progression (Current, Monthly RD 244/2019, Fortnight, and Dynamic Hourly Orden TED/1247/2021) while simplifying `src/presentation/html_report.py`.
- **Target Components:** `src/presentation/html_report.py`, `tests/test_export.py`.
- **Acceptance Criteria:**
  1. Refactor `_calculate_hourly_prevision()` in `src/presentation/html_report.py` to read `current_self_consumed_kwh`, `monthly_share_self_consumed_kwh`, `fortnight_share_self_consumed_kwh`, and `hourly_share_self_consumed_kwh` directly from `OptimizationResult` instead of re-parsing formatted percentage strings (`share_pct`, `estimated_share_pct`) from `time_series_df`, and display the 4-way progression in the HTML report.
  2. Consolidate scattered `if is_es else` string literals in `generate_interactive_html_report()` into a single structured bilingual dictionary.
