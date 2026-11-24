"""Accessible, bilingual storytelling HTML report generator for residential communities."""

from __future__ import annotations

import json
from html import escape
from typing import TYPE_CHECKING, Any

from src.config import get_language, get_precision
from src.presentation.console import format_kwh
from src.presentation.story_data import (
    StoryReportContext,
    build_story_context,
    calculate_hourly_prevision,
    parse_month_int,
    story_context_to_json_payload,
)
from src.presentation.views.common import MONTH_ABBR_EN, MONTH_ABBR_ES
from src.version import get_version

if TYPE_CHECKING:
    from src.ingestion.schema import AlignedDataset, IngestionSummary
    from src.optimization.models import OptimizationResult


def _safe_json_for_script(payload: object) -> str:
    """Serialize data to JSON safe for embedding directly inside HTML <script> tags."""
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def build_story_i18n(version: str = "dev") -> dict[str, dict[str, Any]]:
    """Build complete bilingual (ES/EN) dictionary with strict key parity."""
    return {
        "es": {
            "doc_title": "Nuestra instalación solar comunitaria — Electricity Share Distributor",
            "skip_to_content": "Ir al contenido principal",
            "hero_eyebrow": "Comunidad de propietarios · Autoconsumo colectivo",
            "title": "☀️ La energía solar de nuestra comunidad, explicada paso a paso",
            "subtitle": "Guía visual para los vecinos: qué contadores comunes tenemos, cuánto gastamos según el tiempo que hace, cuánta electricidad generan nuestras placas y cómo la repartimos para aprovecharla al máximo.",
            "mode_simulated": "Simulación horaria diurna",
            "mode_modeled": "Estimación horaria diurna",
            "default_service": "Servicio común",
            "nav_aria": "Capítulos de la guía",
            "nav_ch1": "1. Contadores",
            "nav_ch2": "2. Consumo",
            "nav_ch3": "3. Clima",
            "nav_ch4": "4. Solar",
            "nav_ch5": "5. Reparto",
            "nav_ch6": "6. Glosario",
            "theme_light": "Claro",
            "theme_dark": "Oscuro",
            "theme_hc": "Alto contraste",
            "btn_theme": "🌗 Tema",
            "btn_print": "🖨️ PDF / Imprimir",
            "font_dec_label": "Reducir tamaño de letra",
            "font_reset_label": "Tamaño de letra normal",
            "font_inc_label": "Aumentar tamaño de letra",
            "ch1_badge": "Capítulo 1",
            "ch1_title": "Los contadores de nuestra comunidad (CUPS activos)",
            "ch1_intro": "El edificio cuenta con varios contratos eléctricos independientes para sus zonas comunes (calefacción central, garaje, ascensores, piscina o alumbrado). Cada contador se identifica con un código único llamado <strong>CUPS</strong>. En esta tabla figuran únicamente los suministros activos incluidos en el reparto solar, junto con su consumo en el último año completo disponible.",
            "ch1_col_rank": "#",
            "ch1_col_service": "Servicio común",
            "ch1_col_cups": "Código CUPS",
            "ch1_col_cons": "Consumo ref.",
            "ch1_primary_tip": "Contador principal conectado directamente a las placas solares",
            "ch1_primary_legend": "☀️ Indica el contador principal conectado directamente detrás del inversor solar.",
            "ch1_jump_tip": "Ver la evolución mensual de este servicio en el Capítulo 2",
            "ch1_jump_hint": "↗ Pulsa sobre cualquier servicio común para ver su evolución mensual en el gráfico de consumo.",
            "ch1_total_label": "TOTAL COMUNIDAD",
            "ch1_note": "<strong>¿Afecta esto a la factura de mi vivienda?</strong> No. Este informe trata exclusivamente sobre los contadores de las zonas comunes; los contratos particulares de cada piso o local no cambian.",
            "ch2_badge": "Capítulo 2",
            "ch2_title": "Cuándo y cuánto consumen nuestras zonas comunes",
            "ch2_intro": "El consumo del edificio cambia con las estaciones: en invierno sube la calefacción o aerotermia, mientras que en verano trabajan más la depuradora de la piscina o la ventilación. Puedes ver el total de la comunidad año a año o comparar servicios entre sí.",
            "cons_mode_community": "Total comunidad",
            "cons_mode_single": "Un servicio",
            "cons_mode_compare": "Comparar servicios",
            "lbl_years": "Años",
            "lbl_year": "Año",
            "lbl_service": "Servicio",
            "lbl_services": "Servicios",
            "btn_all_years": "Todos",
            "btn_top4": "Los 4 mayores",
            "btn_all_cups": "Todos",
            "legend_complete": "Línea continua: mes completo",
            "legend_incomplete": "Discontinua / hueco [Inc]: mes incompleto",
            "legend_yoy": "Comparación interanual disponible",
            "stat_selected_total": "Total del periodo",
            "stat_peak_month": "Mes de mayor consumo",
            "stat_low_month": "Mes de menor consumo",
            "stat_yoy_delta": "Diferencia interanual",
            "fake_zero_title": "🔍 El misterio del «falso cero» en el contador oficial",
            "fake_zero_desc": "A plena luz del día, el contador oficial de la calle suele marcar <strong>0 kWh</strong> aunque las máquinas estén trabajando a pleno rendimiento. Así funciona la instalación por dentro y así recuperamos el consumo real:",
            "fake_zero_step1_title": "1. Conexión directa tras el contador",
            "fake_zero_step1_tpl": "Nuestras placas solares están conectadas directamente detrás del contador de <strong>{primary}</strong>, dentro de la instalación privada de la finca.",
            "fake_zero_step2_title": "2. Qué ocurre en una hora de sol",
            "fake_zero_step2_desc": "Si las placas producen <strong>10 kWh</strong> y el servicio consume <strong>6 kWh</strong>, se abastece primero del tejado y los <strong>4 kWh</strong> restantes salen hacia la red. Como no compra nada de la calle, el contador oficial registra <strong>0 kWh</strong>.",
            "fake_zero_step3_title": "3. Cómo reconstruimos el gasto real",
            "fake_zero_step3_desc": "Para evitar que ese servicio parezca inactivo, cruzamos las lecturas de la distribuidora (DATADIS) con los registros reales del inversor solar hora a hora.",
            "fake_zero_recovered": "Consumo real recuperado detrás del contador:",
            "fz_zone_home": "Dentro de la finca (tras el contador)",
            "fz_zone_grid": "Red eléctrica exterior",
            "fz_svg_panels": "Placas solares",
            "fz_svg_panels_val": "+10 kWh solares",
            "fz_svg_panels_sub": "Energía producida",
            "fz_svg_flow_sc": "6 kWh",
            "fz_svg_primary": "Servicio principal",
            "fz_svg_primary_val": "Consume 6 kWh reales",
            "fz_svg_flow_exp": "4 kWh sobrantes ➔",
            "fz_svg_no_grid": "0 kWh comprados de la calle",
            "fz_svg_meter": "Contador oficial",
            "fz_svg_meter_zero": "Compra registrada: 0 kWh",
            "fz_svg_meter_cap1": "Solo mide lo que entra de fuera",
            "fz_svg_meter_cap2": "No ve los 6 kWh del tejado",
            "ch3_badge": "Capítulo 3",
            "ch3_title": "El tiempo en nuestra finca en los años analizados",
            "ch3_intro": "El clima explica buena parte de lo que acabamos de ver: los meses fríos disparan la calefacción y los días despejados multiplican la producción de las placas. Explora la temperatura, la claridad del cielo y el reparto mensual de días de sol o lluvia en los años analizados.",
            "weather_mode_temp": "🌡️ Temperatura (°C)",
            "weather_mode_clear": "☀️ Cielo despejado (%)",
            "weather_mode_days": "📅 Días de cielo y lluvia",
            "weather_stat_temp": "Temperatura media",
            "weather_stat_range": "Mes frío y mes cálido",
            "weather_stat_clear": "Cielo despejado medio",
            "weather_stat_extremes": "Días fríos y calurosos",
            "weather_sunny_days": "Soleados",
            "weather_partly_days": "Nubes y claros",
            "weather_cloudy_days": "Muy nubosos",
            "weather_rainy_days": "Con lluvia",
            "weather_sky_title": "Reparto del cielo en",
            "weather_days_unit": "días registrados",
            "weather_cold_days_lbl": "<10 °C",
            "weather_hot_days_lbl": "≥30 °C",
            "weather_frost_days_lbl": "heladas ≤0 °C",
            "weather_band_note": "Banda sombreada: rango medio diario (mín–máx °C)",
            "weather_cold_ref": "Umbral de frío (10 °C)",
            "weather_no_data": "No hay registros meteorológicos guardados para estos años.",
            "weather_coldest": "Frío",
            "weather_warmest": "Cálido",
            "weather_min_ext": "Mín",
            "weather_max_ext": "Máx",
            "weather_no_extremes": "Sin extremos marcados",
            "weather_insight_single_tpl": "🌤️ En <strong>{year}</strong> la temperatura media fue de <strong>{temp}</strong>, con un <strong>{clear}</strong> de cielos despejados en horas de luz y <strong>{sunny} días soleados</strong> frente a <strong>{rainy} días de lluvia</strong>.",
            "weather_insight_yoy_tpl": "🌤️ Entre <strong>{y0}</strong> y <strong>{y1}</strong>, la temperatura media varió <strong>{dt} °C</strong> y la proporción de cielo despejado <strong>{dc} puntos</strong> (en {y1}: <strong>{temp}</strong> de media y <strong>{clear}</strong> despejado).",
            "weather_card1_title": "🥶 Frío y demanda del edificio",
            "weather_card1_ratio_tpl": "En los meses fríos (media por debajo de 12 °C), las zonas comunes consumen de media <strong>{cold_kwh}</strong> al mes frente a <strong>{mild_kwh}</strong> en los meses templados (15–23 °C): un gasto <strong>{ratio}× mayor</strong>. En {year} se registraron <strong>{cold_days} días fríos (&lt;10 °C)</strong>{frost_part}.",
            "weather_card1_fallback_tpl": "Las jornadas por debajo de 10 °C empujan el consumo de calefacción o aerotermia en la finca. En <strong>{year}</strong> se midieron <strong>{cold_days} días fríos (&lt;10 °C)</strong>, <strong>{hot_days} calurosos (≥30 °C)</strong> y extremos entre <strong>{min_t}</strong> y <strong>{max_t}</strong>.",
            "weather_card2_title": "☀️ Cielo despejado, calor y rendimiento solar",
            "weather_card2_body_tpl": "El mes más luminoso suele ser <strong>{sun_m}</strong> (<strong>{sun_c}</strong> despejado) frente a <strong>{cld_m}</strong> (<strong>{cld_c}</strong>).",
            "weather_card2_peak_tpl": "La mayor producción solar se alcanza en <strong>{peak_m}</strong> ({peak_c} despejado y {peak_t} de media).",
            "weather_card2_heat_note": "Las placas rinden especialmente bien en días despejados y templados de primavera; con calor extremo (>30 °C) el silicio pierde algo de eficiencia (~0,4 % por cada °C sobre 25 °C), aunque los días más largos compensan.",
            "tip_temp_avg": "Media mensual",
            "tip_temp_range": "Mín–Máx diario medio",
            "tip_clear_sky": "Cielo despejado",
            "tip_cloud_cover": "Nubosidad",
            "tip_sky_days": "Días del mes",
            "ch4_badge": "Capítulo 4",
            "ch4_title": "Cuánta electricidad producen nuestras placas",
            "ch4_intro": "Los días más largos y luminosos de primavera y verano disparan la generación respecto al invierno. Si marcas la casilla de demanda diurna, verás al instante en qué meses nos falta sol y en cuáles producimos de sobra.",
            "toggle_daylight_demand": "Superponer consumo en horas de sol",
            "gen_stat_total": "Producción del periodo",
            "gen_stat_peak": "Mes más soleado",
            "gen_stat_low": "Mes de menor producción",
            "gen_stat_yoy": "Diferencia interanual",
            "gen_legend_demand": "Consumo diurno comunitario (referencia)",
            "gen_insight_single_tpl": "🌞 En <strong>{year}</strong> el tejado generó <strong>{total}</strong> en total, con su punto más alto en <strong>{peak_m}</strong> (<strong>{peak_val}</strong>).",
            "gen_insight_ratio_tpl": "🌞 En <strong>{year}</strong> las placas generaron <strong>{total}</strong>. El mes más soleado (<strong>{peak_m}</strong>, {peak_val}) produjo <strong>{ratio}×</strong> más electricidad que el más flojo (<strong>{low_m}</strong>, {low_val}).",
            "gen_insight_yoy_tpl": " Diferencia interanual homogénea ({y0}→{y1}): <strong>{pct}</strong>.",
            "gen_imp_homes_lbl": "Viviendas equivalentes",
            "gen_imp_homes_unit": "hogares medios/año",
            "gen_imp_home_months_unit": "meses de un hogar medio",
            "gen_imp_co2_lbl": "Emisiones evitadas",
            "gen_imp_ev_lbl": "Movilidad limpia equiv.",
            "gen_imp_note": "Equivalencias orientativas para España (IDAE / REE): ~3.300 kWh/año por hogar, ~0,20 kg CO₂/kWh de red evitados y ~6 km/kWh en coche eléctrico.",
            "ch5_badge": "Capítulo 5",
            "ch5_title": "Cómo repartimos el sol entre los contadores",
            "why_equal_title": "💡 ¿Por qué no repartimos siempre a partes iguales?",
            "why_equal_desc": "Si asignáramos siempre el mismo porcentaje fijo todo el año (por ejemplo, un 15 % a la piscina en enero), desperdiciaríamos energía solar en un contador parado mientras la calefacción tendría que comprar electricidad cara de la red. Ajustar los coeficientes (β) cada mes lleva la energía justo donde hace falta.",
            "spotlight_title": "❄️ Invierno frente a ☀️ verano: cómo cambia el reparto",
            "spotlight_winter": "Invierno",
            "spotlight_summer": "Verano",
            "spotlight_single_note": "Solo hay un mes activo disponible; al añadir meses de invierno y verano verás aquí la comparación estacional.",
            "spotlight_gen": "Sol",
            "spotlight_dem": "Consumo",
            "spotlight_sc": "Aprovechado",
            "chart_traj_title": "📊 Balance mensual: producción frente a demanda y autoconsumo",
            "chart_traj_sub": "Compara mes a mes cuánta energía generan las placas, cuánta consume el edificio y cuánta aprovechamos directamente.",
            "legend_bal_gen": "Producción solar (ámbar)",
            "legend_bal_dem": "Demanda comunitaria (azul)",
            "legend_bal_sc": "Autoconsumo colectivo (verde)",
            "prev_box_title": "⚡ El salto colectivo: 4 formas de repartir el sol",
            "prev_box_sub": "Evolución desde dejar todo en un solo contador hasta el reparto mensual (RD 244/2019), quincenal (24 quincenas) y horario dinámico (Orden TED/1247/2021).",
            "hourly_badge_ted": "📜 Orden TED/1247/2021",
            "prev_card1_title": "Sin reparto (1 solo CUPS)",
            "prev_card1_sub": "Aprovechamiento",
            "prev_card1_tag": "Punto de partida",
            "prev_card2_title": "Reparto mensual (RD 244/2019)",
            "prev_card2_vs": "frente a 1 CUPS",
            "prev_card_fortnight_title": "Reparto quincenal (24 quincenas)",
            "prev_card_fortnight_vs": "frente a 1 CUPS",
            "prev_card3_title": "Reparto horario (Orden TED)",
            "prev_card3_vs": "frente a mensual",
            "prev_card3_horizon": "Horizonte futuro",
            "prev_card4_title": "Ganancia colectiva total",
            "prev_card4_sub": "sobre 1 solo CUPS",
            "prev_comp_single": "Sin reparto colectivo (1 solo CUPS)",
            "prev_comp_monthly": "Reparto mensual fijo (RD 244/2019)",
            "prev_comp_fortnight": "Reparto quincenal (24 quincenas)",
            "prev_comp_hourly": "Reparto horario dinámico (Orden TED/1247/2021)",
            "prev_note": "Al pasar de aprovechar las placas en un único contador al reparto mensual (<strong>RD 244/2019</strong>) o quincenal, toda la comunidad absorbe la energía solar según la época del año. El reparto horario dinámico (<strong>Orden TED/1247/2021</strong>) marca el siguiente paso normativo para exprimir aún más las placas sin invertir en nuevos equipos.",
            "prev_uplift_impact_tpl": "🌱 Solo por repartir la energía entre todos los contadores en lugar de dejarla en uno solo, evitamos <strong>{co2}</strong> adicionales (equivalente al consumo de <strong>{home_months} meses de una vivienda media</strong>).",
            "ch6_badge": "Capítulo 6",
            "ch6_title": "Glosario básico",
            "ch6_intro": "Conceptos eléctricos y normativos explicados en lenguaje cotidiano.",
            "g1_term": "CUPS (Código Universal de Punto de Suministro)",
            "g1_desc": "Es el «DNI» de cada contador eléctrico. Nuestra comunidad tiene un CUPS distinto para el garaje, los ascensores, la calefacción o la piscina.",
            "g2_term": "kWh (kilovatio-hora)",
            "g2_desc": "La unidad básica de energía eléctrica. Equivale, por ejemplo, a un lavado en modo eco o a tener encendido un radiador pequeño (1.000 W) durante una hora.",
            "g3_term": "Autoconsumo colectivo",
            "g3_desc": "Electricidad que generan las placas de la cubierta y consumen en esa misma hora los servicios comunes del edificio, evitando comprarla de la red.",
            "g4_term": "Excedente vertido a red",
            "g4_desc": "Energía solar que sobra cuando las placas producen más electricidad de la que consumen juntos todos los servicios comunes en esa hora.",
            "g5_term": "Coeficiente de reparto (β)",
            "g5_desc": "El porcentaje fijo de la producción solar asignado a cada contador ante la distribuidora. La suma de todos los coeficientes debe ser siempre exactamente del 100 %.",
            "g6_term": "Mes incompleto [Inc]",
            "g6_desc": "Señala un mes con menos del 90 % de sus días u horas registrados (por ejemplo, el mes en curso o una puesta en marcha) para evitar comparaciones engañosas.",
            "tip_gen": "Producción solar",
            "tip_dem": "Demanda",
            "tip_solar_dem": "Demanda en horas de sol",
            "tip_solar_cov": "Cobertura en horas de sol",
            "tip_sc": "Autoconsumo",
            "tip_surplus": "Excedente",
            "tip_coverage": "Cobertura",
            "tip_efficiency": "Aprovechamiento",
            "tip_inc_badge": "[Inc]",
            "tip_days": "días",
            "tip_no_data": "Sin datos",
            "tip_yoy": "Interanual",
            "chart_empty": "No hay suficientes datos horarios para esta selección.",
            "cons_insight_prefix": "Mayor consumidor comunitario:",
            "cons_insight_peak": "Mes con mayor gasto:",
            "spotlight_mover_tpl": "Mayor cambio estacional: <strong>{use}</strong> pasa del <strong>{w}%</strong> en invierno al <strong>{s}%</strong> en verano.",
            "footer_text": f"Generado por <strong>Electricity Share Distributor (esd) v{version}</strong> • Real Decreto 244/2019",
            "months": {
                "01": "Ene",
                "02": "Feb",
                "03": "Mar",
                "04": "Abr",
                "05": "May",
                "06": "Jun",
                "07": "Jul",
                "08": "Ago",
                "09": "Sep",
                "10": "Oct",
                "11": "Nov",
                "12": "Dic",
            },
            "months_full": {
                "01": "Enero",
                "02": "Febrero",
                "03": "Marzo",
                "04": "Abril",
                "05": "Mayo",
                "06": "Junio",
                "07": "Julio",
                "08": "Agosto",
                "09": "Septiembre",
                "10": "Octubre",
                "11": "Noviembre",
                "12": "Diciembre",
            },
        },
        "en": {
            "doc_title": "Our Community's Solar Story — Electricity Share Distributor",
            "skip_to_content": "Skip to main content",
            "hero_eyebrow": "Homeowners Association · Collective Solar",
            "title": "☀️ Our Community's Solar Story",
            "subtitle": "An accessible, visual guide showing how our shared building services use electricity, what local weather and our rooftop panels deliver, and how smart sharing maximizes value for every neighbour.",
            "mode_simulated": "Hourly Diurnal Simulation",
            "mode_modeled": "Modeled Diurnal Prevision",
            "default_service": "Common Service",
            "nav_aria": "Report chapters",
            "nav_ch1": "1. Supplies",
            "nav_ch2": "2. Consumption",
            "nav_ch3": "3. Weather",
            "nav_ch4": "4. Solar",
            "nav_ch5": "5. Sharing",
            "nav_ch6": "6. Glossary",
            "theme_light": "Light",
            "theme_dark": "Dark",
            "theme_hc": "High Contrast",
            "btn_theme": "🌗 Theme",
            "btn_print": "🖨️ Print / PDF",
            "font_dec_label": "Decrease text size",
            "font_reset_label": "Reset text size",
            "font_inc_label": "Increase text size",
            "ch1_badge": "Chapter 1",
            "ch1_title": "Meet Our Community Supplies (Active CUPS)",
            "ch1_intro": "Our homeowners association holds separate electricity meters for shared facilities (central heating, garage, elevators, pool, hallway lighting). In Spain, each meter contract has a unique ID called a <strong>CUPS</strong>. Below are strictly the active community meters included in our collective solar agreement, alongside their demand in the latest complete year.",
            "ch1_col_rank": "#",
            "ch1_col_service": "Common Service",
            "ch1_col_cups": "Official CUPS Code",
            "ch1_col_cons": "Ref. Consumption",
            "ch1_primary_tip": "Primary meter connected directly behind the solar inverter",
            "ch1_primary_legend": "☀️ Marks the primary meter connected directly behind the rooftop solar inverter.",
            "ch1_jump_tip": "View this service's monthly curve in Chapter 2",
            "ch1_jump_hint": "↗ Click any common service to jump straight to its monthly curve in Chapter 2.",
            "ch1_total_label": "COMMUNITY TOTAL",
            "ch1_note": "<strong>Good to know:</strong> This report only covers shared building common-service meters. Private apartment electricity contracts and household bills are neither included nor modified.",
            "ch2_badge": "Chapter 2",
            "ch2_title": "How Our Community Consumes Energy",
            "ch2_intro": "Each building service follows the seasons: central heating spikes in winter while swimming pool pumps and ventilation run harder in warmer months. Explore our community total across years or inspect individual services side by side.",
            "cons_mode_community": "Community Total",
            "cons_mode_single": "Single Service (CUPS)",
            "cons_mode_compare": "Compare Services",
            "lbl_years": "Years",
            "lbl_year": "Year",
            "lbl_service": "Service",
            "lbl_services": "Services",
            "btn_all_years": "All",
            "btn_top4": "Top 4",
            "btn_all_cups": "All",
            "legend_complete": "Solid line: complete month",
            "legend_incomplete": "Dashed / hollow [Inc]: partial month",
            "legend_yoy": "Year-over-year delta enabled",
            "stat_selected_total": "Selected Total",
            "stat_peak_month": "Peak Month",
            "stat_low_month": "Lowest Month",
            "stat_yoy_delta": "Year-over-Year Change",
            "fake_zero_title": "🔍 Solving the «Fake Zero» Utility Meter Riddle",
            "fake_zero_desc": "At midday, the street utility meter often logs <strong>0 kWh</strong> even while building equipment is running at full power. Here is how our wiring works inside and how we recover true demand:",
            "fake_zero_step1_title": "1. Wired behind the main meter",
            "fake_zero_step1_tpl": "Our rooftop solar panels feed directly into <strong>{primary}</strong> inside our building's electrical room, before electricity ever reaches the street utility meter.",
            "fake_zero_step2_title": "2. What happens in a sunny hour",
            "fake_zero_step2_desc": "If rooftop panels generate <strong>10 kWh</strong> and the equipment uses <strong>6 kWh</strong>, it runs on sunshine first while the extra <strong>4 kWh</strong> export to the grid. Because zero street electricity is imported, the official meter logs <strong>0 kWh</strong>.",
            "fake_zero_step3_title": "3. How we uncover true demand",
            "fake_zero_step3_desc": "To avoid undercounting what this facility actually needs, our tool reconciles grid-meter imports (DATADIS) hour by hour against the inverter's real generation and flow logs.",
            "fake_zero_recovered": "Hidden behind-the-meter demand recovered:",
            "fz_zone_home": "Inside building (behind meter)",
            "fz_zone_grid": "Public grid (street)",
            "fz_svg_panels": "Rooftop solar",
            "fz_svg_panels_val": "+10 kWh solar",
            "fz_svg_panels_sub": "Clean power generated",
            "fz_svg_flow_sc": "6 kWh",
            "fz_svg_primary": "Primary service",
            "fz_svg_primary_val": "Uses 6 kWh in reality",
            "fz_svg_flow_exp": "4 kWh surplus ➔",
            "fz_svg_no_grid": "0 kWh bought from street",
            "fz_svg_meter": "Street utility meter",
            "fz_svg_meter_zero": "Grid import reads: 0 kWh",
            "fz_svg_meter_cap1": "Only sees power entering",
            "fz_svg_meter_cap2": "Misses the 6 kWh rooftop flow",
            "ch3_badge": "Chapter 3",
            "ch3_title": "Local Weather Across the Analyzed Years",
            "ch3_intro": "Weather connects demand and solar supply: colder months push central heating higher while clear bright skies boost rooftop output. Explore monthly temperatures, clear-sky percentages, and sunny vs. rainy day counts across the exact analyzed years.",
            "weather_mode_temp": "🌡️ Temperature (°C)",
            "weather_mode_clear": "☀️ Clear Sky (%)",
            "weather_mode_days": "📅 Sky & Rain Days",
            "weather_stat_temp": "Average Temperature",
            "weather_stat_range": "Coldest & Warmest Month",
            "weather_stat_clear": "Average Clear Sky",
            "weather_stat_extremes": "Cold & Hot Days",
            "weather_sunny_days": "Sunny",
            "weather_partly_days": "Partly cloudy",
            "weather_cloudy_days": "Overcast",
            "weather_rainy_days": "Rainy",
            "weather_sky_title": "Sky breakdown in",
            "weather_days_unit": "observed days",
            "weather_cold_days_lbl": "<10 °C",
            "weather_hot_days_lbl": "≥30 °C",
            "weather_frost_days_lbl": "frost ≤0 °C",
            "weather_band_note": "Shaded band: average daily min–max (°C)",
            "weather_cold_ref": "Heating zone (<10 °C)",
            "weather_no_data": "No local weather archives available for these years.",
            "weather_coldest": "Coldest",
            "weather_warmest": "Warmest",
            "weather_min_ext": "Min",
            "weather_max_ext": "Max",
            "weather_no_extremes": "Mild range overall",
            "weather_insight_single_tpl": "🌤️ In <strong>{year}</strong> the mean temperature was <strong>{temp}</strong>, with <strong>{clear}</strong> daytime clear skies and <strong>{sunny} sunny days</strong> versus <strong>{rainy} rainy days</strong>.",
            "weather_insight_yoy_tpl": "🌤️ From <strong>{y0}</strong> to <strong>{y1}</strong>, mean temperature shifted by <strong>{dt} °C</strong> and clear skies by <strong>{dc} pp</strong> ({y1}: <strong>{temp}</strong> avg · <strong>{clear}</strong> clear sky).",
            "weather_card1_title": "🥶 Cold Weather & Building Demand",
            "weather_card1_ratio_tpl": "During cold months (avg below 12 °C), shared facilities consume <strong>{cold_kwh}</strong>/month vs. <strong>{mild_kwh}</strong> in mild months (15–23 °C)—a <strong>{ratio}× surge</strong> driven by central heating. {year} logged <strong>{cold_days} cold days (&lt;10 °C)</strong>{frost_part}.",
            "weather_card1_fallback_tpl": "Days averaging below 10 °C drive central heating demand sharply higher. In <strong>{year}</strong> we observed <strong>{cold_days} cold days (&lt;10 °C)</strong>, <strong>{hot_days} hot days (≥30 °C)</strong>, and extremes from <strong>{min_t}</strong> to <strong>{max_t}</strong>.",
            "weather_card2_title": "☀️ Clear Skies, Heat & Panel Efficiency",
            "weather_card2_body_tpl": "The brightest skies typically arrive in <strong>{sun_m}</strong> (<strong>{sun_c}</strong> clear) versus <strong>{cld_m}</strong> (<strong>{cld_c}</strong>).",
            "weather_card2_peak_tpl": "Peak PV generation occurs in <strong>{peak_m}</strong> ({peak_c} clear sky, {peak_t} average).",
            "weather_card2_heat_note": "Panels convert light most efficiently on crisp, bright spring days; extreme heat (>30 °C) trims silicon efficiency slightly (~0.4% per °C above 25 °C), though longer summer daylight more than compensates.",
            "tip_temp_avg": "Monthly Average",
            "tip_temp_range": "Avg Daily Min–Max",
            "tip_clear_sky": "Clear Sky",
            "tip_cloud_cover": "Cloud Cover",
            "tip_sky_days": "Month Days",
            "ch4_badge": "Chapter 4",
            "ch4_title": "How Our Roof Produces Solar Energy",
            "ch4_intro": "Longer, brighter days from spring through summer multiply solar output compared with winter months. Toggle the daylight demand line to see when solar supply exceeds daytime demand and when it falls short.",
            "toggle_daylight_demand": "Overlay Daylight Demand",
            "gen_stat_total": "Selected Generation",
            "gen_stat_peak": "Sunniest Month",
            "gen_stat_low": "Lowest Month",
            "gen_stat_yoy": "Year-over-Year Shift",
            "gen_legend_demand": "Community daylight demand (reference)",
            "gen_insight_single_tpl": "🌞 In <strong>{year}</strong> our roof produced <strong>{total}</strong>, peaking in <strong>{peak_m}</strong> (<strong>{peak_val}</strong>).",
            "gen_insight_ratio_tpl": "🌞 In <strong>{year}</strong> our panels generated <strong>{total}</strong>. The sunniest month (<strong>{peak_m}</strong>, {peak_val}) delivered <strong>{ratio}×</strong> as much solar power as the lowest month (<strong>{low_m}</strong>, {low_val}).",
            "gen_insight_yoy_tpl": " Apples-to-apples YoY shift ({y0}→{y1}): <strong>{pct}</strong>.",
            "gen_imp_homes_lbl": "Equivalent Homes",
            "gen_imp_homes_unit": "avg Spanish homes/yr",
            "gen_imp_home_months_unit": "avg home-months",
            "gen_imp_co2_lbl": "CO₂ Emissions Avoided",
            "gen_imp_ev_lbl": "EV Driving Equivalent",
            "gen_imp_note": "Indicative Spain benchmarks (IDAE / REE): ~3,300 kWh/yr typical household, ~0.20 kg CO₂/kWh grid displacement, ~6 km/kWh EV.",
            "ch5_badge": "Chapter 5",
            "ch5_title": "Sharing the Sun: How Smart Coefficients Work",
            "why_equal_title": "💡 Why NOT Split Everything Equally?",
            "why_equal_desc": "Giving every meter the exact same fixed slice all year (for instance 15% to a closed swimming pool in January) wastes clean rooftop power while central heating buys costly grid electricity. Adjusting shares (β) each month directs sunlight where it works hardest.",
            "spotlight_title": "❄️ Winter vs. ☀️ Summer: Seasonal Spotlight",
            "spotlight_winter": "Winter",
            "spotlight_summer": "Summer",
            "spotlight_single_note": "Showing the available active month; add winter and summer months to unlock the full seasonal comparison.",
            "spotlight_gen": "Solar",
            "spotlight_dem": "Demand",
            "spotlight_sc": "Self-Consumed",
            "chart_traj_title": "📊 Monthly Balance: Solar vs. Demand vs. Self-Consumption",
            "chart_traj_sub": "Solar Generation (amber), Community Demand (sky blue), and Collective Self-Consumption (green).",
            "legend_bal_gen": "Solar Generation (amber)",
            "legend_bal_dem": "Community Demand (blue)",
            "legend_bal_sc": "Collective Self-Consumption (green)",
            "prev_box_title": "⚡ The Collective Journey: 4 Ways to Share",
            "prev_box_sub": "Step-by-step comparison from a single meter to Fixed Monthly (RD 244/2019), Fortnight (24 periods), and future Dynamic Hourly sharing (Order TED/1247/2021).",
            "hourly_badge_ted": "📜 Spanish Order TED/1247/2021",
            "prev_card1_title": "No Share (Single CUPS)",
            "prev_card1_sub": "Utilization",
            "prev_card1_tag": "Baseline",
            "prev_card2_title": "Monthly Share (RD 244/2019)",
            "prev_card2_vs": "vs single CUPS",
            "prev_card_fortnight_title": "Fortnight Share (24 Periods)",
            "prev_card_fortnight_vs": "vs single CUPS",
            "prev_card3_title": "Hourly Share (Order TED)",
            "prev_card3_vs": "vs monthly",
            "prev_card3_horizon": "Future horizon",
            "prev_card4_title": "Total Collective Uplift",
            "prev_card4_sub": "over single CUPS",
            "prev_comp_single": "No Collective Share (Single CUPS)",
            "prev_comp_monthly": "Fixed Monthly Share (RD 244/2019)",
            "prev_comp_fortnight": "Fortnight Share (24 Half-Month Periods)",
            "prev_comp_hourly": "Dynamic Hourly Share (Orden TED/1247/2021)",
            "prev_note": "Moving from single-meter self-consumption to fixed monthly (<strong>RD 244/2019</strong>) or fortnight collective shares lets all common services absorb rooftop power across seasons. Dynamic hourly profiles (<strong>Order TED/1247/2021</strong>) represent the next regulatory horizon to capture even more sunshine without buying extra panels.",
            "prev_uplift_impact_tpl": "🌱 Simply by sharing solar across all common meters instead of just one, the community avoids an extra <strong>{co2}</strong> (equivalent to <strong>{home_months} months of electricity for an average home</strong>).",
            "ch6_badge": "Chapter 6",
            "ch6_title": "Plain-Language Glossary for Neighbours",
            "ch6_intro": "Everyday explanations of key energy and regulatory terms used in this report.",
            "g1_term": "CUPS (Universal Supply Point Code)",
            "g1_desc": "Think of a CUPS as an electricity meter's official ID card. Our building holds separate CUPS contracts for heating, garage, elevators, and pool.",
            "g2_term": "kWh (Kilowatt-hour)",
            "g2_desc": "The standard unit of electricity. Roughly equal to one eco washing machine cycle or running a 1,000 W small heater for one hour.",
            "g3_term": "Collective Self-Consumption",
            "g3_desc": "Solar electricity generated on our roof and used immediately by building services in the same hour—power we never have to buy from the grid.",
            "g4_term": "Grid Surplus",
            "g4_desc": "Extra solar electricity produced when rooftop panels generate more than all shared services can consume during that hour.",
            "g5_term": "Share Coefficient (β)",
            "g5_desc": "The percentage slice of solar energy assigned to each CUPS at the grid distributor. Across all participating meters, shares must always add up to 100%.",
            "g6_term": "Incomplete Month [Inc]",
            "g6_desc": "Marks a month with under 90% of expected days/hours recorded (such as an ongoing month or mid-month start), preventing misleading comparisons.",
            "tip_gen": "Solar Generation",
            "tip_dem": "Demand",
            "tip_solar_dem": "Solar Hours Demand",
            "tip_solar_cov": "Solar Hours Coverage",
            "tip_sc": "Self-Consumed",
            "tip_surplus": "Surplus",
            "tip_coverage": "Coverage",
            "tip_efficiency": "Utilization",
            "tip_inc_badge": "[Inc]",
            "tip_days": "days",
            "tip_no_data": "No data",
            "tip_yoy": "YoY Change",
            "chart_empty": "Not enough hourly data for this selection.",
            "cons_insight_prefix": "Largest community consumer:",
            "cons_insight_peak": "Highest recorded month:",
            "spotlight_mover_tpl": "Biggest seasonal shift: <strong>{use}</strong> moves from <strong>{w}%</strong> in winter to <strong>{s}%</strong> in summer.",
            "footer_text": f"Generated by <strong>Electricity Share Distributor (esd) v{version}</strong> • Spanish RD 244/2019",
            "months": {
                "01": "Jan",
                "02": "Feb",
                "03": "Mar",
                "04": "Apr",
                "05": "May",
                "06": "Jun",
                "07": "Jul",
                "08": "Aug",
                "09": "Sep",
                "10": "Oct",
                "11": "Nov",
                "12": "Dec",
            },
            "months_full": {
                "01": "January",
                "02": "February",
                "03": "March",
                "04": "April",
                "05": "May",
                "06": "June",
                "07": "July",
                "08": "August",
                "09": "September",
                "10": "October",
                "11": "November",
                "12": "December",
            },
        },
    }


