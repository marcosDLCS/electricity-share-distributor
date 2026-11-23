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
| **COH-02** | `P1` High | `Cohesion` | Unify DATADIS Ingestion: Recursive Annualized Discovery, Per-File Validation & Shared CSV/Numeric Helpers | `src/ingestion/consumption.py`, `src/curation/`, `src/presentation/html_report.py` |
| **FEAT-01** | `P1` High | `Features` | Migrate `datadis-analyzer` Community Consumption Summary & Fair-Share Analytics (`esd summary`) | `src/analytics/`, `src/services/`, `src/cli.py`, `src/presentation/`, `src/i18n.py` |
| **FEAT-02** | `P1` High | `Features` | Migrate `datadis-analyzer` Multi-Year Apples-to-Apples Comparison & Visual Charts (`esd compare`) | `src/analytics/`, `src/services/`, `src/cli.py`, `src/presentation/`, `src/i18n.py` |
| **ARCH-01** | `P1` High | `Architecture` | Domain & Ingestion Accuracy: Multi-Year Scaling, Primary Reconciliation, DST & Consumption-Only Doctor Audit | `src/optimization/engine.py`, `src/curation/curator.py`, `src/ingestion/` |
| **SIMP-01** | `P1` High | `Simplicity` | Prune Dead Calculation Options, Unreferenced Views, Legacy Fallbacks & Unused Domain Models | `src/domain/`, `src/curation/`, `src/services/`, `src/presentation/views/` |
| **ARCH-02** | `P2` Medium | `Architecture` | Performance Vectorization: Curation Pipeline, 2D Rounding, Solver Baselines & Excel Export | `src/curation/`, `src/optimization/`, `src/presentation/export.py` |
| **SIMP-02** | `P2` Medium | `Simplicity` | Prune Orphaned Localization Keys & Simplify Translation Catalog Builder | `src/i18n.py`, `tests/` |
| **COH-01** | `P2` Medium | `Cohesion` | Unify `cups.json` Configuration, Primary Supply Point, Coordinate Resolution & Recursive Output Cleanup | `src/curation/curator.py`, `src/services/weather_service.py`, `src/cli.py`, `src/optimization/engine.py`, `src/presentation/html_report.py` |
| **SEC-01** | `P2` Medium | `Security` | Harden Formula Injection Sanitization & Streamline Git History Privacy Audit | `src/presentation/export.py`, `src/security.py` |
| **SEC-02** | `P2` Medium | `Security` | Migrate `datadis-analyzer` Credential, Secret & Private Coordinate Leak Scanners | `src/security.py`, `tests/test_security.py`, `tests/test_weather.py` |
| **DOC-01** | `P2` Medium | `Documentation` | Synchronize `README.md`, Bilingual Guides & CLI Help with Parameterless `calculate` & New Exports | `README.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/presentation/views/common.py` |
| **DOC-02** | `P2` Medium | `Documentation` | Unified Platform Documentation & `datadis-analyzer` Migration / Retirement Guide | `README.md`, `AGENTS.md`, `docs/GUIDE_EN.md`, `docs/GUIDE_ES.md`, `src/presentation/views/common.py` |
| **DES-01** | `P3` Low | `Design` | Align Interactive HTML Dashboard with 4-Way Modality Progression & Streamline Template Logic | `src/presentation/html_report.py` |
| **DES-02** | `P3` Low | `Design` | Cohesive Visual Polish for Consumption Summary & Multi-Year Comparison Views (80-Col UI & Responsive SVG/HTML) | `src/presentation/views/`, `src/presentation/charts.py`, `src/presentation/console.py` |

---

## 🚀 Features

