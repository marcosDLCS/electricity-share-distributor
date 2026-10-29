# 📘 Practical Guide to Electricity Share Distributor (`esd`)

> **Who this guide is for:** Homeowners associations (*comunidades de propietarios*), property managers (*administradores de fincas*), energy consultants, and building engineers who want to understand how collective solar distribution works across shared community facilities, without wading through dense mathematical formulas or legal jargon.

---

> [!IMPORTANT]
> ### 🛡️ Maintenance & Synchronization Harness
> **To developers and autonomous AI agents:**
> This document is the primary conceptual and operational guide for `electricity-share-distributor`.
> Whenever modifying the data ingestion schemas ([`src/ingestion/`](../src/ingestion)), curation logic ([`src/curation/`](../src/curation)), optimization solver ([`src/optimization/`](../src/optimization)), terminal presentation ([`src/presentation/views/`](../src/presentation/views)), or file exporters ([`src/presentation/export.py`](../src/presentation/export.py)), you **MUST** update this guide (`GUIDE_EN.md`) and its Spanish counterpart (`GUIDE_ES.md`) in tandem.

---

## 1. 🎯 What is the Real Purpose of `esd`?

`electricity-share-distributor` (`esd`) is specifically designed to calculate optimal electricity distribution coefficients ($\beta_i$) for **shared common facilities within a single homeowners association (*comunidad de vecinos / propietarios*)** in Spain.

### 🚫 What `esd` is NOT:
- **`esd` is NOT meant to distribute energy to private residential dwellings or individual apartments.**
- It does not calculate domestic billing splits or private consumption shares between neighbors.

### 🏢 What `esd` IS:
When a residential community installs a shared rooftop photovoltaic (PV) system, the community uses the generated solar electricity to power its **own collective facilities and common services**, such as:
1. **Central Aerothermal / Heating & Hot Water (*Aerotermia / Calefacción Central / ACS*):** Typically the largest energy consumer in modern buildings.
2. **Swimming Pool & Community Hall (*Piscina y Sala Comunitaria*):** Filtration pumps, water treatment, lighting, and summer recreational demand.
3. **Underground Garages (*Garaje*):** Continuous ventilation systems, carbon monoxide extractors, and 24/7 lighting.
4. **Building Common Areas, Elevators & Staircases (*Ascensores, escaleras, alumbrado general*):** Hallway lighting, building intercoms, and elevator traction motors.

---

## 2. ⚖️ Why Does a Single Community Need Distribution Coefficients?

Even though all these shared services belong to the exact same *comunidad de propietarios*, Spanish electrical regulations treat each one as an **independent supply point with its own utility contract and electricity meter (CUPS)**.

Under **Real Decreto 244/2019** and **Orden TED/1247/2021**:
- The community must register a formal agreement with the electrical distribution company (DSO / *distribuidora*) specifying what percentage ($\beta_i$) of the solar energy generated each hour is allocated to each community meter.
- The coefficients across all participating community meters must add up to **strictly 100%** ($\sum \beta_i = 1.0$).
- Under standard monthly filing, these percentages remain constant throughout each calendar month. Alternatively, a 24-hour diurnal schedule can be filed under Orden TED/1247/2021.

### Why Naive Splitting Causes Huge Financial Loss:
It might seem simple to divide the solar power equally (e.g., $12.5\%$ to each of 8 community meters) or according to their annual bill. However, this causes severe financial waste:
- **The Seasonal Mismatch (Pool vs. Heating):** In January, the swimming pool filtration is shut down, while the central aerothermal heat pump works non-stop to heat the building. Assigning equal solar shares to the pool in winter spills valuable solar electricity into the street as surplus for pennies, while the community's heat pump is forced to purchase expensive peak grid electricity!
- **The Daily Mismatch (Lighting vs. Garage vs. Heat Pump):** Common area lighting uses very little baseline power (efficient LED bulbs and intercoms), while the central heat pump runs heavy compressor cycles during sunny midday hours. An equal split leaves lighting circuits with unused excess solar energy and starves the central heating.