def _render_monthly_balance_svg(
    opt_result: OptimizationResult,
    is_es: bool,
) -> str:
    """Render clean accessible SVG grouped bar chart comparing generation, demand, and self-consumption."""
    active_months = [m for m in opt_result.monthly_results if m.has_data]
    if not active_months:
        return (
            "<p class='no-data' data-i18n='chart_empty'>No monthly time-series data available.</p>"
        )

    abbr_map = MONTH_ABBR_ES if is_es else MONTH_ABBR_EN
    width = 960
    height = 350
    pad_left = 74
    pad_right = 28
    pad_top = 36
    pad_bottom = 50
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    max_val = max(
        max(m.total_generation_kwh for m in active_months),
        max(m.total_consumption_kwh for m in active_months),
        1.0,
    )
    y_max = max_val * 1.15
    n_months = len(active_months)
    slot_w = chart_w / n_months
    bar_w = min(18.0, slot_w * 0.22)
    spacing = 3.0

    svg_elements: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg chart-monthly-svg" role="img" '
        'aria-label="Monthly generation, demand and self-consumption chart" xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        '  <linearGradient id="gradGen" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#d97706" stop-opacity="0.95"/>',
        '    <stop offset="100%" stop-color="#b45309" stop-opacity="0.65"/>',
        "  </linearGradient>",
        '  <linearGradient id="gradDem" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#0284c7" stop-opacity="0.95"/>',
        '    <stop offset="100%" stop-color="#0369a1" stop-opacity="0.65"/>',
        "  </linearGradient>",
        '  <linearGradient id="gradSc" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#059669" stop-opacity="0.98"/>',
        '    <stop offset="100%" stop-color="#047857" stop-opacity="0.7"/>',
        "  </linearGradient>",
        "</defs>",
    ]

    for tier in range(5):
        tier_val = (y_max / 4) * tier
        y_pos = pad_top + chart_h - (chart_h * (tier / 4))
        svg_elements.append(
            f'<line x1="{pad_left}" y1="{y_pos:.1f}" x2="{width - pad_right}" y2="{y_pos:.1f}" class="grid-line"/>'
        )
        lbl_kwh = f"{tier_val:,.0f} kWh" if tier_val < 10000 else f"{tier_val / 1000:,.1f} MWh"
        svg_elements.append(
            f'<text x="{pad_left - 10}" y="{y_pos + 4:.1f}" text-anchor="end" class="axis-label">{lbl_kwh}</text>'
        )

    for idx, m in enumerate(active_months):
        cx = pad_left + idx * slot_w + (slot_w / 2.0)
        m_int = parse_month_int(m.month)
        m_2d = f"{m_int:02d}"
        m_name = abbr_map.get(m.month, abbr_map.get(m_2d, m.month))

        h_gen = (m.total_generation_kwh / y_max) * chart_h
        h_dem = (m.total_consumption_kwh / y_max) * chart_h
        h_sc = (m.total_self_consumed_kwh / y_max) * chart_h

        y_gen = pad_top + chart_h - h_gen
        y_dem = pad_top + chart_h - h_dem
        y_sc = pad_top + chart_h - h_sc

        x_gen = cx - (bar_w * 1.5) - spacing
        x_dem = cx - (bar_w * 0.5)
        x_sc = cx + (bar_w * 0.5) + spacing

        tip_data = escape(
            json.dumps(
                {
                    "month": m_name,
                    "month_num": m_2d,
                    "gen": f"{m.total_generation_kwh:,.1f} kWh",
                    "dem": f"{m.total_consumption_kwh:,.1f} kWh",
                    "solar_dem": f"{m.solar_hours_consumption_kwh:,.1f} kWh",
                    "solar_cov": f"{m.solar_hours_coverage_rate:.1f}%",
                    "sc": f"{m.total_self_consumed_kwh:,.1f} kWh",
                    "surplus": f"{m.total_surplus_kwh:,.1f} kWh",
                    "cov": f"{m.solar_coverage_rate:.1f}%",
                    "eff": f"{m.self_consumption_rate:.1f}%",
                }
            ),
            quote=True,
        )

        svg_elements.append(
            f'<g class="chart-col" tabindex="0" data-tooltip="{tip_data}" '
            'onmouseenter="showTooltip(event, this)" onfocus="showTooltip(event, this)" '
            'onmouseleave="hideTooltip()" onblur="hideTooltip()">'
        )
        svg_elements.append(
            f'  <rect x="{cx - slot_w / 2:.1f}" y="{pad_top}" width="{slot_w:.1f}" height="{chart_h}" class="hover-bg"/>'
        )
        svg_elements.append(
            f'  <rect x="{x_gen:.1f}" y="{y_gen:.1f}" width="{bar_w:.1f}" height="{h_gen:.1f}" rx="3" fill="url(#gradGen)"/>'
        )
        svg_elements.append(
            f'  <rect x="{x_dem:.1f}" y="{y_dem:.1f}" width="{bar_w:.1f}" height="{h_dem:.1f}" rx="3" fill="url(#gradDem)"/>'
        )
        svg_elements.append(
            f'  <rect x="{x_sc:.1f}" y="{y_sc:.1f}" width="{bar_w:.1f}" height="{h_sc:.1f}" rx="3" fill="url(#gradSc)"/>'
        )
        svg_elements.append(
            f'  <text x="{cx:.1f}" y="{height - pad_bottom + 22}" text-anchor="middle" class="x-label" data-month="{m_2d}">{escape(m_name)}</text>'
        )
        svg_elements.append("</g>")

    svg_elements.append("</svg>")
    return "\n".join(svg_elements)


def _render_active_cups_table(
    ctx: StoryReportContext,
    ui: dict[str, Any],
) -> str:
    """Render Chapter 1 active CUPS table (4 columns) with interactive service jump buttons."""
    rows: list[str] = []
    tot_cons = sum(item.annual_consumption_kwh for item in ctx.active_cups)
    has_primary = any(item.primary for item in ctx.active_cups)

    for idx, item in enumerate(ctx.active_cups, start=1):
        service_name = (
            escape(item.use)
            if item.use
            else f"<span data-i18n='default_service'>{ui['default_service']}</span>"
        )
        primary_badge = (
            f" <span class='primary-sun' data-i18n-title='ch1_primary_tip' "
            f"data-i18n-aria='ch1_primary_tip' title='{escape(ui['ch1_primary_tip'])}' "
            f"aria-label='{escape(ui['ch1_primary_tip'])}'>☀️</span>"
            if item.primary
            else ""
        )
        bar_w = max(0.0, min(100.0, item.consumption_share_pct))

        rows.append(
            "<tr>"
            f"<td class='num muted'>{idx}</td>"
            f"<td><button type='button' class='cups-jump-btn' data-cups='{escape(item.cups, quote=True)}' "
            f"onclick=\"jumpToCupsConsumption(this.getAttribute('data-cups'))\" "
            f"data-i18n-title='ch1_jump_tip' title='{escape(ui['ch1_jump_tip'])}'>"
            f"<span class='color-dot' style='background:{item.color};'></span>"
            f"<strong>{service_name}</strong><span class='jump-arrow' aria-hidden='true'> ↗</span>"
            f"</button>{primary_badge}</td>"
            f"<td><code class='cups-full'>{escape(item.cups)}</code></td>"
            f"<td class='num'><div><strong>{format_kwh(item.annual_consumption_kwh)}</strong> "
            f"<span class='muted'>({item.consumption_share_pct:.1f}%)</span></div>"
            f"<div class='mini-track'><div class='mini-fill' style='width:{bar_w:.1f}%;background:{item.color};'></div></div></td>"
            "</tr>"
        )

    tot_share_str = "100.0%" if tot_cons > 0 else "0.0%"
    primary_note = (
        f"<p class='table-footnote' data-i18n='ch1_primary_legend'>{ui['ch1_primary_legend']}</p>"
        if has_primary
        else ""
    )
    jump_note = f"<p class='table-footnote' data-i18n='ch1_jump_hint'>{ui['ch1_jump_hint']}</p>"
    return (
        "<div class='table-wrap'>"
        "<table id='activeCupsTable'>"
        "<thead><tr>"
        f"<th class='num' data-i18n='ch1_col_rank'>{ui['ch1_col_rank']}</th>"
        f"<th data-i18n='ch1_col_service'>{ui['ch1_col_service']}</th>"
        f"<th data-i18n='ch1_col_cups'>{ui['ch1_col_cups']}</th>"
        f"<th class='num'><span data-i18n='ch1_col_cons'>{ui['ch1_col_cons']}</span> ({escape(ctx.consumption_history.reference_period_label)})</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "<tfoot><tr>"
        "<td></td>"
        f"<td colspan='2'><span class='total-label' data-i18n='ch1_total_label'>{ui['ch1_total_label']}</span></td>"
        f"<td class='num total-val'>{format_kwh(tot_cons)} ({tot_share_str})</td>"
        "</tr></tfoot>"
        f"</table></div>{primary_note}{jump_note}"
    )