### FEAT-01 (`P1` High): Migrate `datadis-analyzer` Community Consumption Summary & Fair-Share Analytics (`esd summary`)
- **Goal:** Port `datadis-analyzer`'s `da summary` consumption-only analytics workflow into `esd` so residential communities can audit and distribute pure electricity consumption across CUPS without requiring solar PV generation files.
- **Target Components:** `src/analytics/`, `src/services/summary_service.py`, `src/cli.py`, `src/presentation/views/`, `src/presentation/export.py`, `src/i18n.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Typed Models & Vectorized Aggregator:** Implement typed consumption analytics dataclasses (`CupsConsumptionShare`, `MonthlyConsumptionSummary`, `AnnualConsumptionSummary`, `CommunityConsumptionSummary`) and vectorized `ConsumptionAggregator.aggregate_community()` + `build_monthly_pivot()` (no `.iterrows()`), guaranteeing the 100.00% relative share invariant ($\text{Share}_i = \frac{\text{kWh}_i}{\sum_j \text{kWh}_j} \times 100$, defaulting to `0.0%` when total consumption is zero) and peak/lowest month detection.
  2. **Consumption-Only Service & CLI Command:** Add `SummaryService` and the `esd summary` CLI command operating on DATADIS consumption CSVs alone (no PV generation Excel required), supporting `--consumption-dir`/`-c`, `--output-dir`/`-o`, `--year`/`-y`, `--view`/`-v` (`all`, `annual`, `monthly`), `--cups` (single-CUPS monthly trajectory), `--cups-file`/`-C`, and `--lang`/`-l`; enriching CUPS with `use` labels from `cups.json` when present while working cleanly without `cups.json`.
  3. **80-Column Rich Terminal Views:** Render per-file validation warnings (when skipped files exist), Executive Community Overview card, ranked Annual & Monthly CUPS share tables reusing `make_percentage_bar()` from `src/presentation/console.py` with `no_wrap=True` on numeric/CUPS columns, consumer badges (`★` dominant `>30%` rank #1, `(0)` inactive `<1 kWh`), single-CUPS trajectory table, and Key Insights panel (dominant consumer `>50%`, inactive meters, seasonality).
  4. **Markdown Export, Localization & Tests:** Add `ReportExporter.export_consumption_summary_markdown()` writing timestamped reports (`YYYYMMDD_HHMMSS_community_summary.md`, `*_summary_<year>.md`, or `*_summary_<cups>.md`) with ASCII share bars and CalVer version into `.output/`, complete EN/ES localization keys in `src/i18n.py`, and automated unit/CLI tests in `tests/` using synthetic CUPS (`ES00210000000000XXYY`).

### FEAT-02 (`P1` High): Migrate `datadis-analyzer` Multi-Year Apples-to-Apples Comparison & Visual Charts (`esd compare`)
- **Goal:** Port `datadis-analyzer`'s `da compare` multi-year comparison engine, calendar completeness heuristic, and visual charts into `esd` using lightweight zero-dependency SVG output.
- **Target Components:** `src/analytics/`, `src/services/comparison_service.py`, `src/cli.py`, `src/presentation/views/comparison.py`, `src/presentation/charts.py`, `src/presentation/export.py`, `src/i18n.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Comparative Models & Calendar Completeness Heuristic:** Implement comparative domain models (`MonthComparison`, `CupsComparison`, `ComparisonSummary`) and `ConsumptionAggregator.compare_years(df, target_years=None)` using `calendar.monthrange(year, month)[1]` (leap-year aware, statuses `complete` / `incomplete` / `no_data`), enforcing the apples-to-apples invariant (deltas $\Delta\text{kWh}$, $\%\Delta$, peak increase/decrease months, and per-CUPS shifts computed strictly over months complete in all compared years) and raising `EsdError` when fewer than 2 distinct years exist.
  2. **Comparison Service & CLI Command:** Add `ComparisonService` and `esd compare` supporting `--consumption-dir`/`-c`, `--years`/`-y` (repeatable `-y 2024 -y 2025` and comma-separated `--years 2024,2025`, defaulting to all available years), `--output-dir`/`-o`, `--cups-file`/`-C`, `--charts/--no-charts` (default `True`), and `--lang`/`-l`.
  3. **80-Column Comparative Views:** Render validation warnings, Executive Comparison Overview card (comparable period, raw vs comparable totals, net saving/increase, peak decrease/increase months, top saving/increasing CUPS, excluded-months note), Month-by-Month Comparative Table (`*` on incomplete months, color-coded `▼`/`▲` variations), and CUPS-Level Shift Table sorted by savings (enriched with `use` labels from `cups.json` when available).
  4. **Zero-Dependency SVG Charts, Markdown Export & Tests:** Implement a lightweight SVG chart module (`src/presentation/charts.py` with no `matplotlib` dependency) generating grouped monthly bar charts into `.output/charts/` (`community_monthly_<years>.svg` and `cups_<CUPS>_<years>.svg`), add `ReportExporter.export_comparison_markdown()` writing timestamped `.output/YYYYMMDD_HHMMSS_comparison_<years>.md` with embedded chart image links, plus EN/ES localization and unit/CLI tests in `tests/`.

## 🏗️ Architecture

