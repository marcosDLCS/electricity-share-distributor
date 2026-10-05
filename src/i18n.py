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
        "cmd_init_desc": "Initialize application directories, configure language preference, and persist settings.",
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
        "init_already": "Workspace was already initialized at {timestamp}.",
        "not_initialized_warning": (
            "[yellow]Warning: Workspace has not been initialized yet. Run 'esd init' to configure settings.[/yellow]"
        ),
        "version_banner": "Electricity Share Distributor (esd) version {version}",
        "cleaning_output": "Cleaning output directory: {output_dir}",
        "cleaned_files": "Removed {count} file(s) from output directory.",
        "no_files_cleaned": "No files found to clean in output directory.",
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
        "cmd_init_desc": "Inicializar directorios, configurar preferencia de idioma y guardar ajustes.",
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
        "init_already": "El espacio de trabajo ya estaba inicializado en {timestamp}.",
        "not_initialized_warning": (
            "[yellow]Aviso: El espacio de trabajo aún no ha sido inicializado. Ejecute 'esd init' para configurarlo.[/yellow]"
        ),
        "version_banner": "Electricity Share Distributor (esd) versión {version}",
        "cleaning_output": "Limpiando directorio de salida: {output_dir}",
        "cleaned_files": "Se han eliminado {count} archivo(s) del directorio de salida.",
        "no_files_cleaned": "No se encontraron archivos para limpiar en el directorio de salida.",
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