def _render_seasonal_spotlight(
    ctx: StoryReportContext,
    ui: dict[str, Any],
) -> str:
    """Render Winter vs. Summer seasonal spotlight comparison cards."""
    sp = ctx.seasonal_spotlight
    if sp.winter is None and sp.summer is None:
        return ""

    def _render_side(side: Any) -> str:
        is_w = side.season == "winter"
        icon = "❄️" if is_w else "☀️"
        title_key = "spotlight_winter" if is_w else "spotlight_summer"
        m_name = ui["months_full"].get(side.month_code, side.month_code)
        bars: list[str] = []
        for cups, use_val, pct, color in side.shares[:6]:
            lbl = escape(use_val or cups)
            bars.append(
                "<div class='spot-bar-row'>"
                f"<div class='spot-bar-head'><span>{lbl}</span><strong>{pct:.1f}%</strong></div>"
                f"<div class='spot-track'><div class='spot-fill' style='width:{min(100.0, max(0.0, pct)):.1f}%;background:{color};'></div></div>"
                "</div>"
            )
        return (
            f"<div class='spot-card spot-{side.season}'>"
            f"<div class='spot-header'><span class='spot-season'>{icon} <span data-i18n='{title_key}'>{ui[title_key]}</span></span>"
            f"<span class='spot-month' data-month-full='{side.month_code}'>{escape(m_name)}</span></div>"
            "<div class='spot-metrics'>"
            f"<div><span class='muted' data-i18n='spotlight_gen'>{ui['spotlight_gen']}</span><strong>{side.generation_kwh:,.0f} kWh</strong></div>"
            f"<div><span class='muted' data-i18n='spotlight_dem'>{ui['spotlight_dem']}</span><strong>{side.consumption_kwh:,.0f} kWh</strong></div>"
            f"<div><span class='muted' data-i18n='spotlight_sc'>{ui['spotlight_sc']}</span><strong class='text-emerald'>{side.self_consumed_kwh:,.0f} kWh</strong></div>"
            "</div>"
            f"<div class='spot-bars'>{''.join(bars)}</div>"
            "</div>"
        )

    cards_html: list[str] = []
    if sp.winter is not None:
        cards_html.append(_render_side(sp.winter))
    if sp.summer is not None:
        cards_html.append(_render_side(sp.summer))

    grid_cls = (
        "spotlight-grid single-season"
        if (sp.winter is None or sp.summer is None)
        else "spotlight-grid"
    )
    takeaway_html = ""
    if sp.winter is not None and sp.summer is not None and sp.top_mover_cups:
        mover_label = escape(sp.top_mover_use or sp.top_mover_cups)
        txt = ui["spotlight_mover_tpl"].format(
            use=mover_label,
            w=f"{sp.top_mover_winter_pct:.1f}",
            s=f"{sp.top_mover_summer_pct:.1f}",
        )
        takeaway_html = f"<p class='spotlight-note' id='spotlight-dynamic-note'>{txt}</p>"
    elif sp.winter is None or sp.summer is None:
        takeaway_html = f"<p class='spotlight-note' data-i18n='spotlight_single_note'>{ui['spotlight_single_note']}</p>"

    return (
        "<div class='subsection'>"
        f"<h3 class='sub-title' data-i18n='spotlight_title'>{ui['spotlight_title']}</h3>"
        f"<div class='{grid_cls}'>{''.join(cards_html)}</div>"
        f"{takeaway_html}"
        "</div>"
    )


_CSS_STYLES: str = """
        :root {
            font-size: 16px;
            --bg-base: #fafaf7;
            --bg-surface: #ffffff;
            --bg-subtle: #f3f1ea;
            --bg-card: #ffffff;
            --bg-card-hover: #f8fafc;
            --border-subtle: #e2e8f0;
            --border-strong: #cbd5e1;
            --text-main: #0f172a;
            --text-muted: #475569;
            --text-dim: #64748b;
            --accent-solar: #d97706;
            --accent-demand: #0284c7;
            --accent-sc: #059669;
            --accent-purple: #7c3aed;
            --accent-danger: #dc2626;
            --focus-ring: 0 0 0 3px rgba(2, 132, 199, 0.45);
            --shadow-card: 0 4px 20px -4px rgba(15, 23, 42, 0.08);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 20px;
            --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            --font-mono: 'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace;
        }
        [data-font-scale="sm"] { font-size: 14.5px; }
        [data-font-scale="md"] { font-size: 16px; }
        [data-font-scale="lg"] { font-size: 18.5px; }
        [data-font-scale="xl"] { font-size: 21px; }

        [data-theme="dark"] {
            --bg-base: #0b1120;
            --bg-surface: #111827;
            --bg-subtle: #1e293b;
            --bg-card: rgba(17, 24, 39, 0.92);
            --bg-card-hover: #1e293b;
            --border-subtle: rgba(148, 163, 184, 0.2);
            --border-strong: rgba(148, 163, 184, 0.35);
            --text-main: #f8fafc;
            --text-muted: #cbd5e1;
            --text-dim: #94a3b8;
            --accent-solar: #fbbf24;
            --accent-demand: #38bdf8;
            --accent-sc: #34d399;
            --accent-purple: #a78bfa;
            --shadow-card: 0 10px 30px -8px rgba(0, 0, 0, 0.45);
        }

        [data-theme="high-contrast"] {
            --bg-base: #000000;
            --bg-surface: #0a0a0a;
            --bg-subtle: #141414;
            --bg-card: #0a0a0a;
            --bg-card-hover: #1a1a1a;
            --border-subtle: #ffffff;
            --border-strong: #ffffff;
            --text-main: #ffffff;
            --text-muted: #f1f5f9;
            --text-dim: #e2e8f0;
            --accent-solar: #ffd43b;
            --accent-demand: #38bdf8;
            --accent-sc: #4ade80;
            --accent-purple: #e879f9;
            --focus-ring: 0 0 0 3px #ffd43b;
            --shadow-card: none;
        }
        [data-theme="high-contrast"] .story-section,
        [data-theme="high-contrast"] .glossary-card,
        [data-theme="high-contrast"] .spot-card,
        [data-theme="high-contrast"] .insight-card,
        [data-theme="high-contrast"] .fz-step-card,
        [data-theme="high-contrast"] .sky-breakdown-card {
            border-width: 2px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }

        body {
            font-family: var(--font-sans);
            background: var(--bg-base);
            color: var(--text-main);
            line-height: 1.6;
            padding-bottom: 4rem;
        }

        :focus-visible { outline: none; box-shadow: var(--focus-ring); }

        .skip-link {
            position: absolute;
            left: -9999px;
            top: 8px;
            z-index: 2000;
            background: var(--accent-demand);
            color: #ffffff;
            font-weight: 700;
            padding: 0.65rem 1rem;
            border-radius: var(--radius-sm);
            text-decoration: none;
        }
        .skip-link:focus { left: 12px; }

        #reading-progress {
            position: fixed;
            top: 0;
            left: 0;
            height: 4px;
            width: 0%;
            z-index: 1500;
            background: linear-gradient(90deg, var(--accent-solar), var(--accent-demand), var(--accent-sc));
        }

        /* Sticky Chapter & Accessibility Toolbar */
        .story-nav {
            position: sticky;
            top: 0;
            z-index: 1000;
            background: var(--bg-surface);
            border-bottom: 1px solid var(--border-subtle);
            box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
        }
        .nav-inner {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0.65rem 1.25rem;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
        }
        .chapter-links {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
        }
        .nav-pill {
            text-decoration: none;
            color: var(--text-muted);
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.35rem 0.65rem;
            border-radius: 999px;
            border: 1px solid transparent;
            transition: background 0.15s, color 0.15s;
        }
        .nav-pill:hover { background: var(--bg-subtle); color: var(--text-main); }
        .nav-pill[aria-current="location"] {
            background: var(--accent-sc);
            color: #ffffff;
        }
        [data-theme="high-contrast"] .nav-pill[aria-current="location"] {
            background: #ffd43b;
            color: #000000;
        }

        .controls-group {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.45rem;
        }
        .seg-group {
            display: inline-flex;
            background: var(--bg-subtle);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-sm);
            padding: 2px;
            gap: 2px;
        }
        .btn-seg, .btn-tool {
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-size: 0.78rem;
            font-weight: 700;
            padding: 0.32rem 0.58rem;
            border-radius: 6px;
            cursor: pointer;
        }
        .btn-seg:hover, .btn-tool:hover { color: var(--text-main); background: var(--bg-card-hover); }
        .btn-seg.active { background: var(--accent-demand); color: #ffffff; }
        [data-theme="high-contrast"] .btn-seg.active { background: #ffd43b; color: #000000; }
        .btn-tool {
            border: 1px solid var(--border-subtle);
            background: var(--bg-surface);
            color: var(--text-main);
        }

        .container { max-width: 1160px; margin: 0 auto; padding: 1.75rem 1.25rem 0; }

        /* Hero */
        .story-hero {
            background: linear-gradient(135deg, rgba(217, 119, 6, 0.08) 0%, rgba(2, 132, 199, 0.08) 60%, rgba(5, 150, 105, 0.08) 100%), var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-xl);
            padding: 2.2rem 2rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow-card);
        }
        .hero-eyebrow {
            display: inline-block;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--accent-solar);
            margin-bottom: 0.45rem;
        }
        .story-hero h1 {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.2;
            letter-spacing: -0.02em;
            margin-bottom: 0.65rem;
        }
        .hero-sub {
            font-size: 1.02rem;
            color: var(--text-muted);
            max-width: 78ch;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.72rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            background: var(--bg-subtle);
            border: 1px solid var(--border-subtle);
            color: var(--text-muted);
        }
        .badge-ted { color: var(--accent-demand); border-color: rgba(2, 132, 199, 0.4); }
        .badge-mode { color: var(--accent-sc); border-color: rgba(5, 150, 105, 0.4); }

        /* Story Sections */
        .story-section {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-xl);
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow-card);
            scroll-margin-top: 4.5rem;
        }
        .chapter-head { margin-bottom: 1.35rem; }
        .chapter-badge {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            background: var(--bg-subtle);
            color: var(--accent-demand);
            margin-bottom: 0.45rem;
        }
        .chapter-title { font-size: 1.45rem; font-weight: 800; letter-spacing: -0.015em; margin-bottom: 0.45rem; }
        .chapter-intro { color: var(--text-muted); max-width: 78ch; font-size: 0.96rem; }
        .sub-title { font-size: 1.12rem; font-weight: 700; margin-bottom: 0.85rem; }
        .subsection { margin-top: 1.85rem; padding-top: 1.6rem; border-top: 1px solid var(--border-subtle); }

        /* Callouts & Diagrams */
        .callout {
            display: flex;
            align-items: flex-start;
            gap: 0.9rem;
            background: var(--bg-subtle);
            border: 1px solid var(--border-subtle);
            border-left: 4px solid var(--accent-demand);
            border-radius: var(--radius-md);
            padding: 1rem 1.2rem;
            margin-top: 1.25rem;
            font-size: 0.9rem;
            color: var(--text-muted);
        }
        .callout.callout-solar { border-left-color: var(--accent-solar); }
        .callout.callout-sc { border-left-color: var(--accent-sc); }
        .callout h3 { font-size: 0.98rem; color: var(--text-main); margin-bottom: 0.25rem; }
        .fake-zero-box {
            margin-top: 1.5rem;
            background: var(--bg-subtle);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 1.4rem 1.5rem;
        }
        .fake-zero-head p { font-size: 0.92rem; color: var(--text-muted); max-width: 78ch; }
        .recovered-pill-banner {
            display: inline-flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.45rem;
            margin-top: 0.85rem;
            padding: 0.45rem 0.9rem;
            border-radius: var(--radius-sm);
            background: rgba(5, 150, 105, 0.14);
            border: 1px solid rgba(5, 150, 105, 0.35);
            color: var(--accent-sc);
            font-size: 0.88rem;
            font-weight: 700;
        }
        .fake-zero-steps {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.9rem;
            margin-top: 1.1rem;
        }
        .fz-step-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-top: 3px solid var(--accent-demand);
            border-radius: var(--radius-md);
            padding: 0.9rem 1rem;
        }
        .fz-step-card.step-solar { border-top-color: var(--accent-solar); }
        .fz-step-card.step-sc { border-top-color: var(--accent-sc); }
        .fz-step-card h4 { font-size: 0.88rem; font-weight: 800; color: var(--text-main); margin-bottom: 0.35rem; }
        .fz-step-card p { font-size: 0.84rem; color: var(--text-muted); line-height: 1.5; }
        .fake-zero-diagram-wrap {
            margin-top: 1.15rem;
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 0.75rem;
        }
        .fz-zone { stroke-width: 1.4; stroke-dasharray: 5 4; }
        .fz-zone-home { fill: rgba(5, 150, 105, 0.04); stroke: rgba(5, 150, 105, 0.35); }
        .fz-zone-grid { fill: rgba(2, 132, 199, 0.04); stroke: rgba(2, 132, 199, 0.35); }
        .fz-zone-lbl { font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; fill: var(--text-dim); font-family: var(--font-sans); }
        .fz-box-panels { fill: rgba(217, 119, 6, 0.11); stroke: var(--accent-solar); stroke-width: 1.8; }
        .fz-box-primary { fill: rgba(5, 150, 105, 0.11); stroke: var(--accent-sc); stroke-width: 1.8; }
        .fz-box-meter { fill: rgba(2, 132, 199, 0.1); stroke: var(--accent-demand); stroke-width: 1.8; }
        .fz-box-title { font-size: 12.5px; font-weight: 800; fill: var(--text-main); font-family: var(--font-sans); }
        .fz-box-sub { font-size: 10.5px; fill: var(--text-muted); font-family: var(--font-sans); }
        .fz-box-sub-sc { font-size: 11px; font-weight: 700; fill: var(--accent-sc); font-family: var(--font-sans); }
        .fz-pill-solar-bg { fill: rgba(217, 119, 6, 0.18); stroke: var(--accent-solar); stroke-width: 1; }
        .fz-pill-solar { font-size: 11px; font-weight: 800; fill: var(--accent-solar); font-family: var(--font-sans); }
        .fz-flow-pill-sc { fill: var(--bg-surface); stroke: var(--accent-sc); stroke-width: 1.5; }
        .fz-flow-txt-sc { font-size: 11px; font-weight: 800; fill: var(--accent-sc); font-family: var(--font-sans); }
        .fz-flow-pill-exp { fill: var(--bg-surface); stroke: var(--accent-demand); stroke-width: 1.5; }
        .fz-flow-txt-exp { font-size: 11px; font-weight: 800; fill: var(--accent-demand); font-family: var(--font-sans); }
        .fz-pill-alert-bg { fill: rgba(220, 38, 38, 0.14); stroke: #dc2626; stroke-width: 1.2; }
        .fz-pill-alert { font-size: 11px; font-weight: 800; fill: #dc2626; font-family: var(--font-sans); }
        [data-theme="dark"] .fz-pill-alert, [data-theme="high-contrast"] .fz-pill-alert { fill: #fca5a5; }
        [data-theme="dark"] .fz-pill-alert-bg, [data-theme="high-contrast"] .fz-pill-alert-bg { stroke: #f87171; }
        .fz-note-dim { font-size: 10.5px; font-weight: 600; fill: var(--text-dim); font-family: var(--font-sans); }

        /* Controls & Interactive Chart Toolbars */
        .chart-card-box {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 1.25rem 1.35rem;
            margin-top: 1.15rem;
        }
        .chart-controls-row {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 0.85rem;
            margin-bottom: 0.9rem;
        }
        .subcontrols-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.65rem;
            padding: 0.7rem 0.9rem;
            background: var(--bg-subtle);
            border-radius: var(--radius-md);
            margin-bottom: 1rem;
            font-size: 0.84rem;
        }
        .pill-btn {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border: 1px solid var(--border-strong);
            background: var(--bg-surface);
            color: var(--text-main);
            padding: 0.36rem 0.75rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
        }
        .pill-btn:hover { background: var(--bg-card-hover); }
        .pill-btn.active {
            background: var(--accent-demand);
            color: #ffffff;
            border-color: var(--accent-demand);
        }
        [data-theme="high-contrast"] .pill-btn.active {
            background: #ffd43b;
            color: #000000;
            border-color: #ffd43b;
        }
        .pill-btn:disabled { opacity: 0.42; cursor: not-allowed; }
        .select-input {
            padding: 0.38rem 0.7rem;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-strong);
            background: var(--bg-surface);
            color: var(--text-main);
            font-size: 0.84rem;
            font-weight: 600;
        }
        .checkbox-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.32rem 0.72rem;
            border-radius: 999px;
            border: 1px solid var(--border-strong);
            background: var(--bg-surface);
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
        }
        .chart-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 0.85rem 1.25rem;
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-top: 0.75rem;
        }
        .legend-item { display: inline-flex; align-items: center; gap: 0.4rem; font-weight: 600; }
        .legend-swatch { width: 16px; height: 4px; border-radius: 2px; display: inline-block; }
        .legend-bar-swatch { width: 14px; height: 10px; border-radius: 3px; display: inline-block; }
        .monthly-balance-legend { margin-top: 0; margin-bottom: 0.75rem; }
        .chart-stats-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 0.75rem;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-subtle);
        }
        .stat-chip {
            background: var(--bg-subtle);
            border-radius: var(--radius-sm);
            padding: 0.65rem 0.85rem;
        }
        .stat-chip-label { font-size: 0.74rem; color: var(--text-dim); font-weight: 700; text-transform: uppercase; }
        .stat-chip-val { font-size: 1.05rem; font-weight: 800; margin-top: 0.1rem; }
        .stat-chip-sub { font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem; font-weight: 600; }

        /* Weather Sky Breakdown & Weather-Energy Insights */
        .sky-breakdown-card {
            margin-top: 1rem;
            padding: 0.9rem 1rem;
            background: var(--bg-subtle);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
        }
        .sky-breakdown-head {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.84rem;
            font-weight: 700;
            margin-bottom: 0.55rem;
        }
        .sky-stacked-bar {
            width: 100%;
            height: 16px;
            border-radius: 999px;
            overflow: hidden;
            display: flex;
            background: var(--border-subtle);
        }
        .sky-bar-seg { height: 100%; }
        .sky-counts-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem 1.15rem;
            margin-top: 0.6rem;
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 600;
        }
        .weather-insights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1rem;
            margin-top: 1.25rem;
        }
        .insight-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-left: 4px solid var(--accent-demand);
            border-radius: var(--radius-md);
            padding: 1.05rem 1.2rem;
        }
        .insight-card.insight-solar { border-left-color: var(--accent-solar); }
        .insight-card h3 { font-size: 0.96rem; font-weight: 800; margin-bottom: 0.4rem; }
        .insight-card p { font-size: 0.88rem; color: var(--text-muted); line-height: 1.55; }
        .insight-card p + p { margin-top: 0.4rem; }

        /* Neighbour Impact Equivalences */
        .impact-strip {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px dashed var(--border-subtle);
        }
        .impact-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.75rem;
        }
        .impact-chip {
            background: linear-gradient(135deg, rgba(5, 150, 105, 0.08), rgba(217, 119, 6, 0.08)), var(--bg-subtle);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 0.75rem 0.9rem;
        }
        .impact-val { font-size: 1.18rem; font-weight: 800; color: var(--accent-sc); margin-top: 0.15rem; }
        .impact-note { font-size: 0.76rem; color: var(--text-dim); margin-top: 0.55rem; }
        .prev-impact-note {
            margin-top: 0.85rem;
            padding: 0.75rem 1rem;
            border-radius: var(--radius-md);
            background: rgba(5, 150, 105, 0.1);
            border: 1px solid rgba(5, 150, 105, 0.3);
            font-size: 0.88rem;
            color: var(--text-main);
        }
        @keyframes cardFlash {
            0% { box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.55); border-color: var(--accent-demand); }
            100% { box-shadow: var(--shadow-card); border-color: var(--border-subtle); }
        }
        .chart-flash { animation: cardFlash 1.4s ease-out; }

        /* SVG Styling */
        .chart-container { width: 100%; position: relative; }
        .chart-svg { width: 100%; height: auto; overflow: visible; display: block; }
        .grid-line { stroke: var(--border-subtle); stroke-dasharray: 3 3; stroke-width: 1; }
        .axis-label, .x-label { font-size: 11px; fill: var(--text-dim); font-family: var(--font-sans); }
        .x-label { font-weight: 600; fill: var(--text-muted); }
        .chart-col { cursor: pointer; }
        .hover-bg { fill: transparent; }
        .chart-col:hover .hover-bg, .chart-col:focus .hover-bg { fill: rgba(2, 132, 199, 0.08); }
        .crosshair-line { stroke: var(--text-dim); stroke-width: 1; stroke-dasharray: 4 3; opacity: 0; pointer-events: none; }
        .chart-col:hover .crosshair-line, .chart-col:focus .crosshair-line { opacity: 0.75; }

        /* Spotlight & 4-Way Progression */
        .spotlight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
        .spotlight-grid.single-season { grid-template-columns: 1fr; }
        @media (max-width: 768px) { .spotlight-grid { grid-template-columns: 1fr; } }
        .spot-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 1.25rem;
        }
        .spot-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem; }
        .spot-season { font-weight: 800; font-size: 1rem; }
        .spot-month { font-size: 0.85rem; font-weight: 700; color: var(--accent-demand); }
        .spot-metrics {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
            padding: 0.65rem 0.75rem;
            background: var(--bg-subtle);
            border-radius: var(--radius-sm);
            margin-bottom: 0.9rem;
            font-size: 0.8rem;
        }
        .spot-metrics strong { display: block; font-size: 0.92rem; }
        .spot-bar-row { margin-bottom: 0.55rem; }
        .spot-bar-head { display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.2rem; }
        .spot-track { width: 100%; height: 9px; background: var(--bg-subtle); border-radius: 999px; overflow: hidden; }
        .spot-fill { height: 100%; border-radius: 999px; }
        .spotlight-note { margin-top: 0.9rem; font-size: 0.9rem; color: var(--text-muted); }

        .section-hourly-prevision {
            margin-top: 1.85rem;
            padding: 1.5rem;
            background: linear-gradient(135deg, rgba(2, 132, 199, 0.06) 0%, rgba(5, 150, 105, 0.06) 100%), var(--bg-surface);
            border: 1px solid var(--border-strong);
            border-radius: var(--radius-lg);
        }
        .title-with-pill { display: flex; flex-wrap: wrap; align-items: center; gap: 0.55rem; margin-bottom: 0.35rem; }
        .hourly-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
            gap: 0.9rem;
            margin: 1.15rem 0 1.35rem;
        }
        .hourly-kpi-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1rem 1.1rem;
        }
        .card-highlight { border-color: var(--accent-solar); }
        .hourly-kpi-label { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); display: block; }
        .hourly-kpi-val { font-size: 1.4rem; font-weight: 800; margin: 0.25rem 0; }
        .hourly-kpi-sub { font-size: 0.79rem; color: var(--text-muted); }
        .pill-uplift { background: rgba(217, 119, 6, 0.16); color: var(--accent-solar); padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 700; }
        .pill-uplift-green { background: rgba(5, 150, 105, 0.16); color: var(--accent-sc); padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 700; }
        .pill-fortnight, .pill-cyan { background: rgba(2, 132, 199, 0.16); color: var(--accent-demand); padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 700; }
        .pill-dim { background: var(--bg-subtle); color: var(--text-dim); padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 700; }

        .comparison-bar-container {
            background: var(--bg-subtle);
            border-radius: var(--radius-md);
            padding: 1.1rem 1.25rem;
        }
        .comp-bar-row { margin-bottom: 0.95rem; }
        .comp-bar-row:last-child { margin-bottom: 0; }
        .comp-bar-meta { display: flex; justify-content: space-between; font-size: 0.84rem; margin-bottom: 0.35rem; font-weight: 600; }
        .comp-bar-track { width: 100%; height: 14px; background: var(--border-subtle); border-radius: 999px; display: flex; overflow: hidden; }
        .fill-single { height: 100%; background: #64748b; }
        .fill-monthly { height: 100%; background: var(--accent-sc); }
        .fill-fortnight { height: 100%; background: var(--accent-demand); }
        .fill-uplift { height: 100%; background: repeating-linear-gradient(45deg, #f59e0b, #f59e0b 8px, #d97706 8px, #d97706 16px); }

        /* Tables & Chapter 1 Interactive Service Links */
        .table-wrap { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
        th {
            padding: 0.7rem 0.6rem;
            font-weight: 700;
            color: var(--text-dim);
            border-bottom: 2px solid var(--border-subtle);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            text-align: left;
        }
        td { padding: 0.65rem 0.6rem; border-bottom: 1px solid var(--border-subtle); vertical-align: middle; }
        tfoot td {
            padding: 0.75rem 0.6rem;
            font-weight: 700;
            border-top: 2px solid var(--border-strong);
            border-bottom: none;
            background: var(--bg-subtle);
        }
        .num, .text-right { text-align: right; font-variant-numeric: tabular-nums; }
        .font-bold { font-weight: 700; }
        .muted { color: var(--text-dim); }
        .color-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 0.45rem; vertical-align: middle; }
        .cups-jump-btn {
            display: inline-flex;
            align-items: center;
            gap: 0.15rem;
            background: transparent;
            border: 1px solid transparent;
            border-radius: 6px;
            padding: 0.2rem 0.45rem;
            margin-left: -0.45rem;
            color: var(--text-main);
            font-family: inherit;
            font-size: inherit;
            cursor: pointer;
            text-align: left;
            transition: background 0.15s, border-color 0.15s, color 0.15s;
        }
        .cups-jump-btn:hover {
            background: var(--bg-subtle);
            border-color: var(--border-strong);
            color: var(--accent-demand);
        }
        .jump-arrow { font-size: 0.82em; color: var(--accent-demand); opacity: 0.8; }
        .primary-sun { margin-left: 0.3rem; font-size: 0.9em; vertical-align: baseline; }
        .table-footnote { margin-top: 0.5rem; font-size: 0.82rem; color: var(--text-dim); }
        .cups-full, .cups-id { font-family: var(--font-mono); font-size: 0.79rem; color: var(--text-muted); }
        .mini-track { width: 100%; height: 6px; background: var(--bg-subtle); border-radius: 999px; overflow: hidden; margin-top: 0.25rem; }
        .mini-fill { height: 100%; border-radius: 999px; }
        .total-val { color: var(--accent-sc); font-family: var(--font-mono); }
        .total-label { font-weight: 800; color: var(--text-main); }

        /* Glossary */
        .glossary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1rem;
            margin-top: 1.15rem;
        }
        .glossary-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1.1rem 1.2rem;
        }
        .glossary-card h3 { font-size: 0.96rem; font-weight: 700; color: var(--accent-demand); margin-bottom: 0.35rem; }
        .glossary-card p { font-size: 0.87rem; color: var(--text-muted); }

        .text-amber { color: var(--accent-solar); }
        .text-cyan { color: var(--accent-demand); }
        .text-emerald { color: var(--accent-sc); }
        .text-purple { color: var(--accent-purple); }
        .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }

        /* Tooltip */
        #tooltip {
            position: fixed;
            display: none;
            background: #0f172a;
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.22);
            border-radius: var(--radius-md);
            padding: 0.75rem 0.95rem;
            font-size: 0.82rem;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
            pointer-events: none;
            z-index: 2000;
            max-width: 310px;
        }

        footer { margin-top: 2.5rem; text-align: center; color: var(--text-dim); font-size: 0.84rem; }

        @media print {
            body { background: #ffffff !important; color: #000000 !important; padding: 0; }
            .story-nav, #reading-progress, .skip-link, .controls-group, #tooltip { display: none !important; }
            .story-section, .story-hero { box-shadow: none !important; border: 1px solid #cbd5e1 !important; background: #ffffff !important; break-inside: avoid; }
        }
"""