### ARCH-01 (`P1` High): Domain & Ingestion Accuracy: Multi-Year Scaling, Primary Reconciliation, DST & Consumption-Only Doctor Audit
- **Goal:** Guarantee strict mathematical, physical, and regulatory accuracy across multi-year datasets, behind-the-meter primary CUPS reconciliation, 25-hour autumn DST transitions, and `DataDoctor` pre-flight diagnostics (including consumption-only workspaces).
- **Target Components:** `src/optimization/engine.py`, `src/curation/curator.py`, `src/ingestion/consumption.py`, `src/ingestion/generation.py`, `src/ingestion/doctor.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Multi-Year Modality Scaling & Fortnight Completeness:** In `DistributionOptimizer.optimize_dataset()` and `evaluate_hourly_self_consumption()`, scale `current_self_consumed_kwh` (physical no-share baseline) and `hourly_share_self_consumed_kwh` (Orden TED/1247/2021) using the exact same per-calendar-month $1/k_m$ multi-year pooling and completeness filtering applied in `_evaluate_calendar_months()`. In `_evaluate_calendar_fortnights()`, validate half-month completeness ($\ge 90\%$ of expected hours in the fortnight when `require_full_month=True`). Guarantee the domain invariant $0 \le \text{Current SC} \le \text{Monthly SC} \le \text{Fortnight SC} \le \text{Hourly SC} \le G_{\text{total}}$.
  2. **Primary Self-Consumption Bounding:** In `DataCurator.curate()`, bound hourly `self_consumption` on the primary CUPS by $\min(\text{generation}, \text{final\_cons})$ so physical behind-the-meter self-consumption never exceeds hourly solar generation or demand.
  3. **Autumn DST Energy Conservation:** In `DatadisConsumptionLoader` (`src/ingestion/consumption.py`) and `HuaweiGenerationLoader` (`src/ingestion/generation.py`), preserve the full 25 hours of energy during the October autumn DST transition (summing the repeated `02:00:00` / `02:00:00 DST` transition hour energy instead of dropping the first hour via `drop_duplicates` or discarding load via `max`), ensuring daily kWh totals match fiscal meters.
  4. **Accurate `DataDoctor` Pre-Flight Diagnostics:** In `DataDoctor.diagnose()` (`src/ingestion/doctor.py`), filter consumption series to the active CUPS in `cups.json` (reporting any unconfigured CUPS in a diagnostic note), count raw duplicate timestamps before deduplication so `duplicate_records` is accurately reported, handle empty input directories cleanly without uncaught `IngestionError`, and handle missing/empty generation directories gracefully so consumption diagnostics still run and report data health (setting `can_calculate=False` for PV optimization) for consumption-only `summary`/`compare` users.

### ARCH-02 (`P2` Medium): Performance Vectorization: Curation Pipeline, 2D Rounding, Solver Baselines & Excel Export
- **Goal:** Eliminate tens of thousands of Python loop iterations and redundant LP/heuristic solves across time-series curation, hourly share optimization, solar efficiency calculation, and styled Excel generation.
- **Target Components:** `src/curation/curator.py`, `src/curation/models.py`, `src/optimization/engine.py`, `src/optimization/efficiency.py`, `src/presentation/export.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Vectorized Curation & DataFrame Construction:** Replace the nested Python loop (`for ts in aligned.data.index` with `aligned.data.loc[ts, ...]`) in `DataCurator.curate()` and per-record `extract_temporal_features()` calls in `CuratedDataset.to_dataframe()` with vectorized Pandas/NumPy operations.
  2. **Vectorized 2D Hare-Niemeyer Rounding & Solar Efficiency:** Vectorize `DistributionOptimizer._round_betas()` and `calculate_solar_efficiency()` to operate on 2D/1D NumPy arrays across all $T$ timestamps simultaneously in `compute_hourly_optimization()` and `evaluate_hourly_self_consumption()`.
  3. **On-Demand Baseline Evaluation:** Default `include_baselines=False` in `CalculationService.execute()` so `esd calculate` does not run 24 extra monthly solves, 48 extra fortnight solves, and 2 extra full-year hourly evaluations for unused `consumption_share` and `equal` baselines unless explicitly requested.
  4. **Fast Openpyxl Styling:** Optimize `ReportExporter._export_styled_dataframe_excel()` to write DataFrame rows directly without `df_out.to_dict(orient="records")` and skip redundant per-cell `ws.cell()` styling on default white-background rows.

