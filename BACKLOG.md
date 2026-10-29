# 📋 Project Improvement Backlog

This document tracks prioritized, actionable improvement tasks for **Electricity Share Distributor (`esd`)**, formatted for autonomous AI agents to execute cleanly.

> [!IMPORTANT]
> **Core Priority Hierarchy & Performance Invariant:** Simplicity, data accuracy, security, architecture, and cohesion must **always** take precedence over introducing new features ("do less, but do better"). Performance—low algorithmic overhead, vectorized data processing, fast linear programming solves, and a lean memory and I/O footprint—is an essential invariant across all modules. Stability, mathematical accuracy, security, and computational efficiency must never be compromised for feature expansion.

## 📐 Backlog Rules & Conventions

1. **Agent-Ready Descriptions:** Every task must have a brief, concise, and self-contained specification detailing the goal, target components, and acceptance criteria so an independent agent can pick it up immediately.
2. **Categories:** Tasks are organized into seven single-word categories:
   - **`Features`** — Functional capabilities and user-facing enhancements.
   - **`Architecture`** — Structural improvements, mathematical/data accuracy, performance, and test coverage.
   - **`Cohesion`** — Codebase unification, pattern alignment, and shared abstractions.
   - **`Security`** — Privacy enforcement, vulnerability hardening, and keeping dependencies fully updated.
   - **`Documentation`** — Guides (`docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`), CLI help strings, and developer docs.
   - **`Simplicity`** — Dead code removal, complexity reduction, and waste elimination.
   - **`Design`** — UX/UI ergonomics, visual polish across console outputs, reports, and documentation, adhering to best practices with modern, fresh, and cohesive aesthetics.
3. **Capacity Limit:** Maximum **2 tasks per category** at any time (fewer or zero is acceptable; never exceed 2).
4. **Prioritization:** Tasks are explicitly prioritized (e.g., `P1` High, `P2` Medium, `P3` Low) both in the summary table and within their category.
5. **Core Priority & Performance Rule:** Simplicity, data accuracy, security, architecture, and cohesion must always take precedence over new features. Feature proposals should be deferred whenever structural, accuracy, security, performance, or simplification improvements are pending. High computational performance (e.g., efficient vectorization, fast linear programming solves, minimal I/O overhead) must be preserved across all implementations.
6. **Zero Completed History:** When a task is completed, it must be **removed** from both the summary table and its category section in `BACKLOG.md`.

---

## 📊 Prioritized Task Overview

| ID | Priority | Category | Title | Target Components |
| :--- | :---: | :--- | :--- | :--- |
| **ARCH-01** | `P1` High | `Architecture` | Fix Multi-Year Energy Normalization, Primary CUPS Reconciliation & DST Accuracy | `src/optimization/engine.py`, `src/curation/curator.py`, `src/ingestion/consumption.py` |
| **ARCH-02** | `P1` High | `Architecture` | Vectorize Curation Pipeline, 2D Hare-Niemeyer Rounding & Excel Export | `src/curation/`, `src/optimization/`, `src/presentation/export.py` |
| **SIMP-01** | `P1` High | `Simplicity` | Flatten `CuratedDataset` Records & Eliminate Dead Domain / Legacy Code | `src/domain/models.py`, `src/curation/`, `src/presentation/views/trajectory.py` |
| **SIMP-02** | `P1` High | `Simplicity` | Prune Orphaned Localization Keys & Simplify Translation Catalog Builder | `src/i18n.py`, `tests/` |
| **COH-01** | `P2` Medium | `Cohesion` | Unify CUPS Configuration, Primary Point & Coordinate Resolution | `src/curation/curator.py`, `src/services/weather_service.py`, `src/optimization/engine.py`, `src/presentation/html_report.py` |
| **COH-02** | `P2` Medium | `Cohesion` | Centralize Curated CSV Reader & Numeric Decimal Normalization | `src/curation/`, `src/ingestion/`, `src/presentation/html_report.py` |
| **SEC-01** | `P2` Medium | `Security` | Harden Formula Injection Sanitization & Batch Git History Privacy Audit | `src/presentation/export.py`, `src/security.py` |
| **DOC-01** | `P2` Medium | `Documentation` | Synchronize Bilingual Guides & CLI Help with Streamlined Pipeline & Accuracy Rules | `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/cli.py` |
| **DES-01** | `P3` Low | `Design` | Streamline HTML Report Prevision Logic & Bilingual Template Dictionary | `src/presentation/html_report.py` |