_SCRIPT_BODY: str = """
        let currentLang = __INIT_LANG__;
        const PRIMARY_DISPLAY = __PRIMARY_JSON__;
        const I18N = __I18N_JSON__;
        const STORY_DATA = __STORY_JSON__;
        const PREVISION_CTX = __PREV_JSON__;
        const SPOTLIGHT_META = __SPOT_JSON__;

        const FONT_SCALES = ['sm', 'md', 'lg', 'xl'];
        const THEME_BTNS = { light: 'btn-theme-light', dark: 'btn-theme-dark', 'high-contrast': 'btn-theme-hc' };
        let fontIdx = 1;
        let consMode = 'community';
        let consSelectedYears = [];
        let consSelectedCups = '';
        let consCompareYear = '';
        let consCompareCups = [];
        let genSelectedYears = [];
        let genOverlayDemand = false;
        let weatherMetric = 'temp';
        let weatherSelectedYears = [];

        function escapeHtml(val) {
            return String(val ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function fmtNum(val, dec) {
            return Number(val).toLocaleString(currentLang === 'es' ? 'es-ES' : 'en-US', {
                minimumFractionDigits: dec,
                maximumFractionDigits: dec
            });
        }

        function fmtCo2(kg) {
            if (kg >= 1000) return fmtNum(kg / 1000, 2) + ' t CO₂';
            return fmtNum(kg, 0) + ' kg CO₂';
        }

        function fmtKwh(val) {
            if (val === null || val === undefined || isNaN(val)) return '—';
            return fmtNum(val, 1) + ' kWh';
        }

        function fmtTick(val) {
            if (val >= 10000) return (val / 1000).toFixed(1) + ' MWh';
            return Math.round(val).toLocaleString(currentLang === 'es' ? 'es-ES' : 'en-US') + ' kWh';
        }

        function niceCeiling(maxVal) {
            if (!maxVal || maxVal <= 0) return 100;
            const raw = maxVal * 1.14;
            const mag = Math.pow(10, Math.floor(Math.log10(raw)));
            const norm = raw / mag;
            const step = norm <= 1.2 ? 1.2 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
            return step * mag;
        }

        function markerPath(shape, cx, cy, r) {
            if (shape === 'square') {
                const s = r * 1.65;
                return `<rect x="${(cx - s / 2).toFixed(1)}" y="${(cy - s / 2).toFixed(1)}" width="${s.toFixed(1)}" height="${s.toFixed(1)}" rx="1.5"`;
            }
            if (shape === 'diamond') {
                const d = r * 1.35;
                return `<polygon points="${cx.toFixed(1)},${(cy - d).toFixed(1)} ${(cx + d).toFixed(1)},${cy.toFixed(1)} ${cx.toFixed(1)},${(cy + d).toFixed(1)} ${(cx - d).toFixed(1)},${cy.toFixed(1)}"`;
            }
            if (shape === 'triangle') {
                const d = r * 1.35;
                return `<polygon points="${cx.toFixed(1)},${(cy - d).toFixed(1)} ${(cx + d).toFixed(1)},${(cy + d * 0.85).toFixed(1)} ${(cx - d).toFixed(1)},${(cy + d * 0.85).toFixed(1)}"`;
            }
            return `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(1)}"`;
        }

        function renderLineChartSvg(svgId, seriesList, options) {
            const svg = document.getElementById(svgId);
            if (!svg) return;
            const t = I18N[currentLang] || I18N.en;
            const width = 940;
            const height = 340;
            const padL = 74;
            const padR = 26;
            const padT = 28;
            const padB = 46;
            const chartW = width - padL - padR;
            const chartH = height - padT - padB;
            const slotW = chartW / 12;

            const allNums = [];
            seriesList.forEach(s => {
                (s.values || []).forEach(v => { if (v !== null && v !== undefined) allNums.push(Number(v)); });
            });

            if (allNums.length === 0) {
                svg.setAttribute('viewBox', `0 0 ${width} 140`);
                svg.innerHTML = `<text x="${width / 2}" y="75" text-anchor="middle" class="axis-label">${escapeHtml(t.chart_empty)}</text>`;
                return;
            }

            svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
            const yMax = niceCeiling(Math.max.apply(null, allNums.concat([1])));
            const isHc = document.documentElement.getAttribute('data-theme') === 'high-contrast';
            const parts = [];

            for (let tier = 0; tier <= 4; tier++) {
                const tv = (yMax / 4) * tier;
                const yp = padT + chartH - (chartH * (tier / 4));
                parts.push(`<line x1="${padL}" y1="${yp.toFixed(1)}" x2="${width - padR}" y2="${yp.toFixed(1)}" class="grid-line"/>`);
                parts.push(`<text x="${padL - 10}" y="${(yp + 4).toFixed(1)}" text-anchor="end" class="axis-label">${escapeHtml(fmtTick(tv))}</text>`);
            }

            const xOf = mIdx => padL + mIdx * slotW + slotW / 2;
            const yOf = val => padT + chartH - (Number(val) / yMax) * chartH;

            seriesList.forEach((s, sIdx) => {
                const shape = STORY_DATA.shapes[sIdx % STORY_DATA.shapes.length];
                const baseDash = s.forceDash || (isHc ? STORY_DATA.dashes[sIdx % STORY_DATA.dashes.length] : '');
                const vals = s.values || [];
                const stats = s.statuses || [];

                for (let i = 0; i < 11; i++) {
                    if (vals[i] === null || vals[i] === undefined || vals[i + 1] === null || vals[i + 1] === undefined) continue;
                    const incSeg = stats[i] === 'incomplete' || stats[i + 1] === 'incomplete';
                    const dash = incSeg ? '5 4' : baseDash;
                    const op = incSeg ? '0.78' : '0.95';
                    const dashAttr = dash ? ` stroke-dasharray="${dash}"` : '';
                    parts.push(`<line x1="${xOf(i).toFixed(1)}" y1="${yOf(vals[i]).toFixed(1)}" x2="${xOf(i + 1).toFixed(1)}" y2="${yOf(vals[i + 1]).toFixed(1)}" stroke="${s.color}" stroke-width="2.8" stroke-linecap="round" stroke-opacity="${op}"${dashAttr}/>`);
                }

                for (let i = 0; i < 12; i++) {
                    if (vals[i] === null || vals[i] === undefined) continue;
                    const cx = xOf(i);
                    const cy = yOf(vals[i]);
                    const isInc = stats[i] === 'incomplete';
                    const fill = isInc ? 'var(--bg-surface)' : s.color;
                    const strokeW = isInc ? '2.5' : '1.6';
                    const strokeCol = isInc ? s.color : 'var(--bg-surface)';
                    if (isInc) {
                        parts.push(`<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="7.5" fill="none" stroke="var(--accent-solar)" stroke-width="1.4" stroke-dasharray="2 2"/>`);
                    }
                    parts.push(`${markerPath(shape, cx, cy, isInc ? 4.8 : 4.6)} fill="${fill}" stroke="${strokeCol}" stroke-width="${strokeW}"/>`);
                }
            });

            for (let mIdx = 0; mIdx < 12; mIdx++) {
                const mCode = String(mIdx + 1).padStart(2, '0');
                const mShort = (t.months && t.months[mCode]) || mCode;
                const cx = xOf(mIdx);
                const tipPayload = escapeHtml(JSON.stringify({
                    chart: options.chartType,
                    mIdx: mIdx,
                    mCode: mCode
                }));
                parts.push(`<g class="chart-col" tabindex="0" data-line-tip="${tipPayload}" onmouseenter="showLineTooltip(event, this)" onfocus="showLineTooltip(event, this)" onmouseleave="hideTooltip()" onblur="hideTooltip()">`);
                parts.push(`<rect x="${(cx - slotW / 2).toFixed(1)}" y="${padT}" width="${slotW.toFixed(1)}" height="${chartH}" class="hover-bg"/>`);
                parts.push(`<line x1="${cx.toFixed(1)}" y1="${padT}" x2="${cx.toFixed(1)}" y2="${padT + chartH}" class="crosshair-line"/>`);
                parts.push(`<text x="${cx.toFixed(1)}" y="${height - padB + 22}" text-anchor="middle" class="x-label" data-month="${mCode}">${escapeHtml(mShort)}</text>`);
                parts.push(`</g>`);
            }
            svg.innerHTML = parts.join('');
        }

        function getActiveConsumptionSeries() {
            const cons = STORY_DATA.consumption;
            const palette = STORY_DATA.year_palette;
            if (consMode === 'compare') {
                const yr = consCompareYear || String(cons.years[cons.years.length - 1] || '');
                return consCompareCups.map(cid => {
                    const meta = (STORY_DATA.cups || []).find(c => c.cups === cid) || { use: cid, color: '#0284c7' };
                    const yrObj = (cons.by_cups[cid] && cons.by_cups[cid][yr]) || { values: [], statuses: [], days: [], annual_total_kwh: 0 };
                    return {
                        key: cid,
                        label: meta.use || cid,
                        color: meta.color,
                        values: yrObj.values,
                        statuses: yrObj.statuses,
                        days: yrObj.days,
                        annual_total_kwh: yrObj.annual_total_kwh,
                        isYearCompare: false
                    };
                });
            }
            const yrs = consSelectedYears.length ? consSelectedYears : [String(cons.years[cons.years.length - 1] || '')];
            return yrs.map((yr, idx) => {
                const yrObj = consMode === 'single'
                    ? ((cons.by_cups[consSelectedCups] && cons.by_cups[consSelectedCups][yr]) || { values: [], statuses: [], days: [], annual_total_kwh: 0 })
                    : (cons.community[yr] || { values: [], statuses: [], days: [], annual_total_kwh: 0 });
                return {
                    key: yr,
                    label: yr,
                    color: palette[idx % palette.length],
                    values: yrObj.values,
                    statuses: yrObj.statuses,
                    days: yrObj.days,
                    annual_total_kwh: yrObj.annual_total_kwh,
                    isYearCompare: true
                };
            });
        }

        function getActiveGenerationSeries() {
            const gen = STORY_DATA.generation;
            const palette = ['#d97706', '#059669', '#0284c7', '#7c3aed', '#db2777'];
            const yrs = genSelectedYears.length ? genSelectedYears : [String(gen.years[gen.years.length - 1] || '')];
            const out = yrs.map((yr, idx) => {
                const yrObj = gen.by_year[yr] || { values: [], statuses: [], days: [], annual_total_kwh: 0 };
                return {
                    key: yr,
                    label: yr,
                    color: palette[idx % palette.length],
                    values: yrObj.values,
                    statuses: yrObj.statuses,
                    days: yrObj.days,
                    annual_total_kwh: yrObj.annual_total_kwh,
                    isYearCompare: true
                };
            });
            if (genOverlayDemand && Array.isArray(gen.solar_hours_demand_by_month)) {
                const t = I18N[currentLang] || I18N.en;
                out.push({
                    key: 'solar_dem',
                    label: t.gen_legend_demand,
                    color: '#0284c7',
                    forceDash: '4 4',
                    values: gen.solar_hours_demand_by_month,
                    statuses: gen.solar_hours_demand_by_month.map(v => v === null ? 'no_data' : 'complete'),
                    days: [],
                    annual_total_kwh: gen.solar_hours_demand_by_month.reduce((acc, v) => acc + (v || 0), 0),
                    isYearCompare: false,
                    isReference: true
                });
            }
            return out;
        }

        function renderSeriesStats(containerId, seriesList, isGen) {
            const box = document.getElementById(containerId);
            if (!box) return;
            const t = I18N[currentLang] || I18N.en;
            const primaryList = seriesList.filter(s => !s.isReference);
            const focus = primaryList[primaryList.length - 1];
            if (!focus) { box.innerHTML = ''; return; }

            let totalSum = 0;
            let bestIdx = -1;
            let bestVal = -Infinity;
            let lowIdx = -1;
            let lowVal = Infinity;
            (focus.values || []).forEach((v, idx) => {
                if (v === null || v === undefined) return;
                const num = Number(v);
                totalSum += num;
                if (num > bestVal) { bestVal = num; bestIdx = idx; }
                if (num < lowVal) { lowVal = num; lowIdx = idx; }
            });

            const mName = idx => idx < 0 ? '—' : ((t.months && t.months[String(idx + 1).padStart(2, '0')]) || '');
            const lblTot = isGen ? t.gen_stat_total : t.stat_selected_total;
            const lblPeak = isGen ? t.gen_stat_peak : t.stat_peak_month;
            const lblLow = isGen ? t.gen_stat_low : t.stat_low_month;
            const lblYoy = isGen ? t.gen_stat_yoy : t.stat_yoy_delta;

            let yoyVal = '—';
            if (primaryList.length >= 2 && primaryList[0].isYearCompare) {
                const s0 = primaryList[0];
                const s1 = primaryList[primaryList.length - 1];
                let sum0 = 0;
                let sum1 = 0;
                for (let i = 0; i < 12; i++) {
                    if (s0.statuses[i] === 'complete' && s1.statuses[i] === 'complete' && s0.values[i] !== null && s1.values[i] !== null) {
                        sum0 += Number(s0.values[i]);
                        sum1 += Number(s1.values[i]);
                    }
                }
                if (sum0 > 0) {
                    const diff = sum1 - sum0;
                    const pct = (diff / sum0) * 100;
                    yoyVal = `${diff >= 0 ? '+' : ''}${pct.toFixed(1)}% (${s0.key}→${s1.key})`;
                }
            }

            box.innerHTML = `
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(lblTot)} (${escapeHtml(focus.label)})</div><div class="stat-chip-val">${escapeHtml(fmtKwh(totalSum))}</div></div>
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(lblPeak)}</div><div class="stat-chip-val">${escapeHtml(mName(bestIdx))} · ${bestIdx >= 0 ? escapeHtml(fmtKwh(bestVal)) : '—'}</div></div>
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(lblLow)}</div><div class="stat-chip-val">${escapeHtml(mName(lowIdx))} · ${lowIdx >= 0 ? escapeHtml(fmtKwh(lowVal)) : '—'}</div></div>
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(lblYoy)}</div><div class="stat-chip-val">${escapeHtml(yoyVal)}</div></div>
            `;
        }

        function renderChartLegend(containerId, seriesList) {
            const box = document.getElementById(containerId);
            if (!box) return;
            const t = I18N[currentLang] || I18N.en;
            const items = seriesList.map(s =>
                `<span class="legend-item"><span class="legend-swatch" style="background:${s.color};"></span>${escapeHtml(s.label)}</span>`
            );
            items.push(`<span class="legend-item">● ${escapeHtml(t.legend_complete)}</span>`);
            items.push(`<span class="legend-item">◌ ${escapeHtml(t.legend_incomplete)}</span>`);
            box.innerHTML = items.join('');
        }

        function renderConsumptionSubcontrols() {
            const bar = document.getElementById('cons-subcontrols');
            if (!bar) return;
            const t = I18N[currentLang] || I18N.en;
            const years = (STORY_DATA.consumption.years || []).map(String);
            const cupsList = STORY_DATA.cups || [];

            if (consMode === 'community') {
                const yrBtns = years.map(y =>
                    `<button type="button" class="pill-btn ${consSelectedYears.includes(y) ? 'active' : ''}" data-yr="${escapeHtml(y)}" onclick="toggleConsYear(this.getAttribute('data-yr'))">${escapeHtml(y)}</button>`
                ).join('');
                bar.innerHTML = `<strong>${escapeHtml(t.lbl_years)}:</strong> ${yrBtns}`;
            } else if (consMode === 'single') {
                const opts = cupsList.map(c =>
                    `<option value="${escapeHtml(c.cups)}" ${c.cups === consSelectedCups ? 'selected' : ''}>${escapeHtml(c.use || c.cups)} (${escapeHtml(c.cups)})</option>`
                ).join('');
                const yrBtns = years.map(y =>
                    `<button type="button" class="pill-btn ${consSelectedYears.includes(y) ? 'active' : ''}" data-yr="${escapeHtml(y)}" onclick="toggleConsYear(this.getAttribute('data-yr'))">${escapeHtml(y)}</button>`
                ).join('');
                bar.innerHTML = `<label for="cons-cups-select"><strong>${escapeHtml(t.lbl_service)}:</strong></label><select id="cons-cups-select" class="select-input" onchange="changeConsCups(this.value)">${opts}</select><strong>${escapeHtml(t.lbl_years)}:</strong> ${yrBtns}`;
            } else {
                const yrBtns = years.map(y =>
                    `<button type="button" class="pill-btn ${consCompareYear === y ? 'active' : ''}" data-yr="${escapeHtml(y)}" onclick="setCompareYear(this.getAttribute('data-yr'))">${escapeHtml(y)}</button>`
                ).join('');
                const cBtns = cupsList.map(c =>
                    `<button type="button" class="pill-btn ${consCompareCups.includes(c.cups) ? 'active' : ''}" data-cups="${escapeHtml(c.cups)}" onclick="toggleCompareCups(this.getAttribute('data-cups'))"><span class="color-dot" style="background:${c.color};"></span>${escapeHtml(c.use || c.cups)}</button>`
                ).join('');
                const quick = `<button type="button" class="btn-tool" onclick="selectTop4Cups()">${escapeHtml(t.btn_top4)}</button><button type="button" class="btn-tool" onclick="selectAllCompareCups()">${escapeHtml(t.btn_all_cups)}</button>`;
                bar.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:0.45rem;align-items:center;width:100%;"><strong>${escapeHtml(t.lbl_year)}:</strong> ${yrBtns} ${quick}</div><div style="display:flex;flex-wrap:wrap;gap:0.4rem;align-items:center;width:100%;"><strong>${escapeHtml(t.lbl_services)}:</strong> ${cBtns}</div>`;
            }
        }

        function renderConsumptionSection() {
            renderConsumptionSubcontrols();
            const series = getActiveConsumptionSeries();
            renderLineChartSvg('consumption-chart-svg', series, { chartType: 'cons' });
            renderChartLegend('cons-chart-legend', series);
            renderSeriesStats('cons-chart-stats', series, false);
        }

        function renderGenerationControls() {
            const bar = document.getElementById('gen-subcontrols');
            if (!bar) return;
            const t = I18N[currentLang] || I18N.en;
            const years = (STORY_DATA.generation.years || []).map(String);
            const yrBtns = years.map(y =>
                `<button type="button" class="pill-btn ${genSelectedYears.includes(y) ? 'active' : ''}" data-yr="${escapeHtml(y)}" onclick="toggleGenYear(this.getAttribute('data-yr'))">${escapeHtml(y)}</button>`
            ).join('');
            bar.innerHTML = `<strong>${escapeHtml(t.lbl_years)}:</strong> ${yrBtns}<label class="checkbox-pill"><input type="checkbox" ${genOverlayDemand ? 'checked' : ''} onchange="toggleGenDemand(this.checked)"> ${escapeHtml(t.toggle_daylight_demand)}</label>`;
        }

        function updateGenDynamicInsight(seriesList) {
            const box = document.getElementById('gen-dynamic-insight');
            if (!box) return;
            const t = I18N[currentLang] || I18N.en;
            const primary = seriesList.filter(s => !s.isReference);
            const focus = primary[primary.length - 1];
            if (!focus) { box.style.display = 'none'; return; }

            let totalSum = 0;
            let bestIdx = -1;
            let bestVal = -1;
            let lowIdx = -1;
            let lowVal = Infinity;
            (focus.values || []).forEach((v, idx) => {
                if (v === null || v === undefined) return;
                const num = Number(v);
                totalSum += num;
                if (num > bestVal) { bestVal = num; bestIdx = idx; }
                if (num > 0 && num < lowVal) { lowVal = num; lowIdx = idx; }
            });
            if (bestIdx < 0) { box.style.display = 'none'; return; }
            box.style.display = 'flex';
            const mName = idx => (t.months_full && t.months_full[String(idx + 1).padStart(2, '0')]) || '';
            let html = '';
            if (lowIdx >= 0 && bestIdx !== lowIdx && lowVal > 0 && (bestVal / lowVal) >= 1.1) {
                html = t.gen_insight_ratio_tpl
                    .replace('{year}', escapeHtml(focus.label))
                    .replace('{total}', escapeHtml(fmtKwh(totalSum)))
                    .replace('{peak_m}', escapeHtml(mName(bestIdx)))
                    .replace('{peak_val}', escapeHtml(fmtKwh(bestVal)))
                    .replace('{ratio}', escapeHtml(fmtNum(bestVal / lowVal, 1)))
                    .replace('{low_m}', escapeHtml(mName(lowIdx)))
                    .replace('{low_val}', escapeHtml(fmtKwh(lowVal)));
            } else {
                html = t.gen_insight_single_tpl
                    .replace('{year}', escapeHtml(focus.label))
                    .replace('{total}', escapeHtml(fmtKwh(totalSum)))
                    .replace('{peak_m}', escapeHtml(mName(bestIdx)))
                    .replace('{peak_val}', escapeHtml(fmtKwh(bestVal)));
            }
            if (primary.length >= 2) {
                const s0 = primary[0];
                const s1 = primary[primary.length - 1];
                let sum0 = 0;
                let sum1 = 0;
                for (let i = 0; i < 12; i++) {
                    if (s0.statuses[i] === 'complete' && s1.statuses[i] === 'complete' && s0.values[i] !== null && s1.values[i] !== null) {
                        sum0 += Number(s0.values[i]);
                        sum1 += Number(s1.values[i]);
                    }
                }
                if (sum0 > 0) {
                    const pct = ((sum1 - sum0) / sum0) * 100;
                    const pctStr = `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
                    html += t.gen_insight_yoy_tpl
                        .replace('{y0}', escapeHtml(s0.key))
                        .replace('{y1}', escapeHtml(s1.key))
                        .replace('{pct}', escapeHtml(pctStr));
                }
            }
            box.innerHTML = `<p>${html}</p>`;
        }

        function renderGenImpactStrip(seriesList) {
            const box = document.getElementById('gen-impact-strip');
            if (!box) return;
            const t = I18N[currentLang] || I18N.en;
            const primary = seriesList.filter(s => !s.isReference);
            const focus = primary[primary.length - 1];
            if (!focus) { box.innerHTML = ''; return; }
            const totalSum = (focus.values || []).reduce((acc, v) => acc + (v !== null && v !== undefined ? Number(v) : 0), 0);
            if (totalSum <= 0) { box.innerHTML = ''; return; }

            const homesYr = totalSum / 3300.0;
            const homesStr = homesYr >= 0.3
                ? `${fmtNum(homesYr, 1)} ${t.gen_imp_homes_unit}`
                : `${fmtNum(homesYr * 12.0, 1)} ${t.gen_imp_home_months_unit}`;
            const co2Str = fmtCo2(totalSum * 0.20);
            const evKmStr = `${Math.round(totalSum * 6).toLocaleString(currentLang === 'es' ? 'es-ES' : 'en-US')} km`;

            box.innerHTML = `
                <div class="impact-grid">
                    <div class="impact-chip">
                        <div class="stat-chip-label">🏠 ${escapeHtml(t.gen_imp_homes_lbl)} (${escapeHtml(focus.label)})</div>
                        <div class="impact-val">${escapeHtml(homesStr)}</div>
                    </div>
                    <div class="impact-chip">
                        <div class="stat-chip-label">🌱 ${escapeHtml(t.gen_imp_co2_lbl)} (${escapeHtml(focus.label)})</div>
                        <div class="impact-val">${escapeHtml(co2Str)}</div>
                    </div>
                    <div class="impact-chip">
                        <div class="stat-chip-label">🚗 ${escapeHtml(t.gen_imp_ev_lbl)} (${escapeHtml(focus.label)})</div>
                        <div class="impact-val">${escapeHtml(evKmStr)}</div>
                    </div>
                </div>
                <p class="impact-note">${escapeHtml(t.gen_imp_note)}</p>
            `;
        }

        function renderGenerationSection() {
            renderGenerationControls();
            const series = getActiveGenerationSeries();
            renderLineChartSvg('generation-chart-svg', series, { chartType: 'gen' });
            renderChartLegend('gen-chart-legend', series);
            renderSeriesStats('gen-chart-stats', series, true);
            updateGenDynamicInsight(series);
            renderGenImpactStrip(series);
        }

        function jumpToCupsConsumption(cupsId) {
            if (!cupsId) return;
            consSelectedCups = cupsId;
            setConsMode('single');
            const sec = document.getElementById('ch-consumption');
            if (sec && sec.scrollIntoView) sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
            const card = document.querySelector('#ch-consumption .chart-card-box');
            if (card) {
                card.classList.remove('chart-flash');
                if (card.offsetWidth >= 0) card.classList.add('chart-flash');
            }
        }

        function setConsMode(mode) {
            consMode = mode;
            ['community', 'single', 'compare'].forEach(m => {
                const btn = document.getElementById('btn-cons-' + m);
                if (btn) {
                    btn.classList.toggle('active', m === mode);
                    btn.setAttribute('aria-selected', m === mode ? 'true' : 'false');
                }
            });
            renderConsumptionSection();
        }

        function toggleConsYear(yr) {
            if (consSelectedYears.includes(yr)) {
                if (consSelectedYears.length > 1) consSelectedYears = consSelectedYears.filter(y => y !== yr);
            } else {
                consSelectedYears = consSelectedYears.concat([yr]).sort();
            }
            renderConsumptionSection();
        }

        function changeConsCups(cid) {
            consSelectedCups = cid;
            renderConsumptionSection();
        }

        function setCompareYear(yr) {
            consCompareYear = yr;
            renderConsumptionSection();
        }

        function toggleCompareCups(cid) {
            if (consCompareCups.includes(cid)) {
                if (consCompareCups.length > 1) consCompareCups = consCompareCups.filter(c => c !== cid);
            } else {
                consCompareCups = consCompareCups.concat([cid]);
            }
            renderConsumptionSection();
        }

        function selectTop4Cups() {
            consCompareCups = (STORY_DATA.cups || []).slice(0, 4).map(c => c.cups);
            renderConsumptionSection();
        }

        function selectAllCompareCups() {
            consCompareCups = (STORY_DATA.cups || []).map(c => c.cups);
            renderConsumptionSection();
        }

        function toggleGenYear(yr) {
            if (genSelectedYears.includes(yr)) {
                if (genSelectedYears.length > 1) genSelectedYears = genSelectedYears.filter(y => y !== yr);
            } else {
                genSelectedYears = genSelectedYears.concat([yr]).sort();
            }
            renderGenerationSection();
        }

        function toggleGenDemand(checked) {
            genOverlayDemand = !!checked;
            renderGenerationSection();
        }

        function getActiveWeatherSeries() {
            const w = STORY_DATA.weather;
            if (!w || !w.has_data || !w.years || !w.years.length) return [];
            const palette = STORY_DATA.year_palette;
            const yrs = weatherSelectedYears.length ? weatherSelectedYears : [String(w.years[w.years.length - 1] || '')];
            return yrs.map((yr, idx) => {
                const wObj = w.by_year[yr] || {
                    temp_avg: [], temp_min: [], temp_max: [], clear_sky_pct: [], cloud_cover_pct: [],
                    statuses: [], days: [], annual_avg_temp: null, annual_avg_clear_pct: null,
                    sunny_days: 0, partly_cloudy_days: 0, cloudy_days: 0, rainy_days: 0,
                    observed_days: 0, abs_min_temp: null, abs_max_temp: null,
                    cold_days: 0, frost_days: 0, hot_days: 0,
                    monthly_sunny_days: [], monthly_partly_days: [], monthly_cloudy_days: [], monthly_rainy_days: [],
                    has_weather_codes: false
                };
                return {
                    key: yr,
                    label: yr,
                    color: palette[idx % palette.length],
                    values: weatherMetric === 'temp' ? (wObj.temp_avg || []) : (wObj.clear_sky_pct || []),
                    temp_min: wObj.temp_min || [],
                    temp_max: wObj.temp_max || [],
                    temp_avg: wObj.temp_avg || [],
                    clear_sky_pct: wObj.clear_sky_pct || [],
                    cloud_cover_pct: wObj.cloud_cover_pct || [],
                    monthly_sunny_days: wObj.monthly_sunny_days || [],
                    monthly_partly_days: wObj.monthly_partly_days || [],
                    monthly_cloudy_days: wObj.monthly_cloudy_days || [],
                    monthly_rainy_days: wObj.monthly_rainy_days || [],
                    statuses: wObj.statuses || [],
                    days: wObj.days || [],
                    meta: wObj
                };
            });
        }

        function renderWeatherControls() {
            const bar = document.getElementById('weather-subcontrols');
            if (!bar) return;
            const w = STORY_DATA.weather;
            const t = I18N[currentLang] || I18N.en;
            if (!w || !w.has_data || !w.years || !w.years.length) {
                bar.style.display = 'none';
                return;
            }
            bar.style.display = 'flex';
            const years = w.years.map(String);
            const yrBtns = years.map(y =>
                `<button type="button" class="pill-btn ${weatherSelectedYears.includes(y) ? 'active' : ''}" data-yr="${escapeHtml(y)}" onclick="toggleWeatherYear(this.getAttribute('data-yr'))">${escapeHtml(y)}</button>`
            ).join('');
            bar.innerHTML = `<strong>${escapeHtml(t.lbl_years)}:</strong> ${yrBtns}`;
        }

        function renderWeatherDaysSvg(seriesList) {
            const svg = document.getElementById('weather-chart-svg');
            if (!svg) return;
            const t = I18N[currentLang] || I18N.en;
            const width = 940;
            const height = 340;
            const padL = 74;
            const padR = 26;
            const padT = 28;
            const padB = 46;
            const chartW = width - padL - padR;
            const chartH = height - padT - padB;
            const slotW = chartW / 12;
            const barW = Math.min(34, slotW * 0.52);

            const focus = seriesList[seriesList.length - 1];
            const hasAny = focus && (focus.statuses || []).some(st => st !== 'no_data');
            if (!focus || !hasAny) {
                svg.setAttribute('viewBox', `0 0 ${width} 140`);
                svg.innerHTML = `<text x="${width / 2}" y="75" text-anchor="middle" class="axis-label">${escapeHtml(t.weather_no_data)}</text>`;
                return;
            }

            svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
            const yMax = 32;
            const parts = [];
            [0, 8, 16, 24, 32].forEach(tv => {
                const yp = padT + chartH - (chartH * (tv / yMax));
                parts.push(`<line x1="${padL}" y1="${yp.toFixed(1)}" x2="${width - padR}" y2="${yp.toFixed(1)}" class="grid-line"/>`);
                parts.push(`<text x="${padL - 10}" y="${(yp + 4).toFixed(1)}" text-anchor="end" class="axis-label">${tv} d</text>`);
            });

            const segColors = ['#f59e0b', '#38bdf8', '#94a3b8', '#2563eb'];
            const mSun = focus.monthly_sunny_days || [];
            const mPart = focus.monthly_partly_days || [];
            const mCld = focus.monthly_cloudy_days || [];
            const mRain = focus.monthly_rainy_days || [];
            const stats = focus.statuses || [];

            for (let mIdx = 0; mIdx < 12; mIdx++) {
                const mCode = String(mIdx + 1).padStart(2, '0');
                const mShort = (t.months && t.months[mCode]) || mCode;
                const cx = padL + mIdx * slotW + slotW / 2;
                const bx = cx - barW / 2;
                const st = stats[mIdx] || 'no_data';
                const tipPayload = escapeHtml(JSON.stringify({ mIdx: mIdx, mCode: mCode }));

                parts.push(`<g class="chart-col" tabindex="0" data-weather-tip="${tipPayload}" onmouseenter="showWeatherTooltip(event, this)" onfocus="showWeatherTooltip(event, this)" onmouseleave="hideTooltip()" onblur="hideTooltip()">`);
                parts.push(`<rect x="${(cx - slotW / 2).toFixed(1)}" y="${padT}" width="${slotW.toFixed(1)}" height="${chartH}" class="hover-bg"/>`);

                if (st !== 'no_data') {
                    const vals = [
                        Math.max(0, Number(mSun[mIdx] || 0)),
                        Math.max(0, Number(mPart[mIdx] || 0)),
                        Math.max(0, Number(mCld[mIdx] || 0)),
                        Math.max(0, Number(mRain[mIdx] || 0))
                    ];
                    let accH = 0;
                    vals.forEach((cnt, sIdx) => {
                        if (cnt <= 0) return;
                        const sh = (cnt / yMax) * chartH;
                        const sy = padT + chartH - accH - sh;
                        accH += sh;
                        parts.push(`<rect x="${bx.toFixed(1)}" y="${sy.toFixed(1)}" width="${barW.toFixed(1)}" height="${Math.max(1.5, sh).toFixed(1)}" rx="2" fill="${segColors[sIdx]}" fill-opacity="${st === 'incomplete' ? '0.68' : '0.94'}"/>`);
                    });
                    if (st === 'incomplete' && accH > 0) {
                        const ty = padT + chartH - accH;
                        parts.push(`<rect x="${bx.toFixed(1)}" y="${ty.toFixed(1)}" width="${barW.toFixed(1)}" height="${accH.toFixed(1)}" rx="2" fill="none" stroke="var(--accent-solar)" stroke-width="1.6" stroke-dasharray="3 2"/>`);
                        parts.push(`<text x="${cx.toFixed(1)}" y="${Math.max(padT + 10, ty - 5).toFixed(1)}" text-anchor="middle" style="font-size:9px;font-weight:800;fill:var(--accent-solar);">${escapeHtml(t.tip_inc_badge)}</text>`);
                    }
                }
                parts.push(`<text x="${cx.toFixed(1)}" y="${height - padB + 22}" text-anchor="middle" class="x-label" data-month="${mCode}">${escapeHtml(mShort)}</text>`);
                parts.push(`</g>`);
            }
            svg.innerHTML = parts.join('');
        }

        function renderWeatherLineSvg(seriesList) {
            if (weatherMetric === 'days') {
                renderWeatherDaysSvg(seriesList);
                return;
            }
            const svg = document.getElementById('weather-chart-svg');
            if (!svg) return;
            const t = I18N[currentLang] || I18N.en;
            const width = 940;
            const height = 340;
            const padL = 74;
            const padR = 26;
            const padT = 28;
            const padB = 46;
            const chartW = width - padL - padR;
            const chartH = height - padT - padB;
            const slotW = chartW / 12;

            const allNums = [];
            seriesList.forEach(s => {
                (s.values || []).forEach(v => { if (v !== null && v !== undefined) allNums.push(Number(v)); });
                if (weatherMetric === 'temp' && seriesList.length === 1) {
                    (s.temp_min || []).forEach(v => { if (v !== null && v !== undefined) allNums.push(Number(v)); });
                    (s.temp_max || []).forEach(v => { if (v !== null && v !== undefined) allNums.push(Number(v)); });
                }
            });

            if (seriesList.length === 0 || allNums.length === 0) {
                svg.setAttribute('viewBox', `0 0 ${width} 140`);
                svg.innerHTML = `<text x="${width / 2}" y="75" text-anchor="middle" class="axis-label">${escapeHtml(t.weather_no_data)}</text>`;
                return;
            }

            svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
            let yMin = 0;
            let yMax = 100;
            if (weatherMetric === 'temp') {
                const rawMin = Math.min.apply(null, allNums);
                const rawMax = Math.max.apply(null, allNums);
                yMin = Math.floor((rawMin - 2) / 5) * 5;
                yMax = Math.ceil((rawMax + 2) / 5) * 5;
                if (yMax <= yMin) yMax = yMin + 10;
            }

            const isHc = document.documentElement.getAttribute('data-theme') === 'high-contrast';
            const parts = [];
            for (let tier = 0; tier <= 4; tier++) {
                const tv = yMin + ((yMax - yMin) / 4) * tier;
                const yp = padT + chartH - (chartH * (tier / 4));
                const lbl = weatherMetric === 'temp' ? `${tv.toFixed(0)} °C` : `${tv.toFixed(0)}%`;
                parts.push(`<line x1="${padL}" y1="${yp.toFixed(1)}" x2="${width - padR}" y2="${yp.toFixed(1)}" class="grid-line"/>`);
                parts.push(`<text x="${padL - 10}" y="${(yp + 4).toFixed(1)}" text-anchor="end" class="axis-label">${escapeHtml(lbl)}</text>`);
            }

            const xOf = mIdx => padL + mIdx * slotW + slotW / 2;
            const yOf = val => padT + chartH - ((Number(val) - yMin) / (yMax - yMin)) * chartH;

            if (weatherMetric === 'temp' && yMin < 10 && 10 < yMax) {
                const y10 = yOf(10);
                parts.push(`<line x1="${padL}" y1="${y10.toFixed(1)}" x2="${width - padR}" y2="${y10.toFixed(1)}" stroke="#0284c7" stroke-width="1.2" stroke-dasharray="4 4" stroke-opacity="0.55"/>`);
                parts.push(`<text x="${width - padR - 4}" y="${(y10 - 5).toFixed(1)}" text-anchor="end" class="axis-label" style="fill:var(--accent-demand);font-size:10px;">${escapeHtml(t.weather_cold_ref)}</text>`);
            }

            if (weatherMetric === 'temp' && seriesList.length === 1) {
                const s0 = seriesList[0];
                const tMin = s0.temp_min || [];
                const tMax = s0.temp_max || [];
                for (let i = 0; i < 11; i++) {
                    if (tMin[i] === null || tMin[i] === undefined || tMax[i] === null || tMax[i] === undefined) continue;
                    if (tMin[i + 1] === null || tMin[i + 1] === undefined || tMax[i + 1] === null || tMax[i + 1] === undefined) continue;
                    const pts = `${xOf(i).toFixed(1)},${yOf(tMax[i]).toFixed(1)} ${xOf(i + 1).toFixed(1)},${yOf(tMax[i + 1]).toFixed(1)} ${xOf(i + 1).toFixed(1)},${yOf(tMin[i + 1]).toFixed(1)} ${xOf(i).toFixed(1)},${yOf(tMin[i]).toFixed(1)}`;
                    parts.push(`<polygon points="${pts}" fill="${s0.color}" fill-opacity="0.14"/>`);
                }
            }

            seriesList.forEach((s, sIdx) => {
                const shape = STORY_DATA.shapes[sIdx % STORY_DATA.shapes.length];
                const baseDash = isHc ? STORY_DATA.dashes[sIdx % STORY_DATA.dashes.length] : '';
                const vals = s.values || [];
                const stats = s.statuses || [];

                for (let i = 0; i < 11; i++) {
                    if (vals[i] === null || vals[i] === undefined || vals[i + 1] === null || vals[i + 1] === undefined) continue;
                    const incSeg = stats[i] === 'incomplete' || stats[i + 1] === 'incomplete';
                    const dash = incSeg ? '5 4' : baseDash;
                    const op = incSeg ? '0.78' : '0.95';
                    const dashAttr = dash ? ` stroke-dasharray="${dash}"` : '';
                    parts.push(`<line x1="${xOf(i).toFixed(1)}" y1="${yOf(vals[i]).toFixed(1)}" x2="${xOf(i + 1).toFixed(1)}" y2="${yOf(vals[i + 1]).toFixed(1)}" stroke="${s.color}" stroke-width="2.8" stroke-linecap="round" stroke-opacity="${op}"${dashAttr}/>`);
                }

                for (let i = 0; i < 12; i++) {
                    if (vals[i] === null || vals[i] === undefined) continue;
                    const cx = xOf(i);
                    const cy = yOf(vals[i]);
                    const isInc = stats[i] === 'incomplete';
                    const fill = isInc ? 'var(--bg-surface)' : s.color;
                    const strokeW = isInc ? '2.5' : '1.6';
                    const strokeCol = isInc ? s.color : 'var(--bg-surface)';
                    if (isInc) {
                        parts.push(`<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="7.5" fill="none" stroke="var(--accent-solar)" stroke-width="1.4" stroke-dasharray="2 2"/>`);
                    }
                    parts.push(`${markerPath(shape, cx, cy, isInc ? 4.8 : 4.6)} fill="${fill}" stroke="${strokeCol}" stroke-width="${strokeW}"/>`);
                }
            });

            for (let mIdx = 0; mIdx < 12; mIdx++) {
                const mCode = String(mIdx + 1).padStart(2, '0');
                const mShort = (t.months && t.months[mCode]) || mCode;
                const cx = xOf(mIdx);
                const tipPayload = escapeHtml(JSON.stringify({ mIdx: mIdx, mCode: mCode }));
                parts.push(`<g class="chart-col" tabindex="0" data-weather-tip="${tipPayload}" onmouseenter="showWeatherTooltip(event, this)" onfocus="showWeatherTooltip(event, this)" onmouseleave="hideTooltip()" onblur="hideTooltip()">`);
                parts.push(`<rect x="${(cx - slotW / 2).toFixed(1)}" y="${padT}" width="${slotW.toFixed(1)}" height="${chartH}" class="hover-bg"/>`);
                parts.push(`<line x1="${cx.toFixed(1)}" y1="${padT}" x2="${cx.toFixed(1)}" y2="${padT + chartH}" class="crosshair-line"/>`);
                parts.push(`<text x="${cx.toFixed(1)}" y="${height - padB + 22}" text-anchor="middle" class="x-label" data-month="${mCode}">${escapeHtml(mShort)}</text>`);
                parts.push(`</g>`);
            }
            svg.innerHTML = parts.join('');
        }

        function renderWeatherLegend(seriesList) {
            const box = document.getElementById('weather-chart-legend');
            if (!box) return;
            if (seriesList.length === 0) { box.innerHTML = ''; return; }
            const t = I18N[currentLang] || I18N.en;
            if (weatherMetric === 'days') {
                const focus = seriesList[seriesList.length - 1];
                box.innerHTML = [
                    `<span class="legend-item"><strong>${escapeHtml(focus.label)}</strong></span>`,
                    `<span class="legend-item"><span class="legend-bar-swatch" style="background:#f59e0b;"></span>${escapeHtml(t.weather_sunny_days)}</span>`,
                    `<span class="legend-item"><span class="legend-bar-swatch" style="background:#38bdf8;"></span>${escapeHtml(t.weather_partly_days)}</span>`,
                    `<span class="legend-item"><span class="legend-bar-swatch" style="background:#94a3b8;"></span>${escapeHtml(t.weather_cloudy_days)}</span>`,
                    `<span class="legend-item"><span class="legend-bar-swatch" style="background:#2563eb;"></span>${escapeHtml(t.weather_rainy_days)}</span>`,
                    `<span class="legend-item">◌ ${escapeHtml(t.legend_incomplete)}</span>`
                ].join('');
                return;
            }
            const items = seriesList.map(s =>
                `<span class="legend-item"><span class="legend-swatch" style="background:${s.color};"></span>${escapeHtml(s.label)}</span>`
            );
            if (weatherMetric === 'temp' && seriesList.length === 1) {
                items.push(`<span class="legend-item"><span class="legend-bar-swatch" style="background:${seriesList[0].color};opacity:0.25;"></span>${escapeHtml(t.weather_band_note)}</span>`);
            }
            items.push(`<span class="legend-item">● ${escapeHtml(t.legend_complete)}</span>`);
            items.push(`<span class="legend-item">◌ ${escapeHtml(t.legend_incomplete)}</span>`);
            box.innerHTML = items.join('');
        }

        function renderWeatherSkyBreakdown(seriesList) {
            const box = document.getElementById('weather-sky-breakdown');
            if (!box) return;
            const focus = seriesList[seriesList.length - 1];
            const meta = focus && focus.meta;
            if (!focus || !meta || !meta.observed_days) {
                box.style.display = 'none';
                box.innerHTML = '';
                return;
            }
            const t = I18N[currentLang] || I18N.en;
            const totDays = Number(meta.observed_days) || 0;
            if (totDays <= 0) {
                box.style.display = 'none';
                box.innerHTML = '';
                return;
            }
            box.style.display = 'block';
            const segments = [
                { label: t.weather_sunny_days, cnt: Number(meta.sunny_days || 0), color: '#f59e0b' },
                { label: t.weather_partly_days, cnt: Number(meta.partly_cloudy_days || 0), color: '#38bdf8' },
                { label: t.weather_cloudy_days, cnt: Number(meta.cloudy_days || 0), color: '#94a3b8' },
                { label: t.weather_rainy_days, cnt: Number(meta.rainy_days || 0), color: '#2563eb' }
            ];
            const barHtml = segments.map(seg => {
                const wPct = (seg.cnt / totDays) * 100;
                return seg.cnt > 0
                    ? `<div class="sky-bar-seg" style="width:${wPct.toFixed(1)}%;background:${seg.color};" title="${escapeHtml(seg.label)}: ${seg.cnt} (${wPct.toFixed(0)}%)"></div>`
                    : '';
            }).join('');
            const countsHtml = segments.map(seg => {
                const wPct = ((seg.cnt / totDays) * 100).toFixed(0);
                return `<span><span class="color-dot" style="background:${seg.color};"></span>${escapeHtml(seg.label)}: <strong>${seg.cnt}</strong> (${wPct}%)</span>`;
            }).join('');

            box.innerHTML = `
                <div class="sky-breakdown-head">
                    <span>☀️ ${escapeHtml(t.weather_sky_title)} ${escapeHtml(focus.label)}</span>
                    <span class="muted">${totDays} ${escapeHtml(t.weather_days_unit)}</span>
                </div>
                <div class="sky-stacked-bar">${barHtml}</div>
                <div class="sky-counts-row">${countsHtml}</div>
            `;
        }

        function renderWeatherStats(seriesList) {
            const box = document.getElementById('weather-chart-stats');
            if (!box) return;
            const focus = seriesList[seriesList.length - 1];
            if (!focus) { box.innerHTML = ''; return; }
            const t = I18N[currentLang] || I18N.en;
            const meta = focus.meta || {};
            const mName = idx => idx < 0 ? '—' : ((t.months && t.months[String(idx + 1).padStart(2, '0')]) || '');

            let coldIdx = -1;
            let coldVal = Infinity;
            let warmIdx = -1;
            let warmVal = -Infinity;
            (meta.temp_avg || []).forEach((v, idx) => {
                if (v === null || v === undefined) return;
                const num = Number(v);
                if (num < coldVal) { coldVal = num; coldIdx = idx; }
                if (num > warmVal) { warmVal = num; warmIdx = idx; }
            });

            const avgTempStr = meta.annual_avg_temp !== null && meta.annual_avg_temp !== undefined
                ? `${Number(meta.annual_avg_temp).toFixed(1)} °C` : '—';
            let tempSub = '';
            if (seriesList.length >= 2) {
                const t0 = seriesList[0].meta && seriesList[0].meta.annual_avg_temp;
                const t1 = meta.annual_avg_temp;
                if (t0 !== null && t0 !== undefined && t1 !== null && t1 !== undefined) {
                    const dt = Number(t1) - Number(t0);
                    tempSub = `${dt >= 0 ? '+' : ''}${dt.toFixed(1)} °C (${seriesList[0].label}→${focus.label})`;
                }
            }

            const rangeStr = (coldIdx >= 0 && warmIdx >= 0)
                ? `${mName(coldIdx)} ${coldVal.toFixed(1)}°C / ${mName(warmIdx)} ${warmVal.toFixed(1)}°C`
                : '—';
            const extSub = (meta.abs_min_temp !== null && meta.abs_min_temp !== undefined && meta.abs_max_temp !== null && meta.abs_max_temp !== undefined)
                ? `${t.weather_min_ext} ${Number(meta.abs_min_temp).toFixed(1)}°C · ${t.weather_max_ext} ${Number(meta.abs_max_temp).toFixed(1)}°C`
                : '';

            const clearStr = meta.annual_avg_clear_pct !== null && meta.annual_avg_clear_pct !== undefined
                ? `${Number(meta.annual_avg_clear_pct).toFixed(1)}%` : '—';
            let clearSub = '';
            if (seriesList.length >= 2) {
                const c0 = seriesList[0].meta && seriesList[0].meta.annual_avg_clear_pct;
                const c1 = meta.annual_avg_clear_pct;
                if (c0 !== null && c0 !== undefined && c1 !== null && c1 !== undefined) {
                    const dc = Number(c1) - Number(c0);
                    clearSub = `${dc >= 0 ? '+' : ''}${dc.toFixed(1)} pp (${seriesList[0].label}→${focus.label})`;
                }
            }

            const cDays = Number(meta.cold_days || 0);
            const hDays = Number(meta.hot_days || 0);
            const fDays = Number(meta.frost_days || 0);
            const extDaysVal = `${cDays} ${t.weather_cold_days_lbl} · ${hDays} ${t.weather_hot_days_lbl}`;
            const frostSub = fDays > 0 ? `${fDays} ${t.weather_frost_days_lbl}` : t.weather_no_extremes;

            box.innerHTML = `
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(t.weather_stat_temp)} (${escapeHtml(focus.label)})</div><div class="stat-chip-val">${escapeHtml(avgTempStr)}</div>${tempSub ? `<div class="stat-chip-sub">${escapeHtml(tempSub)}</div>` : ''}</div>
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(t.weather_stat_range)}</div><div class="stat-chip-val">${escapeHtml(rangeStr)}</div>${extSub ? `<div class="stat-chip-sub">${escapeHtml(extSub)}</div>` : ''}</div>
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(t.weather_stat_clear)} (${escapeHtml(focus.label)})</div><div class="stat-chip-val">${escapeHtml(clearStr)}</div>${clearSub ? `<div class="stat-chip-sub">${escapeHtml(clearSub)}</div>` : ''}</div>
                <div class="stat-chip"><div class="stat-chip-label">${escapeHtml(t.weather_stat_extremes)} (${escapeHtml(focus.label)})</div><div class="stat-chip-val">${escapeHtml(extDaysVal)}</div><div class="stat-chip-sub">${escapeHtml(frostSub)}</div></div>
            `;
        }

        function updateWeatherDynamicInsight(seriesList) {
            const box = document.getElementById('weather-dynamic-insight');
            if (!box) return;
            const w = STORY_DATA.weather;
            const focus = seriesList[seriesList.length - 1];
            if (!w || !w.has_data || !focus) {
                box.style.display = 'none';
                box.innerHTML = '';
                return;
            }
            box.style.display = 'flex';
            const t = I18N[currentLang] || I18N.en;
            const meta = focus.meta || {};
            const tempStr = meta.annual_avg_temp !== null && meta.annual_avg_temp !== undefined
                ? `${Number(meta.annual_avg_temp).toFixed(1)} °C` : '—';
            const clearStr = meta.annual_avg_clear_pct !== null && meta.annual_avg_clear_pct !== undefined
                ? `${Number(meta.annual_avg_clear_pct).toFixed(1)}%` : '—';

            if (seriesList.length >= 2) {
                const m0 = seriesList[0].meta || {};
                const t0 = m0.annual_avg_temp;
                const t1 = meta.annual_avg_temp;
                const c0 = m0.annual_avg_clear_pct;
                const c1 = meta.annual_avg_clear_pct;
                if (t0 !== null && t0 !== undefined && t1 !== null && t1 !== undefined && c0 !== null && c0 !== undefined && c1 !== null && c1 !== undefined) {
                    const dt = Number(t1) - Number(t0);
                    const dc = Number(c1) - Number(c0);
                    const html = t.weather_insight_yoy_tpl
                        .replace('{y0}', escapeHtml(seriesList[0].label))
                        .replace('{y1}', escapeHtml(focus.label))
                        .replace('{y1}', escapeHtml(focus.label))
                        .replace('{dt}', `${dt >= 0 ? '+' : ''}${dt.toFixed(1)}`)
                        .replace('{dc}', `${dc >= 0 ? '+' : ''}${dc.toFixed(1)}`)
                        .replace('{temp}', escapeHtml(tempStr))
                        .replace('{clear}', escapeHtml(clearStr));
                    box.innerHTML = `<p>${html}</p>`;
                    return;
                }
            }
            const html = t.weather_insight_single_tpl
                .replace('{year}', escapeHtml(focus.label))
                .replace('{temp}', escapeHtml(tempStr))
                .replace('{clear}', escapeHtml(clearStr))
                .replace('{sunny}', String(meta.sunny_days || 0))
                .replace('{rainy}', String(meta.rainy_days || 0));
            box.innerHTML = `<p>${html}</p>`;
        }

        function renderWeatherInsights(seriesList) {
            const box = document.getElementById('weather-energy-insights');
            if (!box) return;
            const w = STORY_DATA.weather;
            const focus = seriesList[seriesList.length - 1];
            if (!w || !w.has_data || !focus) {
                box.style.display = 'none';
                box.innerHTML = '';
                return;
            }
            box.style.display = 'grid';
            const t = I18N[currentLang] || I18N.en;
            const meta = focus.meta || {};
            const ins = w.insights || {};
            const mFull = code => (code && t.months_full && t.months_full[code]) || code || '—';

            let card1Body = '';
            const frostPart = (meta.frost_days || 0) > 0 ? ` (${meta.frost_days} ${t.weather_frost_days_lbl})` : '';
            if (ins.cold_vs_mild_ratio !== null && ins.cold_vs_mild_ratio !== undefined && ins.cold_month_avg_kwh !== null && ins.mild_month_avg_kwh !== null) {
                card1Body = t.weather_card1_ratio_tpl
                    .replace('{cold_kwh}', escapeHtml(fmtKwh(ins.cold_month_avg_kwh)))
                    .replace('{mild_kwh}', escapeHtml(fmtKwh(ins.mild_month_avg_kwh)))
                    .replace('{ratio}', escapeHtml(fmtNum(ins.cold_vs_mild_ratio, 1)))
                    .replace('{year}', escapeHtml(focus.label))
                    .replace('{cold_days}', String(meta.cold_days || 0))
                    .replace('{frost_part}', escapeHtml(frostPart));
            } else {
                const minT = meta.abs_min_temp !== null && meta.abs_min_temp !== undefined ? `${Number(meta.abs_min_temp).toFixed(1)} °C` : '—';
                const maxT = meta.abs_max_temp !== null && meta.abs_max_temp !== undefined ? `${Number(meta.abs_max_temp).toFixed(1)} °C` : '—';
                card1Body = t.weather_card1_fallback_tpl
                    .replace('{year}', escapeHtml(focus.label))
                    .replace('{cold_days}', String(meta.cold_days || 0))
                    .replace('{hot_days}', String(meta.hot_days || 0))
                    .replace('{min_t}', escapeHtml(minT))
                    .replace('{max_t}', escapeHtml(maxT));
            }

            const card2Parts = [];
            if (ins.sunniest_month_code && ins.cloudiest_month_code && ins.sunniest_month_clear_pct !== null && ins.cloudiest_month_clear_pct !== null) {
                card2Parts.push(
                    `<p>${t.weather_card2_body_tpl
                        .replace('{sun_m}', escapeHtml(mFull(ins.sunniest_month_code)))
                        .replace('{sun_c}', `${Number(ins.sunniest_month_clear_pct).toFixed(0)}%`)
                        .replace('{cld_m}', escapeHtml(mFull(ins.cloudiest_month_code)))
                        .replace('{cld_c}', `${Number(ins.cloudiest_month_clear_pct).toFixed(0)}%`)}</p>`
                );
            }
            if (ins.peak_solar_month_code && ins.peak_solar_month_clear_pct !== null && ins.peak_solar_month_temp !== null) {
                card2Parts.push(
                    `<p>${t.weather_card2_peak_tpl
                        .replace('{peak_m}', escapeHtml(mFull(ins.peak_solar_month_code)))
                        .replace('{peak_c}', `${Number(ins.peak_solar_month_clear_pct).toFixed(0)}%`)
                        .replace('{peak_t}', `${Number(ins.peak_solar_month_temp).toFixed(1)} °C`)}</p>`
                );
            }
            card2Parts.push(`<p>${escapeHtml(t.weather_card2_heat_note)}</p>`);

            box.innerHTML = `
                <article class="insight-card">
                    <h3>${escapeHtml(t.weather_card1_title)}</h3>
                    <p>${card1Body}</p>
                </article>
                <article class="insight-card insight-solar">
                    <h3>${escapeHtml(t.weather_card2_title)}</h3>
                    ${card2Parts.join('')}
                </article>
            `;
        }

        function renderWeatherSection() {
            renderWeatherControls();
            const series = getActiveWeatherSeries();
            renderWeatherLineSvg(series);
            renderWeatherLegend(series);
            renderWeatherSkyBreakdown(series);
            renderWeatherStats(series);
            updateWeatherDynamicInsight(series);
            renderWeatherInsights(series);
        }

        function setWeatherMetric(metric) {
            weatherMetric = (metric === 'clear' || metric === 'days') ? metric : 'temp';
            ['temp', 'clear', 'days'].forEach(m => {
                const btn = document.getElementById('btn-weather-' + m);
                if (btn) {
                    btn.classList.toggle('active', m === weatherMetric);
                    btn.setAttribute('aria-selected', m === weatherMetric ? 'true' : 'false');
                }
            });
            renderWeatherSection();
        }

        function toggleWeatherYear(yr) {
            if (weatherSelectedYears.includes(yr)) {
                if (weatherSelectedYears.length > 1) weatherSelectedYears = weatherSelectedYears.filter(y => y !== yr);
            } else {
                weatherSelectedYears = weatherSelectedYears.concat([yr]).sort();
            }
            renderWeatherSection();
        }

        function showWeatherTooltip(evt, el) {
            const raw = el.getAttribute('data-weather-tip');
            if (!raw) return;
            const info = JSON.parse(raw);
            const t = I18N[currentLang] || I18N.en;
            const mIdx = info.mIdx;
            const mFull = (t.months_full && t.months_full[info.mCode]) || info.mCode;
            const seriesList = getActiveWeatherSeries();

            if (weatherMetric === 'days') {
                const focus = seriesList[seriesList.length - 1];
                const tip = document.getElementById('tooltip');
                if (!focus) return;
                const st = focus.statuses ? focus.statuses[mIdx] : 'no_data';
                if (st === 'no_data') {
                    tip.innerHTML = `<div style="font-weight:700;">🌤️ ${escapeHtml(mFull)} (${escapeHtml(focus.label)})</div><div class="muted">${escapeHtml(t.tip_no_data)}</div>`;
                    placeTooltip(evt, tip);
                    return;
                }
                const sCnt = Number((focus.monthly_sunny_days && focus.monthly_sunny_days[mIdx]) || 0);
                const pCnt = Number((focus.monthly_partly_days && focus.monthly_partly_days[mIdx]) || 0);
                const cCnt = Number((focus.monthly_cloudy_days && focus.monthly_cloudy_days[mIdx]) || 0);
                const rCnt = Number((focus.monthly_rainy_days && focus.monthly_rainy_days[mIdx]) || 0);
                const dPair = focus.days && focus.days[mIdx] ? focus.days[mIdx] : null;
                const incTag = st === 'incomplete'
                    ? ` <span style="color:#fbbf24;font-weight:700;">${escapeHtml(t.tip_inc_badge)}${dPair ? ` (${dPair[0]}/${dPair[1]} ${escapeHtml(t.tip_days)})` : ''}</span>`
                    : '';
                tip.innerHTML = `
                    <div style="font-weight:700;border-bottom:1px solid rgba(255,255,255,0.16);padding-bottom:4px;margin-bottom:5px;">📅 ${escapeHtml(mFull)} · ${escapeHtml(focus.label)}${incTag}</div>
                    <div>☀️ ${escapeHtml(t.weather_sunny_days)}: <strong>${sCnt}</strong></div>
                    <div>⛅ ${escapeHtml(t.weather_partly_days)}: <strong>${pCnt}</strong></div>
                    <div>☁️ ${escapeHtml(t.weather_cloudy_days)}: <strong>${cCnt}</strong></div>
                    <div>🌧️ ${escapeHtml(t.weather_rainy_days)}: <strong>${rCnt}</strong></div>
                `;
                placeTooltip(evt, tip);
                return;
            }

            const rowsHtml = seriesList.map(s => {
                const val = s.values ? s.values[mIdx] : null;
                const st = s.statuses ? s.statuses[mIdx] : 'no_data';
                const dPair = s.days && s.days[mIdx] ? s.days[mIdx] : null;
                const tMin = s.temp_min ? s.temp_min[mIdx] : null;
                const tMax = s.temp_max ? s.temp_max[mIdx] : null;
                const tAvg = s.temp_avg ? s.temp_avg[mIdx] : null;
                const clr = s.clear_sky_pct ? s.clear_sky_pct[mIdx] : null;
                const cld = s.cloud_cover_pct ? s.cloud_cover_pct[mIdx] : null;
                let rightStr = `<span class="muted">${escapeHtml(t.tip_no_data)}</span>`;
                if (val !== null && val !== undefined) {
                    const incTag = st === 'incomplete'
                        ? ` <span style="color:#fbbf24;font-weight:700;">${escapeHtml(t.tip_inc_badge)}${dPair ? ` (${dPair[0]}/${dPair[1]} ${escapeHtml(t.tip_days)})` : ''}</span>`
                        : '';
                    if (weatherMetric === 'temp') {
                        const rangeSub = (tMin !== null && tMax !== null) ? ` <span style="font-size:0.74rem;color:#cbd5e1;">(${tMin.toFixed(1)}–${tMax.toFixed(1)}°C)</span>` : '';
                        const skySub = clr !== null ? ` · ☀️ ${clr.toFixed(0)}%` : '';
                        rightStr = `<strong>${Number(val).toFixed(1)} °C</strong>${rangeSub}${skySub}${incTag}`;
                    } else {
                        const cldSub = cld !== null ? ` <span style="font-size:0.74rem;color:#cbd5e1;">(☁️ ${cld.toFixed(0)}%)</span>` : '';
                        const tempSub = tAvg !== null ? ` · 🌡️ ${tAvg.toFixed(1)}°C` : '';
                        rightStr = `<strong>${Number(val).toFixed(1)}%</strong>${cldSub}${tempSub}${incTag}`;
                    }
                }
                return `<div style="display:flex;justify-content:space-between;gap:10px;margin-top:3px;"><span><span class="color-dot" style="background:${s.color};"></span>${escapeHtml(s.label)}</span><span>${rightStr}</span></div>`;
            }).join('');

            let yoyHtml = '';
            if (seriesList.length >= 2) {
                const v0 = seriesList[0].values[mIdx];
                const v1 = seriesList[seriesList.length - 1].values[mIdx];
                if (v0 !== null && v0 !== undefined && v1 !== null && v1 !== undefined) {
                    const diff = Number(v1) - Number(v0);
                    const sign = diff >= 0 ? '+' : '';
                    const unit = weatherMetric === 'temp' ? ' °C' : ' pp';
                    yoyHtml = `<div style="margin-top:6px;padding-top:5px;border-top:1px solid rgba(255,255,255,0.16);font-size:0.78rem;">${escapeHtml(t.tip_yoy)} (${escapeHtml(seriesList[0].label)}→${escapeHtml(seriesList[seriesList.length - 1].label)}): <strong>${sign}${diff.toFixed(1)}${unit}</strong></div>`;
                }
            }

            const tip = document.getElementById('tooltip');
            tip.innerHTML = `<div style="font-weight:700;border-bottom:1px solid rgba(255,255,255,0.16);padding-bottom:4px;margin-bottom:5px;">🌤️ ${escapeHtml(mFull)}</div>${rowsHtml}${yoyHtml}`;
            placeTooltip(evt, tip);
        }

        function placeTooltip(evt, tip) {
            const rect = evt.target && evt.target.getBoundingClientRect ? evt.target.getBoundingClientRect() : null;
            const baseX = evt.clientX || (rect ? rect.left + rect.width / 2 : 120);
            const baseY = evt.clientY || (rect ? rect.top + 20 : 120);
            tip.style.display = 'block';
            const tw = tip.offsetWidth || 220;
            const th = tip.offsetHeight || 140;
            const left = Math.min(window.innerWidth - tw - 12, Math.max(8, baseX + 14));
            const top = Math.min(window.innerHeight - th - 12, Math.max(8, baseY + 14));
            tip.style.left = left + 'px';
            tip.style.top = top + 'px';
        }

        function showLineTooltip(evt, el) {
            const raw = el.getAttribute('data-line-tip');
            if (!raw) return;
            const info = JSON.parse(raw);
            const t = I18N[currentLang] || I18N.en;
            const mIdx = info.mIdx;
            const mFull = (t.months_full && t.months_full[info.mCode]) || info.mCode;
            const seriesList = info.chart === 'gen' ? getActiveGenerationSeries() : getActiveConsumptionSeries();
            const rowsHtml = seriesList.map(s => {
                const val = s.values ? s.values[mIdx] : null;
                const st = s.statuses ? s.statuses[mIdx] : 'no_data';
                const dPair = s.days && s.days[mIdx] ? s.days[mIdx] : null;
                let rightStr = `<span class="muted">${escapeHtml(t.tip_no_data)}</span>`;
                if (val !== null && val !== undefined) {
                    const incTag = st === 'incomplete'
                        ? ` <span style="color:#fbbf24;font-weight:700;">${escapeHtml(t.tip_inc_badge)}${dPair ? ` (${dPair[0]}/${dPair[1]} ${escapeHtml(t.tip_days)})` : ''}</span>`
                        : '';
                    rightStr = `<strong>${escapeHtml(fmtKwh(val))}</strong>${incTag}`;
                }
                return `<div style="display:flex;justify-content:space-between;gap:10px;margin-top:3px;"><span><span class="color-dot" style="background:${s.color};"></span>${escapeHtml(s.label)}</span><span>${rightStr}</span></div>`;
            }).join('');

            let yoyHtml = '';
            const yrSeries = seriesList.filter(s => s.isYearCompare);
            if (yrSeries.length >= 2) {
                const v0 = yrSeries[0].values[mIdx];
                const v1 = yrSeries[yrSeries.length - 1].values[mIdx];
                if (v0 !== null && v0 !== undefined && v1 !== null && v1 !== undefined && v0 > 0) {
                    const diff = v1 - v0;
                    const pct = (diff / v0) * 100;
                    const sign = diff >= 0 ? '+' : '';
                    yoyHtml = `<div style="margin-top:6px;padding-top:5px;border-top:1px solid rgba(255,255,255,0.16);font-size:0.78rem;">${escapeHtml(t.tip_yoy)} (${escapeHtml(yrSeries[0].label)}→${escapeHtml(yrSeries[yrSeries.length - 1].label)}): <strong>${sign}${pct.toFixed(1)}%</strong> (${sign}${escapeHtml(fmtKwh(diff))})</div>`;
                }
            }

            const tip = document.getElementById('tooltip');
            tip.innerHTML = `<div style="font-weight:700;border-bottom:1px solid rgba(255,255,255,0.16);padding-bottom:4px;margin-bottom:5px;">📅 ${escapeHtml(mFull)}</div>${rowsHtml}${yoyHtml}`;
            placeTooltip(evt, tip);
        }

        function showTooltip(evt, el) {
            const raw = el.getAttribute('data-tooltip');
            if (!raw) return;
            const data = JSON.parse(raw);
            const tip = document.getElementById('tooltip');
            const t = I18N[currentLang] || I18N.en;
            const mName = (t.months_full && t.months_full[data.month_num]) || data.month;
            tip.innerHTML = `
                <div style="font-weight:700;border-bottom:1px solid rgba(255,255,255,0.16);padding-bottom:4px;margin-bottom:6px;">📅 ${escapeHtml(mName)}</div>
                <div>🌞 ${escapeHtml(t.tip_gen)}: <strong>${escapeHtml(data.gen)}</strong></div>
                <div>⚡ ${escapeHtml(t.tip_dem)}: <strong>${escapeHtml(data.dem)}</strong></div>
                ${data.solar_dem ? `<div>☀️ ${escapeHtml(t.tip_solar_dem)}: <strong>${escapeHtml(data.solar_dem)}</strong></div>` : ''}
                <div>🏆 ${escapeHtml(t.tip_sc)}: <strong style="color:#4ade80;">${escapeHtml(data.sc)}</strong></div>
                <div>🛡️ ${escapeHtml(t.tip_surplus)}: <strong>${escapeHtml(data.surplus)}</strong></div>
                <div style="margin-top:4px;font-size:0.75rem;color:#cbd5e1;">${escapeHtml(t.tip_coverage)}: <strong>${escapeHtml(data.cov)}</strong> • ${escapeHtml(t.tip_efficiency)}: <strong>${escapeHtml(data.eff)}</strong></div>
            `;
            placeTooltip(evt, tip);
        }

        function hideTooltip() {
            const tip = document.getElementById('tooltip');
            if (tip) tip.style.display = 'none';
        }

        function updateDynamicNarrative() {
            const t = I18N[currentLang] || I18N.en;
            const consIns = document.getElementById('cons-dynamic-insight');
            if (consIns && STORY_DATA.cups && STORY_DATA.cups.length) {
                const top = STORY_DATA.cups[0];
                const cons = STORY_DATA.consumption;
                const refYr = String(cons.reference_year || cons.years[cons.years.length - 1] || '');
                const yrObj = cons.community[refYr];
                let peakStr = '—';
                if (yrObj && yrObj.values) {
                    let bIdx = -1;
                    let bVal = -1;
                    yrObj.values.forEach((v, i) => { if (v !== null && v > bVal) { bVal = v; bIdx = i; } });
                    if (bIdx >= 0) {
                        const mFull = (t.months_full && t.months_full[String(bIdx + 1).padStart(2, '0')]) || '';
                        peakStr = `${mFull} ${refYr} (${fmtKwh(bVal)})`;
                    }
                }
                consIns.innerHTML = `💡 ${escapeHtml(t.cons_insight_prefix)} <strong>${escapeHtml(top.use || top.cups)}</strong> (${top.consumption_share_pct.toFixed(1)}%) · ${escapeHtml(t.cons_insight_peak)} <strong>${escapeHtml(peakStr)}</strong>`;
            }

            const fzStep1 = document.getElementById('fake-zero-step1-desc');
            if (fzStep1 && t.fake_zero_step1_tpl) {
                fzStep1.innerHTML = t.fake_zero_step1_tpl.replace('{primary}', escapeHtml(PRIMARY_DISPLAY));
            }

            const spotNote = document.getElementById('spotlight-dynamic-note');
            if (spotNote && SPOTLIGHT_META && SPOTLIGHT_META.has_both) {
                spotNote.innerHTML = t.spotlight_mover_tpl
                    .replace('{use}', escapeHtml(SPOTLIGHT_META.use))
                    .replace('{w}', SPOTLIGHT_META.winter_pct)
                    .replace('{s}', SPOTLIGHT_META.summer_pct);
            }

            const prevImp = document.getElementById('prev-uplift-impact');
            if (prevImp) {
                const gainKwh = Number(PREVISION_CTX && PREVISION_CTX.gain_total_kwh || 0);
                if (gainKwh > 0 && t.prev_uplift_impact_tpl) {
                    const co2Str = fmtCo2(gainKwh * 0.20);
                    const homeMonthsStr = fmtNum((gainKwh / 3300.0) * 12.0, 1);
                    prevImp.style.display = 'block';
                    prevImp.innerHTML = t.prev_uplift_impact_tpl
                        .replace('{co2}', escapeHtml(co2Str))
                        .replace('{home_months}', escapeHtml(homeMonthsStr));
                } else {
                    prevImp.style.display = 'none';
                }
            }
        }

        function setLang(lang) {
            if (!I18N[lang]) return;
            currentLang = lang;
            document.documentElement.lang = lang;

            const btnEs = document.getElementById('btn-lang-es');
            const btnEn = document.getElementById('btn-lang-en');
            if (btnEs) { btnEs.className = lang === 'es' ? 'btn-seg active' : 'btn-seg'; btnEs.setAttribute('aria-pressed', lang === 'es' ? 'true' : 'false'); }
            if (btnEn) { btnEn.className = lang === 'en' ? 'btn-seg active' : 'btn-seg'; btnEn.setAttribute('aria-pressed', lang === 'en' ? 'true' : 'false'); }

            document.title = I18N[lang].doc_title;

            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (I18N[lang][key] !== undefined) {
                    if (el.namespaceURI === 'http://www.w3.org/2000/svg') el.textContent = I18N[lang][key];
                    else el.innerHTML = I18N[lang][key];
                }
            });
            document.querySelectorAll('[data-i18n-title]').forEach(el => {
                const key = el.getAttribute('data-i18n-title');
                if (I18N[lang][key] !== undefined) el.title = I18N[lang][key];
            });
            document.querySelectorAll('[data-i18n-aria]').forEach(el => {
                const key = el.getAttribute('data-i18n-aria');
                if (I18N[lang][key] !== undefined) el.setAttribute('aria-label', I18N[lang][key]);
            });
            document.querySelectorAll('[data-month]').forEach(el => {
                const m = el.getAttribute('data-month');
                if (I18N[lang].months && I18N[lang].months[m]) el.textContent = I18N[lang].months[m];
            });
            document.querySelectorAll('[data-month-full]').forEach(el => {
                const m = el.getAttribute('data-month-full');
                if (I18N[lang].months_full && I18N[lang].months_full[m]) el.textContent = I18N[lang].months_full[m];
            });

            const hourlyModeBadge = document.getElementById('badge-hourly-mode');
            if (hourlyModeBadge) {
                const isSim = hourlyModeBadge.getAttribute('data-simulated') === 'true';
                hourlyModeBadge.textContent = isSim ? I18N[lang].mode_simulated : I18N[lang].mode_modeled;
            }

            updateDynamicNarrative();
            renderConsumptionSection();
            renderWeatherSection();
            renderGenerationSection();
        }

        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            Object.keys(THEME_BTNS).forEach(tKey => {
                const btn = document.getElementById(THEME_BTNS[tKey]);
                if (btn) {
                    btn.classList.toggle('active', tKey === theme);
                    btn.setAttribute('aria-pressed', tKey === theme ? 'true' : 'false');
                }
            });
            try { localStorage.setItem('esd_story_theme', theme); } catch (_) {}
            renderConsumptionSection();
            renderWeatherSection();
            renderGenerationSection();
        }

        function toggleTheme() {
            const cur = document.documentElement.getAttribute('data-theme') || 'light';
            setTheme(cur === 'light' ? 'dark' : cur === 'dark' ? 'high-contrast' : 'light');
        }

        function adjustFont(action) {
            if (action === 'reset') fontIdx = 1;
            else fontIdx = Math.max(0, Math.min(FONT_SCALES.length - 1, fontIdx + Number(action)));
            const scale = FONT_SCALES[fontIdx];
            document.documentElement.setAttribute('data-font-scale', scale);
            const dec = document.getElementById('btn-font-dec');
            const inc = document.getElementById('btn-font-inc');
            if (dec) dec.disabled = fontIdx === 0;
            if (inc) inc.disabled = fontIdx === FONT_SCALES.length - 1;
            try { localStorage.setItem('esd_story_font', scale); } catch (_) {}
        }

        function initScrollChrome() {
            const bar = document.getElementById('reading-progress');
            window.addEventListener('scroll', () => {
                if (!bar) return;
                const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
                const pct = Math.min(100, Math.max(0, (window.scrollY / maxScroll) * 100));
                bar.style.width = pct.toFixed(1) + '%';
            }, { passive: true });

            if ('IntersectionObserver' in window) {
                const observer = new IntersectionObserver(entries => {
                    entries.forEach(entry => {
                        if (!entry.isIntersecting) return;
                        const id = entry.target.getAttribute('id');
                        document.querySelectorAll('.nav-pill').forEach(link => {
                            if (link.getAttribute('href') === '#' + id) link.setAttribute('aria-current', 'location');
                            else link.removeAttribute('aria-current');
                        });
                    });
                }, { rootMargin: '-25% 0px -60% 0px' });
                document.querySelectorAll('section[id]').forEach(sec => observer.observe(sec));
            }
        }

        (function bootstrapStory() {
            const consYears = (STORY_DATA.consumption && STORY_DATA.consumption.years || []).map(String);
            consSelectedYears = consYears.length <= 3 ? consYears.slice() : consYears.slice(-2);
            consSelectedCups = (STORY_DATA.cups && STORY_DATA.cups[0] && STORY_DATA.cups[0].cups) || '';
            consCompareYear = consYears[consYears.length - 1] || '';
            consCompareCups = (STORY_DATA.cups || []).slice(0, 4).map(c => c.cups);

            const genYears = (STORY_DATA.generation && STORY_DATA.generation.years || []).map(String);
            genSelectedYears = genYears.length <= 3 ? genYears.slice() : genYears.slice(-2);

            const wYears = (STORY_DATA.weather && STORY_DATA.weather.years || []).map(String);
            weatherSelectedYears = wYears.length <= 3 ? wYears.slice() : wYears.slice(-2);

            try {
                const savedTheme = localStorage.getItem('esd_story_theme');
                if (savedTheme && THEME_BTNS[savedTheme]) {
                    document.documentElement.setAttribute('data-theme', savedTheme);
                    Object.keys(THEME_BTNS).forEach(tKey => {
                        const btn = document.getElementById(THEME_BTNS[tKey]);
                        if (btn) {
                            btn.classList.toggle('active', tKey === savedTheme);
                            btn.setAttribute('aria-pressed', tKey === savedTheme ? 'true' : 'false');
                        }
                    });
                }
                const savedFont = localStorage.getItem('esd_story_font');
                if (savedFont && FONT_SCALES.includes(savedFont)) {
                    fontIdx = FONT_SCALES.indexOf(savedFont);
                    adjustFont(0);
                }
            } catch (_) {}

            updateDynamicNarrative();
            renderConsumptionSection();
            renderWeatherSection();
            renderGenerationSection();
            initScrollChrome();
        })();
"""