## 🔗 Cohesion

### COH-02 (`P1` High): Unify DATADIS Ingestion: Recursive Annualized Discovery, Per-File Validation & Shared CSV/Numeric Helpers
- **Goal:** Unify DATADIS ingestion across flat and annualized folder layouts, add resilient per-file validation for batch workflows, and centralize CSV delimiter/decimal sniffing and comma-decimal string cleaning into shared helpers across ingestion, curation, and reporting.
- **Target Components:** `src/ingestion/consumption.py`, `src/curation/curator.py`, `src/curation/models.py`, `src/ingestion/generation.py`, `src/presentation/html_report.py`, `tests/`.
- **Acceptance Criteria:**
  1. **Recursive Annualized Discovery & Header Normalization:** Update `DatadisConsumptionLoader.discover_files()` (`src/ingestion/consumption.py`) to recursively discover CSVs across both flat `.input/consumption/*.csv` and `datadis-analyzer`'s annualized `.input/consumption/<year>/*.csv` subdirectories (skipping hidden files/folders and supporting an optional `year` filter), and accept the `consumoKwh` header alias alongside `consumo_kWh`.
  2. **Per-File Validation & Graceful Skipping:** Introduce per-file `ValidationResult` checks (existence, non-zero size, encoding, delimiter, mandatory columns, `>=1` data row) so batch ingestion can gracefully skip malformed/empty CSVs and surface structured warnings to `summary`, `compare`, and `doctor` instead of crashing the entire run.
  3. **Shared Curated CSV Reader & Numeric Cleaner:** Extract a single reusable CSV reader helper for curated datasets (`load_generation_dataset`, `load_consumption_dataset`, `load_aligned_dataset`) encapsulating delimiter sniffing (`;` vs `,`), decimal character selection, and `CurationError` wrapping, and expose/reuse `clean_numeric_series()` across `dataframe_to_aligned_dataset()`, `HuaweiGenerationLoader`, `DatadisConsumptionLoader`, and `html_report.py`.

### COH-01 (`P2` Medium): Unify `cups.json` Configuration, Primary Supply Point, Coordinate Resolution & Recursive Output Cleanup
- **Goal:** Eliminate duplicated `cups.json` loading, primary CUPS discovery, geographical coordinate fallback chains, and non-recursive output cleanup logic across curation, services, CLI, optimization, and HTML reporting.
- **Target Components:** `src/curation/curator.py`, `src/services/weather_service.py`, `src/ingestion/doctor.py`, `src/optimization/engine.py`, `src/presentation/html_report.py`, `src/cli.py`.
- **Acceptance Criteria:**
  1. Ensure `AlignedDataset` and `OptimizationResult` always carry pre-resolved `primary_cups` and `cups_uses` from `cups.json`, removing fallback `DataCurator().load_cups_config()` calls and brittle use-name keyword heuristics (`["aerotermia", "principal", ...]`) from `DistributionOptimizer` and `html_report.py`.
  2. Consolidate coordinate resolution (`DataCurator.get_default_location()` and `WeatherService.resolve_coordinates()`) into a single shared resolution helper following the deterministic priority order: explicit CLI coordinates $\rightarrow$ primary CUPS in `cups.json` $\rightarrow$ participating CUPS in `cups.json` $\rightarrow$ persistent `AppConfig` (isolated from custom test directories).
  3. Refactor `cleanup_command()` in `src/cli.py` to reuse `clear_output_directory()` from `src/config.py` so nested subdirectories such as `.output/charts/` are removed cleanly, and add a hidden `clean` CLI alias matching `da clean`.

## 🛡️ Security

### SEC-01 (`P2` Medium): Harden Formula Injection Sanitization & Streamline Git History Privacy Audit
- **Goal:** Ensure spreadsheet formula sanitization protects all string columns (including leading-whitespace payloads and lite matrix exports) and optimize `scan_git_history()` to execute in a single streamed `git log` pass.
- **Target Components:** `src/presentation/export.py`, `src/security.py`, `tests/test_security.py`.
- **Acceptance Criteria:**
  1. Update `sanitize_formula_injection()` in `src/presentation/export.py` to detect dangerous spreadsheet prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) even after leading whitespace (`value.lstrip().startswith(...)`) and apply it consistently across all string columns in CSV and Excel exports.
  2. Refactor `scan_git_history()` in `src/security.py` to replace the per-commit `git log -1` and `git show` subprocess loop ($2 \times N_{\text{commits}}$ processes) with a single `git log --all --format=... -p` stream parser, maintaining 100% detection parity in `tests/test_security.py` while cutting execution time by >90%.

