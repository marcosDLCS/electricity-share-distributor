# ☀️ Electricity Share Distributor (`esd`)

> Unified Python CLI for residential community energy analytics (*comunidades de propietarios*) and optimal photovoltaic self-consumption distribution coefficients ($\beta_i$) in Spain under **Real Decreto 244/2019** & **Orden TED/1247/2021**.

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-2026.11.017-blue.svg)](pyproject.toml)
[![CLI Framework](https://img.shields.io/badge/CLI-Typer-009688?style=flat)](https://typer.tiangolo.com/)
[![Terminal UI](https://img.shields.io/badge/UI-Rich-E9573F?style=flat)](https://rich.readthedocs.io/)
[![Optimization](https://img.shields.io/badge/Solver-SciPy%20HiGHS-00599C?style=flat)](https://scipy.org/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000?style=flat&logo=ruff&logoColor=white)](https://astral.sh/ruff)
[![Pre-commit](https://img.shields.io/badge/Pre--commit-Enabled-brightgreen?style=flat&logo=pre-commit&logoColor=white)](https://pre-commit.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

`electricity-share-distributor` (`esd`) is the **unified platform** combining residential community electricity analytics (consolidating and superseding [`datadis-analyzer`](https://github.com/marcosDLCS/datadis-analyzer)) and optimal collective PV distribution under **Real Decreto 244/2019** & **Orden TED/1247/2021** for homeowners associations (*comunidades de propietarios*) in Spain (such as central aerothermal heating, swimming pool, garage ventilation, common area lighting, and elevators).

It supports both **consumption-only workflows** (`esd summary`, `esd compare`, consumption-only `esd doctor` — requiring only DATADIS CSVs) and **full solar optimization workflows** (`esd curate`, `esd calculate`). It is **not** meant for splitting bills among private domestic apartments.

📚 **Guides & Documentation:**
- [🇬🇧 Technical & Operational Guide (English)](docs/GUIDE_EN.md)
- [🇪🇸 Guía Técnica y de Funcionamiento (Español)](docs/GUIDE_ES.md)
- [📋 Project Improvement Backlog](BACKLOG.md)
- [🤖 Autonomous AI Agent Guide](AGENTS.md)

---

## 🚀 Key Capabilities

- **📊 Consumption Analytics & Fair Shares (`esd summary`):** Computes exact **100.00% fair-share percentages** (Hare-Niemeyer largest remainder rounding) across annual and monthly periods from DATADIS CSVs alone, with dominant (`★` >30%) and inactive (`(0)` <1 kWh) consumer badges, inline share bars, single-CUPS trajectories, and Markdown reports.
- **📈 Multi-Year Comparison & Native SVGs (`esd compare`):** Evaluates year-over-year energy trends using an **apples-to-apples calendar completeness heuristic** (flagging incomplete months as `[Inc]` and excluding them from deltas), plus zero-dependency grouped SVG bar charts in `.output/charts/` and Markdown reports.
- **📥 Unified Time-Series & Weather Ingestion:** Pre-validates DATADIS CSVs via `DatadisValidator` across both flat (`.input/consumption/*.csv`) and annualized (`.input/consumption/<year>/*.csv`) trees, auto-detects `consumoKwh`/`consumo_kWh` aliases, and ingests solar inverter Excel reports (`.xlsx`) plus Open-Meteo weather CSVs.
- **⏱️ Time-Series Alignment & DST:** Synchronizes disparate timestamps across leap years, missing intervals, and European DST switches (23h spring leap, 25h autumn transition with per-file energy conservation prior to cross-file deduplication).
- **🧮 Regulatory Optimization Engine:** Solves monthly and fortnight (24 half-month) linear programming models under **Real Decreto 244/2019** alongside dynamic 24-hour profiles under **Orden TED/1247/2021** via `scipy.optimize.linprog(method='highs')`, finding optimal $\beta_i$ coefficients ($\sum \beta_i = 1.0$) that maximize collective self-consumption.
- **📋 Annual Prevision Distribution Matrix:** Formulates a 12-month calendar schedule (Jan–Dec) for an upcoming operating year, skipping incomplete months (`—`) and pooling multi-year observations with exact per-month $1/k_m$ energy scaling.
- **⚡ 4-Way Modality Progression:** Evaluates Current No-Share baseline against Monthly Share (RD 244/2019), Fortnight Share, and Hourly Share (Orden TED/1247/2021).
- **🖥️ Rich 80-Column Terminal UI:** Tabular overviews, monthly trajectories, and visual share bars formatted cleanly for 80-column terminals.
- **📝 Multi-Format Reporting:** Timestamped exports across **6 `calculate` deliverables** (interactive HTML dashboard, monthly shares CSV + lite matrix CSV, fortnight shares CSV + lite matrix CSV, hourly shares CSV) plus `summary`/`compare` Markdown reports & SVG charts in `.output/`.
- **🌐 Localization & Versioning:** Bilingual English/Spanish (`en`/`es`) support and automated per-commit CalVer (`YYYY.MM.NNN`).

---

## 📐 Regulatory Framework (Real Decreto 244/2019)

In Spanish shared self-consumption schemes (*autoconsumo colectivo*), participating supplies receive a fixed fraction $\beta_i$ of hourly PV generation $G_h$ throughout each billing month:

1. **Coefficient Constraint:**
   $$0 \le \beta_i \le 1 \quad \text{and} \quad \sum_{i=1}^{N} \beta_i \le 1.0000 \; (100.00\%)$$

2. **Hourly Energy Balance per Supply Point (CUPS $i$ in hour $h$):**
   - **Allocated Solar Generation:** $G_{i, h} = \beta_i \cdot G_h$
   - **Self-Consumed Energy:** $SC_{i, h} = \min(C_{i, h}, \beta_i \cdot G_h)$
   - **Residual Grid Demand:** $RD_{i, h} = \max(0, C_{i, h} - \beta_i \cdot G_h)$
   - **Surplus Energy Spilled:** $Surplus_{i, h} = \max(0, \beta_i \cdot G_h - C_{i, h})$

3. **Collective Optimization Problem:**
   $$\max_{\beta_1, \dots, \beta_N} \sum_{i=1}^{N} \sum_{h \in \text{month}} \min(C_{i, h}, \beta_i \cdot G_h) \quad \text{s.t.} \quad \sum_{i=1}^{N} \beta_i \le 1, \; \beta_i \ge 0$$

   This piecewise-linear optimization is cast as a standard Linear Program and solved in milliseconds via SciPy's Simplex/HiGHS solver.

---

## 🖥️ Terminal Output Preview

```text
╭────────────── ⚡ COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY ──────────────╮
│                                                                              │
│  Supply Points (CUPS)     Total PV Generation      Total Community Demand    │
│  9 CUPS                   17,979.40 kWh            7,661.80 kWh              │
│  Date Range               Total Self-Consumed      Total Solar Surplus       │
│  2026-05-01 ➔ 2026-05-31  1,998.61 kWh (11.1%)     15,980.79 kWh             │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

              📈 Month-by-Month Community Energy Trajectory (kWh)
╭─────────┬───────────┬───────────┬───────────┬───────────┬─────────┬─────────╮
│ Month   │ Solar (k… │ Demand (… │ Self-Con… │ Surplus … │ Self-C… │ Covera… │
├─────────┼───────────┼───────────┼───────────┼───────────┼─────────┼─────────┤
│ 2026-05 │  17,979.4 │   7,661.8 │   1,998.6 │  15,980.8 │   11.1% │   26.1% │
├─────────┼───────────┼───────────┼───────────┼───────────┼─────────┼─────────┤
│ Total   │  17,979.4 │   7,661.8 │   1,998.6 │  15,980.8 │   11.1% │   26.1% │
╰─────────┴───────────┴───────────┴───────────┴───────────┴─────────┴─────────╯

               ⚖️ Allocation Strategy Efficiency Comparison (kWh)
╭────────────────────────┬───────────┬──────────┬─────────┬────────────────────╮
│ Strategy               │ Self-Con… │ Surplus… │ Self-C… │     Self-Cons Gain │
├────────────────────────┼───────────┼──────────┼─────────┼────────────────────┤
│ ★ Optimal (RD 244/201… │   1,998.6 │ 15,980.8 │   11.1% │    +240.7 (+13.7%) │
│   consumption_share    │   1,993.3 │ 15,986.1 │   11.1% │    +235.4 (+13.4%) │
│   equal                │   1,758.0 │ 16,221.4 │    9.8% │           Baseline │
╰────────────────────────┴───────────┴──────────┴─────────┴────────────────────╯

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

---

## ⚡ Quick Start

### 1. Installation

Clone the repository and install dependencies in an isolated virtual environment:

```bash
git clone https://github.com/marcosDLCS/electricity-share-distributor.git
cd electricity-share-distributor

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. Initialize Project Directories

Create the necessary `.input/` and `.output/` directories and default configuration:

```bash
esd init
# Or initialize in Spanish:
esd init --lang es
```

### 3. Place Input Files

- Put DATADIS hourly CSV files into `.input/consumption/` (flat `*.csv` or annualized `<year>/*.csv` subdirectories).
- *(Optional, required only for `curate`/`calculate`)* Put solar inverter `.xlsx` generation reports into `.input/generation/` and configure participating facilities in `.input/cups/cups.json`.

### 4. Run Analytics or Optimization

```bash
# Consumption-only analytics (works without solar generation or cups.json):
esd summary
esd compare -y 2024 -y 2025

# Full collective PV optimization (monthly, fortnight & hourly shares + 6 .output/ files):
esd calculate

# (Optional) Adjust precision or language beforehand in persistent configuration
esd config --precision 2 --lang es
```

---

## 📖 CLI Command Reference

### `esd summary`
Aggregates DATADIS community consumption by year and month, enforces an exact **100.00% fair-share invariant**, tags dominant (`★` >30%) and inactive (`(0)` <1 kWh) meters, optionally enriches rows with `use` labels from `cups.json`, renders 80-column terminal tables, and exports a Markdown report (`*_esd_consumption_summary.md`):

```bash
esd summary                               # Annual + monthly overview and Markdown export
esd summary --year 2025 --view annual     # Filter to 2025 annual fair-share table
esd summary --cups ES0021000000000001AA   # Dedicated trajectory for a single CUPS
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--consumption-dir` | `-c` | Folder containing DATADIS CSVs (flat or `<year>/` trees) | From config |
| `--output-dir` | `-o` | Destination folder for Markdown reports | From config |
| `--year` | `-y` | Filter display and report to a specific calendar year | `None` (all) |
| `--view` | `-v` | View mode: `all`, `annual`, or `monthly` | `all` |
| `--cups` | — | Filter display to a single CUPS trajectory | `None` (all) |
| `--cups-file` | `-C` | Optional path to `cups.json` for functional `use` labels | `.input/cups/cups.json` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd compare`
Performs apples-to-apples multi-year community energy comparison across selected years. Months with incomplete telemetry in any compared year are flagged `[Inc]` and excluded from annual totals, deltas, and trend metrics so comparisons remain fair. Exports a Markdown report (`*_esd_consumption_comparison.md`) and native SVG grouped bar charts in `.output/charts/`:

```bash
esd compare                        # Compare all available years with SVG charts
esd compare -y 2024 -y 2025        # Compare specific years (--years 2024,2025 also valid)
esd compare --no-charts            # Skip SVG chart generation
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--consumption-dir` | `-c` | Folder containing DATADIS CSVs (flat or `<year>/` trees) | From config |
| `--years` | `-y` | Years to compare (`-y 2024 -y 2025` or `--years 2024,2025`) | `None` (all) |
| `--output-dir` | `-o` | Destination folder for Markdown report and `.output/charts/*.svg` | From config |
| `--cups-file` | `-C` | Optional path to `cups.json` for functional `use` labels | `.input/cups/cups.json` |
| `--charts/--no-charts` | — | Generate native monthly SVG comparison bar charts | `True` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd calculate`
Calculates optimal monthly (RD 244/2019), fortnight (24 half-month), and dynamic hourly (Orden TED/1247/2021) distribution coefficients ($\beta_i$) using zero command-line arguments. Reads workspace directories, language, and share precision from `.esd_config.json`, evaluates only participating CUPS and optional per-CUPS `min_share`/`max_share` bylaws configured in `cups.json`, auto-curates `.curated/esd.csv` when missing or stale, renders 80-column terminal summary/trajectory/matrix tables, and exports all **6 timestamped `.output/` deliverables**:

```bash
esd calculate
```

| Deliverable | Format | Contents |
| :--- | :--- | :--- |
| `*_esd_interactive_report.html` | HTML (Standalone) | Interactive offline ES/EN executive dashboard, 4 KPI cards, hourly profile, SEI chart & monthly heatmap |
| `*_esd_monthly_shares.csv` | CSV (`;`) | Full monthly allocation and energy balance per CUPS |
| `*_esd_monthly_shares_lite.csv` | CSV (`;`) | Compact monthly share matrix (CUPS vs. months `01`..`12`) |
| `*_esd_fortnight_shares.csv` | CSV (`;`) | Full fortnight allocation (`1`: days 1–15, `2`: days 16–end) and energy balance per CUPS |
| `*_esd_fortnight_shares_lite.csv` | CSV (`;`) | Compact fortnight share matrix (CUPS vs. fortnights `01-1`..`12-2`) |
| `*_esd_hourly_shares.csv` | CSV (`;`) | Hourly time-series shares (with 1% active floor) and integer Solar Efficiency Index (`0`–`100`) |

### `esd curate`
Executes the 3-stage canonical data pipeline: (1) aggregates split solar generation files into `.curated/generation.csv` and `.curated/generation.xlsx` (`GenerationDataset`), (2) aggregates split CUPS consumption files into `.curated/consumption.csv` and `.curated/consumption.xlsx` (`ConsumptionDataset`), and (3) reconciles fake-zero loads on the primary meter, enriches with CUPS metadata and weather indicators (temperature, cloud cover), and produces the master `.curated/esd.csv` and `.curated/esd.xlsx` datasets:

```bash
# Curate entire historical dataset (generates generation.*, consumption.*, and esd.* in .curated/)
esd curate

# Filter curation to a specific year and month
esd curate --year 2026 --month 5

# Customize master output filename and CSV delimiter
esd curate --name community_data --delimiter ";"
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--consumption-dir` | `-c` | Folder containing DATADIS hourly consumption CSVs | `.input/consumption` |
| `--generation-dir` | `-g` | Folder containing solar inverter generation Excel files | `.input/generation` |
| `--curated-dir` | `-u`, `-o` | Folder where curated CSV and Excel files will be written | `.curated` |
| `--cups-file` | `-C` | Path to `cups.json` specifying CUPS uses and primary flags | `.input/cups/cups.json` |
| `--weather-dir` | `-w` | Folder containing Open-Meteo hourly weather CSV files | `.input/weather` |
| `--name` | `-n` | Base filename for master curated output files (without extension) | `esd` |
| `--delimiter` | `-d` | Delimiter character for curated CSV output (`;` or `,`) | `;` |
| `--year` | `-y` | Optional calendar year filter (e.g. 2026) | `None` (all) |
| `--month` | `-m` | Optional calendar month filter (1–12) | `None` (all) |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd doctor`
Audits input data files to detect gaps, missing hourly intervals, inactive meters, weather dataset continuity, and temporal alignment issues. Enriches CUPS with functional uses (e.g. heat pump, pool, garage) from `cups.json`. When `.input/generation/` is empty or absent, it seamlessly runs in **consumption-only diagnostic mode** (exiting with status `1` while clearly marking `can_calculate=False` since PV generation is absent):

```bash
esd doctor
# With detailed missing timestamps list:
esd doctor --verbose
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--consumption-dir` | `-c` | Folder containing DATADIS hourly consumption CSVs | `.input/consumption` |
| `--generation-dir` | `-g` | Folder containing solar inverter generation Excel files | `.input/generation` |
| `--cups-file` | `-C` | Path to `cups.json` specifying CUPS uses and primary flags | `.input/cups/cups.json` |
| `--weather-dir` | `-w` | Folder containing Open-Meteo hourly weather CSV files | `.input/weather` |
| `--verbose` | `-v` | Show complete list of all detected missing intervals | `False` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd weather`
Downloads hourly historical weather data (temperature, cloud cover, WMO weather code) from the Open-Meteo Archive API into `.input/weather/` for an entire calendar year. The year is the only mandatory parameter: if coordinates are not provided on the CLI, `esd weather` automatically inspects `cups.json` (`.input/cups/cups.json`), deduplicates any repeated coordinates across supply points, and downloads a concise weather file for each unique location (`{year}_{lat}_{lon}_weather.csv`, e.g. `2024_40.4168_-3.7038_weather.csv`). If a file already exists for that year and location, it is automatically overwritten:

```bash
# Download weather for all unique locations defined in cups.json (no duplicate downloads)
esd weather --year 2024

# Or specify custom coordinates explicitly:
esd weather --year 2024 --latitude 40.4168 --longitude -3.7038

# Using configured coordinates
esd weather -y 2024
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--year` | `-y` | Calendar year to download (mandatory) | — |
| `--latitude` | `--lat` | Geographical latitude coordinate (-90 to 90) | From cups.json or config |
| `--longitude` | `--lon` | Geographical longitude coordinate (-180 to 180) | From cups.json or config |
| `--cups-file` | `-C` | Path to custom cups.json file to extract coordinates from | `.input/cups/cups.json` |
| `--weather-dir` | `-w` | Destination folder for weather CSV files | `.input/weather` |
| `--timezone` | `-tz` | Timezone for hourly timestamps | `auto` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd init`
Sets up project directory hierarchy (`.input/consumption`, `.input/generation`, `.input/weather`, `.output`) and default `.esd_config.json`. Defaults to English (`en`) and zero precision (`0`).

```bash
esd init [--lang en|es] [--precision 0|1|2]
```

### `esd config`
Inspects or modifies persistent configuration:

```bash
# View active configuration
esd config

# Set default application language to Spanish
esd config --lang es

# Save community geographical coordinates for weather queries
esd config --latitude 40.4168 --longitude -3.7038

# Update default data directories
esd config --consumption-dir /path/to/consumption --generation-dir /path/to/generation --weather-dir /path/to/weather --curated-dir /path/to/curated
```

### `esd cleanup`
Recursively removes generated reports, charts, curated datasets, and cached weather files from `.output`, `.curated`, and `.input/weather` (preserving hidden files such as `.gitkeep`). Also supports the hidden `esd clean` command alias:

```bash
esd cleanup
esd cleanup --force  # Skip interactive confirmation
esd clean --force    # Alias preserved for former da users
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--output-dir` | `-o` | Output directory to clean | From config (`.output`) |
| `--curated-dir` | `-u` | Curated directory to clean | From config (`.curated`) |
| `--weather-dir` | `-w` | Weather cache directory to clean | From config (`.input/weather`) |
| `--force` | `-f` | Force deletion without interactive confirmation | `False` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd version`
Displays active CalVer release version and build metadata:

```bash
esd version
```

---

## 📁 Supported Ingestion Formats

1. **DATADIS Consumption Files (`.input/consumption/*.csv` or `.input/consumption/<year>/*.csv`):** Discovers CSVs recursively, pre-validates headers via `DatadisValidator`, auto-detects delimiters (`;`, `,`, `\t`), decimal formats (`0,152` / `0.152`), encodings (`utf-8`, `utf-8-sig`, `latin-1`, `cp1252`), supports both `consumo_kWh` and `consumoKwh` column aliases, and conserves 25h autumn DST transition energy.
2. **Solar Inverter Generation Files (`.input/generation/*.xlsx`):** Ingests inverter and plant generation reports, extracting PV yield (`Rendimiento FV` or `Rendimiento del inversor`), standardizing timestamps, and conserving 25h autumn DST intervals.
3. **Open-Meteo Hourly Weather Files (`.input/weather/{YYYY}_{lat}_{lon}_weather.csv`):** Standardized CSVs containing hourly records with columns `timestamp,temperature,cloud_cover,weather_code`.

---

## 🔄 Migrating from `datadis-analyzer` (`da` ➔ `esd`)

`esd` absorbs all core workflows of [`datadis-analyzer`](https://github.com/marcosDLCS/datadis-analyzer) into one CLI so `datadis-analyzer` can be cleanly archived:

| Workflow / Artifact | Former `datadis-analyzer` (`da`) | Unified `electricity-share-distributor` (`esd`) |
| :--- | :--- | :--- |
| **Initialize Workspace** | `da init` | `esd init` |
| **Consumption Summary** | `da summary [--year --view --cups]` | `esd summary [--year --view --cups -C cups.json]` |
| **Multi-Year Comparison** | `da compare [-y 2024 -y 2025 --no-charts]` | `esd compare [-y 2024 -y 2025 --no-charts]` |
| **Charts Output** | Matplotlib PNG charts in `.output/charts/` | Zero-dependency native SVGs in `.output/charts/*.svg` |
| **Input CSV Layout** | `.input/<year>/*.csv` | `.input/consumption/<year>/*.csv` (or flat `.input/consumption/*.csv`) |
| **Clean Generated Files** | `da cleanup` / `da clean` | `esd cleanup` / `esd clean` (cleans `.output`, `.curated`, `.input/weather`) |
| **Config & Version** | `.da_config.json`, `da version` | `.esd_config.json`, `esd config`, `esd version` |
| **Collective PV Sizing** | *(Not available)* | `esd doctor` ➔ `esd curate` ➔ `esd calculate` |

---

## 🧪 Testing & Code Quality

The codebase enforces strict type safety, 100% English naming, and comprehensive test coverage across all modules.

```bash
# Run complete automated test suite
pytest -v

# Run linter and formatter checks
ruff check .
ruff format --check .

# Run pre-commit hooks manually
pre-commit run --all-files
```

---

## 🔒 Security & Data Privacy Notice

Under Spain's regulatory framework and European GDPR (Regulation EU 2016/679, along with Spanish Organic Law 3/2018 LOPDGDD), Universal Supply Point Codes (**CUPS**) and granular consumption time-series are confidential personal data.

- **Synthetic Identifiers:** All documentation examples, sample reports, and test cases use synthetic mock identifiers adhering strictly to `ES00210000000000XXYY` (`ES0021000000000001AA`, `ES0021000000000002BB`, etc.).
- **Local Data Isolation:** Input folders (`.input/`) and generated reports (`.output/`) are excluded from Git tracking via `.gitignore`.
- **Automated Verification Harness:** A pre-commit hook and automated CI harness execute `python3 -m src.security` to audit workspace files, `.xlsx` workbooks, staged diffs, and the entire Git commit history for real CUPS, private geographic coordinates, local paths, and exposed secrets/credentials:
  ```bash
  python3 -m src.security                # Verify workspace and all commit history
  python3 -m src.security --staged       # Verify staged git index changes
  python3 -m src.security --scan <path>  # Verify a specific file or directory
  ```

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, development setup, and the Conventional Commits specification, and check [BACKLOG.md](BACKLOG.md) for prioritized improvement tasks.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