**How `esd` Solves This:** The optimization engine analyzes hour-by-hour consumption curves across all community services and finds the exact mathematical coefficients that maximize self-consumption inside the community, drastically cutting the association's total electricity bill.

---

## 3. 🔍 The Curation Process: Solving the "Fake Zero" Riddle

Before calculating optimal shares, real-world community solar installations face a major measurement obstacle: **utility meters record "fake zeros" during sunny hours**.

### Why Utility Data Has Fake Zeros
In most community installations, the solar panels and inverter are physically wired right behind the meter of the primary facility (typically the central aerothermal heating or central services room):

```mermaid
graph LR
    Solar[☀️ Community Solar Panels & Inverter] -->|Direct Solar Electricity| PrimaryLoad[🏢 Primary Facility: Central Aerothermal / Heating]
    StreetGrid[⚡ Street Power Grid] -->|Only Net Imported Energy| UtilityMeter[📟 Utility Meter: DATADIS]
    UtilityMeter --> PrimaryLoad
```

1. **Inside the Community:** During sunny daylight hours, the aerothermal system runs directly on clean electricity generated by the rooftop panels.
2. **At the Utility Meter (DATADIS):** The utility meter only records electricity drawn from the street grid. Because solar power satisfies the demand on-site, the utility meter records **0.0 kWh**.
3. **The Trap:** If you optimize based solely on utility data, the community's primary facility looks completely inactive during the day! The algorithm would mistakenly strip solar shares away from the building's biggest consumer and reassign them to small meters (like staircase lighting) that cannot use the power.

### How `esd curate` Reconciles the Physical Reality
The curation engine ([`src/curation/`](../src/curation)) reconciles two separate data streams to recover true physical consumption:

1. **Utility Data (DATADIS):** Hourly consumption imported from the grid for each community meter.
2. **Solar Inverter Data:** The inverter's smart power sensor measures both solar production and the *total actual electrical demand* of the primary facility connected behind it.
3. **CUPS Descriptions ([`.input/cups/cups.json`](../.input/cups/cups.json)):** Maps 20-character CUPS codes to human-friendly facility names (e.g., `"Aerotermia"`, `"Piscina"`, `"Garaje"`, `"Alumbrado"`), and marks which one is the `"primary": true` connection point.

Whenever the utility meter reports zero (or artificially low power) while the inverter confirms that the equipment was actively running, `esd curate` **replaces the fake zero with the real load consumption**.

### The Curated Result (`.curated/curated.csv` and `.curated/curated.xlsx`)
The output produces two complementary sibling formats in the `.curated/` folder: a standardized CSV and a beautifully styled Excel workbook (`curated.xlsx`):

#### 1. Standardized CSV (`curated.csv`)
Formatted using `;` as delimiter and `,` for decimals without thousands separators, grouping related analytical dimensions:
1. **Temporal coordinates:** `timestamp`, `year`, `month`, `day`, `hour`, `day_of_week`, `is_weekend`
2. **Individual consumer:** `cups_id`, `use`, `consumption`
3. **Community & solar balance:** `community_demand`, `generation`, `self_consumption`, `exported_energy`, `imported_energy`
4. **Weather context:** `temperature`, `cloud_cover`

```csv
timestamp;year;month;day;hour;day_of_week;is_weekend;cups_id;use;consumption;community_demand;generation;self_consumption;exported_energy;imported_energy;temperature;cloud_cover
2026-05-01 12:00:00;2026;5;1;12;Friday;False;ES0021000000000001AA;Aerotermia;8,5;9,7;12,5;6,0;6,0;2,5;21,4;12
2026-05-01 12:00:00;2026;5;1;12;Friday;False;ES0021000000000002BB;Garaje;1,2;9,7;12,5;0,0;0,0;0,0;21,4;12
```