### SEC-02 (`P2` Medium): Migrate `datadis-analyzer` Credential, Secret & Private Coordinate Leak Scanners
- **Goal:** Bring `src/security.py` to full parity with `datadis-analyzer` by adding exposed-secret and private-coordinate detection while preserving `esd`'s synthetic weather test examples.
- **Target Components:** `src/security.py`, `tests/test_security.py`, `tests/test_weather.py`.
- **Acceptance Criteria:**
  1. Migrate `datadis-analyzer` credential and secret pattern scanners into `src/security.py` (PEM private keys, `Bearer` tokens, API/auth/secret token assignments, AWS `AKIA` keys, GitHub `gh[pousr]_` tokens, and Slack `xox` tokens) and integrate them across file, directory, staged, and git-history scans.
  2. Migrate private geographic coordinate leak detection into `src/security.py`: dynamically discover private coordinates from local `.input/cups/cups.json` and `.esd_config.json`, detect cardinal/decimal coordinate pairs across repository files, define an explicit synthetic city-center allowlist for approved documentation/test fixtures, and replace any non-synthetic high-precision coordinate fixtures in tests or docs.
  3. Support single-path targeted auditing via `--scan <path>` in `src/security.py` CLI and add comprehensive unit tests in `tests/test_security.py`.

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

### SIMP-01 (`P1` High): Prune Dead Calculation Options, Unreferenced Views, Legacy Fallbacks & Unused Domain Models
- **Goal:** Remove dead domain classes, unreferenced terminal views, obsolete `CalculationRequest` fields, legacy `curated.csv` fallbacks, and redundant attributes in curation models.
- **Target Components:** `src/domain/models.py`, `src/domain/__init__.py`, `src/curation/models.py`, `src/curation/curator.py`, `src/services/calculation_service.py`, `src/presentation/views/matrix.py`, `src/presentation/views/trajectory.py`, `src/presentation/views/__init__.py`.
- **Acceptance Criteria:**
  1. Remove unused `ShareAllocation` and `EnergyBalance` classes from `src/domain/models.py` and `src/domain/__init__.py`.
  2. Remove unreferenced terminal table renderers (`render_monthly_coefficients_table`, `render_hourly_profile_table`, `render_strategy_comparison_table`) and dead sparkline helpers (`_coverage_sparkline`, `SPARK_BLOCKS`) along with their orphaned exports in `src/presentation/views/`.
  3. Simplify `CalculationRequest` and `CalculationService.execute()` by removing obsolete fields (`force_curate`, `is_custom_input`, `is_custom_curated`, `year`, `month`, `export_format`, `min_share`, `max_share`) and legacy `curated.csv` fallback checks in `DataCurator.load_aligned_dataset()` and `CalculationService.execute()`.
  4. Simplify `CuratedHourRecord` and `CuratedCupsReading` by removing unused attributes (`date`, `hour`, `solar_surplus`, `net_grid_demand`), eliminating duplicated `self_consumption`, `exported_energy`, and `imported_energy` storage across parent and child records, and deleting unused `.to_dict()` / `.to_json()` methods and aliases (`CupsConfig`, `SolarGenerationLoader`).

### SIMP-02 (`P2` Medium): Prune Orphaned Localization Keys & Simplify Translation Catalog Builder
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

### DES-02 (`P3` Low): Cohesive Visual Polish for Consumption Summary & Multi-Year Comparison Views (80-Col UI & Responsive SVG/HTML)
- **Goal:** Ensure the migrated `summary` and `compare` terminal views, SVG charts, and reports share `esd`'s modern visual hierarchy, palette, and 80-column clarity.
- **Target Components:** `src/presentation/views/`, `src/presentation/charts.py`, `src/presentation/console.py`, `src/presentation/html_report.py`.
- **Acceptance Criteria:**
  1. Unify 80-column Rich styling (`CUSTOM_THEME` tokens, `make_percentage_bar()`, consistent status icons, and `cups.json` `use` labels alongside masked/full CUPS) across `summary`, `compare`, and `calculate` views.
  2. Style `src/presentation/charts.py` SVGs with `esd`'s modern color palette, clean gridlines, legible value/axis typography, and accessible contrast, with optional standalone interactive HTML comparison dashboard parity (`*_esd_comparison_report.html`).
