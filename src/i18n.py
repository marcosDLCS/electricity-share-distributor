"""Internationalization (i18n) module supporting English and Spanish localization for esd."""

from __future__ import annotations

from typing import Any

from src.config import get_language

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # App banner & overview
        "app_title": "☀️ ELECTRICITY SHARE DISTRIBUTOR (esd)",
        "app_subtitle": "Collective Photovoltaic Allocation & Optimization CLI (RD 244/2019)",
        "overview_heading": "OVERVIEW",
        "overview_text": (
            "Calculates optimal electricity distribution coefficients (β_i) for shared PV self-consumption\n"
            "in Spain under Real Decreto 244/2019, combining DATADIS hourly consumption curves and\n"
            "Huawei FusionSolar PV generation exports to maximize collective self-consumption."
        ),
        # Commands
        "available_commands": "AVAILABLE COMMANDS",
        "cmd_name": "Command",
        "cmd_desc": "Description",
        "cmd_calculate_desc": "Ingest consumption and generation curves, optimize monthly coefficients, and display results.",
        "cmd_doctor_desc": "Audit input files to detect gaps, missing hourly intervals, and data inconsistencies.",
        "cmd_init_desc": "Initialize application directories, configure language preference, and persist settings.",
        "cmd_config_desc": "Inspect or update persistent application configuration and directory paths.",
        "cmd_cleanup_desc": "Remove generated export reports and clear files from the .output directory.",
        "cmd_help_desc": "Display comprehensive command reference, input structure guidelines, and examples.",
        "cmd_version_desc": "Display the active CalVer version (YYYY.MM.NNN) and exit.",
        # Options
        "opt_name": "Option",
        "opt_type": "Type",
        "opt_default": "Default",
        "opt_desc": "Description",
        "opt_lang": "Language code override ('en' or 'es').",
        "opt_consumption_dir": "Directory containing DATADIS hourly consumption CSV files.",
        "opt_generation_dir": "Directory containing Huawei FusionSolar generation Excel files.",
        "opt_output_dir": "Directory where summary files and exports will be written.",
        "opt_year": "Filter analysis to a specific calendar year.",
        "opt_month": "Filter analysis to a specific month (1-12).",
        "opt_format": "Export format: 'table', 'csv', 'json', 'markdown', or 'all'.",
        "opt_force": "Execute cleanup without interactive confirmation.",
        # Messages
        "init_success": "Workspace successfully initialized with language '{language}'.",
        "init_reinit": "Workspace successfully re-initialized with language '{language}'.",
        "init_already": "Workspace was already initialized at {timestamp}.",
        "not_initialized_warning": (
            "[yellow]Warning: Workspace has not been initialized yet. Run 'esd init' to configure settings.[/yellow]"
        ),
        "version_banner": "Electricity Share Distributor (esd) version {version}",
        "cleaning_output": "Cleaning output directory: {output_dir}",
        "cleaned_files": "Removed {count} file(s) from output directory.",
        "no_files_cleaned": "No files found to clean in output directory.",
        # Spinners & CLI Messages
        "status_ingesting": "Ingesting and synchronizing curves from {consumption_dir} and {generation_dir}...",
        "status_optimizing": "Solving RD 244/2019 optimization linear programs...",
        "status_doctor": "Scanning and verifying consumption and generation datasets...",
        "prompt_lang": "Select language preference ('en' for English, 'es' for Spanish)",
        "prompt_precision": "Select share percentage precision (0, 1, or 2 decimal places)",
        # Table & View Labels
        "title_community_summary": "⚡ COLLECTIVE SELF-CONSUMPTION COMMUNITY SUMMARY",
        "title_monthly_coefficients": "📅 Monthly Coefficient Proposals (β_i): {month}",
        "title_monthly_trajectory": "📈 Month-by-Month Community Energy Trajectory",
        "title_strategy_comparison": "⚖️ Allocation Strategy Efficiency Comparison",
        "lbl_supply_points": "Supply Points (CUPS)",
        "lbl_date_range": "Date Range",
        "lbl_total_hours": "Analyzed Hours",
        "lbl_total_gen": "Total PV Generation",
        "lbl_total_cons": "Total Community Demand",
        "lbl_total_sc": "Total Self-Consumed",
        "lbl_total_surplus": "Total Solar Surplus",
        "lbl_collective_sc_rate": "Self-Consumption Efficiency",
        "lbl_collective_cov_rate": "Solar Demand Coverage",
        "lbl_total": "Total",
        "lbl_optimal_strat": "★ Optimal (RD 244/2019)",
        "lbl_baseline": "Baseline",
        "col_rank": "Rank",
        "col_cups": "CUPS",
        "col_demand": "Demand (kWh)",
        "col_solar_alloc": "Alloc (kWh)",
        "col_self_cons": "Self-Cons (kWh)",
        "col_surplus": "Surplus (kWh)",
        "col_grid": "Grid (kWh)",
        "col_beta": "Beta (β)",
        "col_share_bar": "Share",
        "col_month": "Month",
        "col_generation": "Solar (kWh)",
        "col_consumption": "Demand (kWh)",
        "col_sc_rate": "Self-Cons %",
        "col_cov_rate": "Coverage %",
        "col_strategy": "Strategy",
        "col_gain_vs_equal": "Self-Cons Gain",
        "export_success_title": "✓ Exports Generated Successfully",
        # Doctor Diagnostic Views
        "title_doctor_gen": "☀️ Solar PV Generation Health (Huawei FusionSolar)",
        "title_doctor_gaps": "⚠️ Detected Missing Interval Gaps",
        "lbl_doctor_source": "Source",
        "lbl_doctor_files": "Files",
        "lbl_doctor_readings": "Readings",
        "lbl_doctor_gaps": "Gaps",
        "lbl_doctor_status": "Status",
        "lbl_doctor_diagnosis": "Diagnosis Notes",
        "lbl_doctor_series": "Series",
        "lbl_doctor_gap_start": "Gap Start",
        "lbl_doctor_gap_end": "Gap End",
        "lbl_doctor_missing": "Missing",
        "doc_adv_inactive": "[yellow]• Inactive Meter:[/yellow] {id} has {pct}% zero readings. In optimization, its β coefficient will be 0.00% to protect community solar energy.",
        "doc_adv_cons_gaps": "[yellow]• Consumption Gaps:[/yellow] {id} has {hours} missing hours. Download updated DATADIS CSV for complete billing periods.",
        "doc_adv_gen_gaps": "[yellow]• Generation Gaps:[/yellow] Huawei solar series has {hours} missing hours. Check inverter log exports.",
        "doc_adv_clean": "[green]• Dataset is clean and ready. You can safely run 'esd calculate'.[/green]",
        "doc_title_advice": "[bold yellow]💡 Actionable Diagnostic Insights[/bold yellow]",
        # Markdown Report Exporter Strings
        "md_report_title": "# ☀️ Electricity Share Distributor (esd v{version})",
        "md_meta_generated_at": "> **Generated at:** {timestamp}  ",
        "md_meta_regulatory": "> **Regulatory Basis:** Real Decreto 244/2019 (*Autoconsumo Colectivo*, Spain)  ",
        "md_meta_strategy": "> **Strategy:** `{strategy}` (Linear Programming Max Collective Self-Consumption)  ",
        "md_sec_community_overview": "## 📊 Collective Community Overview",
        "md_lbl_participating_cups": "- **Participating CUPS:** {count}",
        "md_lbl_date_range": "- **Date Range:** `{start}` ➔ `{end}`",
        "md_lbl_total_hours": "- **Total Time Steps:** {hours:,} hours",
        "md_lbl_total_gen": "- **Total Solar PV Generation:** **{gen:,.2f} kWh**",
        "md_lbl_total_dem": "- **Total Community Demand:** **{dem:,.2f} kWh**",
        "md_lbl_total_sc": "- **Total Self-Consumed Energy:** **{sc:,.2f} kWh** ({rate:.1f}% efficiency)",
        "md_lbl_total_surplus": "- **Total Solar Surplus Spilled:** **{surplus:,.2f} kWh**",
        "md_lbl_solar_coverage": "- **Solar Demand Coverage:** **{cov:.1f}%**",
        "md_sec_trajectory": "## 📈 Month-by-Month Energy Trajectory",
        "md_traj_header": "| Month | Solar Gen (kWh) | Demand (kWh) | Self-Consumed (kWh) | Surplus (kWh) | Grid (kWh) | Self-Cons % | Coverage % |",
        "md_sec_strategy_comp": "## ⚖️ Allocation Strategy Comparison",
        "md_comp_header": "| Strategy | Self-Consumed (kWh) | Solar Surplus (kWh) | Efficiency % | vs Equal Gain |",
        "md_sec_monthly_coeffs": "## 📅 Proposed Monthly Distribution Coefficients (β_i)",
        "md_month_header": "### Month: `{month}` (Solar Gen: {gen:,.1f} kWh)",
        "md_coeff_header": "| CUPS | Beta (β) | Share % | Demand (kWh) | Allocated Solar (kWh) | Self-Consumed (kWh) | Surplus (kWh) | Grid (kWh) |",
        "md_lbl_optimal_strat": "**Optimal (RD 244/2019 LP)**",
    },
    "es": {
        # App banner & overview
        "app_title": "☀️ DISTRIBUIDOR DE ENERGÍA COMPARTIDA (esd)",
        "app_subtitle": "CLI de Optimización y Reparto de Autoconsumo Colectivo (RD 244/2019)",
        "overview_heading": "DESCRIPCIÓN GENERAL",
        "overview_text": (
            "Calcula los coeficientes óptimos de reparto (β_i) para autoconsumo colectivo fotovoltaico\n"
            "en España bajo el Real Decreto 244/2019, combinando curvas horarias de DATADIS y\n"
            "exportaciones de generación FV de Huawei FusionSolar para maximizar el autoconsumo colectivo."
        ),
        # Commands
        "available_commands": "COMANDOS DISPONIBLES",
        "cmd_name": "Comando",
        "cmd_desc": "Descripción",
        "cmd_calculate_desc": "Procesar curvas de consumo y generación, optimizar coeficientes mensuales y mostrar resultados.",
        "cmd_doctor_desc": "Auditar archivos de entrada para detectar huecos, intervalos faltantes e incoherencias de datos.",
        "cmd_init_desc": "Inicializar directorios, configurar preferencia de idioma y guardar ajustes.",
        "cmd_config_desc": "Inspeccionar o actualizar la configuración persistente y las rutas de directorios.",
        "cmd_cleanup_desc": "Eliminar informes generados y limpiar archivos del directorio .output.",
        "cmd_help_desc": "Mostrar referencia completa de comandos, guía de datos de entrada y ejemplos.",
        "cmd_version_desc": "Mostrar la versión activa CalVer (YYYY.MM.NNN) y salir.",
        # Options
        "opt_name": "Opción",
        "opt_type": "Tipo",
        "opt_default": "Por defecto",
        "opt_desc": "Descripción",
        "opt_lang": "Anular código de idioma ('en' o 'es').",
        "opt_consumption_dir": "Directorio con los archivos CSV de consumo horario de DATADIS.",
        "opt_generation_dir": "Directorio con los archivos Excel de generación de Huawei FusionSolar.",
        "opt_output_dir": "Directorio de destino para informes y exportaciones.",
        "opt_year": "Filtrar análisis a un año natural específico.",
        "opt_month": "Filtrar análisis a un mes específico (1-12).",
        "opt_format": "Formato de exportación: 'table', 'csv', 'json', 'markdown' o 'all'.",
        "opt_force": "Ejecutar limpieza sin confirmación interactiva.",
        # Messages
        "init_success": "Espacio de trabajo inicializado correctamente con idioma '{language}'.",
        "init_reinit": "Espacio de trabajo reinicializado correctamente con idioma '{language}'.",
        "init_already": "El espacio de trabajo ya estaba inicializado en {timestamp}.",
        "not_initialized_warning": (
            "[yellow]Aviso: El espacio de trabajo aún no ha sido inicializado. Ejecute 'esd init' para configurarlo.[/yellow]"
        ),
        "version_banner": "Electricity Share Distributor (esd) versión {version}",
        "cleaning_output": "Limpiando directorio de salida: {output_dir}",
        "cleaned_files": "Se han eliminado {count} archivo(s) del directorio de salida.",
        "no_files_cleaned": "No se encontraron archivos para limpiar en el directorio de salida.",
        # Spinners & CLI Messages
        "status_ingesting": "Cargando y sincronizando curvas desde {consumption_dir} y {generation_dir}...",
        "status_optimizing": "Resolviendo modelos de programación lineal RD 244/2019...",
        "status_doctor": "Analizando y verificando conjuntos de datos de consumo y generación...",
        "prompt_lang": "Seleccione idioma preferido ('en' para inglés, 'es' para español)",
        "prompt_precision": "Seleccione precisión de porcentaje de reparto (0, 1 o 2 decimales)",
        # Table & View Labels
        "title_community_summary": "⚡ RESUMEN DE LA COMUNIDAD DE AUTOCONSUMO COLECTIVO",
        "title_monthly_coefficients": "📅 Propuesta de Coeficientes Mensuales (β_i): {month}",
        "title_monthly_trajectory": "📈 Trayectoria Energética Mensual de la Comunidad",
        "title_strategy_comparison": "⚖️ Comparativa de Eficiencia según Estrategia de Reparto",
        "lbl_supply_points": "Puntos de Suministro (CUPS)",
        "lbl_date_range": "Rango de Fechas",
        "lbl_total_hours": "Horas Analizadas",
        "lbl_total_gen": "Generación FV Total",
        "lbl_total_cons": "Demanda Total Comunidad",
        "lbl_total_sc": "Autoconsumo Total",
        "lbl_total_surplus": "Excedentes Totales a Red",
        "lbl_collective_sc_rate": "Eficiencia de Autoconsumo",
        "lbl_collective_cov_rate": "Cobertura Solar de Demanda",
        "lbl_total": "Total",
        "lbl_optimal_strat": "★ Óptimo (RD 244/2019 PL)",
        "lbl_baseline": "Base de referencia",
        "col_rank": "Pos",
        "col_cups": "CUPS",
        "col_demand": "Demanda (kWh)",
        "col_solar_alloc": "FV Asig (kWh)",
        "col_self_cons": "Autocons (kWh)",
        "col_surplus": "Exced (kWh)",
        "col_grid": "Red (kWh)",
        "col_beta": "Beta (β)",
        "col_share_bar": "Reparto",
        "col_month": "Mes",
        "col_generation": "Solar (kWh)",
        "col_consumption": "Demanda (kWh)",
        "col_sc_rate": "% Auto",
        "col_cov_rate": "% Cob",
        "col_strategy": "Estrategia",
        "col_gain_vs_equal": "Ganancia Autoconsumo",
        "export_success_title": "✓ Informes Generados Correctamente",
        # Doctor Diagnostic Views
        "title_doctor_gen": "☀️ Estado de Generación Solar FV (Huawei FusionSolar)",
        "title_doctor_gaps": "⚠️ Huecos e Intervalos Faltantes Detectados",
        "lbl_doctor_source": "Origen",
        "lbl_doctor_files": "Archivos",
        "lbl_doctor_readings": "Lecturas",
        "lbl_doctor_gaps": "Huecos",
        "lbl_doctor_status": "Estado",
        "lbl_doctor_diagnosis": "Diagnóstico",
        "lbl_doctor_series": "Serie",
        "lbl_doctor_gap_start": "Inicio Hueco",
        "lbl_doctor_gap_end": "Fin Hueco",
        "lbl_doctor_missing": "Faltante",
        "doc_adv_inactive": "[yellow]• Contador Inactivo:[/yellow] {id} tiene un {pct}% de lecturas a cero. En la optimización, su coeficiente β será 0.00% para proteger la energía solar comunitaria.",
        "doc_adv_cons_gaps": "[yellow]• Huecos en Consumo:[/yellow] {id} tiene {hours} horas faltantes. Descargue un CSV actualizado de DATADIS para periodos de facturación completos.",
        "doc_adv_gen_gaps": "[yellow]• Huecos en Generación:[/yellow] La serie solar de Huawei tiene {hours} horas faltantes. Revise las exportaciones del inversor.",
        "doc_adv_clean": "[green]• Conjunto de datos limpio y listo. Puede ejecutar 'esd calculate' con total seguridad.[/green]",
        "doc_title_advice": "[bold yellow]💡 Recomendaciones y Diagnóstico[/bold yellow]",
        # Markdown Report Exporter Strings
        "md_report_title": "# ☀️ Distribuidor de Energía Compartida (esd v{version})",
        "md_meta_generated_at": "> **Generado el:** {timestamp}  ",
        "md_meta_regulatory": "> **Marco Regulatorio:** Real Decreto 244/2019 (*Autoconsumo Colectivo*, España)  ",
        "md_meta_strategy": "> **Estrategia:** `{strategy}` (Programación Lineal Máximo Autoconsumo Colectivo)  ",
        "md_sec_community_overview": "## 📊 Resumen de la Comunidad de Autoconsumo Colectivo",
        "md_lbl_participating_cups": "- **Puntos de Suministro (CUPS):** {count}",
        "md_lbl_date_range": "- **Rango de Fechas:** `{start}` ➔ `{end}`",
        "md_lbl_total_hours": "- **Horas Analizadas:** {hours:,} horas",
        "md_lbl_total_gen": "- **Generación Solar FV Total:** **{gen:,.2f} kWh**",
        "md_lbl_total_dem": "- **Demanda Total de la Comunidad:** **{dem:,.2f} kWh**",
        "md_lbl_total_sc": "- **Energía Total Autoconsumida:** **{sc:,.2f} kWh** ({rate:.1f}% eficiencia)",
        "md_lbl_total_surplus": "- **Excedentes Solares Totales a Red:** **{surplus:,.2f} kWh**",
        "md_lbl_solar_coverage": "- **Cobertura Solar de la Demanda:** **{cov:.1f}%**",
        "md_sec_trajectory": "## 📈 Trayectoria Energética Mensual de la Comunidad",
        "md_traj_header": "| Mes | Solar FV (kWh) | Demanda (kWh) | Autoconsumo (kWh) | Excedentes (kWh) | Red (kWh) | % Autoconsumo | % Cobertura |",
        "md_sec_strategy_comp": "## ⚖️ Comparativa de Estrategias de Reparto",
        "md_comp_header": "| Estrategia | Autoconsumo (kWh) | Excedentes (kWh) | % Eficiencia | Ganancia vs Igualitario |",
        "md_sec_monthly_coeffs": "## 📅 Propuesta de Coeficientes de Reparto Mensuales (β_i)",
        "md_month_header": "### Mes: `{month}` (Gen Solar: {gen:,.1f} kWh)",
        "md_coeff_header": "| CUPS | Beta (β) | % Reparto | Demanda (kWh) | Solar Asignada (kWh) | Autoconsumo (kWh) | Excedentes (kWh) | Red (kWh) |",
        "md_lbl_optimal_strat": "**Óptimo (RD 244/2019 PL)**",
    },
}


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Retrieve translated message for a given key, interpolating any keyword arguments.

    Args:
        key: Unique string identifier for the message.
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
        except (KeyError, ValueError):
            return template

    return template