---

## 🚀 Features

_No pending tasks. New feature proposals are intentionally deferred in favor of simplicity, data accuracy, and performance ("do less, but do better")._

## 🏗️ Architecture

### ARCH-01 (`P1` High): Fix Multi-Year Energy Normalization, Primary CUPS Reconciliation & DST Accuracy
- **Goal:** Guarantee strict mathematical and physical data accuracy across multi-year datasets, behind-the-meter primary CUPS reconciliation, and 25-hour autumn DST transitions.
- **Target Components:** `src/optimization/engine.py`, `src/curation/curator.py`, `src/ingestion/consumption.py`, `src/presentation/html_report.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Multi-Year Modality Consistency:** In `DistributionOptimizer.optimize_dataset()` and `evaluate_hourly_self_consumption()`, compute `current_self_consumed_kwh` (physical no-share baseline) and `hourly_share_self_consumed_kwh` (Orden TED/1247/2021) using the exact same per-calendar-month $1/k_m$ multi-year scaling and `require_full_month` filtering applied in `_evaluate_calendar_months()`. Guarantee the physical invariant $0 \le \text{current\_sc} \le \text{monthly\_sc} \le \text{hourly\_sc} \le \text{total\_generation\_kwh}$ without artificial post-hoc clamping in `html_report.py`.
  2. **Non-Destructive Primary CUPS Reconciliation:** In `DataCurator.curate()`, ensure primary CUPS behind-the-meter reconciliation never overwrites a higher metered DATADIS grid reading with a lower or zero inverter reading (`final_cons = max(datadis_cons, hw_cons_val)`), and bound hourly `self_consumption` by $\min(\text{generation}, \text{final\_cons})$.
  3. **Autumn DST Energy Preservation:** In `DatadisConsumptionLoader.parse_file()`, prevent 25-hour autumn DST days from mapping two distinct rows to identical `01:00:00` timestamps that get silently dropped by `drop_duplicates`, preserving exact daily kWh totals.
  4. Add unit tests covering multi-year modality scaling, non-destructive primary reconciliation when inverter consumption is zero/lower, and 25-hour autumn DST ingestion.

### ARCH-02 (`P1` High): Vectorize Curation Pipeline, 2D Hare-Niemeyer Rounding & Excel Export
- **Goal:** Eliminate tens of thousands of Python loop iterations across time-series curation, hourly share optimization, solar efficiency calculation, and styled Excel generation.
- **Target Components:** `src/curation/curator.py`, `src/curation/models.py`, `src/optimization/engine.py`, `src/optimization/efficiency.py`, `src/presentation/export.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Vectorized Curation & DataFrame Construction:** Replace the nested Python loop (`for ts in aligned.data.index` with `aligned.data.loc[ts, ...]`) in `DataCurator.curate()` and per-record `extract_temporal_features()` calls in `CuratedDataset.to_dataframe()` with vectorized Pandas/NumPy operations (`pd.to_datetime` `.dt` accessors and array operations).
  2. **Vectorized Hourly Optimization & Solar Efficiency:** Vectorize `DistributionOptimizer._round_betas()` and `calculate_solar_efficiency()` to operate on 2D/1D NumPy arrays across all $T$ timestamps simultaneously in `compute_hourly_optimization()` and `evaluate_hourly_self_consumption()`. Avoid recomputing identical hourly self-consumption between `OPTIMAL` and `CONSUMPTION_SHARE` strategies when evaluating baselines.
  3. **Fast Openpyxl Styling:** Optimize `ReportExporter._export_styled_dataframe_excel()` to avoid `df_out.to_dict(orient="records")` and redundant `ws.cell()` lookups on white-background rows across 70,000+ rows.
  4. Verify all existing unit and integration tests pass with identical numerical outputs and measurably faster execution.

