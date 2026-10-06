# ☀️ Electricity Share Distributor (`esd`)

> Optimal electricity distribution coefficients ($\beta_i$) for collective photovoltaic self-consumption (*autoconsumo colectivo*) in Spain under **Real Decreto 244/2019**.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-2026.10.014-blue.svg)](pyproject.toml)
[![CLI Framework](https://img.shields.io/badge/CLI-Typer-009688?style=flat)](https://typer.tiangolo.com/)
[![Terminal UI](https://img.shields.io/badge/UI-Rich-E9573F?style=flat)](https://rich.readthedocs.io/)
[![Optimization](https://img.shields.io/badge/Solver-SciPy%20HiGHS-00599C?style=flat)](https://scipy.org/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000?style=flat&logo=ruff&logoColor=white)](https://astral.sh/ruff)
[![Pre-commit](https://img.shields.io/badge/Pre--commit-Enabled-brightgreen?style=flat&logo=pre-commit&logoColor=white)](https://pre-commit.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

`electricity-share-distributor` (`esd`) is a high-performance Python CLI utility designed to determine optimal electricity distribution coefficients ($\beta_i$) for collective photovoltaic installations (*autoconsumo colectivo*) in Spain.

It is a sibling utility to [`datadis-analyzer`](https://github.com/marcosDLCS/datadis-analyzer).

📚 **Guides & Documentation:**
- [🇬🇧 Technical & Operational Guide (English)](docs/GUIDE_EN.md)
- [🇪🇸 Guía Técnica y de Funcionamiento (Español)](docs/GUIDE_ES.md)

---

## 🚀 Key Capabilities

- **📥 Dual Time-Series Ingestion:** DATADIS hourly consumption curves (per CUPS) and Huawei FusionSolar generation Excel workbooks (`.xlsx`).
- **⏱️ Time-Series Alignment & DST:** Synchronizes disparate timestamps across leap years, missing intervals, and European DST switches (23h spring leap, 25h autumn transition).
- **🧮 Regulatory Optimization Engine:** Solves monthly linear programming models under **Real Decreto 244/2019** via `scipy.optimize.linprog(method='highs')`, finding optimal $\beta_i$ coefficients ($\sum \beta_i \le 1.0$) that maximize collective self-consumption.
- **📋 Annual Prevision Distribution Matrix:** Formulates a 12-month calendar schedule (Jan–Dec) for an upcoming operating year, skipping incomplete months (`—`) and pooling multi-year observations with $1/K$ energy scaling.
- **⚖️ Strategy Benchmarking:** Evaluates `optimal` LP against `consumption_share` and `equal` ($1/N$) baselines.
- **📊 Rich 80-Column Terminal UI:** Tabular overviews, monthly trajectories, strategy comparisons, and visual share bars formatted for 80-column terminals.
- **📝 Multi-Format Reporting:** Timestamped exports in CSV (DSO-ready), JSON, and Markdown in `.output/`.
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

- Put DATADIS hourly CSV files into `.input/consumption/` (one file per CUPS, or bulk exports).
- Put Huawei FusionSolar `.xlsx` generation reports into `.input/generation/`.

### 4. Run Optimization

```bash
# Calculate optimal coefficients for all available data
esd calculate

# Focus on a specific month and export all reports (CSV, JSON, Markdown)
esd calculate -y 2026 -m 5 -f all

# Inspect comparison between LP optimization and equal allocation
esd calculate -v comparison
```

---

## 📖 CLI Command Reference

### `esd calculate`
Calculates optimal monthly distribution coefficients ($\beta_i$).

```bash
esd calculate [OPTIONS]
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--strategy` | `-s` | Allocation method: `optimal`, `consumption_share`, or `equal` | `optimal` |
| `--year` | `-y` | Filter calculation to a specific calendar year | `None` (all) |
| `--month` | `-m` | Filter calculation to a specific month (1–12) | `None` (all) |
| `--view` | `-v` | Terminal view mode: `summary` (overview + matrix + details), `matrix` (share matrix), `trajectory`, `coefficients`, `comparison`, or `all` | `summary` |
| `--format` | `-f` | Report export format: `all`, `csv`, `json`, `markdown`, `table` / `none` | `all` |
| `--output-dir` | `-o` | Custom report destination directory | `.output` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd doctor`
Audits input data files to detect gaps, missing hourly intervals, inactive meters, and temporal alignment issues:

```bash
esd doctor
# With detailed missing timestamps list:
esd doctor --verbose
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--consumption-dir` | `-c` | Folder containing DATADIS hourly consumption CSVs | `.input/consumption` |
| `--generation-dir` | `-g` | Folder containing Huawei FusionSolar generation Excel files | `.input/generation` |
| `--verbose` | `-v` | Show complete list of all detected missing intervals | `False` |
| `--lang` | `-l` | Language override (`en` or `es`) | From config |

### `esd init`
Sets up project directory hierarchy (`.input/consumption`, `.input/generation`, `.output`) and default `.esd_config.json`. Defaults to English (`en`) and zero precision (`0`).

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

# Update default data directories
esd config --consumption-dir /path/to/consumption --generation-dir /path/to/generation
```

### `esd cleanup`
Removes generated reports and export files from `.output/`:

```bash
esd cleanup
esd cleanup --force  # Skip interactive confirmation
```

### `esd version`
Displays active CalVer release version and build metadata:

```bash
esd version
```

---

## 📁 Supported Ingestion Formats

1. **DATADIS Consumption Files (`.input/consumption/*.csv`):** Auto-detects delimiters (`;`, `,`, `\t`), decimal formats (`0,152` / `0.152`), character encodings (`utf-8`, `latin-1`), and standardizes Spanish 01:00–24:00 billing hours.
2. **Huawei FusionSolar Generation Files (`.input/generation/*.xlsx`):** Ingests inverter and plant generation reports, extracting PV yield (`Rendimiento FV` or `Rendimiento del inversor`) and standardizing timestamps.

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
- **Automated Verification Harness:** A pre-commit hook and automated CI harness execute `python3 -m src.security` to audit workspace files and the entire Git commit history, guaranteeing that no real CUPS or residential identifiers ever enter version control.
  ```bash
  python3 -m src.security         # Verify workspace and all commit history
  python3 -m src.security --staged # Verify staged git index changes
  ```

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, development setup, and the Conventional Commits specification.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
