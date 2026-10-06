# 📘 Comprehensive Technical & Operational Guide (`esd`)

> **Target Audience:** Developers, data engineers, and energy consultants who have technical proficiency but are not necessarily domain specialists in Spanish electricity regulatory frameworks or linear programming.

---

> [!IMPORTANT]
> ### 🛡️ Maintenance & Synchronization Harness
> **To all engineers, developers, and autonomous AI agents:**
> This document is the primary conceptual and operational blueprint for `electricity-share-distributor`.
> Whenever modifying the data ingestion schemas ([`src/ingestion/`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion)), linear programming solver models ([`src/optimization/`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization)), terminal presentation tables ([`src/presentation/views.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/views.py)), or file exporters ([`src/presentation/export.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/export.py)), you **MUST** update this guide (`GUIDE_EN.md`) and its Spanish sibling (`GUIDE_ES.md`) to maintain strict architectural alignment.

---

## 1. 🎯 Foundational Principles & Regulatory Context

In Spain, **Real Decreto 244/2019** governs collective self-consumption (*autoconsumo colectivo*), where multiple supply points (**CUPS**) share generation from a common photovoltaic (PV) installation.

### Regulatory Rules & Hourly Balance
1. **Hourly Allocation ($\beta_i$):** In each hour $h$, participant $i$ receives $G_{i, h} = \beta_i \cdot G_h$.
2. **Monthly Static Constraint:** Coefficients $\beta_{i, m}$ remain strictly fixed throughout calendar month $m$.
3. **Budget Constraint:** Total shares cannot exceed 100%: $\sum_{i=1}^{N} \beta_{i, m} \le 1.0000$ ($100.00\%$).
4. **Energy Balance per CUPS:**
   - Self-Consumed: $SC_{i, h} = \min(C_{i, h}, \beta_i \cdot G_h)$
   - Residual Grid Demand: $RD_{i, h} = \max(0, C_{i, h} - \beta_i \cdot G_h)$
   - Surplus Spilled: $Surplus_{i, h} = \max(0, \beta_i \cdot G_h - C_{i, h})$

### Why Optimization Outperforms Naive Splits
Flat equal splits ($1/N$) or total demand ratios ignore the diurnal solar window (08:00–20:00). Absent occupants spill assigned solar energy to the grid at wholesale surplus rates while daytime consumers buy expensive grid electricity. `esd` solves for coefficients that **maximize collective self-consumption** $\sum_i \min(C_{i, h}, \beta_i \cdot G_h)$, minimizing grid imports.

---

## 2. 📥 Ingestion Specifications

`esd` processes raw data placed in `.input/`:
- **DATADIS Hourly Consumption (`.input/consumption/*.csv`):** Official DSO curves. [`DatadisConsumptionLoader`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/consumption.py) auto-detects encodings (`utf-8`, `latin-1`), delimiters (`;`, `,`, `\t`), decimal formats, and maps Spanish 01:00–24:00 billing hours to standard zero-indexed timestamps.
- **Huawei FusionSolar PV Generation (`.input/generation/*.xlsx`):** Inverter export reports. [`HuaweiGenerationLoader`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/generation.py) extracts production curves (`Rendimiento FV` or `Rendimiento del inversor`) and normalizes hourly timestamps.

---

## 3. ⚙️ Processing Pipeline

The calculation pipeline consists of five stages:

1. **Pre-Flight Diagnostic Audit ([`DataDoctor`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/doctor.py)):** Audits input series for missing hours, inactive meters (>90% zero readings), and validates date range overlaps.
2. **Time-Series Synchronization ([`TimeSeriesAligner`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/aligner.py)):** Pivots CUPS series into columns and intersects timestamps with solar production, handling Daylight Saving Time transitions (23-hour March spring leap, 25-hour October autumn shift).
3. **Linear Programming Solver ([`DistributionOptimizer`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/engine.py)):** Formulates the non-linear objective $\max \sum \min(C_{i, h}, \beta_i G_h)$ using an epigraph reformulation with auxiliary variables $s_{i, h} \le C_{i, h}$ and $s_{i, h} - \beta_i G_h \le 0$, solved globally via SciPy HiGHS.
4. **Exact 100% Rounding ([`_round_betas`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/engine.py#L136)):** Uses the **Hare-Niemeyer Largest Remainder Method** to ensure sum of rounded shares equals **exactly 100%** across any decimal precision (0, 1, or 2).
5. **Baseline Benchmarking:** Automatically compares optimal results against `equal` ($1/N$) and `consumption_share` baselines.

---

## 4. 📤 Expected Outputs & Deliverables

### 1. The Consolidated Distribution Share Matrix
The core deliverable of `esd` is the **Regulatory Distribution Share Matrix** ([`CoefficientsMatrix`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/models.py#L78)):
- **Prevision Schedule (Brand-New Year):** Rather than a retrospective analysis of historical dates, `esd` generates a forward-looking 12-month calendar distribution schedule from **January to December** for an upcoming operating year.
- **Incomplete Month Handling:** If complete data (≥90% calendar day and hourly coverage) for PV generation or consumption is unavailable for at least one full calendar month, `esd` skips the calculation for that month and displays `—` (no-data / hyphen).
- **Multi-Year Aggregation Heuristic:** If complete data exists for the same calendar month across multiple years (e.g., May 2025 and May 2026), `esd` pools historical hourly observations into a unified LP optimization model to solve for the optimal $\beta_i$ distribution coefficients, scaling energy totals by $1/K$ to represent a typical single annual cycle.
- **Rows (Y-axis):** Participating CUPS.
- **Columns (X-axis):** 12 calendar months (Jan–Dec), plus the **Annual Average** share.
- **Cells:** Recommended $\beta_i$ percentage share formatted to the configured precision (0, 1, or 2 decimal places), or `—` for months without complete data.
- **TOTAL Row:** Verifies that every evaluated month column sums strictly to $100\%$.

```text
          📅 Suggested Electricity Distribution Share Matrix (β_i %)
╭────────────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────╮
│CUPS        │ Jan│ Feb│ Mar│ Apr│ May│ Jun│ Jul│ Aug│ Sep│ Oct│ Nov│ Dec│ Avg│
├────────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
│…00000001AA │  1%│  1%│  1%│  2%│  2%│  2%│  2%│  2%│  1%│   —│   —│   —│  2%│
│…00000002BB │  1%│  1%│  1%│  2%│  2%│  1%│  1%│  1%│  2%│   —│   —│   —│  1%│
│…00000003CC │  1%│  1%│  2%│  2%│  2%│  1%│  1%│  2%│  2%│   —│   —│   —│  2%│
│…00000004DD │  9%│ 11%│ 12%│ 24%│ 21%│ 14%│ 15%│ 18%│ 18%│   —│   —│   —│ 17%│
│…00000005EE │  1%│  2%│  2%│  3%│  3%│  2%│  2%│  2%│  2%│   —│   —│   —│  2%│
│…00000006FF │  0%│  0%│  0%│  0%│  0%│  0%│  0%│  0%│  0%│   —│   —│   —│  0%│
│…00000007GG │  1%│  1%│  1%│  2%│  2%│  1%│  1%│  2%│  2%│   —│   —│   —│  1%│
│…00000008HH │  0%│  0%│  0%│  0%│ 15%│ 21%│ 19%│ 28%│ 25%│   —│   —│   —│ 14%│
│…00000009II │ 86%│ 83%│ 81%│ 65%│ 53%│ 58%│ 59%│ 45%│ 48%│   —│   —│   —│ 61%│
├────────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
│TOTAL       │100%│100%│100%│100%│100%│100%│100%│100%│100%│   —│   —│   —│100%│
╰────────────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────╯
      Regulatory allocation schedule (RD 244/2019) • Sum per month: 100%
```

### 2. Multi-Format Output Files (`.output/`)
Running `esd calculate` automatically generates timestamped artifacts:

| Generated File | Format | Purpose |
| :--- | :--- | :--- |
| `*_esd_coefficients_matrix.csv` | CSV (`;` delimited) | Ready-to-import spreadsheet table for direct submission to the utility distributor (DSO). |
| `*_esd_optimization_summary.md` | Markdown | Executive report containing the signed schedule annex for the collective self-consumption agreement. |
| `*_esd_coefficients.csv` | CSV (`;` delimited) | Detailed hourly and monthly energy metrics (kWh self-consumed, surplus, grid demand) per CUPS. |
| `*_esd_results.json` | JSON | Machine-readable structural data export for API integrations. |

---

## 5. 🗺️ Code Map & Traceability Reference

To inspect or extend the codebase, use this map to trace directly from concepts to code symbols:

| Architecture Layer | Core Module | Key Classes / Functions | Primary Responsibility |
| :--- | :--- | :--- | :--- |
| **CLI & Commands** | [`src/cli.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/cli.py) | `calculate_command`, `init_command`, `doctor_command` | Typer command routing, parameter parsing, and execution dispatch. |
| **Configuration** | [`src/config.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/config.py) | `AppConfig`, `get_language`, `get_precision` | Settings persistence (`.esd_config.json`) and path resolution. |
| **Internationalization** | [`src/i18n.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/i18n.py) | `t()`, `TRANSLATIONS` | English and Spanish dictionary lookups with string interpolation. |
| **Ingestion: Consumption** | [`src/ingestion/consumption.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/consumption.py) | `DatadisConsumptionLoader` | DATADIS hourly CSV discovery, encoding detection, and parsing. |
| **Ingestion: Generation** | [`src/ingestion/generation.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/generation.py) | `HuaweiGenerationLoader` | Huawei FusionSolar `.xlsx` parsing and extraction. |
| **Ingestion: Doctor** | [`src/ingestion/doctor.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/doctor.py) | `DataDoctor`, `DoctorReport` | Pre-flight gap detection, inactive meter alerts, and date overlap verification. |
| **Ingestion: Alignment** | [`src/ingestion/aligner.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/aligner.py) | `TimeSeriesAligner` | Hourly timestamp intersection, missing value imputation, and DST management. |
| **Optimization: Models** | [`src/optimization/models.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/models.py) | `CoefficientsMatrix`, `OptimizationResult` | Consolidated matrix structure and community balance dataclasses. |
| **Optimization: Solver** | [`src/optimization/engine.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/engine.py) | `DistributionOptimizer` | SciPy HiGHS LP formulation, baseline comparisons, and Hare-Niemeyer rounding. |
| **Presentation: Views** | [`src/presentation/views.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/views.py) | `render_coefficients_matrix_table` | Rich terminal tables, adaptive 80-column formatting, and visual progress bars. |
| **Presentation: Exports** | [`src/presentation/export.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/export.py) | `export_all`, `export_coefficients_matrix_csv` | Markdown summary generator, CSV exporter, and JSON serialization. |
| **Security & Privacy** | [`src/security.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/security.py) | `CupsPrivacyChecker`, `scan_git_history` | GDPR enforcement and synthetic CUPS verification harness. |