## 🔗 Cohesion

### COH-01 (`P2` Medium): Unify CUPS Configuration, Primary Point & Coordinate Resolution
- **Goal:** Eliminate duplicated `load_cups_config()`, primary CUPS discovery, and geographical coordinate fallback chains scattered across curation, services, optimization, and HTML reporting.
- **Target Components:** `src/curation/curator.py`, `src/services/weather_service.py`, `src/optimization/engine.py`, `src/presentation/html_report.py`, `src/ingestion/weather.py`.
- **Acceptance Criteria:**
  1. Ensure `AlignedDataset` and `OptimizationResult` always carry pre-resolved `primary_cups` and `cups_uses`, removing fallback `DataCurator().load_cups_config()` calls and brittle use-name keyword heuristics (`["aerotermia", "principal", ...]`) from `DistributionOptimizer` and `html_report.py`.
  2. Consolidate coordinate resolution (`DataCurator.get_default_location()` and `WeatherService.resolve_coordinates()`) into a single shared resolution helper following the deterministic priority order: explicit CLI coordinates $\rightarrow$ primary CUPS in `cups.json` $\rightarrow$ participating CUPS in `cups.json` $\rightarrow$ persistent `AppConfig`.

### COH-02 (`P2` Medium): Centralize Curated CSV Reader & Numeric Decimal Normalization
- **Goal:** Unify CSV delimiter/decimal auto-detection and comma-decimal string cleaning into shared helpers across ingestion, curation, and reporting.
- **Target Components:** `src/curation/curator.py`, `src/curation/models.py`, `src/ingestion/consumption.py`, `src/ingestion/generation.py`, `src/presentation/html_report.py`.
- **Acceptance Criteria:**
  1. Extract a single reusable CSV reader helper for curated datasets (`load_generation_dataset`, `load_consumption_dataset`, `load_aligned_dataset`) that encapsulates header sniffing (`;` vs `,`), decimal character selection, and error wrapping in `CurationError`.
  2. Reuse `clean_numeric_series()` across `dataframe_to_aligned_dataset()`, `HuaweiGenerationLoader`, `DatadisConsumptionLoader`, and `html_report.py` instead of repeating inline `.astype(str).str.replace(",", ".")` chains.

## 🛡️ Security

### SEC-01 (`P2` Medium): Harden Formula Injection Sanitization & Batch Git History Privacy Audit
- **Goal:** Ensure spreadsheet formula sanitization protects all string columns (including leading-whitespace payloads) and optimize `scan_git_history()` to execute in a single streamed `git log` pass.
- **Target Components:** `src/presentation/export.py`, `src/security.py`, `tests/test_security.py`.
- **Acceptance Criteria:**
  1. Update `sanitize_formula_injection()` in `src/presentation/export.py` to also detect risky prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) after leading whitespace (`value.lstrip().startswith(...)`) and apply it consistently across all string columns in CSV and Excel exports.
  2. Refactor `scan_git_history()` in `src/security.py` to replace the per-commit `git log -1` and `git show` subprocess loop ($2 \times N_{\text{commits}}$ processes) with a single `git log --all --format=... -p` stream parser, maintaining 100% detection parity in `tests/test_security.py` while cutting execution time by >90%.

## 📚 Documentation