#### 2. Styled Excel Workbook (`curated.xlsx`)
Created alongside the CSV with executive styling for interactive analysis:
- **Semantic Group Header Colors:** Similar columns share identical harmonious header colors (Steel Slate Blue for Time coordinates, Deep Petrol Teal for CUPS identification, Warm Terracotta for Demand/Consumption, Solar Emerald for Solar Generation & Balance, and Royal Amethyst for Weather).
- **Hour-Grouped Zebra Pattern:** Rows belonging to the same hour block share the same background, alternating hour-by-hour between pure white and a soft neutral tint (`#F4F6F9`) so all supply points in each interval are visually grouped.
- **Boolean Emojis:** The `is_weekend` column displays intuitive visual checkmarks (`✅` for weekend, `❌` for weekday).
- **Freeze Panes & AutoFilter:** The header row is frozen and native Excel filters are enabled across all columns.

For the primary installation point, `esd` always adopts the higher consumption between the utility (DATADIS) and the solar inverter smart power sensor ($\max(C_{\text{DATADIS}}, C_{\text{inverter}})$). This guarantees full equipment demand is captured while avoiding fake zero underreporting. The primary supply point also receives the detailed solar energy balance metrics: physical instantaneous self-consumption (`self_consumption`), solar generation exported to the grid (`exported_energy`), and grid electricity imported (`imported_energy`). Other participating points receive zero for these plant-level flows prior to collective allocation. The dataset is ordered chronologically by timestamp (date/hour) and within each timestamp alphabetically by facility use. Furthermore, each hourly record includes local weather context (`temperature` in °C and `cloud_cover` percentage from 0 to 100%). If weather data is not already stored locally in `.input/weather/`, `esd curate` automatically queries Open-Meteo using the community's default location from `.input/cups/cups.json`.

---

## 4. 🧠 Core Heuristics Explained (Without Complex Math)

`esd` incorporates several practical rules to make community calculations robust and DSO-compliant:

### 1. Behind-the-Meter Fake Zero Detection & Maximum Load Adoption
For the community supply designated as primary, the solar inverter's smart power meter measures the total actual load demanded by the equipment. During solar generation hours, self-consumption behind the meter causes utility grid import readings (DATADIS) to drop to zero or artificially low levels. To capture the full true facility consumption while preventing measurement dropouts, `esd` always adopts $\max(C_{\text{DATADIS}}, C_{\text{inverter}})$, restoring the true load and recording the exact kWh recovered.

### 2. Forward-Looking Calendar Schedule (January to December)
Communities don't sign regulatory agreements to distribute energy in the past; they need a distribution schedule for an **upcoming operating year**. `esd` always structures its results as a clean 12-month calendar matrix running from January through December.

### 3. Complete Month Quality Threshold (The 90% Rule)
If the solar plant was commissioned midway through a month (e.g., on June 20th), optimizing a permanent monthly percentage based on just 10 days would produce an unfair, distorted result.
- `esd` verifies that each historical month has readings spanning from the start to the end of the month, covering **at least 90% of expected calendar days and hours**.
- If a month does not meet this threshold, the tool skips that month and displays a clean dash (`—`) rather than guessing with incomplete data.

### 4. Multi-Year Seasonal Pooling
Weather varies from year to year. A rainy May in 2025 followed by an exceptionally sunny May in 2026 shouldn't mislead the community agreement. When historical data is available for the same calendar month across multiple years, `esd` pools all hourly observations together. This blends out short-term weather anomalies and creates a balanced, representative profile for future years.

### 5. Exact 100% Rounding (The Hare-Niemeyer Method)
Electrical distribution companies (DSOs) reject regulatory share filings if the percentages do not sum to **strictly 100%**.
- Standard mathematical rounding often creates sums of 99% or 101% due to accumulated fractional decimals.
- `esd` uses the **Largest Remainder Method** (Hare-Niemeyer): it gives every community facility its integer share first, and then allocates the remaining decimal fractions to the facilities with the largest remainders until the sum is **strictly 100%** across any chosen precision (0, 1, or 2 decimal places).