def generate_story_html_report(
    opt_result: OptimizationResult,
    ingestion_summary: IngestionSummary,
    lang: str | None = None,
    precision: int | None = None,
    story_context: StoryReportContext | None = None,
    aligned_dataset: AlignedDataset | None = None,
) -> str:
    """Generate an accessible, bilingual, self-contained HTML storytelling report for neighbours."""
    active_lang = "es" if (lang or get_language() or "en").lower().startswith("es") else "en"
    is_es = active_lang == "es"
    prec = get_precision() if precision is None else precision
    version = get_version()

    i18n_catalog = build_story_i18n(version)
    ui = i18n_catalog[active_lang]

    ctx = story_context or build_story_context(
        opt_result=opt_result,
        ingestion_summary=ingestion_summary,
        aligned_dataset=aligned_dataset,
    )
    h_prev = calculate_hourly_prevision(opt_result)

    hourly_mode_badge = ui["mode_simulated"] if h_prev["is_simulated"] else ui["mode_modeled"]

    monthly_rate = float(h_prev["monthly_sc_rate"])
    fortnight_rate = float(h_prev["fortnight_sc_rate"])
    hourly_rate = float(h_prev["hourly_sc_rate"])
    bar3_base_w = min(monthly_rate, fortnight_rate)
    bar3_fort_w = max(0.0, fortnight_rate - bar3_base_w)
    bar4_base_w = min(monthly_rate, hourly_rate)
    bar4_fort_w = max(0.0, min(fortnight_rate, hourly_rate) - bar4_base_w)
    bar4_hour_w = max(0.0, hourly_rate - bar4_base_w - bar4_fort_w)

    primary_item = next((c for c in ctx.active_cups if c.primary), None)
    primary_display_raw = (
        (primary_item.use or primary_item.cups)
        if primary_item
        else str(h_prev.get("primary_name") or "")
    )
    primary_display = escape(primary_display_raw)
    gain_total_kwh = float(h_prev["gain_total_kwh"])
    gain_total_pct = float(h_prev["gain_total_pct"])

    active_cups_table = _render_active_cups_table(ctx, ui)
    seasonal_spotlight_html = _render_seasonal_spotlight(ctx, ui)
    svg_monthly_chart = _render_monthly_balance_svg(opt_result, is_es)

    fake_zero_step1_html = ui["fake_zero_step1_tpl"].format(primary=primary_display)
    recovered_banner = ""
    if ctx.consumption_history.recovered_kwh > 0:
        recovered_banner = (
            f"<div class='recovered-pill-banner'><span data-i18n='fake_zero_recovered'>{ui['fake_zero_recovered']}</span> "
            f"<span>{format_kwh(ctx.consumption_history.recovered_kwh)} ({ctx.consumption_history.reconciled_hours_count:,} h)</span></div>"
        )

    if gain_total_kwh > 0:
        extra_co2_kg = gain_total_kwh * 0.20
        co2_str = (
            f"{extra_co2_kg / 1000.0:.2f} t CO₂"
            if extra_co2_kg >= 1000.0
            else f"{extra_co2_kg:,.0f} kg CO₂"
        )
        home_months_str = f"{(gain_total_kwh / 3300.0) * 12.0:.1f}"
        prev_uplift_impact_html = (
            "<div class='prev-impact-note' id='prev-uplift-impact'>"
            f"{ui['prev_uplift_impact_tpl'].format(co2=co2_str, home_months=home_months_str)}"
            "</div>"
        )
    else:
        prev_uplift_impact_html = (
            "<div class='prev-impact-note' id='prev-uplift-impact' style='display:none;'></div>"
        )

    story_payload = story_context_to_json_payload(ctx, opt_result, prec)
    spotlight_meta = {
        "has_both": (
            ctx.seasonal_spotlight.winter is not None and ctx.seasonal_spotlight.summer is not None
        ),
        "use": ctx.seasonal_spotlight.top_mover_use or ctx.seasonal_spotlight.top_mover_cups,
        "winter_pct": f"{ctx.seasonal_spotlight.top_mover_winter_pct:.1f}",
        "summer_pct": f"{ctx.seasonal_spotlight.top_mover_summer_pct:.1f}",
    }

    script_block = (
        _SCRIPT_BODY.replace("__INIT_LANG__", json.dumps(active_lang))
        .replace("__PRIMARY_JSON__", _safe_json_for_script(primary_display_raw))
        .replace("__I18N_JSON__", _safe_json_for_script(i18n_catalog))
        .replace("__STORY_JSON__", _safe_json_for_script(story_payload))
        .replace("__PREV_JSON__", _safe_json_for_script(h_prev))
        .replace("__SPOT_JSON__", _safe_json_for_script(spotlight_meta))
    )

    return f"""<!DOCTYPE html>
<html lang="{active_lang}" data-theme="light" data-font-scale="md">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(ui["doc_title"])}</title>
    <style>{_CSS_STYLES}</style>
</head>
<body>
    <a href="#main-content" class="skip-link" data-i18n="skip_to_content">{ui["skip_to_content"]}</a>
    <div id="reading-progress" aria-hidden="true"></div>

    <nav class="story-nav" aria-label="{escape(ui["nav_aria"])}">
        <div class="nav-inner">
            <div class="chapter-links">
                <a class="nav-pill" href="#ch-supplies" aria-current="location" data-i18n="nav_ch1">{ui["nav_ch1"]}</a>
                <a class="nav-pill" href="#ch-consumption" data-i18n="nav_ch2">{ui["nav_ch2"]}</a>
                <a class="nav-pill" href="#ch-weather" data-i18n="nav_ch3">{ui["nav_ch3"]}</a>
                <a class="nav-pill" href="#ch-generation" data-i18n="nav_ch4">{ui["nav_ch4"]}</a>
                <a class="nav-pill" href="#ch-sharing" data-i18n="nav_ch5">{ui["nav_ch5"]}</a>
                <a class="nav-pill" href="#ch-glossary" data-i18n="nav_ch6">{ui["nav_ch6"]}</a>
            </div>
            <div class="controls-group">
                <div class="seg-group" role="group" aria-label="Language">
                    <button type="button" class="btn-seg {"active" if is_es else ""}" id="btn-lang-es" aria-pressed="{"true" if is_es else "false"}" onclick="setLang('es')">ES</button>
                    <button type="button" class="btn-seg {"active" if not is_es else ""}" id="btn-lang-en" aria-pressed="{"true" if not is_es else "false"}" onclick="setLang('en')">EN</button>
                </div>
                <div class="seg-group" role="group" aria-label="Theme">
                    <button type="button" class="btn-seg active" id="btn-theme-light" aria-pressed="true" onclick="setTheme('light')" data-i18n-title="theme_light" data-i18n-aria="theme_light" title="{escape(ui["theme_light"])}" aria-label="{escape(ui["theme_light"])}">☀️</button>
                    <button type="button" class="btn-seg" id="btn-theme-dark" aria-pressed="false" onclick="setTheme('dark')" data-i18n-title="theme_dark" data-i18n-aria="theme_dark" title="{escape(ui["theme_dark"])}" aria-label="{escape(ui["theme_dark"])}">🌙</button>
                    <button type="button" class="btn-seg" id="btn-theme-hc" aria-pressed="false" onclick="setTheme('high-contrast')" data-i18n-title="theme_hc" data-i18n-aria="theme_hc" title="{escape(ui["theme_hc"])}" aria-label="{escape(ui["theme_hc"])}">◐</button>
                </div>
                <div class="seg-group" role="group" aria-label="Text size">
                    <button type="button" class="btn-seg" id="btn-font-dec" onclick="adjustFont(-1)" data-i18n-aria="font_dec_label" aria-label="{escape(ui["font_dec_label"])}">A-</button>
                    <button type="button" class="btn-seg" id="btn-font-reset" onclick="adjustFont('reset')" data-i18n-aria="font_reset_label" aria-label="{escape(ui["font_reset_label"])}">A</button>
                    <button type="button" class="btn-seg" id="btn-font-inc" onclick="adjustFont(1)" data-i18n-aria="font_inc_label" aria-label="{escape(ui["font_inc_label"])}">A+</button>
                </div>
                <button type="button" class="btn-tool" id="btn-print" onclick="window.print()" data-i18n="btn_print">{ui["btn_print"]}</button>
            </div>
        </div>
    </nav>

    <main id="main-content" class="container">
        <!-- Hero -->
        <header class="story-hero">
            <span class="hero-eyebrow" data-i18n="hero_eyebrow">{ui["hero_eyebrow"]}</span>
            <h1 data-i18n="title">{ui["title"]}</h1>
            <p class="hero-sub" data-i18n="subtitle">{ui["subtitle"]}</p>
        </header>

        <!-- Chapter 1: Active Supplies -->
        <section id="ch-supplies" class="story-section" aria-labelledby="ch1-heading">
            <div class="chapter-head">
                <span class="chapter-badge" data-i18n="ch1_badge">{ui["ch1_badge"]}</span>
                <h2 id="ch1-heading" class="chapter-title" data-i18n="ch1_title">{ui["ch1_title"]}</h2>
                <p class="chapter-intro" data-i18n="ch1_intro">{ui["ch1_intro"]}</p>
            </div>
            {active_cups_table}
            <div class="callout callout-sc">
                <span>🏡</span>
                <p data-i18n="ch1_note">{ui["ch1_note"]}</p>
            </div>
        </section>

        <!-- Chapter 2: Community Consumption -->
        <section id="ch-consumption" class="story-section" aria-labelledby="ch2-heading">
            <div class="chapter-head">
                <span class="chapter-badge" data-i18n="ch2_badge">{ui["ch2_badge"]}</span>
                <h2 id="ch2-heading" class="chapter-title" data-i18n="ch2_title">{ui["ch2_title"]}</h2>
                <p class="chapter-intro" data-i18n="ch2_intro">{ui["ch2_intro"]}</p>
            </div>

            <div class="callout" id="cons-dynamic-insight" aria-live="polite"></div>

            <div class="chart-card-box">
                <div class="chart-controls-row">
                    <div class="seg-group" role="tablist" aria-label="Consumption chart view">
                        <button type="button" role="tab" aria-selected="true" class="btn-seg active" id="btn-cons-community" onclick="setConsMode('community')" data-i18n="cons_mode_community">{ui["cons_mode_community"]}</button>
                        <button type="button" role="tab" aria-selected="false" class="btn-seg" id="btn-cons-single" onclick="setConsMode('single')" data-i18n="cons_mode_single">{ui["cons_mode_single"]}</button>
                        <button type="button" role="tab" aria-selected="false" class="btn-seg" id="btn-cons-compare" onclick="setConsMode('compare')" data-i18n="cons_mode_compare">{ui["cons_mode_compare"]}</button>
                    </div>
                </div>
                <div id="cons-subcontrols" class="subcontrols-bar"></div>
                <div class="chart-container">
                    <svg id="consumption-chart-svg" class="chart-svg chart-line-svg" role="img" aria-labelledby="ch2-heading" xmlns="http://www.w3.org/2000/svg"></svg>
                </div>
                <div id="cons-chart-legend" class="chart-legend"></div>
                <div id="cons-chart-stats" class="chart-stats-strip"></div>
            </div>

            <div class="fake-zero-box">
                <div class="fake-zero-head">
                    <h3 style="font-size:1.05rem;margin-bottom:0.4rem;" data-i18n="fake_zero_title">{ui["fake_zero_title"]}</h3>
                    <p data-i18n="fake_zero_desc">{ui["fake_zero_desc"]}</p>
                    {recovered_banner}
                </div>
                <div class="fake-zero-steps">
                    <div class="fz-step-card step-solar">
                        <h4 data-i18n="fake_zero_step1_title">{ui["fake_zero_step1_title"]}</h4>
                        <p id="fake-zero-step1-desc">{fake_zero_step1_html}</p>
                    </div>
                    <div class="fz-step-card">
                        <h4 data-i18n="fake_zero_step2_title">{ui["fake_zero_step2_title"]}</h4>
                        <p data-i18n="fake_zero_step2_desc">{ui["fake_zero_step2_desc"]}</p>
                    </div>
                    <div class="fz-step-card step-sc">
                        <h4 data-i18n="fake_zero_step3_title">{ui["fake_zero_step3_title"]}</h4>
                        <p data-i18n="fake_zero_step3_desc">{ui["fake_zero_step3_desc"]}</p>
                    </div>
                </div>
                <div class="fake-zero-diagram-wrap">
                    <svg id="fake-zero-diagram" viewBox="0 0 820 265" class="chart-svg" role="img" aria-labelledby="fake-zero-diagram-title" xmlns="http://www.w3.org/2000/svg">
                        <title id="fake-zero-diagram-title">{escape(ui["fake_zero_title"])}</title>
                        <rect x="10" y="10" width="530" height="245" rx="14" class="fz-zone fz-zone-home"/>
                        <text x="28" y="34" class="fz-zone-lbl" data-i18n="fz_zone_home">{escape(ui["fz_zone_home"])}</text>
                        <rect x="554" y="10" width="256" height="245" rx="14" class="fz-zone fz-zone-grid"/>
                        <text x="572" y="34" class="fz-zone-lbl" data-i18n="fz_zone_grid">{escape(ui["fz_zone_grid"])}</text>

                        <rect x="26" y="86" width="186" height="122" rx="12" class="fz-box-panels"/>
                        <text x="119" y="114" text-anchor="middle" font-size="22">☀️</text>
                        <text x="119" y="139" text-anchor="middle" class="fz-box-title" data-i18n="fz_svg_panels">{escape(ui["fz_svg_panels"])}</text>
                        <rect x="55" y="152" width="128" height="26" rx="13" class="fz-pill-solar-bg"/>
                        <text x="119" y="169" text-anchor="middle" class="fz-pill-solar" data-i18n="fz_svg_panels_val">{escape(ui["fz_svg_panels_val"])}</text>
                        <text x="119" y="196" text-anchor="middle" class="fz-box-sub" data-i18n="fz_svg_panels_sub">{escape(ui["fz_svg_panels_sub"])}</text>

                        <path d="M 212 147 L 248 147" stroke="#d97706" stroke-width="3" stroke-linecap="round"/>
                        <circle cx="248" cy="147" r="6" fill="#d97706"/>

                        <path d="M 248 147 C 272 147, 276 94, 312 94" fill="none" stroke="#059669" stroke-width="3" stroke-linecap="round"/>
                        <polygon points="310,88 320,94 310,100" fill="#059669"/>
                        <rect x="236" y="54" width="68" height="22" rx="11" class="fz-flow-pill-sc"/>
                        <text x="270" y="69" text-anchor="middle" class="fz-flow-txt-sc" data-i18n="fz_svg_flow_sc">{escape(ui["fz_svg_flow_sc"])}</text>

                        <rect x="322" y="48" width="204" height="96" rx="12" class="fz-box-primary"/>
                        <text x="424" y="75" text-anchor="middle" font-size="20">🏢</text>
                        <text x="424" y="99" text-anchor="middle" class="fz-box-title" data-i18n="fz_svg_primary">{escape(ui["fz_svg_primary"])}</text>
                        <text x="424" y="122" text-anchor="middle" class="fz-box-sub-sc" data-i18n="fz_svg_primary_val">{escape(ui["fz_svg_primary_val"])}</text>

                        <path d="M 248 147 C 274 147, 286 188, 336 188 L 564 188" fill="none" stroke="#0284c7" stroke-width="2.6" stroke-dasharray="6 4"/>
                        <polygon points="562,182 572,188 562,194" fill="#0284c7"/>
                        <rect x="336" y="156" width="176" height="22" rx="11" class="fz-flow-pill-exp"/>
                        <text x="424" y="171" text-anchor="middle" class="fz-flow-txt-exp" data-i18n="fz_svg_flow_exp">{escape(ui["fz_svg_flow_exp"])}</text>
                        <text x="424" y="212" text-anchor="middle" class="fz-note-dim" data-i18n="fz_svg_no_grid">{escape(ui["fz_svg_no_grid"])}</text>

                        <rect x="574" y="64" width="218" height="172" rx="12" class="fz-box-meter"/>
                        <text x="683" y="94" text-anchor="middle" font-size="22">📟</text>
                        <text x="683" y="119" text-anchor="middle" class="fz-box-title" data-i18n="fz_svg_meter">{escape(ui["fz_svg_meter"])}</text>
                        <rect x="588" y="133" width="190" height="30" rx="8" class="fz-pill-alert-bg"/>
                        <text x="683" y="152" text-anchor="middle" class="fz-pill-alert" data-i18n="fz_svg_meter_zero">{escape(ui["fz_svg_meter_zero"])}</text>
                        <text x="683" y="185" text-anchor="middle" class="fz-box-sub" data-i18n="fz_svg_meter_cap1">{escape(ui["fz_svg_meter_cap1"])}</text>
                        <text x="683" y="203" text-anchor="middle" class="fz-box-sub" data-i18n="fz_svg_meter_cap2">{escape(ui["fz_svg_meter_cap2"])}</text>
                    </svg>
                </div>
            </div>
        </section>

        <!-- Chapter 3: Local Weather -->
        <section id="ch-weather" class="story-section" aria-labelledby="ch3-weather-heading">
            <div class="chapter-head">
                <span class="chapter-badge" data-i18n="ch3_badge">{ui["ch3_badge"]}</span>
                <h2 id="ch3-weather-heading" class="chapter-title" data-i18n="ch3_title">{ui["ch3_title"]}</h2>
                <p class="chapter-intro" data-i18n="ch3_intro">{ui["ch3_intro"]}</p>
            </div>
            <div class="callout" id="weather-dynamic-insight" aria-live="polite" style="display:none;"></div>
            <div class="chart-card-box">
                <div class="chart-controls-row">
                    <div class="seg-group" role="tablist" aria-label="Weather metric">
                        <button type="button" role="tab" aria-selected="true" class="btn-seg active" id="btn-weather-temp" onclick="setWeatherMetric('temp')" data-i18n="weather_mode_temp">{ui["weather_mode_temp"]}</button>
                        <button type="button" role="tab" aria-selected="false" class="btn-seg" id="btn-weather-clear" onclick="setWeatherMetric('clear')" data-i18n="weather_mode_clear">{ui["weather_mode_clear"]}</button>
                        <button type="button" role="tab" aria-selected="false" class="btn-seg" id="btn-weather-days" onclick="setWeatherMetric('days')" data-i18n="weather_mode_days">{ui["weather_mode_days"]}</button>
                    </div>
                </div>
                <div id="weather-subcontrols" class="subcontrols-bar"></div>
                <div class="chart-container">
                    <svg id="weather-chart-svg" class="chart-svg chart-line-svg" role="img" aria-labelledby="ch3-weather-heading" xmlns="http://www.w3.org/2000/svg"></svg>
                </div>
                <div id="weather-chart-legend" class="chart-legend"></div>
                <div id="weather-sky-breakdown" class="sky-breakdown-card" style="display:none;"></div>
                <div id="weather-chart-stats" class="chart-stats-strip"></div>
            </div>
            <div id="weather-energy-insights" class="weather-insights-grid" style="display:none;"></div>
        </section>

        <!-- Chapter 4: Solar Generation -->
        <section id="ch-generation" class="story-section" aria-labelledby="ch4-gen-heading">
            <div class="chapter-head">
                <span class="chapter-badge" data-i18n="ch4_badge">{ui["ch4_badge"]}</span>
                <h2 id="ch4-gen-heading" class="chapter-title" data-i18n="ch4_title">{ui["ch4_title"]}</h2>
                <p class="chapter-intro" data-i18n="ch4_intro">{ui["ch4_intro"]}</p>
            </div>
            <div class="callout callout-solar" id="gen-dynamic-insight" aria-live="polite" style="display:none;"></div>
            <div class="chart-card-box">
                <div id="gen-subcontrols" class="subcontrols-bar"></div>
                <div class="chart-container">
                    <svg id="generation-chart-svg" class="chart-svg chart-line-svg" role="img" aria-labelledby="ch4-gen-heading" xmlns="http://www.w3.org/2000/svg"></svg>
                </div>
                <div id="gen-chart-legend" class="chart-legend"></div>
                <div id="gen-chart-stats" class="chart-stats-strip"></div>
                <div id="gen-impact-strip" class="impact-strip"></div>
            </div>
        </section>

        <!-- Chapter 5: Sharing the Sun -->
        <section id="ch-sharing" class="story-section" aria-labelledby="ch5-share-heading">
            <div class="chapter-head">
                <span class="chapter-badge" data-i18n="ch5_badge">{ui["ch5_badge"]}</span>
                <h2 id="ch5-share-heading" class="chapter-title" data-i18n="ch5_title">{ui["ch5_title"]}</h2>
            </div>

            <div class="callout callout-solar">
                <span>⚖️</span>
                <div>
                    <h3 data-i18n="why_equal_title">{ui["why_equal_title"]}</h3>
                    <p data-i18n="why_equal_desc">{ui["why_equal_desc"]}</p>
                </div>
            </div>

            {seasonal_spotlight_html}

            <div class="subsection">
                <h3 class="sub-title" data-i18n="chart_traj_title">{ui["chart_traj_title"]}</h3>
                <p style="font-size:0.88rem;color:var(--text-muted);margin-bottom:0.75rem;" data-i18n="chart_traj_sub">{ui["chart_traj_sub"]}</p>
                <div class="chart-legend monthly-balance-legend" aria-label="Chart legend">
                    <span class="legend-item"><span class="legend-bar-swatch" style="background:#d97706;"></span><span data-i18n="legend_bal_gen">{ui["legend_bal_gen"]}</span></span>
                    <span class="legend-item"><span class="legend-bar-swatch" style="background:#0284c7;"></span><span data-i18n="legend_bal_dem">{ui["legend_bal_dem"]}</span></span>
                    <span class="legend-item"><span class="legend-bar-swatch" style="background:#059669;"></span><span data-i18n="legend_bal_sc">{ui["legend_bal_sc"]}</span></span>
                </div>
                <div class="chart-container">{svg_monthly_chart}</div>
            </div>

            <div class="section-hourly-prevision">
                <div class="title-with-pill">
                    <h3 class="sub-title" style="margin-bottom:0;" data-i18n="prev_box_title">{ui["prev_box_title"]}</h3>
                    <span class="badge badge-ted" data-i18n="hourly_badge_ted">{ui["hourly_badge_ted"]}</span>
                    <span class="badge badge-mode" id="badge-hourly-mode" data-simulated="{"true" if h_prev["is_simulated"] else "false"}">{hourly_mode_badge}</span>
                </div>
                <p style="font-size:0.88rem;color:var(--text-muted);" data-i18n="prev_box_sub">{ui["prev_box_sub"]}</p>

                <div class="hourly-kpi-grid">
                    <div class="hourly-kpi-card">
                        <span class="hourly-kpi-label" data-i18n="prev_card1_title">{ui["prev_card1_title"]}</span>
                        <div class="hourly-kpi-val">{format_kwh(float(h_prev["single_sc_kwh"]))}</div>
                        <span class="hourly-kpi-sub"><span data-i18n="prev_card1_sub">{ui["prev_card1_sub"]}</span>: <strong>{float(h_prev["single_sc_rate"]):.1f}%</strong> · <span class="pill-dim" data-i18n="prev_card1_tag">{ui["prev_card1_tag"]}</span></span>
                    </div>
                    <div class="hourly-kpi-card">
                        <span class="hourly-kpi-label" data-i18n="prev_card2_title">{ui["prev_card2_title"]}</span>
                        <div class="hourly-kpi-val text-emerald">{format_kwh(float(h_prev["monthly_sc_kwh"]))}</div>
                        <span class="hourly-kpi-sub"><strong>{float(h_prev["monthly_sc_rate"]):.1f}%</strong> · <span class="pill-uplift-green">+{float(h_prev["gain_monthly_pct"]):.1f}% <span data-i18n="prev_card2_vs">{ui["prev_card2_vs"]}</span></span></span>
                    </div>
                    <div class="hourly-kpi-card">
                        <span class="hourly-kpi-label" data-i18n="prev_card_fortnight_title">{ui["prev_card_fortnight_title"]}</span>
                        <div class="hourly-kpi-val text-cyan">{format_kwh(float(h_prev["fortnight_sc_kwh"]))}</div>
                        <span class="hourly-kpi-sub"><strong>{float(h_prev["fortnight_sc_rate"]):.1f}%</strong> · <span class="pill-fortnight">+{float(h_prev["gain_fortnight_pct"]):.1f}% <span data-i18n="prev_card_fortnight_vs">{ui["prev_card_fortnight_vs"]}</span></span></span>
                    </div>
                    <div class="hourly-kpi-card card-highlight">
                        <span class="hourly-kpi-label" data-i18n="prev_card3_title">{ui["prev_card3_title"]}</span>
                        <div class="hourly-kpi-val text-amber">{format_kwh(float(h_prev["hourly_sc_kwh"]))}</div>
                        <span class="hourly-kpi-sub"><strong>{float(h_prev["hourly_sc_rate"]):.1f}%</strong> · <span class="pill-uplift">+{float(h_prev["gain_hourly_pct"]):.1f}% <span data-i18n="prev_card3_vs">{ui["prev_card3_vs"]}</span></span> · <span class="pill-dim" data-i18n="prev_card3_horizon">{ui["prev_card3_horizon"]}</span></span>
                    </div>
                    <div class="hourly-kpi-card">
                        <span class="hourly-kpi-label" data-i18n="prev_card4_title">{ui["prev_card4_title"]}</span>
                        <div class="hourly-kpi-val text-cyan">+{gain_total_kwh:,.1f} kWh</div>
                        <span class="hourly-kpi-sub"><span class="pill-cyan">+{gain_total_pct:.1f}%</span> <span data-i18n="prev_card4_sub">{ui["prev_card4_sub"]}</span></span>
                    </div>
                </div>

                <div class="comparison-bar-container">
                    <div class="comp-bar-row">
                        <div class="comp-bar-meta"><span data-i18n="prev_comp_single">{ui["prev_comp_single"]}</span><span>{format_kwh(float(h_prev["single_sc_kwh"]))} ({float(h_prev["single_sc_rate"]):.1f}%)</span></div>
                        <div class="comp-bar-track"><div class="fill-single" style="width:{float(h_prev["single_sc_rate"]):.1f}%;"></div></div>
                    </div>
                    <div class="comp-bar-row">
                        <div class="comp-bar-meta"><span data-i18n="prev_comp_monthly">{ui["prev_comp_monthly"]}</span><span>{format_kwh(float(h_prev["monthly_sc_kwh"]))} ({float(h_prev["monthly_sc_rate"]):.1f}%)</span></div>
                        <div class="comp-bar-track"><div class="fill-monthly" style="width:{float(h_prev["monthly_sc_rate"]):.1f}%;"></div></div>
                    </div>
                    <div class="comp-bar-row">
                        <div class="comp-bar-meta"><span class="text-cyan" data-i18n="prev_comp_fortnight">{ui["prev_comp_fortnight"]}</span><span class="text-cyan">{format_kwh(float(h_prev["fortnight_sc_kwh"]))} ({float(h_prev["fortnight_sc_rate"]):.1f}%)</span></div>
                        <div class="comp-bar-track"><div class="fill-monthly" style="width:{bar3_base_w:.1f}%;"></div><div class="fill-fortnight" style="width:{bar3_fort_w:.1f}%;"></div></div>
                    </div>
                    <div class="comp-bar-row">
                        <div class="comp-bar-meta"><span class="text-amber" data-i18n="prev_comp_hourly">{ui["prev_comp_hourly"]}</span><span class="text-emerald">{format_kwh(float(h_prev["hourly_sc_kwh"]))} ({float(h_prev["hourly_sc_rate"]):.1f}%)</span></div>
                        <div class="comp-bar-track"><div class="fill-monthly" style="width:{bar4_base_w:.1f}%;"></div><div class="fill-fortnight" style="width:{bar4_fort_w:.1f}%;"></div><div class="fill-uplift" style="width:{bar4_hour_w:.1f}%;"></div></div>
                    </div>
                </div>

                <div class="callout">
                    <span>💡</span>
                    <p data-i18n="prev_note">{ui["prev_note"]}</p>
                </div>
                {prev_uplift_impact_html}
            </div>
        </section>

        <!-- Chapter 6: Glossary -->
        <section id="ch-glossary" class="story-section" aria-labelledby="ch6-heading">
            <div class="chapter-head">
                <span class="chapter-badge" data-i18n="ch6_badge">{ui["ch6_badge"]}</span>
                <h2 id="ch6-heading" class="chapter-title" data-i18n="ch6_title">{ui["ch6_title"]}</h2>
                <p class="chapter-intro" data-i18n="ch6_intro">{ui["ch6_intro"]}</p>
            </div>
            <div class="glossary-grid">
                <article class="glossary-card"><h3 data-i18n="g1_term">{ui["g1_term"]}</h3><p data-i18n="g1_desc">{ui["g1_desc"]}</p></article>
                <article class="glossary-card"><h3 data-i18n="g2_term">{ui["g2_term"]}</h3><p data-i18n="g2_desc">{ui["g2_desc"]}</p></article>
                <article class="glossary-card"><h3 data-i18n="g3_term">{ui["g3_term"]}</h3><p data-i18n="g3_desc">{ui["g3_desc"]}</p></article>
                <article class="glossary-card"><h3 data-i18n="g4_term">{ui["g4_term"]}</h3><p data-i18n="g4_desc">{ui["g4_desc"]}</p></article>
                <article class="glossary-card"><h3 data-i18n="g5_term">{ui["g5_term"]}</h3><p data-i18n="g5_desc">{ui["g5_desc"]}</p></article>
                <article class="glossary-card"><h3 data-i18n="g6_term">{ui["g6_term"]}</h3><p data-i18n="g6_desc">{ui["g6_desc"]}</p></article>
            </div>
        </section>

        <footer>
            <span data-i18n="footer_text">{ui["footer_text"]}</span>
        </footer>
    </main>

    <div id="tooltip" role="status" aria-live="polite"></div>

    <script>{script_block}</script>
</body>
</html>
"""
