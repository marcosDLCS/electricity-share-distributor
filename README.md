# ☀️ Electricity Share Distributor (`esd`)

> Unified Python CLI for residential community energy analytics (*comunidades de propietarios*) and optimal photovoltaic self-consumption distribution coefficients ($\beta_i$) in Spain under **Real Decreto 244/2019** & **Orden TED/1247/2021**.

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-2026.11.029-blue.svg)](pyproject.toml)
[![CLI Framework](https://img.shields.io/badge/CLI-Typer-009688?style=flat)](https://typer.tiangolo.com/)
[![Terminal UI](https://img.shields.io/badge/UI-Rich-E9573F?style=flat)](https://rich.readthedocs.io/)
[![Optimization](https://img.shields.io/badge/Solver-Water--Filling%20%2B%20HiGHS-00599C?style=flat)](https://scipy.org/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000?style=flat&logo=ruff&logoColor=white)](https://astral.sh/ruff)
[![Pre-commit](https://img.shields.io/badge/Pre--commit-Enabled-brightgreen?style=flat&logo=pre-commit&logoColor=white)](https://pre-commit.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

`electricity-share-distributor` (`esd`) is a **unified Python CLI platform** for residential community electricity analytics and optimal collective PV distribution under **Real Decreto 244/2019** & **Orden TED/1247/2021** across shared common services in homeowners associations (*comunidades de propietarios*) in Spain (such as central aerothermal heating, swimming pool, garage ventilation, common area lighting, and elevators).

It supports both **consumption-only workflows** (`esd summary`, `esd compare`, consumption-only `esd doctor` — requiring only DATADIS CSVs) and **full solar optimization workflows** (`esd calculate`, including `--curate-only` and `--refresh`). It is **not** meant for splitting bills among private domestic apartments.

📚 **Guides & Documentation:**
- [🇬🇧 Technical & Operational Guide (English)](docs/GUIDE_EN.md)
- [🇪🇸 Guía Técnica y de Funcionamiento (Español)](docs/GUIDE_ES.md)
- [📋 Project Improvement Backlog](BACKLOG.md)
- [🤖 Autonomous AI Agent Guide](AGENTS.md)

---

## 🚀 Key Capabilities

- **📊 Consumption Analytics & Fair Shares (`esd summary`):** Computes exact **100.00% fair-share percentages** (Hare-Niemeyer largest-remainder rounding) across annual and monthly periods from DATADIS CSVs alone, with dominant (`★` >30%) and inactive (`(0)` <1 kWh) consumer badges, inline share bars, single-CUPS trajectories, and Markdown reports.
- **📈 Multi-Year Comparison & Native SVGs (`esd compare`):** Evaluates year-over-year energy trends using an **apples-to-apples calendar completeness heuristic** (flagging incomplete months `[Inc]` and excluding them from deltas), plus zero-dependency grouped SVG bar charts in `.output/charts/`, Markdown reports, and optional `--html` dashboards.
- **📥 Unified Time-Series & Weather Ingestion:** Pre-validates DATADIS CSVs via `DatadisValidator` across flat (`.input/consumption/*.csv`) and annualized (`.input/consumption/<year>/*.csv`) trees (`consumoKwh`/`consumo_kWh`), ingests Huawei `.xlsx` generation reports (read-only streaming) plus Open-Meteo archives, and reconciles primary-CUPS fake zeros ($\max(C_{\text{DATADIS}}, C_{\text{inverter}})$).
- **⏱️ Time-Series Alignment & DST:** Synchronizes timestamps across leap years, missing intervals, and European DST switches (23h spring jump, 25h autumn transition conserved within each file prior to cross-file deduplication).
- **🧮 Vectorized Regulatory Optimization Engine:** Solves monthly and fortnight (24 half-month) models under **Real Decreto 244/2019** via exact separable-concave water-filling (cross-verified against `scipy.optimize.linprog(method='highs')`) alongside dynamic 24-hour schedules under **Orden TED/1247/2021** and optional per-CUPS `min_share`/`max_share` bylaws.
- **📋 Annual Prevision & 4-Way Progression:** Formulates normalized Jan–Dec schedules with exact per-month $1/k_m$ calendar scaling and contrasts Current No-Share vs. Monthly Share vs. Fortnight Share vs. Hourly Share.
- **🖥️ 80-Column Rich UI & Deliverables:** Renders decluttered 80-column tables, writes streaming styled `.xlsx` workbooks on `--curate-only`, exports **6 timestamped `.output/` deliverables**, supports bilingual EN/ES i18n, bumps CalVer automatically, and audits GDPR compliance via `src.security`.

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

   This piecewise-linear concave problem is solved exactly in milliseconds via vectorized water-filling (matching SciPy HiGHS optimality).

---

## 🖥️ Terminal Output Preview

```text
╭───────────── ⚡ COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY ──────────────╮
│  🌞 Solar Gen: 17,979.40 kWh   ⚡ Demand: 7,661.80 kWh   🏆 Self-Cons: 1,998.61 kWh │
│  ╭───────────────────────────┬─────────┬────────┬──────────────────╮        │
│  │ Modality                  │ Self-C. │   SC % │ Gain vs Baseline │        │
│  │ ★ Hourly Share (Order TED)│ 2,340.5 │  13.0% │ +1,050.2 (+81%)  │        │
│  │   Fortnight Share         │ 2,110.2 │  11.7% │   +819.9 (+63%)  │        │
│  │   Monthly Share (RD 244)  │ 1,998.6 │  11.1% │   +708.3 (+55%)  │        │
│  ╰───────────────────────────┴─────────┴────────┴──────────────────╯        │
│  9 CUPS • Strategy: OPTIMAL • Range: 2026-01-01 ➔ 2026-09-30                │
╰─────────────────────────────────────────────────────────────────────────────╯
          📅 Suggested Electricity Distribution Share Matrix (β_i %)
╭────────────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────╮
│CUPS        │ Jan│ Feb│ Mar│ Apr│ May│ Jun│ Jul│ Aug│ Sep│ Oct│ Nov│ Dec│ Avg│
│…00000008HH │  0%│  0%│  0%│  0%│ 15%│ 21%│ 19%│ 28%│ 25%│   —│   —│   —│ 14%│
│…00000009II │ 86%│ 83%│ 81%│ 65%│ 53%│ 58%│ 59%│ 45%│ 48%│   —│   —│   —│ 61%│
│TOTAL       │100%│100%│100%│100%│100%│100%│100%│100%│100%│   —│   —│   —│100%│
╰────────────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────╯
✔ Exported: .output: *_esd_monthly_shares.csv, *_esd_fortnight_shares.csv, *_esd_interactive_report.html
```

---

## ⚡ Quick Start

### 1. Installation
Clone the repository and install dependencies in an isolated virtual environment:
```bash
git clone https://github.com/marcosDLCS/electricity-share-distributor.git
cd electricity-share-distributor
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Initialize Project Directories
Create `.input/`, `.curated/`, `.output/`, and default `.esd_config.json` (defaults: English, `0` share decimals):
```bash
esd init [--lang en|es] [--precision 0|1|2]
```

### 3. Place Input Files & Configure Supply Points
- Place DATADIS hourly CSVs into `.input/consumption/` (flat `*.csv` or annualized `<year>/*.csv`).
- *(Optional for `summary`/`compare`; required for full solar `calculate`)* Place Huawei inverter `.xlsx` reports into `.input/generation/` and configure facilities in `.input/cups/cups.json`:
  ```json
  [
    {"cups": "ES0021000000000001AA", "use": "Aerotermia", "primary": true, "latitude": 40.4168, "longitude": -3.7038},
    {"cups": "ES0021000000000002BB", "use": "Garaje", "min_share": 0.05, "max_share": 0.40}
  ]
  ```

### 4. Run Consumption Analytics or Solar Optimization
```bash
# Quick workflow
esd doctor                      # Audit data health & date overlap
esd summary                     # 100.00% fair-share consumption tables
esd compare -y 2024 -y 2025     # YoY comparison & SVG charts
esd calculate                   # Optimize shares + export 6 .output/ files
```

---

## 📖 CLI Command Reference

`esd` provides **7 consolidated commands** (`init`, `doctor`, `summary`, `compare`, `calculate`, `config`, `clean`), plus root options `-V`/`--version` (display active CalVer panel), `-h`/`--help`, and bare `esd` (render formatted Rich overview). Persistent paths, coordinates, language, and share precision live in `.esd_config.json`.

### `esd init`
Sets up the workspace directory hierarchy (`.input/consumption`, `.input/generation`, `.input/weather`, `.curated`, `.output`), clears stale `.output/` artifacts, and writes default `.esd_config.json` (English, zero decimal precision).

```bash
esd init [--lang en|es] [--precision 0|1|2]
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--lang` | `-l` | Interactive or preset UI language (`en` or `es`) | Prompt / `en` |
| `--precision` | `-p` | Decimal places for share percentages (`0`, `1`, or `2`) | Prompt / `0` |

### `esd config`
Inspects active settings or persists language, share decimal precision, Open-Meteo coordinates, `cups.json`, and workspace directories into `.esd_config.json` (used automatically across all analytical commands):

```bash
# View active persistent configuration
esd config

# Update UI language and share decimal precision
esd config --lang es --precision 2

# Save community geographical coordinates for Open-Meteo queries
esd config --latitude 40.4168 --longitude -3.7038

# Update default input, CUPS, curated, and output paths
esd config -c /path/cons -g /path/gen -w /path/weather -u /path/curated -o /path/output -C /path/cups.json
```

| Option | Flag | Description |
| :--- | :--- | :--- |
| `--lang` / `--precision` | `-l` / `-p` | Persist UI language (`en`/`es`) and share precision (`0`/`1`/`2`) |
| `--latitude` / `--longitude` | `--lat` / `--lon` | Persist community geographic coordinates (`-90..90`, `-180..180`) |
| `--consumption-dir` / `--generation-dir` | `-c` / `-g` | Persist default DATADIS and solar inverter input folders |
| `--weather-dir` / `--curated-dir` / `--output-dir` | `-w` / `-u` / `-o` | Persist Open-Meteo archive, curated cache, and report output folders |
| `--cups-file` | `-C` | Persist default path to `cups.json` configuration file |

### Root Flags (`esd`)
Running bare `esd` prints the compact 7-command Rich reference, `-h`/`--help` displays Typer usage, and `-V`/`--version` displays active CalVer release metadata:

```bash
esd             # Render styled command overview and workflow summary
esd --version   # Display active CalVer version panel (alias: -V)
esd --help      # Show CLI usage and available commands (alias: -h)
```

### `esd doctor`
Audits configured DATADIS CSVs, solar inverter `.xlsx` exports, and Open-Meteo weather archives for gaps, duplicates, inactive meters (`>=99%` zeros), prolonged inverter outages (`>=48h`), and timestamp overlap. Runs in **consumption-only mode** when `.input/generation/` is empty (`can_calculate=False`, exit status `1`).
```bash
esd doctor [--verbose] [--lang en|es]
```
| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--verbose` | `-v` | Show complete list of missing hourly intervals | `False` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd summary`
Aggregates DATADIS community demand from configured paths by year and month under the **100.00% fair-share invariant**, tags `★` (`>30%` rank #1) and `(0)` (`<1 kWh`) meters, renders 80-column tables (hiding detailed per-CUPS monthly tables unless `--view monthly`), and exports `*_esd_consumption_summary.md`:
```bash
esd summary                               # Overview + annual shares + Markdown export
esd summary --year 2025 --view monthly    # Add per-CUPS monthly breakdown
esd summary --cups ES0021000000000001AA   # Trajectory for a single CUPS
```
| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--year` | `-y` | Filter display and report to a specific calendar year | `None` (all) |
| `--view` | `-v` | View mode: `all`, `annual`, or `monthly` | `all` |
| `--cups` | — | Filter display to a single CUPS trajectory | `None` (all) |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd compare`
Performs apples-to-apples multi-year comparisons from configured paths, flagging incomplete months `[Inc]` and excluding them from annual totals and deltas. Exports `*_esd_consumption_comparison.md`, grouped SVG charts in `.output/charts/`, and an optional standalone `--html` dashboard:
```bash
esd compare -y 2024 -y 2025 [--no-charts] [--html] [--lang en|es]
```
| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--years` | `-y` | Years to compare (`-y 2024 -y 2025` or `--years 2024,2025`) | `None` (all) |
| `--charts/--no-charts` | — | Toggle native monthly SVG grouped bar charts | `True` |
| `--html` | — | Export standalone interactive comparison HTML report | `False` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd calculate`
Config-first flagship command. Reads workspace paths, precision, and participating supplies from `.esd_config.json` and `cups.json` (respecting `min_share`/`max_share` bylaws), auto-curates `.curated/esd.csv` when missing/stale (skipping heavy Excel writes unless `--curate-only` is passed), fetches missing Open-Meteo weather archives, reconciles primary CUPS fake zeros, computes monthly, fortnight, and 24h coefficients, renders 80-column summaries, and exports **6 timestamped `.output/` deliverables**:
```bash
esd calculate                 # Auto-curate if needed + optimize + export 6 deliverables
esd calculate --refresh       # Refresh Open-Meteo weather & force full re-curation
esd calculate --curate-only   # Build CSV + styled Excel datasets in .curated/ and exit
```
| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--refresh` | `-r` | Force re-curation and refresh cached weather files | `False` |
| `--curate-only` | — | Write curated CSV & styled `.xlsx` files without optimizing | `False` |

| Deliverable | Format | Contents |
| :--- | :--- | :--- |
| `*_esd_interactive_report.html` | HTML (Standalone) | Interactive offline ES/EN dashboard: 4 KPIs, hourly profile, SEI chart & monthly heatmap |
| `*_esd_monthly_shares.csv` | CSV (`;`) | Full monthly allocation and energy balance per CUPS |
| `*_esd_monthly_shares_lite.csv` | CSV (`;`) | Compact monthly share matrix (CUPS vs. months `01`..`12`) |
| `*_esd_fortnight_shares.csv` | CSV (`;`) | Full fortnight allocation (`1`: days 1–15, `2`: days 16–end) and energy balance per CUPS |
| `*_esd_fortnight_shares_lite.csv` | CSV (`;`) | Compact fortnight share matrix (CUPS vs. fortnights `01-1`..`12-2`) |
| `*_esd_hourly_shares.csv` | CSV (`;`) | Hourly time-series shares (1% active floor) and integer Solar Efficiency Index (`0`–`100`) |

### `esd clean`
Recursively removes generated files and subdirectories in the configured `.output/`, `.curated/`, and `.input/weather/` directories (preserving hidden files such as `.gitkeep`):
```bash
esd clean [--force] [--lang en|es]
```
| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--force` | `-f` | Force deletion without confirmation | `False` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

---

## 📁 Supported Ingestion & Configuration Formats

1. **DATADIS Consumption Files (`.input/consumption/*.csv` or `<year>/*.csv`):** Discovered recursively and pre-validated by `DatadisValidator` (required columns: `cups`, `fecha`, `hora`, `consumo_kWh` or `consumoKwh`). Auto-detects delimiters (`;`, `,`, `\t`), decimals (`0,152` / `0.152`), and encodings (`utf-8`, `utf-8-sig`, `latin-1`, `cp1252`), conserving 25h autumn DST intervals inside each file before deduplication.
2. **Solar Inverter Generation Reports (`.input/generation/*.xlsx`):** Parsed read-only via Openpyxl (`Rendimiento FV (kWh)` or `Rendimiento del inversor (kWh)`), normalizing `YYYY-MM-DD HH:MM:SS` timestamps and conserving 25h autumn DST intervals.
3. **Open-Meteo Hourly Weather Files (`.input/weather/{YYYY}_{lat}_{lon}_weather.csv`):** Cached or automatically downloaded hourly CSVs (`timestamp,temperature,cloud_cover,weather_code`) used for cloud-cover context and the Solar Efficiency Index (SEI).
4. **Facility Mapping (`.input/cups/cups.json`):** Optional JSON array (required for solar `calculate` filtering and primary reconciliation) defining participating supplies:
   - `cups` & `use`: Synthetic CUPS (`ES00210000000000XXYY`) and human-readable facility label (`Aerotermia`, `Garaje`, etc.).
   - `primary`: Marks the behind-the-meter main supply point eligible for inverter load reconciliation.
   - `latitude` / `longitude` & `min_share` / `max_share`: Community coordinates for Open-Meteo and statutory bylaw bounds.
5. **Curated Medallion Datasets (`.curated/`):** `generation.csv`, `consumption.csv`, and master `esd.csv` (plus streaming styled `.xlsx` sibling workbooks when running `esd calculate --curate-only`).

---

## 🧪 Testing & Code Quality

The repository enforces strict type safety, English naming, and comprehensive test coverage:
```bash
pytest -v                       # Automated unit & integration tests
ruff check . && ruff format --check .
pre-commit run --all-files
```

---

## 🔒 Security & Data Privacy Notice

Under Spain's regulatory framework, European **GDPR (EU 2016/679)**, and Spanish **LOPDGDD (3/2018)**, Universal Supply Point Codes (**CUPS**) and hourly load curves are confidential personal data.

- **Synthetic Identifiers:** All examples, tests, and documentation exclusively use synthetic mock CUPS `ES00210000000000XXYY` (`ES0021000000000001AA`, `ES0021000000000002BB`, etc.).
- **Local Data Isolation:** `.input/`, `.curated/`, and `.output/` remain excluded from Git via `.gitignore`.
- **Automated Verification Harness:** Pre-commit and CI run `python3 -m src.security` across workspace files, `.xlsx` workbooks, staged diffs, and full Git history for real CUPS, private coordinates, local paths, and exposed secrets:
  ```bash
  python3 -m src.security                # Audit workspace files and git history
  python3 -m src.security --staged       # Audit staged git changes
  python3 -m src.security --scan <path>  # Audit a specific file or directory
  ```

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, test expectations, and the Conventional Commits specification, and check [BACKLOG.md](BACKLOG.md) for prioritized improvement tasks.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