### 6. Cloud-Resilient Hourly Profiles & Night Allocation
On cloudy or stormy days, solar production can drop to near zero. If elevator motors kick in during a momentary solar lull, calculating an instantaneous percentage would assign the elevator an absurdly high share (like 95%) that doesn't reflect typical habits.
- The 24-hour diurnal profile (`--hourly`) calculates consolidated hourly patterns across all observed days.
- It provides both the actual share (`share_pct`) and a cloud-resilient estimated share (`estimated_share_pct`) formatted for filing under Orden TED/1247/2021.
- **Night Hours with Exact Zero Generation:** In night hours where solar generation is exactly zero, every participating CUPS receives an active regulatory floor of 1% (or its configured minimum share), with the remaining share assigned to the primary installation CUPS (e.g. 99% primary / 1% secondary for a two-supply community). This ensures every participating point retains a continuous active coefficient in hourly filings while maintaining an exact regulatory 100% sum.

### 7. Photovoltaic Solar Efficiency Index (SEI)
In the hourly calculation (`--hourly`), each record includes a dedicated `solar_efficiency` metric as a plain integer without decimals. For hours with active solar generation ($G_h > 0$), it yields an index from **1 to 100**. For hours without generation (or nighttime intervals), it is set to **0**.

The index models real-world photovoltaic performance and optical solar geometry based on Open-Meteo local weather archives:
$$\text{SEI} = \begin{cases} \text{clip}\left(\text{round}\left(100.0 \times f_{\text{cloud}} \times f_{\text{temp}} \times f_{\text{season}} \times f_{\text{hour}}\right), \; 1, \; 100\right) & \text{if } G_h > 0 \\ 0 & \text{if } G_h = 0 \end{cases}$$

- **Cloud Optical Attenuation ($f_{\text{cloud}}$):** Captures non-linear direct beam extinction through atmospheric cloud layers while preserving ~25% diffuse ambient irradiance under overcast skies:
  $$f_{\text{cloud}} = 1.0 - 0.75 \times \left(\frac{CC}{100.0}\right)^{1.2}$$
- **Cell Temperature Derating ($f_{\text{temp}}$):** Reflects standard silicon PV power temperature coefficients ($-0.4\% / ^\circ\text{C}$ relative to $20^\circ\text{C}$ ambient reference). Cold bright mornings provide an efficiency boost (up to $+8\%$), whereas summer midday heat causes thermal semiconductor degradation:
  $$f_{\text{temp}} = \text{clip}\left(1.0 - 0.004 \times (T_{\text{amb}} - 20.0), \; 0.80, \; 1.08\right)$$
- **Seasonal Solar Elevation ($f_{\text{season}}$):** Models solar declination and atmospheric air mass path length across Spanish latitudes (36°N–43°N), peaking near the summer solstice (June/July ~ 1.00) and reaching its minimum during winter solstice (December/January ~ 0.70):
  $$f_{\text{season}} = 0.85 + 0.15 \times \cos\left(\frac{2\pi \times (m - 6.5)}{12.0}\right)$$
- **Diurnal Solar Zenith Angle ($f_{\text{hour}}$):** Models the diurnal solar arc and cosine incidence angle on fixed rooftop panels, peaking around solar noon (13:00–14:00 in Spain) with minimal optical reflection, and tapering during morning and evening grazing angles:
  $$f_{\text{hour}} = \begin{cases} 0.70 + 0.30 \times \sin\left(\pi \times \frac{h - 6.0}{15.0}\right) & \text{if } 6 \le h \le 21 \\ 0.65 & \text{otherwise} \end{cases}$$

