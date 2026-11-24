"""Internationalization (i18n) module supporting English and Spanish localization for esd.

Organized into structured domain namespaces (app, cli, status, doctor, curate, weather, tables, export, analytics)
with dot-notation and legacy flat key access and guaranteed EN/ES parity.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from src.config import get_language


class I18nNamespace(StrEnum):
    """Domain namespaces for structured localization."""

    APP = "app"
    CLI = "cli"
    STATUS = "status"
    DOCTOR = "doctor"
    CURATE = "curate"
    WEATHER = "weather"
    TABLES = "tables"
    EXPORT = "export"
    ANALYTICS = "analytics"


STRUCTURED_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "en": {
        "app": {
            "app_subtitle": "Unified Community Energy Analytics & Collective PV Optimization CLI",
            "app_title": "☀️ ELECTRICITY SHARE DISTRIBUTOR (esd)",
            "overview_heading": "OVERVIEW",
            "overview_text": "Unified platform for residential community consumption analytics and collective PV\nallocation under RD 244/2019 & Orden TED/1247/2021. Runs consumption-only fair-share\nsummaries and multi-year comparisons, or optimizes β_i coefficients with PV generation.",
        },
        "cli": {
            "available_commands": "AVAILABLE COMMANDS",
            "cleaned_files": "Removed {count} file(s) from target directories.",
            "cleanup_aborted": "Cleanup aborted by user.",
            "cmd_calculate_desc": "Calculate optimal monthly, fortnight, and hourly shares (supports --refresh and --curate-only).",
            "cmd_clean_desc": "Remove generated data from .output, .curated, and .input/weather directories.",
            "cmd_compare_desc": "Compare consumption and variations across multiple years with apples-to-apples completeness.",
            "cmd_config_desc": "Inspect or update persistent application configuration and directory paths.",
            "cmd_desc": "Description",
            "cmd_doctor_desc": "Audit input files to detect gaps, missing hourly intervals, and data inconsistencies.",
            "cmd_init_desc": "Initialize application directories, configure language preference, and persist settings.",
            "cmd_name": "Command",
            "cmd_summary_desc": "Aggregate consumption by year and month, show fair-share tables, and export Markdown reports.",
            "err_lat_range": "Latitude must be between -90.0 and 90.0 (got {val}).",
            "err_lon_range": "Longitude must be between -180.0 and 180.0 (got {val}).",
            "help_workflow_body": (
                "  Consumption Analytics (no PV/generation files required):\n"
                "    esd summary     Annual & monthly 100.00% shares, ★/(0) badges + .md\n"
                "    esd compare     Multi-year [Inc] completeness delta & SVG charts\n"
                "  Collective PV Allocation (RD 244/2019 & Orden TED/1247/2021):\n"
                "    esd doctor      Audit consumption, solar PV & weather data health\n"
                "    esd calculate   Auto-curate + optimize -> 6 CSV/HTML files in .output/\n"
                "                    (--refresh updates cache; --curate-only skips opt)\n"
                "    esd clean       Remove generated files from .output/.curated/weather\n"
                "  Global flags: -V/--version, -h/--help (run bare 'esd' for this guide)"
            ),
            "help_workflow_heading": "QUICK WORKFLOW & OUTPUT DELIVERABLES",
            "init_clean_cleared": "Cleared {count} file(s) from .output",
            "init_clean_ready": "Ready & clean",
            "init_lbl_lang": "Language",
            "init_lbl_output": "Output Directory",
            "init_lbl_precision": "Share Precision",
            "init_lbl_timestamp": "Timestamp",
            "init_prec_desc": "{precision} decimal(s) (e.g. {example}, sums to 100%)",
            "init_reinit": "Workspace successfully re-initialized with language '{language}'.",
            "init_success": "Workspace successfully initialized with language '{language}'.",
            "init_title_reinit": "✓ Re-initialized Successfully",
            "init_title_success": "✓ Initialized Successfully",
            "msg_config_updated": "✓ Configuration updated successfully.",
            "no_files_cleaned": "No files found to clean in target directories.",
            "not_initialized_warning": "[yellow]Warning: Workspace has not been initialized yet. Run 'esd init' to configure settings.[/yellow]",
            "prompt_cleanup_confirm": "Are you sure you want to delete {count} files in {dir}?",
            "prompt_lang": "Select language preference ('en' for English, 'es' for Spanish)",
            "prompt_precision": "Select share percentage precision (0, 1, or 2 decimal places)",
        },
        "status": {
            "status_curating": "Reconciling and curating time-series data...",
            "status_doctor": "Scanning and verifying consumption and generation datasets...",
            "status_step_1": "Ingesting and verifying input datasets...",
            "status_step_2": "Reconciling inverter and solar time-series...",
            "status_step_3": "Solving RD 244/2019 LP optimization...",
            "status_step_4": "Generating multi-format deliverables...",
            "status_comparing": "Ingesting DATADIS CSVs and calculating multi-year comparisons...",
            "status_summarizing": "Ingesting DATADIS CSVs and aggregating community shares...",
        },
        "doctor": {
            "doc_adv_clean": "[green]• Dataset is clean and ready. You can safely run 'esd calculate'.[/green]",
            "doc_adv_cons_gaps": "[yellow]• Consumption Gaps:[/yellow] {id} has {hours} missing hours. Download updated DATADIS CSV for complete billing periods.",
            "doc_adv_gen_gaps": "[yellow]• Generation Gaps:[/yellow] Huawei solar series has {hours} missing hours. Check inverter log exports.",
            "doc_adv_inactive": "[yellow]• Inactive Meter:[/yellow] {id} has {pct}% zero readings. In optimization, its β coefficient will be 0.00% to protect community solar energy.",
            "doc_adv_weather_coverage": "[yellow]• Incomplete Weather Coverage:[/yellow] Weather data does not fully cover the calculation period ({period}). Run 'esd calculate --refresh' for missing years.",
            "doc_adv_weather_gaps": "[yellow]• Weather Gaps:[/yellow] Open-Meteo weather series has {hours} missing hours. Re-run 'esd calculate --refresh' to re-fetch.",
            "doc_adv_weather_missing": "[yellow]• Missing Weather Data:[/yellow] No weather data found in {dir}. Run 'esd calculate --refresh' to download historical archives.",
            "doc_lbl_common_hours": "Common Hours:",
            "doc_lbl_healthy": "Healthy",
            "doc_lbl_overlap_range": "Overlap Date Range:",
            "doc_lbl_participating_cups": "Participating CUPS:",
            "doc_lbl_ready_calc": "Ready to Calculate:",
            "doc_lbl_zero_pct": "Zero %",
            "doc_more_gaps": "+{count} more gaps",
            "doc_no": "No",
            "doc_source_huawei": "Huawei PV Generation",
            "doc_source_weather": "Open-Meteo Weather",
            "doc_status_error": "✗ CRITICAL DATA ISSUES DETECTED",
            "doc_status_ok": "✓ ALL DATA HEALTHY & SYNCHRONIZED",
            "doc_status_warning": "⚠ DATA USABLE WITH DIAGNOSTIC WARNINGS",
            "doc_title_advice": "[bold yellow]💡 Actionable Diagnostic Insights[/bold yellow]",
            "doc_title_banner": "🩺 ESD DATA DOCTOR DIAGNOSTIC REPORT",
            "doc_title_consumption": "📥 Consumption Data Health per CUPS (DATADIS)",
            "doc_verbose_hint": "Use --verbose to view all",
            "doc_yes": "Yes",
            "lbl_date_range": "Date Range",
        },
        "curate": {
            "col_curated_cons": "Curated Demand (kWh)",
            "col_primary": "Primary",
            "col_reconciled_hours": "Reconciled",
            "col_use": "Use / Description",
            "curate_success_title": "✓ Curation & Data Reconciliation Complete",
            "lbl_reconciled_hours": "Reconciled Hours (Fake Zeros Fixed)",
            "lbl_recovered_kwh": "Recovered Hidden Consumption",
            "title_curate_summary": "✨ DATA RECONCILIATION & TIME-SERIES CURATION",
        },
        "weather": {
            "err_coords_required": "Coordinates are required: specify --latitude and --longitude, provide coordinates in cups.json, or configure them via 'esd config --latitude <lat> --longitude <lon>'.",
            "weather_lbl_cloud": "Cloud Cover",
            "weather_lbl_coords": "Coordinates",
            "weather_lbl_dest": "Destination File",
            "weather_lbl_period": "Observation Period",
            "weather_lbl_temp": "Temperature",
            "weather_lbl_year": "Year & Records",
            "weather_overwritten": "[yellow](overwritten existing file)[/yellow]",
        },
        "tables": {
            "col_annual_avg": "Annual Avg",
            "col_cov_rate": "Coverage %",
            "col_cups": "CUPS",
            "col_cups_desc": "CUPS / Use",
            "col_gain_vs_baseline": "Gain vs Base",
            "col_modality": "Modality",
            "col_sc_rate": "Self-Cons %",
            "col_self_cons": "Self-Cons (kWh)",
            "col_setting": "Setting",
            "col_strategy": "Strategy",
            "col_value": "Value",
            "desc_coefficients_matrix": "Regulatory allocation schedule (RD 244/2019) • Sum per month: 100%",
            "lbl_baseline": "Baseline",
            "lbl_directory": "Directory",
            "lbl_doctor_files": "Files",
            "lbl_doctor_gap_end": "Gap End",
            "lbl_doctor_gap_start": "Gap Start",
            "lbl_doctor_gaps": "Gaps",
            "lbl_doctor_missing": "Missing",
            "lbl_doctor_readings": "Readings",
            "lbl_doctor_series": "Series",
            "lbl_doctor_source": "Source",
            "lbl_doctor_status": "Status",
            "lbl_license": "License",
            "lbl_sc_current": "Current (No Share)",
            "lbl_sc_fortnight": "Fortnight Share",
            "lbl_sc_hourly": "Hourly Share (Order TED)",
            "lbl_sc_monthly": "Monthly Share (RD 244/2019)",
            "lbl_solar_hours_cov": "Coverage (Solar Hours)",
            "lbl_solar_hours_demand": "Demand (Solar Hours)",
            "lbl_solar_hours_gen": "Solar Hours Gen",
            "lbl_source": "Source",
            "lbl_supply_points": "Supply Points (CUPS)",
            "lbl_total": "Total",
            "lbl_total_cons": "Total Community Demand",
            "lbl_total_gen": "Total PV Generation",
            "lbl_total_hours": "Analyzed Hours",
            "lbl_total_rd244": "TOTAL (RD 244/2019)",
            "lbl_total_sc": "Total Self-Consumed",
            "lbl_total_surplus": "Total Solar Surplus",
            "lbl_version": "Version",
            "title_cleanup": "🧹 Cleanup Summary",
            "title_coefficients_matrix": "📅 Suggested Electricity Distribution Share Matrix (β_i %)",
            "title_community_summary": "⚡ COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY",
            "title_config": "⚙️ Active Configuration",
            "title_doctor_gaps": "⚠️ Detected Missing Interval Gaps",
            "title_doctor_sources": "📊 Data Sources (Generation & Weather)",
            "title_monthly_trajectory": "📈 Month-by-Month Community Energy Trajectory",
            "title_sc_progression": "⚡ Self-Consumption Modality Progression",
            "title_weather": "☀️ OPEN-METEO HOURLY WEATHER INGESTION",
        },
        "export": {
            "export_footer_label": "Exported",
            "export_success_title": "✓ Exports Generated Successfully",
        },
        "analytics": {
            "summary_validation_title": "⚠️ Input File Validation Warnings",
            "summary_col_file": "File",
            "summary_col_status": "Status",
            "summary_col_issue": "Issue Details",
            "summary_overview_title": "🏢 Residential Community Energy Overview",
            "summary_total_consumption": "Total Community Consumption:",
            "summary_active_cups": "Active CUPS Meters:",
            "summary_files_processed": "CSV Files Processed:",
            "summary_date_range": "Date Range:",
            "summary_peak_month": "Peak Month:",
            "summary_total_readings": "Total Hourly Readings:",
            "summary_meters_count": "{count} meters",
            "summary_files_count": "{count} files",
            "summary_hours_count": "{count} hours",
            "summary_annual_title": "📅 Annual Summary — Year {year}",
            "summary_community_total_label": "Community Total: {total}",
            "summary_col_rank": "#",
            "summary_col_cups": "CUPS",
            "summary_col_use": "Use",
            "summary_col_consumption": "Consumption",
            "summary_col_share": "Share %",
            "summary_col_distribution": "Share",
            "summary_col_total": "TOTAL",
            "summary_annual_legend": "Legend: ★ Dominant Community Load (>30%) | (0) Inactive Meter (<1 kWh)",
            "summary_monthly_timeline_title": "📊 Monthly Community Timeline & Top Contributor",
            "summary_col_period": "Period",
            "summary_col_community_total": "Community Total",
            "summary_col_top_cups": "Top Consumer CUPS",
            "summary_col_top_share": "Top Share",
            "summary_period_title": "📆 Period {period}",
            "summary_cups_trajectory_title": "🔍 Monthly Trajectory for CUPS: {cups}",
            "summary_col_cups_kwh": "CUPS kWh",
            "summary_col_community_kwh": "Community kWh",
            "summary_insights_title": "💡 Community Key Insights & Observations",
            "summary_dominant_insight": "• [bold magenta]Dominant Community Consumer:[/] CUPS [bold]{cups}[/bold] accounts for [bold yellow]{pct}%[/bold yellow] of community electricity ({kwh}).",
            "summary_zero_insight": "• [dim white]Zero / Negligible Consumption:[/] {count} supply point(s) recorded under 1 kWh: [dim]{cups}[/dim].",
            "summary_seasonality_insight": "• [cyan]Seasonality & Peaks:[/] Peak consumption occurred in [bold yellow]{peak_month}[/bold yellow] ({peak_kwh}), while lowest was in [bold cyan]{lowest_month}[/bold cyan] ({lowest_kwh}).",
            "summary_md_doc_title": "# DATADIS Residential Community Energy Report",
            "summary_md_generated_at": "**Generated:** {datetime}",
            "summary_md_version_label": "Version",
            "summary_md_section_overview": "## 1. Executive Summary",
            "summary_md_section_annual": "## 2. Annual Consumption & CUPS Percentage Shares",
            "summary_md_section_timeline": "## 3. Monthly Community Timeline & Peak Contributors",
            "summary_md_section_monthly": "## 4. Detailed Monthly CUPS Breakdown",
            "summary_md_section_insights": "## 5. Key Community Observations",
            "summary_md_metric_col": "Metric",
            "summary_md_value_col": "Value",
            "compare_overview_title": "⚡ Multi-Year Community Energy Comparison",
            "compare_years_label": "Years Compared:",
            "compare_overall_change": "Overall Energy Variation:",
            "compare_status_saving": "Community reduced consumption by [bold green]{diff_kwh}[/bold green] ([bold green]{pct}%[/bold green])",
            "compare_status_increase": "Community increased consumption by [bold red]{diff_kwh}[/bold red] ([bold red]+{pct}%[/bold red])",
            "compare_status_stable": "Community consumption remained unchanged ({diff_kwh})",
            "compare_max_decrease": "Biggest Monthly Reduction:",
            "compare_max_increase": "Biggest Monthly Surge:",
            "compare_top_saver": "Top Energy Reducer CUPS:",
            "compare_top_increaser": "Top Energy Increaser CUPS:",
            "compare_monthly_title": "📅 Monthly Community Consumption & Year-over-Year Variation",
            "compare_month_col": "Month",
            "compare_diff_col": "Diff (kWh)",
            "compare_var_col": "Variation",
            "compare_trend_col": "Trend",
            "compare_trend_reduced": "▼ Reduced",
            "compare_trend_increased": "▲ Increased",
            "compare_trend_equal": "— Stable",
            "compare_cups_title": "👥 Supply Points (CUPS) Year-over-Year Evolution",
            "compare_cups_col": "CUPS",
            "compare_no_data": "No data",
            "compare_comparable_period_note": "Comparable period: {period} ({months} months)",
            "compare_no_comparable_months": "No complete overlapping months found across all selected years.",
            "compare_excluded_months_note": "{count} month(s) excluded due to missing or incomplete data ({months})",
            "compare_charts_generated": "Generated {count} monthly comparison chart(s) in: [cyan]{path}[/cyan]",
            "compare_md_title": "# ⚡ Multi-Year Community Energy Comparison ({years})",
            "compare_md_overview": "## 1. Executive Comparison Overview",
            "compare_md_monthly": "## 2. Month-by-Month Consumption Comparison",
            "compare_md_cups": "## 3. Individual CUPS Evolution",
            "compare_md_charts": "## 4. Visual Monthly Trajectories by CUPS",
            "compare_md_insights": "## 5. Key Comparison Takeaways",
            "compare_md_community_consumption": "{year} Community Consumption",
            "compare_md_full_year_suffix": "{total} full year",
            "chart_cups_title": "CUPS: {cups}",
            "chart_subtitle": "Monthly Energy Consumption Comparison ({years})",
            "chart_month_axis": "Month",
            "chart_kwh_axis": "Consumption (kWh)",
            "chart_community_title": "Community Total Energy Consumption",
            "chart_legend_total": "Total: {total}",
        },
    },
    "es": {
        "app": {
            "app_subtitle": "Plataforma Unificada de Análisis de Consumo y Reparto Solar Colectivo",
            "app_title": "☀️ DISTRIBUIDOR DE ENERGÍA COMPARTIDA (esd)",
            "overview_heading": "DESCRIPCIÓN GENERAL",
            "overview_text": "Plataforma unificada para análisis de consumo comunitario y optimización de reparto FV\nbajo RD 244/2019 y Orden TED/1247/2021. Ejecuta resúmenes y comparativas interanuales\nsolo con consumo DATADIS, o calcula coeficientes óptimos β_i con producción solar.",
        },
        "cli": {
            "available_commands": "COMANDOS DISPONIBLES",
            "cleaned_files": "Se han eliminado {count} archivo(s) de los directorios de destino.",
            "cleanup_aborted": "Limpieza cancelada por el usuario.",
            "cmd_calculate_desc": "Calcular cuotas óptimas mensuales, quincenales y horarias (admite --refresh y --curate-only).",
            "cmd_clean_desc": "Eliminar datos generados de los directorios .output, .curated y .input/weather.",
            "cmd_compare_desc": "Comparar consumo y variaciones entre varios años con comparativa homogénea de meses completos.",
            "cmd_config_desc": "Inspeccionar o actualizar la configuración persistente y las rutas de directorios.",
            "cmd_desc": "Descripción",
            "cmd_doctor_desc": "Auditar archivos de entrada para detectar huecos, intervalos faltantes e incoherencias de datos.",
            "cmd_init_desc": "Inicializar directorios, configurar preferencia de idioma y guardar ajustes.",
            "cmd_name": "Comando",
            "cmd_summary_desc": "Agregar consumo por año y mes, mostrar tablas de reparto y exportar informes Markdown.",
            "err_lat_range": "La latitud debe estar entre -90.0 y 90.0 (valor recibido: {val}).",
            "err_lon_range": "La longitud debe estar entre -180.0 y 180.0 (valor recibido: {val}).",
            "help_workflow_body": (
                "  Análisis de Consumo (sin archivos de generación FV requeridos):\n"
                "    esd summary     Cuotas 100.00% anuales/mensuales, insignias ★/(0) + .md\n"
                "    esd compare     Comparativa interanual [Inc] y gráficos SVG en .output/\n"
                "  Reparto Solar Colectivo (RD 244/2019 y Orden TED/1247/2021):\n"
                "    esd doctor      Auditar salud de consumo, generación FV y clima\n"
                "    esd calculate   Auto-curado + optimización -> 6 archivos en .output/\n"
                "                    (--refresh actualiza caché; --curate-only solo curado)\n"
                "    esd clean       Limpiar archivos generados de .output/.curated/clima\n"
                "  Flags globales: -V/--version, -h/--help ('esd' sin args abre esta guía)"
            ),
            "help_workflow_heading": "FLUJO RÁPIDO Y ENTREGABLES",
            "init_clean_cleared": "Se eliminaron {count} archivo(s) de .output",
            "init_clean_ready": "Listo y limpio",
            "init_lbl_lang": "Idioma",
            "init_lbl_output": "Directorio de salida",
            "init_lbl_precision": "Precisión de reparto",
            "init_lbl_timestamp": "Fecha y hora",
            "init_prec_desc": "{precision} decimal(es) (ej. {example}, suma 100%)",
            "init_reinit": "Espacio de trabajo reinicializado correctamente con idioma '{language}'.",
            "init_success": "Espacio de trabajo inicializado correctamente con idioma '{language}'.",
            "init_title_reinit": "✓ Reinicializado Correctamente",
            "init_title_success": "✓ Inicializado Correctamente",
            "msg_config_updated": "✓ Configuración actualizada correctamente.",
            "no_files_cleaned": "No se encontraron archivos para limpiar en los directorios de destino.",
            "not_initialized_warning": "[yellow]Aviso: El espacio de trabajo aún no ha sido inicializado. Ejecute 'esd init' para configurarlo.[/yellow]",
            "prompt_cleanup_confirm": "¿Está seguro de que desea eliminar {count} archivos en {dir}?",
            "prompt_lang": "Seleccione idioma preferido ('en' para inglés, 'es' para español)",
            "prompt_precision": "Seleccione precisión de porcentaje de reparto (0, 1 o 2 decimales)",
        },
        "status": {
            "status_curating": "Reconciliando y curando series temporales de datos...",
            "status_doctor": "Analizando y verificando conjuntos de datos de consumo y generación...",
            "status_step_1": "Ingestando y verificando datos de entrada...",
            "status_step_2": "Reconciliando series temporales del inversor...",
            "status_step_3": "Resolviendo optimización PL según RD 244/2019...",
            "status_step_4": "Generando entregables multiformato...",
            "status_comparing": "Cargando CSVs de DATADIS y calculando comparativas interanuales...",
            "status_summarizing": "Cargando archivos CSV de DATADIS y agregando porcentajes comunitarios...",
        },
        "doctor": {
            "doc_adv_clean": "[green]• Conjunto de datos limpio y listo. Puede ejecutar 'esd calculate' con total seguridad.[/green]",
            "doc_adv_cons_gaps": "[yellow]• Huecos en Consumo:[/yellow] {id} tiene {hours} horas faltantes. Descargue un CSV actualizado de DATADIS para periodos de facturación completos.",
            "doc_adv_gen_gaps": "[yellow]• Huecos en Generación:[/yellow] La serie solar de Huawei tiene {hours} horas faltantes. Revise las exportaciones del inversor.",
            "doc_adv_inactive": "[yellow]• Contador Inactivo:[/yellow] {id} tiene un {pct}% de lecturas a cero. En la optimización, su coeficiente β será 0.00% para proteger la energía solar comunitaria.",
            "doc_adv_weather_coverage": "[yellow]• Cobertura Meteorológica Incompleta:[/yellow] Los datos meteorológicos no cubren todo el periodo de cálculo ({period}). Ejecute 'esd calculate --refresh' para los años faltantes.",
            "doc_adv_weather_gaps": "[yellow]• Huecos Meteorológicos:[/yellow] La serie meteorológica de Open-Meteo tiene {hours} horas faltantes. Vuelva a ejecutar 'esd calculate --refresh' para descargarla.",
            "doc_adv_weather_missing": "[yellow]• Faltan Datos Meteorológicos:[/yellow] No se encontraron archivos en {dir}. Ejecute 'esd calculate --refresh' para descargar el histórico.",
            "doc_lbl_common_hours": "Horas Comunes:",
            "doc_lbl_healthy": "Correcto",
            "doc_lbl_overlap_range": "Rango de Fechas:",
            "doc_lbl_participating_cups": "Puntos Suministro:",
            "doc_lbl_ready_calc": "Listo para Calcular:",
            "doc_lbl_zero_pct": "% Ceros",
            "doc_more_gaps": "+{count} huecos más",
            "doc_no": "No",
            "doc_source_huawei": "Gen. Solar FV Huawei",
            "doc_source_weather": "Met. Open-Meteo",
            "doc_status_error": "✗ DETECTADAS INCIDENCIAS CRÍTICAS EN LOS DATOS",
            "doc_status_ok": "✓ TODOS LOS DATOS CORRECTOS Y SINCRONIZADOS",
            "doc_status_warning": "⚠ DATOS UTILIZABLES CON AVISOS DE DIAGNÓSTICO",
            "doc_title_advice": "[bold yellow]💡 Recomendaciones y Diagnóstico[/bold yellow]",
            "doc_title_banner": "🩺 INFORME DE DIAGNÓSTICO ESD DATA DOCTOR",
            "doc_title_consumption": "📥 Estado de Datos de Consumo por CUPS (DATADIS)",
            "doc_verbose_hint": "Use --verbose para ver todos",
            "doc_yes": "Sí",
            "lbl_date_range": "Rango de Fechas",
        },
        "curate": {
            "col_curated_cons": "Demanda Curada (kWh)",
            "col_primary": "Principal",
            "col_reconciled_hours": "Reconciliadas",
            "col_use": "Uso / Descripción",
            "curate_success_title": "✓ Reconciliación y Curado de Datos Completado",
            "lbl_reconciled_hours": "Horas Reconciliadas (Ceros Falsos Corregidos)",
            "lbl_recovered_kwh": "Consumo Oculto Recuperado",
            "title_curate_summary": "✨ RECONCILIACIÓN Y CURADO DE SERIES TEMPORALES",
        },
        "weather": {
            "err_coords_required": "Se requieren coordenadas: especifique --latitude y --longitude, indique coordenadas en cups.json, o configúrelas con 'esd config --latitude <lat> --longitude <lon>'.",
            "weather_lbl_cloud": "Nubosidad",
            "weather_lbl_coords": "Coordenadas",
            "weather_lbl_dest": "Archivo de Destino",
            "weather_lbl_period": "Periodo de Observación",
            "weather_lbl_temp": "Temperatura",
            "weather_lbl_year": "Año y Registros",
            "weather_overwritten": "[yellow](archivo existente sobrescrito)[/yellow]",
        },
        "tables": {
            "col_annual_avg": "Media Anual",
            "col_cov_rate": "% Cob",
            "col_cups": "CUPS",
            "col_cups_desc": "CUPS / Uso",
            "col_gain_vs_baseline": "Ganancia vs Base",
            "col_modality": "Modalidad",
            "col_sc_rate": "% Auto",
            "col_self_cons": "Autocons (kWh)",
            "col_setting": "Parámetro",
            "col_strategy": "Estrategia",
            "col_value": "Valor",
            "desc_coefficients_matrix": "Acuerdo regulatorio de reparto (RD 244/2019) • Suma mensual: 100%",
            "lbl_baseline": "Base de referencia",
            "lbl_directory": "Directorio",
            "lbl_doctor_files": "Archivos",
            "lbl_doctor_gap_end": "Fin Hueco",
            "lbl_doctor_gap_start": "Inicio Hueco",
            "lbl_doctor_gaps": "Huecos",
            "lbl_doctor_missing": "Faltante",
            "lbl_doctor_readings": "Lecturas",
            "lbl_doctor_series": "Serie",
            "lbl_doctor_source": "Origen",
            "lbl_doctor_status": "Estado",
            "lbl_license": "Licencia",
            "lbl_sc_current": "Actual (Sin Reparto)",
            "lbl_sc_fortnight": "Reparto Quincenal",
            "lbl_sc_hourly": "Reparto Horario (Orden TED)",
            "lbl_sc_monthly": "Reparto Mensual (RD 244/2019)",
            "lbl_solar_hours_cov": "Cobertura (Horas Sol)",
            "lbl_solar_hours_demand": "Demanda (Horas Sol)",
            "lbl_solar_hours_gen": "Gen. Horas Sol",
            "lbl_source": "Repositorio",
            "lbl_supply_points": "Puntos de Suministro (CUPS)",
            "lbl_total": "Total",
            "lbl_total_cons": "Demanda Total Comunidad",
            "lbl_total_gen": "Generación FV Total",
            "lbl_total_hours": "Horas Analizadas",
            "lbl_total_rd244": "TOTAL (RD 244/2019)",
            "lbl_total_sc": "Autoconsumo Total",
            "lbl_total_surplus": "Excedentes Totales a Red",
            "lbl_version": "Versión",
            "title_cleanup": "🧹 Resumen de Limpieza",
            "title_coefficients_matrix": "📅 Matriz Sugerida de Coeficientes de Reparto (β_i %)",
            "title_community_summary": "⚡ RESUMEN DE LA COMUNIDAD DE AUTOCONSUMO COLECTIVO",
            "title_config": "⚙️ Configuración Activa",
            "title_doctor_gaps": "⚠️ Huecos e Intervalos Faltantes Detectados",
            "title_doctor_sources": "📊 Orígenes de Datos (Generación y Clima)",
            "title_monthly_trajectory": "📈 Trayectoria Energética Mensual de la Comunidad",
            "title_sc_progression": "⚡ Progresión del Autoconsumo Colectivo",
            "title_weather": "☀️ INGESTA METEOROLÓGICA HORARIA OPEN-METEO",
        },
        "export": {
            "export_footer_label": "Exportado",
            "export_success_title": "✓ Informes Generados Correctamente",
        },
        "analytics": {
            "summary_validation_title": "⚠️ Avisos de Validación de Archivos de Entrada",
            "summary_col_file": "Archivo",
            "summary_col_status": "Estado",
            "summary_col_issue": "Detalle de la Incidencia",
            "summary_overview_title": "🏢 Resumen Energético de la Comunidad de Propietarios",
            "summary_total_consumption": "Consumo Total de la Comunidad:",
            "summary_active_cups": "Contadores CUPS Activos:",
            "summary_files_processed": "Archivos CSV Procesados:",
            "summary_date_range": "Rango de Fechas:",
            "summary_peak_month": "Mes de Máximo Consumo:",
            "summary_total_readings": "Total de Lecturas Horarias:",
            "summary_meters_count": "{count} contadores",
            "summary_files_count": "{count} archivos",
            "summary_hours_count": "{count} horas",
            "summary_annual_title": "📅 Resumen Anual — Año {year}",
            "summary_community_total_label": "Total Comunidad: {total}",
            "summary_col_rank": "#",
            "summary_col_cups": "CUPS",
            "summary_col_use": "Uso",
            "summary_col_consumption": "Consumo",
            "summary_col_share": "% Cuota",
            "summary_col_distribution": "Reparto",
            "summary_col_total": "TOTAL",
            "summary_annual_legend": "Leyenda: ★ Carga Principal Comunitaria (>30%) | (0) Contador Inactivo (<1 kWh)",
            "summary_monthly_timeline_title": "📊 Cronología Mensual de la Comunidad y Mayor Consumidor",
            "summary_col_period": "Periodo",
            "summary_col_community_total": "Total Comunidad",
            "summary_col_top_cups": "CUPS Mayor Consumidor",
            "summary_col_top_share": "% Mayor Consumo",
            "summary_period_title": "📆 Periodo {period}",
            "summary_cups_trajectory_title": "🔍 Trayectoria Mensual para el CUPS: {cups}",
            "summary_col_cups_kwh": "kWh CUPS",
            "summary_col_community_kwh": "kWh Comunidad",
            "summary_insights_title": "💡 Conclusiones y Observaciones Clave de la Comunidad",
            "summary_dominant_insight": "• [bold magenta]Consumidor Dominante de la Comunidad:[/] El CUPS [bold]{cups}[/bold] representa el [bold yellow]{pct}%[/bold yellow] de la electricidad comunitaria ({kwh}).",
            "summary_zero_insight": "• [dim white]Consumo Nulo o Despreciable:[/] {count} punto(s) de suministro registraron menos de 1 kWh: [dim]{cups}[/dim].",
            "summary_seasonality_insight": "• [cyan]Estacionalidad y Picos:[/] El pico de consumo se registró en [bold yellow]{peak_month}[/bold yellow] ({peak_kwh}), mientras que el mínimo fue en [bold cyan]{lowest_month}[/bold cyan] ({lowest_kwh}).",
            "summary_md_doc_title": "# Informe Energético de la Comunidad de Propietarios (DATADIS)",
            "summary_md_generated_at": "**Fecha de generación:** {datetime}",
            "summary_md_version_label": "Versión",
            "summary_md_section_overview": "## 1. Resumen Ejecutivo",
            "summary_md_section_annual": "## 2. Consumo Anual y Porcentajes de Reparto por CUPS",
            "summary_md_section_timeline": "## 3. Cronología Mensual Comunitaria y Mayores Contribuyentes",
            "summary_md_section_monthly": "## 4. Desglose Mensual Detallado por CUPS",
            "summary_md_section_insights": "## 5. Observaciones Clave de la Comunidad",
            "summary_md_metric_col": "Métrica",
            "summary_md_value_col": "Valor",
            "compare_overview_title": "⚡ Comparativa Energética Interanual de la Comunidad",
            "compare_years_label": "Años Comparados:",
            "compare_overall_change": "Variación Energética Total:",
            "compare_status_saving": "La comunidad redujo su consumo en [bold green]{diff_kwh}[/bold green] ([bold green]{pct}%[/bold green])",
            "compare_status_increase": "La comunidad aumentó su consumo en [bold red]{diff_kwh}[/bold red] ([bold red]+{pct}%[/bold red])",
            "compare_status_stable": "El consumo de la comunidad se mantuvo sin cambios ({diff_kwh})",
            "compare_max_decrease": "Mes con Mayor Reducción:",
            "compare_max_increase": "Mes con Mayor Incremento:",
            "compare_top_saver": "CUPS con Mayor Reducción:",
            "compare_top_increaser": "CUPS con Mayor Incremento:",
            "compare_monthly_title": "📅 Consumo Mensual y Variación Interanual de la Comunidad",
            "compare_month_col": "Mes",
            "compare_diff_col": "Dif. (kWh)",
            "compare_var_col": "Variación",
            "compare_trend_col": "Tendencia",
            "compare_trend_reduced": "▼ Reducción",
            "compare_trend_increased": "▲ Incremento",
            "compare_trend_equal": "— Estable",
            "compare_cups_title": "👥 Evolución Interanual por Punto de Suministro (CUPS)",
            "compare_cups_col": "CUPS",
            "compare_no_data": "Sin datos",
            "compare_comparable_period_note": "Periodo comparable: {period} ({months} meses)",
            "compare_no_comparable_months": "No se encontraron meses completos coincidentes entre los años seleccionados.",
            "compare_excluded_months_note": "{count} mes(es) excluido(s) por datos incompletos o ausentes ({months})",
            "compare_charts_generated": "Se han generado {count} gráfico(s) comparativo(s) en: [cyan]{path}[/cyan]",
            "compare_md_title": "# ⚡ Comparativa Energética Interanual de la Comunidad ({years})",
            "compare_md_overview": "## 1. Resumen Ejecutivo de la Comparativa",
            "compare_md_monthly": "## 2. Comparativa de Consumo Mes a Mes",
            "compare_md_cups": "## 3. Evolución Individual por Punto de Suministro (CUPS)",
            "compare_md_charts": "## 4. Gráficos Comparativos Mensuales por CUPS",
            "compare_md_insights": "## 5. Conclusiones Clave de la Comparativa",
            "compare_md_community_consumption": "Consumo Comunidad {year}",
            "compare_md_full_year_suffix": "{total} año completo",
            "chart_cups_title": "CUPS: {cups}",
            "chart_subtitle": "Comparativa Mensual de Consumo Energético ({years})",
            "chart_month_axis": "Mes",
            "chart_kwh_axis": "Consumo (kWh)",
            "chart_community_title": "Consumo Total de la Comunidad",
            "chart_legend_total": "Total: {total}",
        },
    },
}


def _build_translation_catalog() -> dict[str, dict[str, str]]:
    """Compile structured namespaces into flat catalog with dot-notation and flat key support."""
    catalog: dict[str, dict[str, str]] = {}
    for lang, namespaces in STRUCTURED_TRANSLATIONS.items():
        lang_catalog: dict[str, str] = {}
        for ns, entries in namespaces.items():
            for key, val in entries.items():
                lang_catalog[f"{ns}.{key}"] = val
                lang_catalog[key] = val
        catalog[lang] = lang_catalog
    return catalog


TRANSLATIONS: dict[str, dict[str, str]] = _build_translation_catalog()

MONTH_NAMES: dict[str, dict[int, str]] = {
    "en": {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    },
    "es": {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    },
}

MONTH_NAMES_SHORT: dict[str, dict[int, str]] = {
    "en": {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec",
    },
    "es": {
        1: "Ene",
        2: "Feb",
        3: "Mar",
        4: "Abr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dic",
    },
}


def get_month_name(month: int, lang: str | None = None, short: bool = False) -> str:
    """Return the localized month name or 3-letter abbreviation for month 1..12."""
    selected_lang = (lang or get_language()).lower()
    norm_lang = "es" if selected_lang.startswith("es") else "en"
    mapping = MONTH_NAMES_SHORT if short else MONTH_NAMES
    return mapping[norm_lang].get(month, f"M{month:02d}")


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Retrieve translated message for a given key, interpolating any keyword arguments.

    Args:
        key: Unique string identifier for the message (namespaced or legacy flat key).
        lang: Language code ('en' or 'es'). If None, uses active configured language.
        **kwargs: Values to interpolate into the translated string template.

    Returns:
        Interpolated translated string.
    """
    selected_lang = (lang or get_language()).lower()
    if selected_lang not in TRANSLATIONS:
        selected_lang = "en"

    template = TRANSLATIONS[selected_lang].get(key)
    if template is None:
        template = TRANSLATIONS["en"].get(key, key)

    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError, ValueError:
            return template

    return template