### DOC-01 (`P2` Medium): Synchronize Bilingual Guides & CLI Help with Streamlined Pipeline & Accuracy Rules
- **Goal:** Ensure `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, and `src/cli.py` accurately reflect the simplified 3-stage curation pipeline, physical reconciliation safeguards, and multi-year normalization rules.
- **Target Components:** `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/cli.py`.
- **Acceptance Criteria:**
  1. Remove any remaining mentions of legacy `curated.csv` / `curated.xlsx` filenames or deprecated export formats across CLI option help texts and documentation guides.
  2. Document the non-destructive primary CUPS reconciliation formula (`max(datadis, inverter)`) and multi-year $1/k_m$ calendar scaling in both `docs/GUIDE_EN.md` and `docs/GUIDE_ES.md`.

## 🧹 Simplicity

### SIMP-01 (`P1` High): Flatten `CuratedDataset` Records & Eliminate Dead Domain / Legacy Code
- **Goal:** Remove unused domain classes, dead JSON/dict serialization methods, legacy `curated.csv` fallbacks, and redundant fields in curation models.
- **Target Components:** `src/domain/models.py`, `src/domain/__init__.py`, `src/curation/models.py`, `src/curation/curator.py`, `src/ingestion/generation.py`, `src/presentation/views/trajectory.py`, `src/services/calculation_service.py`.
- **Acceptance Criteria:**
  1. Remove unused `ShareAllocation` and `EnergyBalance` classes from `src/domain/models.py` and `src/domain/__init__.py`.
  2. Remove unused serialization methods (`CuratedDataset.to_json()`, `CuratedHourRecord.to_dict()`, `CuratedCupsReading.to_dict()`, `GenerationRecord.to_dict()`, `ConsumptionRecord.to_dict()`), redundant aliases (`CupsConfig`, `SolarGenerationLoader`), and dead sparkline helpers (`_coverage_sparkline`, `SPARK_BLOCKS`) in `src/presentation/views/trajectory.py`.
  3. Remove legacy `curated.csv` fallback checks in `DataCurator.load_aligned_dataset()` and `CalculationService.execute()`.
  4. Simplify `CuratedHourRecord` and `CuratedCupsReading` by removing unused attributes (`date`, `hour`, `solar_surplus`, `net_grid_demand`) and eliminating duplicated `self_consumption`, `exported_energy`, and `imported_energy` storage across parent and child records.

### SIMP-02 (`P1` High): Prune Orphaned Localization Keys & Simplify Translation Catalog Builder
- **Goal:** Delete 45 orphaned translation keys from `src/i18n.py` and remove unnecessary prefix-stripping key multiplication in `_build_translation_catalog()`.
- **Target Components:** `src/i18n.py`, `tests/`.
- **Acceptance Criteria:**
  1. Remove all ~45 unused translation keys (including `opt_*`, `cleaning_output`, `init_already`, `version_banner`, `status_curating_auto`, `status_ingesting`, `status_loading_curated`, `status_optimizing`, `lbl_curated_files`, `err_weather_download`, `weather_file_saved`, `col_consumption`, `col_generation`, `col_grid`, `col_solar_alloc`, `col_solar_demand`, `lbl_collective_cov_rate`, `lbl_collective_sc_rate`) from both `"en"` and `"es"` dictionaries in `STRUCTURED_TRANSLATIONS`.
  2. Simplify `_build_translation_catalog()` to index only `f"{ns}.{key}"` and flat `key`, removing the unused prefix-stripping loop.
  3. Verify 100% EN/ES key and format-placeholder parity in `tests/`.

## 🎨 Design

### DES-01 (`P3` Low): Streamline HTML Report Prevision Logic & Bilingual Template Dictionary
- **Goal:** Reduce complexity and size in `src/presentation/html_report.py` by removing redundant DataFrame string re-parsing and consolidating scattered inline bilingual conditionals.
- **Target Components:** `src/presentation/html_report.py`, `tests/`.
- **Acceptance Criteria:**
  1. Simplify `_calculate_hourly_prevision()` in `src/presentation/html_report.py` to read `current_self_consumed_kwh`, `monthly_share_self_consumed_kwh`, and `hourly_share_self_consumed_kwh` directly from `OptimizationResult` instead of re-parsing formatted percentage strings (`share_pct`, `estimated_share_pct`) out of `time_series_df`.
  2. Consolidate scattered `if is_es else` string literals in `generate_interactive_html_report()` into a single structured bilingual dictionary, keeping the interactive HTML output visually and functionally identical.