### 8. Regulatory Constraints & Community Bylaw Limits (*Estatutos de la Comunidad*)
Homeowners association agreements and community bylaws frequently establish statutory allocation bounds across shared supplies:
- **Minimum Share Floor (`--min-share`):** Guarantees smaller common circuits (e.g. garage ventilation, elevator cabs, stair lighting) a baseline allocation (e.g., $\beta_i \ge 0.05$ or 5%) so all facilities benefit from the collective installation.
- **Maximum Share Cap (`--max-share`):** Prevents dominant consumers (e.g. centralized aerothermal heating) from monopolizing generation (e.g., capped at $\beta_i \le 0.70$ or 70%).
- **Custom Per-CUPS Bylaws in `cups.json`:** Individual supply points can also define specific `"min_share"` and `"max_share"` limits directly in `cups.json`.
- The HiGHS linear programming solver incorporates variable bounds $L_i \le \beta_i \le U_i$, checks mathematical feasibility ($\sum L_i \le 1.0$), and applies Hare-Niemeyer exact rounding strictly within bounds across both monthly calculations and the 24-hour diurnal profile and hourly time-series (`--hourly`), guaranteeing an exact $\sum \beta_i = 100.0\%$.

---

## 5. 📊 Community Energy Balance & 3-Way Self-Consumption Progression

To provide complete transparency and support informed decision-making by property owners and HOA boards, `esd` reports a consolidated six-metric energy balance and a three-tier self-consumption progression across all terminal views, interactive HTML dashboards, and multi-format exports.

### The Six Core Energy Balance KPIs
1. **Total Solar Generation ($G_{\text{total}}$):** Aggregate kilowatt-hours produced by the rooftop photovoltaic system across the entire evaluation horizon.
2. **Total Community Demand ($C_{\text{total}}$):** Full round-the-clock electrical energy demanded by all participating community facilities.
3. **Solar-Hours Generation ($G_{\text{solar}}$):** Generation occurring strictly during active daylight hours ($G_h > 0$). Because solar PV operates purely diurnally, this metric matches total generation and confirms zero nocturnal generation distortion.
4. **Solar-Hours Demand ($C_{\text{solar}}$):** Aggregate community consumption demanded exclusively during daylight/generation intervals ($G_h > 0$). This defines the physical instantaneous upper bound for self-consumption without battery storage.
5. **Solar Surplus Spilled ($Surplus$):** Excess solar electricity generated when instantaneous photovoltaic production exceeds simultaneous community demand ($\max(0, G_h - C_h)$), injected into the street grid.
6. **Total Self-Consumed Energy ($SC$):** Net solar kilowatt-hours directly captured and consumed by community equipment on-site ($\min(C_h, G_h)$), avoiding retail utility grid purchases.

### The 3-Way Self-Consumption Modality Progression
`esd` calculates and contrasts three distinct operating regimes directly from telemetry:
1. **Current Self-Consumption (Baseline / No Share):** Direct self-consumption achieved when solar generation is wired solely to the primary installation (e.g., central aerothermal heating) with zero collective sharing. Recorded directly from inverter telemetry.
2. **Estimated Monthly Share (Real Decreto 244/2019):** Optimal collective self-consumption under legally fixed monthly coefficients ($\beta_{i, m}$). By dynamically shifting shares between facilities according to seasonal habits (e.g., allocating higher shares to pool filtration in summer and to central heating in winter), self-consumption increases substantially over single-meter wiring.
3. **Estimated Hourly Share (Orden TED/1247/2021):** Dynamic diurnal self-consumption utilizing variable hourly schedules ($\beta_{i, h}$). Because facility loads vary significantly throughout the day (elevator motors during commute peaks, pool filtration around solar noon, and heat pumps in diurnal cycles), dynamic hourly allocation maximizes instantaneous coincidence, capturing maximum solar energy and reducing the community's overall electricity bill to the physical minimum.

---

## 6. 🚀 Practical Workflow & Commands

You can execute the entire pipeline with simple commands:

```mermaid
graph TD
    A[Raw Input Data in .input/] --> B[esd doctor: Pre-flight Health Audit]
    B --> C[esd curate: Reconcile Fake Zeros & Match Facility Names]
    C --> D[esd calculate: Optimize Monthly Shares & Export Reports]
    D --> E[Deliverables in .output/ ready for Utility DSO]
```

