# 📘 Guía Técnica y de Funcionamiento (`esd`)

> **Público Objetivo:** Desarrolladores, ingenieros de datos y consultores energéticos con perfil técnico que desean comprender el funcionamiento interno de la herramienta sin necesidad de ser expertos en regulación eléctrica española o programación matemática lineal.

---

> [!IMPORTANT]
> ### 🛡️ Arnés de Mantenimiento para Desarrolladores y Agentes IA
> **Aviso para ingenieros, desarrolladores y agentes autónomos:**
> Este documento representa la referencia conceptual y operativa fundamental de `electricity-share-distributor`.
> Cada vez que se modifiquen los esquemas de ingesta ([`src/ingestion/`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion)), los modelos de programación lineal ([`src/optimization/`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization)), las tablas en consola ([`src/presentation/views.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/views.py)) o los exportadores de archivos ([`src/presentation/export.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/export.py)), **DEBE** actualizarse esta guía (`GUIDE_ES.md`) y su equivalente en inglés (`GUIDE_EN.md`) para evitar discrepancias arquitectónicas o de documentación.

---

## 1. 🎯 Principios Básicos y Contexto Regulatorio

En España, el **Real Decreto 244/2019** regula el autoconsumo colectivo, donde varios suministros (**CUPS**) comparten la producción de una instalación fotovoltaica (FV) común.

### Reglas Regulatorias y Balance Horario
1. **Asignación Horaria ($\beta_i$):** En cada hora $h$, el participante $i$ recibe $G_{i, h} = \beta_i \cdot G_h$.
2. **Restricción Mensual:** Los coeficientes $\beta_{i, m}$ son estrictamente fijos a lo largo de cada mes natural $m$.
3. **Restricción Presupuestaria:** La suma de cuotas no puede superar el 100%: $\sum_{i=1}^{N} \beta_{i, m} \le 1{,}0000$ ($100{,}00\%$).
4. **Balance Horario por CUPS:**
   - Autoconsumido: $SC_{i, h} = \min(C_{i, h}, \beta_i \cdot G_h)$
   - Demanda Residual de Red: $RD_{i, h} = \max(0, C_{i, h} - \beta_i \cdot G_h)$
   - Excedente Vertido: $Surplus_{i, h} = \max(0, \beta_i \cdot G_h - C_{i, h})$

### Por qué la Optimización Supera a los Repartos Simples
Los repartos simétricos ($1/N$) o por consumo total ignoran la ventana solar diurna (08:00–20:00). Los suministros ausentes vierten energía a precio mayorista de excedentes mientras los consumidores diurnos compran energía cara de red. `esd` calcula coeficientes que **maximizan el autoconsumo colectivo** $\sum_i \min(C_{i, h}, \beta_i \cdot G_h)$, minimizando la dependencia de red.

---

## 2. 📥 Especificaciones de Ingesta

`esd` procesa datos depositados en `.input/`:
- **Consumo Horario DATADIS (`.input/consumption/*.csv`):** Curvas oficiales de distribuidoras. [`DatadisConsumptionLoader`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/consumption.py) autodetecta codificaciones (`utf-8`, `latin-1`), delimitadores (`;`, `,`, `\t`), formato decimal y mapea las horas 01:00–24:00 a marcas estándar indexadas en cero.
- **Generación FV Huawei FusionSolar (`.input/generation/*.xlsx`):** Informes de inversor. [`HuaweiGenerationLoader`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/generation.py) extrae la producción (`Rendimiento FV` o `Rendimiento del inversor`) y normaliza la frecuencia horaria.

---

## 3. ⚙️ Flujo de Procesamiento

El pipeline de cálculo opera en cinco fases:

1. **Auditoría Previa de Salud ([`DataDoctor`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/doctor.py)):** Audita series por huecos horarios, contadores inactivos (>90% ceros) y verifica el solape temporal.
2. **Sincronización Temporal ([`TimeSeriesAligner`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/aligner.py)):** Pivota los CUPS en columnas e interseca índices con la generación solar, gestionando cambios de hora estacionales DST (23 h en marzo, 25 h en octubre).
3. **Optimizador de Programación Lineal ([`DistributionOptimizer`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/engine.py)):** Reformula la función no lineal $\max \sum \min(C_{i, h}, \beta_i G_h)$ mediante variables auxiliares $s_{i, h} \le C_{i, h}$ y $s_{i, h} - \beta_i G_h \le 0$, resuelta globalmente con SciPy HiGHS.
4. **Redondeo Exacto al 100% ([`_round_betas`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/engine.py#L136)):** Aplica el **Método del Resto Mayor (Hare-Niemeyer)** para garantizar que la suma sea **exactamente 100%** en cualquier precisión decimal (0, 1 o 2).
5. **Comparativa de Referencia:** Contrasta la asignación óptima frente a escenarios base `equal` ($1/N$) y `consumption_share`.*`equal` ($1/N$):** Reparto simétrico e indiferenciado entre todos los contadores.
- **`consumption_share`:** Reparto proporcional al consumo bruto acumulado de cada miembro.

---

## 4. 📤 Salidas y Resultados Generados

### 1. La Matriz de Coeficientes de Reparto Mensuales
El resultado principal de `esd` es la **Matriz Regulatoria de Coeficientes de Reparto** ([`CoefficientsMatrix`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/models.py#L78)):
- **Calendario Previsional (Año Nuevo en Inicio):** En lugar de un análisis retrospectivo de fechas pasadas, `esd` genera una tabla previsional de 12 meses naturales, de **enero a diciembre**, para un nuevo año operativo que comienza.
- **Tratamiento de Meses Incompletos:** Si no se dispone de datos completos (cobertura ≥90% de días y horas) de generación o consumo en al menos un mes completo (independientemente del año), `esd` omite el cálculo de dicho mes y muestra un guion / sin datos (`—`).
- **Heurística de Agregación Multianual:** Si existen datos del mismo mes natural en diferentes años (ej. mayo de 2025 y mayo de 2026), `esd` agrega las observaciones horarias en un modelo de programación lineal unificado para calcular los $\beta_i$ óptimos, escalando los totales energéticos por $1/K$ para representar un ciclo anual representativo.
- **Filas (Eje Y):** Códigos CUPS de los suministros participantes.
- **Columnas (Eje X):** Los 12 meses naturales (Ene–Dic) y columna de **Media Anual Ponderada**.
- **Celdas:** Porcentaje de reparto sugerido ($\beta_i$) con la precisión configurada, o `—` para meses sin datos completos.
- **Fila TOTAL:** Acreditación de que cada columna mensual evaluada suma exactamente el $100\%$.

```text
             📅 Matriz Sugerida de Coeficientes de Reparto (β_i %)
╭────────────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────╮
│CUPS        │ Ene│ Feb│ Mar│ Abr│ May│ Jun│ Jul│ Ago│ Sep│ Oct│ Nov│ Dic│Med…│
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
       Acuerdo regulatorio de reparto (RD 244/2019) • Suma mensual: 100%
```

### 2. Archivos e Informes Exportados (`.output/`)
La ejecución de `esd calculate` genera automáticamente cuatro entregables fechados:

| Archivo Generado | Formato | Finalidad |
| :--- | :--- | :--- |
| `*_esd_coefficients_matrix.csv` | CSV (delimitado por `;`) | Tabla en formato hoja de cálculo preparada para el anexo oficial a remitir a la distribuidora. |
| `*_esd_optimization_summary.md` | Markdown | Informe ejecutivo y anexo documental listo para la firma del acuerdo de reparto por la comunidad. |
| `*_esd_coefficients.csv` | CSV (delimitado por `;`) | Balance horario y mensual completo (kWh autoconsumidos, excedentes, demanda de red) por CUPS. |
| `*_esd_results.json` | JSON | Estructura de datos completa serializada para integraciones API o análisis posterior. |

---

## 5. 🗺️ Mapa de Código y Trazabilidad

Para inspeccionar o ampliar el código fuente, utilice la siguiente tabla de correspondencias:

| Capa Arquitectónica | Módulo | Clases / Funciones Clave | Responsabilidad |
| :--- | :--- | :--- | :--- |
| **CLI e Interfaz** | [`src/cli.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/cli.py) | `calculate_command`, `init_command`, `doctor_command` | Enrutamiento de comandos Typer, validación de parámetros y flujo general. |
| **Configuración** | [`src/config.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/config.py) | `AppConfig`, `get_language`, `get_precision` | Persistencia de ajustes en `.esd_config.json` y rutas de trabajo. |
| **Internacionalización** | [`src/i18n.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/i18n.py) | `t()`, `TRANSLATIONS` | Diccionarios bilingües inglés/español con interpolación de variables. |
| **Ingesta: Consumo** | [`src/ingestion/consumption.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/consumption.py) | `DatadisConsumptionLoader` | Localización, lectura y normalización de archivos CSV de DATADIS. |
| **Ingesta: Generación** | [`src/ingestion/generation.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/generation.py) | `HuaweiGenerationLoader` | Lectura de libros Excel `.xlsx` de Huawei FusionSolar. |
| **Ingesta: Diagnóstico** | [`src/ingestion/doctor.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/doctor.py) | `DataDoctor`, `DoctorReport` | Detección previa de huecos, contadores inactivos y comprobación de solapes. |
| **Ingesta: Alineación** | [`src/ingestion/aligner.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/ingestion/aligner.py) | `TimeSeriesAligner` | Sincronización temporal horaria, imputación de nulos y cambios de hora DST. |
| **Optimización: Modelos** | [`src/optimization/models.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/models.py) | `CoefficientsMatrix`, `OptimizationResult` | Estructuras de datos matriciales y métricas de balances energéticos. |
| **Optimización: Solver** | [`src/optimization/engine.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/optimization/engine.py) | `DistributionOptimizer` | Formulación PL en SciPy HiGHS, comparativas y redondeo Hare-Niemeyer. |
| **Presentación: Vistas** | [`src/presentation/views.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/views.py) | `render_coefficients_matrix_table` | Tablas Rich para terminales de 80 columnas y barras gráficas de reparto. |
| **Presentación: Exportación** | [`src/presentation/export.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/presentation/export.py) | `export_all`, `export_coefficients_matrix_csv` | Generación de informes en Markdown, exportación a CSV y volcado en JSON. |
| **Seguridad y Privacidad** | [`src/security.py`](file:///Users/marcos/workspace/repo/electricity-share-distributor/src/security.py) | `CupsPrivacyChecker`, `scan_git_history` | Protección LOPD/RGPD y verificación estricta de CUPS sintéticos. |