### Step 1: Check Data Health (`esd doctor`)
Scans all DATADIS CSV files, solar inverter Excel reports, and Open-Meteo weather datasets to detect gaps, inactive meters, and overlapping date ranges before running calculations. Enriches CUPS with functional uses (e.g. Aerothermal heat pump, garage, elevators) from `cups.json`:
```bash
esd doctor
# With custom CUPS config or weather directory:
esd doctor -C .input/cups/cups.json -w .input/weather --verbose
```

### Step 2: Automatic or Manual Curation (`esd curate`)
Reconciles the fake zeros from the primary meter and outputs `.curated/curated.csv` and styled `.curated/curated.xlsx`:
```bash
esd curate
# Or filter to a specific month and custom output name:
esd curate --year 2026 --month 5 --name community_curated
```
> [!TIP]
> **Automatic Curation:** You do not even need to run `esd curate` manually! When you run `esd calculate`, the tool checks if `.curated/curated.csv` exists. If it's missing, it automatically curates the data first. You can also pass `--force-curate` to `esd calculate` to force re-curating existing files.

### Step 3: Fetch Hourly Weather Data (`esd weather`)
Download historical hourly weather (temperature, cloud cover, WMO weather codes) from Open-Meteo into `.input/weather/{YYYY}_{lat}_{lon}_weather.csv`. Year is the only mandatory parameter: if coordinates are not provided on the CLI, `esd weather` automatically inspects `cups.json`, deduplicates repeated locations across facilities in the same building, and downloads each unique coordinate once:
```bash
# Automatically discover and download weather for all unique locations in cups.json
esd weather --year 2024

# Or specify custom coordinates explicitly
esd weather --year 2024 --latitude 40.4168 --longitude -3.7038
```

### Step 4: Calculate Optimal Community Shares (`esd calculate`)
Solves the optimal distribution schedule and displays clean 80-column terminal tables:
```bash
# Calculate full 12-month calendar schedule
esd calculate

# Enforce regulatory or bylaw limits (e.g. 5% minimum floor, 70% maximum cap per supply)
esd calculate --min-share 5% --max-share 70%

# Choose specific terminal view mode ('summary', 'matrix', 'trajectory', 'hourly', 'coefficients', 'comparison', 'all')
esd calculate --view matrix
esd calculate --view comparison

# Override input/output directories (dynamically defaults to .esd_config.json)
esd calculate -c .input/consumption -g .input/generation -o .output

# Filter to a specific year and month
esd calculate --year 2026 --month 5

# Include 24-hour diurnal profile and hourly time-series
esd calculate --hourly

# Set share percentage precision (0 = 53%, 1 = 52.8%, 2 = 52.86%)
esd calculate --precision 1

# Export only the standalone interactive HTML report
esd calculate --format html

# Export only the monthly and hourly shares CSV files
esd calculate --format csv
```

---

## 7. 📊 Deliverables & Official Documents (`.output/`)

Running `esd calculate` generates ready-to-use artifacts in `.output/`:

| File Name | Format | Practical Purpose |
| :--- | :--- | :--- |
| `*_esd_interactive_report.html` | HTML (Standalone) | Offline interactive executive dashboard with dynamic bilingual ES/EN switcher, 4 primary energy KPI cards, dynamic hourly coefficient prevision (Orden TED/1247/2021), energy trajectory multi-bars, Photovoltaic Solar Efficiency Index graphic, and monthly coefficient matrix heatmap. |
| `*_esd_monthly_shares.csv` | CSV (`;` delimited) | Monthly allocation breakdown per CUPS: consumption, generation, share percentage ($\beta_i$ %), self-consumed kWh, solar surplus, and remaining grid demand, ordered by month and facility use. |
| `*_esd_hourly_shares.csv` | CSV (`;` delimited) | Full hourly time-series recording consumption, generation, shares (with 1% floor), and the Solar Efficiency Index (integer 1-100 for generation hours, 0 without generation), ordered by timestamp and use. |

---

## 8. 🗺️ Code Map & Traceability Reference

For developers and autonomous agents navigating the codebase:

| Architecture Layer | Module | Key Classes / Functions | Responsibility |
| :--- | :--- | :--- | :--- |
| **CLI & Commands** | [`src/cli.py`](../src/cli.py) | `calculate_command`, `curate_command`, `weather_command`, `doctor_command` | Typer command routing, parameter validation, and user workflow dispatch. |
| **Application Services** | [`src/services/`](../src/services) | `CalculationService`, `CurationService`, `DoctorService`, `WeatherService` | Core workflow orchestrators encapsulating business processes. |
| **Domain Core** | [`src/domain/`](../src/domain) | `SupplyPoint`, `ShareAllocation`, `EnergyBalance`, `EsdError` | Pure domain models, value objects, and centralized domain exceptions. |
| **Configuration** | [`src/config.py`](../src/config.py) | `AppConfig`, `get_language`, `get_precision`, `get_weather_dir` | Settings persistence (`.esd_config.json`) and folder resolution. |
| **Localization** | [`src/i18n.py`](../src/i18n.py) | `t()`, `I18nNamespace`, `TRANSLATIONS` | Structured domain namespaces (app, cli, doctor, curate, weather, tables, export) with parameter parity and dual-mode resolution. |
| **Ingestion: Consumption** | [`src/ingestion/consumption.py`](../src/ingestion/consumption.py) | `DatadisConsumptionLoader` | DATADIS CSV discovery, encoding detection, and reading. |
| **Ingestion: Generation** | [`src/ingestion/generation.py`](../src/ingestion/generation.py) | `HuaweiGenerationLoader` | Solar inverter `.xlsx` report parsing (solar production and load demand). |
| **Ingestion: Weather** | [`src/ingestion/weather.py`](../src/ingestion/weather.py) | `OpenMeteoWeatherDownloader`, `WeatherLoader` | Open-Meteo Archive API downloader, WMO weather codes, and weather CSV ingestion. |
| **Ingestion: Audit** | [`src/ingestion/doctor.py`](../src/ingestion/doctor.py) | `DataDoctor`, `DoctorReport` | Pre-flight gap detection, weather health audit, CUPS use enrichment, inactive meter alerts, and date overlap verification. |
| **Curation & Reconciliation** | [`src/curation/`](../src/curation) | `DataCurator`, `CuratedDataset` | Fake-zero reconciliation, CUPS metadata lookup, and curated CSV export. |
| **Optimization: Models** | [`src/optimization/models.py`](../src/optimization/models.py) | `CoefficientsMatrix`, `HourlyProfileMatrix`, `OptimizationResult` | Matrix structures, diurnal profiles, and community metrics. |
| **Optimization: Solver** | [`src/optimization/engine.py`](../src/optimization/engine.py) | `DistributionOptimizer` | Linear programming solver, diurnal profile engine, baselines, and Hare-Niemeyer rounding. |
| **Presentation: Views** | [`src/presentation/views/`](../src/presentation/views) | `render_coefficients_matrix_table`, `render_community_summary` | Rich terminal tables, executive KPI cards with baseline gain badges, two-tone heatmaps, unicode sparklines, 4-step progress stepper, and adaptive 80-column formatting. |
| **Presentation: Exports** | [`src/presentation/export.py`](../src/presentation/export.py) | `ReportExporter` | Unified report exporter architecture for monthly and hourly CSV shares and standalone interactive HTML dashboards. |
| **Security & Privacy** | [`src/security.py`](../src/security.py) | `check_privacy`, `scan_xlsx_file`, `scan_git_history` | GDPR enforcement, cups.json signature tracking, Excel workbook scanning, and synthetic CUPS verification harness. |
