"""Unit tests for standalone interactive HTML report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.ingestion.schema import IngestionSummary
from src.optimization.models import (
    CommunityMonthlyMetrics,
    CupsMonthlyMetrics,
    OptimizationResult,
    OptimizationStrategy,
)
from src.presentation.export import ReportExporter
from src.presentation.html_report import generate_interactive_html_report


def _create_mock_optimization_result() -> tuple[OptimizationResult, IngestionSummary]:
    """Create a minimal mock OptimizationResult and IngestionSummary for testing."""
    cups_list = ["ES0021000000000001AA", "ES0021000000000002BB"]
    cups_uses = {"ES0021000000000001AA": "Aerotermia", "ES0021000000000002BB": "Garaje"}

    cm1 = CupsMonthlyMetrics(
        cups="ES0021000000000001AA",
        month="05",
        beta=0.70,
        consumption_kwh=1000.0,
        generation_allocated_kwh=1400.0,
        self_consumed_kwh=800.0,
        surplus_kwh=600.0,
        grid_demand_kwh=200.0,
        self_consumption_rate=57.1,
        solar_coverage_rate=80.0,
        use="Aerotermia",
    )
    cm2 = CupsMonthlyMetrics(
        cups="ES0021000000000002BB",
        month="05",
        beta=0.30,
        consumption_kwh=400.0,
        generation_allocated_kwh=600.0,
        self_consumed_kwh=300.0,
        surplus_kwh=300.0,
        grid_demand_kwh=100.0,
        self_consumption_rate=50.0,
        solar_coverage_rate=75.0,
        use="Garaje",
    )

    monthly_metrics = CommunityMonthlyMetrics(
        month="05",
        strategy=OptimizationStrategy.OPTIMAL.value,
        total_consumption_kwh=1400.0,
        total_generation_kwh=2000.0,
        total_self_consumed_kwh=1100.0,
        total_surplus_kwh=900.0,
        total_grid_demand_kwh=300.0,
        self_consumption_rate=55.0,
        solar_coverage_rate=78.6,
        beta_sum=1.0,
        cups_metrics=[cm1, cm2],
        has_data=True,
    )

    total_summary = CommunityMonthlyMetrics(
        month="Total",
        strategy=OptimizationStrategy.OPTIMAL.value,
        total_consumption_kwh=1400.0,
        total_generation_kwh=2000.0,
        total_self_consumed_kwh=1100.0,
        total_surplus_kwh=900.0,
        total_grid_demand_kwh=300.0,
        self_consumption_rate=55.0,
        solar_coverage_rate=78.6,
        beta_sum=1.0,
        cups_metrics=[cm1, cm2],
        has_data=True,
    )

    opt_result = OptimizationResult(
        strategy=OptimizationStrategy.OPTIMAL.value,
        monthly_results=[monthly_metrics],
        total_summary=total_summary,
        cups_list=cups_list,
        cups_uses=cups_uses,
    )

    summary = IngestionSummary(
        cups_count=2,
        cups_list=cups_list,
        consumption_files_loaded=2,
        generation_files_loaded=1,
        start_time="2026-05-01 00:00:00",
        end_time="2026-05-31 23:00:00",
        total_hours=744,
        missing_hours_count=0,
    )

    return opt_result, summary


def test_generate_interactive_html_report_structure() -> None:
    """Verify that generated HTML storytelling report contains all 7 chapters, accessibility chrome, and bilingual UI."""
    opt_result, summary = _create_mock_optimization_result()
    opt_result.primary_cups = "ES0021000000000001AA"
    html_en = generate_interactive_html_report(opt_result, summary, lang="en")

    # Document type and basic tags
    assert "<!DOCTYPE html>" in html_en
    assert "<html" in html_en
    assert "</html>" in html_en

    # 100% offline requirement: no external script or stylesheet sources
    assert '<script src="http' not in html_en
    assert '<script src="//' not in html_en
    assert 'href="http' not in html_en

    # Sticky chapter stepper, reading progress bar, and accessibility controls
    assert "reading-progress" in html_en
    assert "skip-link" in html_en
    assert "story-nav" in html_en
    assert 'id="ch-supplies"' in html_en
    assert 'id="ch-consumption"' in html_en
    assert 'id="ch-weather"' in html_en
    assert 'id="ch-generation"' in html_en
    assert 'id="ch-sharing"' in html_en
    assert 'id="ch-tables"' in html_en
    assert 'id="ch-glossary"' in html_en
    assert "btn-theme-light" in html_en
    assert "btn-theme-dark" in html_en
    assert "btn-theme-hc" in html_en
    assert "btn-font-dec" in html_en
    assert "btn-font-reset" in html_en
    assert "btn-font-inc" in html_en

    # Chapter 1: Active CUPS table (no Role & Bylaws column, subtle primary sun icon & legend)
    assert "activeCupsTable" in html_en
    assert "Role &amp; Bylaws" not in html_en
    assert "Role & Bylaws" not in html_en
    assert "primary-sun" in html_en
    assert "ch1_primary_legend" in html_en
    assert "ES0021000000000001AA" in html_en
    assert "ES0021000000000002BB" in html_en
    assert "Aerotermia" in html_en
    assert "Garaje" in html_en

    # Chapter 2, 3 & 4: Interactive consumption, weather, and generation line charts + fake zero diagram
    assert "consumption-chart-svg" in html_en
    assert "btn-cons-community" in html_en
    assert "btn-cons-single" in html_en
    assert "btn-cons-compare" in html_en
    assert "fake-zero-box" in html_en
    assert "weather-chart-svg" in html_en
    assert "btn-weather-temp" in html_en
    assert "btn-weather-clear" in html_en
    assert "generation-chart-svg" in html_en
    assert "gen-subcontrols" in html_en

    # Chapter 5: Didactic sharing story, spotlight, monthly chart with legend, and 4-way progression
    assert "chart-monthly-svg" in html_en
    assert "monthly-balance-legend" in html_en
    assert "Solar Generation (amber)" in html_en
    assert "Community Demand (blue)" in html_en
    assert "Collective Self-Consumption (green)" in html_en
    assert "spotlight-grid" in html_en
    assert "section-hourly-prevision" in html_en
    assert "TED/1247/2021" in html_en
    assert "No Share (Single CUPS)" in html_en
    assert "Monthly Share (RD 244/2019)" in html_en
    assert "Fortnight Share (24 Periods)" in html_en
    assert "Hourly Share (Order TED)" in html_en
    assert "Total Collective Uplift" in html_en
    assert "No Collective Share (Single CUPS)" in html_en
    assert "Fixed Monthly Share (RD 244/2019)" in html_en
    assert "Fortnight Share (24 Half-Month Periods)" in html_en
    assert "Dynamic Hourly Share (Orden TED/1247/2021)" in html_en

    # Chapter 6 & 7: 100 kWh simulator, tabbed Monthly & Fortnight matrices, and glossary
    assert "sim-box" in html_en
    assert "matrixTable" in html_en
    assert "fortnightTable" in html_en
    assert "tab-monthly" in html_en
    assert "tab-fortnight" in html_en
    assert "glossary-grid" in html_en
    assert "Hare-Niemeyer" not in html_en

    # Bilingual language selector and JS engine
    assert "btn-lang-es" in html_en
    assert "btn-lang-en" in html_en
    assert "setLang" in html_en
    assert "showLineTooltip" in html_en
    assert "showWeatherTooltip" in html_en
    assert "STORY_DATA" in html_en

    # Matrix table summary footer
    assert "<tfoot>" in html_en
    assert "</tfoot>" in html_en
    assert "TOTAL (RD 244/2019)" in html_en
    assert "100%" in html_en
    assert "total-label" in html_en
    assert "total-val" in html_en

    # English titles
    assert "Our Community's Solar Story" in html_en
    assert "Meet Our Community Supplies (Active CUPS)" in html_en
    assert "How Our Community Consumes Energy" in html_en
    assert "Local Weather Across the Analyzed Years" in html_en
    assert "How Our Roof Produces Solar Energy" in html_en

    # Bilingual natural Spanish generation
    html_es = generate_interactive_html_report(opt_result, summary, lang="es")
    assert "La energía solar de nuestra comunidad, explicada paso a paso" in html_es
    assert "Los contadores de nuestra comunidad (CUPS activos)" in html_es
    assert "Cuándo y cuánto consumen nuestras zonas comunes" in html_es
    assert "El tiempo en nuestra finca en los años analizados" in html_es
    assert "Cuánta electricidad producen nuestras placas" in html_es
    assert "Producción solar (ámbar)" in html_es
    assert "Demanda comunitaria (azul)" in html_es
    assert "Autoconsumo colectivo (verde)" in html_es
    assert "Rol y Estatutos" not in html_es
    assert "Sin reparto (1 solo CUPS)" in html_es
    assert "Reparto mensual (RD 244/2019)" in html_es
    assert "Reparto quincenal (24 quincenas)" in html_es
    assert "Reparto horario (Orden TED)" in html_es
    assert "Ganancia colectiva total" in html_es
    assert "Sin reparto colectivo (1 solo CUPS)" in html_es
    assert "Reparto mensual fijo (RD 244/2019)" in html_es
    assert "Reparto horario dinámico (Orden TED/1247/2021)" in html_es
    assert "Hare-Niemeyer" not in html_es


def test_prevision_four_way_progression_fallback_and_ordering() -> None:
    """Verify _calculate_hourly_prevision computes monotonic 4-way fallback metrics when optional fields are 0."""
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    prev = _calculate_hourly_prevision(opt_result)

    assert prev["single_sc_kwh"] == 800.0
    assert prev["monthly_sc_kwh"] == 1100.0
    assert prev["fortnight_sc_kwh"] == 1100.0
    assert prev["hourly_sc_kwh"] == 1100.0
    assert prev["has_fortnight"] is False
    assert prev["is_simulated"] is False

    # Physical progression invariant: single <= monthly <= fortnight <= hourly
    assert prev["single_sc_kwh"] <= prev["monthly_sc_kwh"]
    assert prev["monthly_sc_kwh"] <= prev["fortnight_sc_kwh"]
    assert prev["fortnight_sc_kwh"] <= prev["hourly_sc_kwh"]

    assert prev["single_sc_rate"] <= prev["monthly_sc_rate"]
    assert prev["monthly_sc_rate"] <= prev["fortnight_sc_rate"]
    assert prev["fortnight_sc_rate"] <= prev["hourly_sc_rate"]

    # Step-by-step and cumulative gains
    assert round(prev["gain_monthly_kwh"], 1) == round(
        prev["monthly_sc_kwh"] - prev["single_sc_kwh"], 1
    )
    assert round(prev["gain_fortnight_kwh"], 1) == round(
        prev["fortnight_sc_kwh"] - prev["single_sc_kwh"], 1
    )
    assert round(prev["gain_hourly_kwh"], 1) == round(
        prev["hourly_sc_kwh"] - prev["monthly_sc_kwh"], 1
    )
    assert round(prev["gain_total_kwh"], 1) == round(
        prev["hourly_sc_kwh"] - prev["single_sc_kwh"], 1
    )


def test_prevision_reads_four_way_metrics_directly_from_opt_result() -> None:
    """Verify _calculate_hourly_prevision reads 4-way kWh directly without re-parsing time_series_df strings."""
    import pandas as pd

    from src.optimization.models import HourlyOptimizationResult, HourlyProfileMatrix
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    opt_result.current_self_consumed_kwh = 720.0
    opt_result.monthly_share_self_consumed_kwh = 1100.0
    opt_result.fortnight_share_self_consumed_kwh = 1240.0
    opt_result.hourly_share_self_consumed_kwh = 1360.0

    # Inject deliberately conflicting formatted strings in time_series_df to verify they are NOT re-parsed
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-05-01 12:00:00",
                "cups": "ES0021000000000001AA",
                "consumption_kwh": "1,0",
                "generation_kwh": "10,0",
                "share_pct": "1.0%",
                "estimated_share_pct": "1.0%",
            }
        ]
    )
    opt_result.hourly_result = HourlyOptimizationResult(
        profile_matrix=HourlyProfileMatrix(
            cups_list=opt_result.cups_list,
            hours=[f"{h:02d}" for h in range(24)],
            matrix={c: {} for c in opt_result.cups_list},
            hourly_sums={},
            average_shares={},
            average_sum=1.0,
        ),
        time_series_df=df,
    )

    prev = _calculate_hourly_prevision(opt_result)
    assert prev["has_fortnight"] is True
    assert prev["is_simulated"] is True
    assert prev["single_sc_kwh"] == 720.0
    assert prev["monthly_sc_kwh"] == 1100.0
    assert prev["fortnight_sc_kwh"] == 1240.0
    assert prev["hourly_sc_kwh"] == 1360.0

    # Exact self-consumption rates against 2,000 kWh generation: 36%, 55%, 62%, 68%
    assert prev["single_sc_rate"] == 36.0
    assert prev["monthly_sc_rate"] == 55.0
    assert prev["fortnight_sc_rate"] == 62.0
    assert prev["hourly_sc_rate"] == 68.0

    # Step gains
    assert prev["gain_monthly_kwh"] == 380.0
    assert prev["gain_fortnight_kwh"] == 520.0
    assert prev["gain_fortnight_vs_monthly_kwh"] == 140.0
    assert prev["gain_hourly_kwh"] == 260.0
    assert prev["gain_total_kwh"] == 640.0


def test_html_i18n_dictionary_parity() -> None:
    """Verify unified EN/ES HTML report dictionary has complete top-level and month key parity."""
    from src.presentation.html_report import _build_html_i18n

    catalog = _build_html_i18n(version="2026.11.018")
    assert set(catalog.keys()) == {"es", "en"}
    assert set(catalog["es"].keys()) == set(catalog["en"].keys())
    assert set(catalog["es"]["months"].keys()) == set(catalog["en"]["months"].keys())
    assert set(catalog["es"]["months_full"].keys()) == set(catalog["en"]["months_full"].keys())
    assert "2026.11.018" in catalog["es"]["footer_text"]
    assert "2026.11.018" in catalog["en"]["footer_text"]


def test_export_interactive_html_file(tmp_path: Path) -> None:
    """Verify that ReportExporter exports the HTML report to disk."""
    opt_result, summary = _create_mock_optimization_result()
    exporter = ReportExporter(output_dir=tmp_path, timestamp="20261025_150000")

    # 1. Direct method call
    html_file = exporter.export_interactive_html(opt_result, summary)
    assert html_file.exists()
    assert html_file.name == "20261025_150000_esd_interactive_report.html"
    content = html_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content

    # 2. export_all with formats='html'
    exported_html_only = exporter.export_all(opt_result, summary, formats="html")
    assert len(exported_html_only) == 1
    assert exported_html_only[0].suffix == ".html"

    # 3. export_all with formats='all'
    exported_all = exporter.export_all(opt_result, summary, formats="all")
    assert any(p.suffix == ".html" for p in exported_all)

    # 4. Custom timestamp exporter
    p_custom = ReportExporter(
        output_dir=tmp_path, timestamp="20261025_150001"
    ).export_interactive_html(opt_result, summary)
    assert p_custom.exists()


def test_prevision_reads_primary_cups_directly_without_disk_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _calculate_hourly_prevision reads opt_result.primary_cups directly without calling DataCurator."""
    from src.curation.curator import DataCurator
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    opt_result.primary_cups = "ES0021000000000002BB"
    opt_result.cups_uses = {"ES0021000000000002BB": "Custom Primary"}

    def fail_load_cups_config(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "DataCurator.load_cups_config should not be called when primary_cups is present"
        )

    monkeypatch.setattr(DataCurator, "load_cups_config", fail_load_cups_config)

    prev = _calculate_hourly_prevision(opt_result)
    assert prev["primary_cups"] == "ES0021000000000002BB"
    assert prev["primary_name"] == "Custom Primary"


def test_prevision_no_disk_read_or_keyword_heuristic_when_primary_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _calculate_hourly_prevision never reads cups.json or uses keyword heuristics when primary_cups is None."""
    from src.curation.curator import DataCurator
    from src.presentation.html_report import _calculate_hourly_prevision

    opt_result, _ = _create_mock_optimization_result()
    opt_result.primary_cups = None
    # Put keyword-like name on the second CUPS to prove keyword heuristics are absent
    opt_result.cups_uses = {
        "ES0021000000000001AA": "Garaje",
        "ES0021000000000002BB": "Aerotermia Principal",
    }

    def fail_load_cups_config(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("DataCurator.load_cups_config must not be called by html_report")

    monkeypatch.setattr(DataCurator, "load_cups_config", fail_load_cups_config)

    prev = _calculate_hourly_prevision(opt_result)
    assert prev["primary_cups"] == "ES0021000000000001AA"
    assert prev["primary_name"] == "Garaje"


def test_matrix_table_total_footer_row() -> None:
    """Verify that matrix table contains a styled <tfoot> row with TOTAL (RD 244/2019) and 100.00%."""
    opt_result, summary = _create_mock_optimization_result()
    html = generate_interactive_html_report(opt_result, summary, lang="en", precision=2)

    assert "<tfoot>" in html
    assert "</tfoot>" in html
    assert (
        "<span class='total-label' data-i18n='lbl_total_rd244'>TOTAL (RD 244/2019)</span>" in html
    )
    assert "100.00%" in html

    html_es = generate_interactive_html_report(opt_result, summary, lang="es", precision=2)
    assert "<tfoot>" in html_es
    assert (
        "<span class='total-label' data-i18n='lbl_total_rd244'>TOTAL (RD 244/2019)</span>"
        in html_es
    )
    assert "100.00%" in html_es


def _build_hourly_timestamps(year: int, month: int, n_days: int) -> list[str]:
    """Generate hourly YYYY-MM-DD HH:MM:SS timestamps for the first n_days of a month."""
    return [
        f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:00:00"
        for day in range(1, n_days + 1)
        for hour in range(24)
    ]


def test_story_data_active_cups_filtering_and_sorting() -> None:
    """Only CUPS present in cups_configs appear in Chapter 1 and Chapter 2 consumption history."""
    import pandas as pd

    from src.domain.models import SupplyPoint
    from src.presentation.story_data import build_story_context

    opt_result, summary = _create_mock_optimization_result()
    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    c_ignored = "ES0021000000000099ZZ"

    cups_configs = {
        c1: SupplyPoint(cups=c1, use="Aerotermia", primary=True, min_share=0.2),
        c2: SupplyPoint(cups=c2, use="Garaje", max_share=0.5),
    }

    ts_list = _build_hourly_timestamps(2025, 1, 31)
    rows = []
    for ts in ts_list:
        rows.append({"timestamp": ts, "cups_id": c1, "consumption": 3.0})
        rows.append({"timestamp": ts, "cups_id": c2, "consumption": 1.0})
        rows.append({"timestamp": ts, "cups_id": c_ignored, "consumption": 9.0})
    cons_df = pd.DataFrame(rows)

    ctx = build_story_context(
        opt_result=opt_result,
        ingestion_summary=summary,
        cups_configs=cups_configs,
        consumption_df=cons_df,
    )

    assert [c.cups for c in ctx.active_cups] == [c1, c2]
    assert c_ignored not in ctx.consumption_history.by_cups
    assert ctx.active_cups[0].primary is True
    assert ctx.active_cups[0].consumption_share_pct == 75.0
    assert ctx.active_cups[1].consumption_share_pct == 25.0

    html_out = generate_interactive_html_report(opt_result, summary, lang="en", story_context=ctx)
    assert c1 in html_out
    assert c2 in html_out
    assert c_ignored not in html_out


def test_story_data_multi_year_consumption_and_incomplete_detection() -> None:
    """Multi-year consumption tracks complete vs incomplete [Inc] vs missing months accurately."""
    import calendar

    import pandas as pd

    from src.domain.models import SupplyPoint
    from src.presentation.story_data import build_story_context

    opt_result, summary = _create_mock_optimization_result()
    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    cups_configs = {
        c1: SupplyPoint(cups=c1, use="Aerotermia", primary=True),
        c2: SupplyPoint(cups=c2, use="Garaje"),
    }

    rows: list[dict[str, object]] = []
    for yr in (2024, 2025):
        for m in range(1, 13):
            n_days = calendar.monthrange(yr, m)[1]
            for ts in _build_hourly_timestamps(yr, m, n_days):
                rows.append({"timestamp": ts, "cups_id": c1, "consumption": 2.0})
                rows.append({"timestamp": ts, "cups_id": c2, "consumption": 1.0})

    # Partial 2026: Jan complete (31d), Feb incomplete (10d), Mar absent (no_data)
    for ts in _build_hourly_timestamps(2026, 1, 31):
        rows.append({"timestamp": ts, "cups_id": c1, "consumption": 2.5})
        rows.append({"timestamp": ts, "cups_id": c2, "consumption": 1.0})
    for ts in _build_hourly_timestamps(2026, 2, 10):
        rows.append({"timestamp": ts, "cups_id": c1, "consumption": 2.5})
        rows.append({"timestamp": ts, "cups_id": c2, "consumption": 1.0})

    cons_df = pd.DataFrame(rows)
    ctx = build_story_context(
        opt_result=opt_result,
        ingestion_summary=summary,
        cups_configs=cups_configs,
        consumption_df=cons_df,
    )

    ch = ctx.consumption_history
    assert ctx.has_multi_year_consumption is True
    assert ch.years == [2024, 2025, 2026]
    assert ch.reference_period_label == "2025"
    assert ch.community[2025].complete_months_count == 12
    assert ch.community[2026].statuses[0] == "complete"
    assert ch.community[2026].statuses[1] == "incomplete"
    assert ch.community[2026].days[1] == (10, 28)
    assert ch.community[2026].statuses[2] == "no_data"
    assert ch.community[2026].values[2] is None


def test_story_data_primary_cups_behind_the_meter_reconciliation() -> None:
    """Primary CUPS behind-the-meter fake zeros are reconciled without altering pre-solar years."""
    import pandas as pd

    from src.domain.models import SupplyPoint
    from src.ingestion.schema import AlignedDataset
    from src.presentation.story_data import build_story_context

    opt_result, summary = _create_mock_optimization_result()
    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    cups_configs = {
        c1: SupplyPoint(cups=c1, use="Aerotermia", primary=True),
        c2: SupplyPoint(cups=c2, use="Garaje"),
    }

    # Pre-solar 2024-05 (raw = 5.0/h), Solar 2025-05 (raw DATADIS fake zero 0.0/h)
    ts_2024 = _build_hourly_timestamps(2024, 5, 31)
    ts_2025 = _build_hourly_timestamps(2025, 5, 31)
    rows = []
    for ts in ts_2024:
        rows.append({"timestamp": ts, "cups_id": c1, "consumption": 5.0})
        rows.append({"timestamp": ts, "cups_id": c2, "consumption": 1.0})
    for ts in ts_2025:
        rows.append({"timestamp": ts, "cups_id": c1, "consumption": 0.0})
        rows.append({"timestamp": ts, "cups_id": c2, "consumption": 2.0})
    cons_df = pd.DataFrame(rows)

    aligned_df = pd.DataFrame(
        {
            c1: [8.0] * len(ts_2025),
            c2: [2.0] * len(ts_2025),
            "generation_kwh": [10.0] * len(ts_2025),
        },
        index=ts_2025,
    )
    aligned = AlignedDataset(
        data=aligned_df,
        cups_list=[c1, c2],
        metadata=summary,
        monthly_groups={"2025-05": aligned_df},
        cups_uses={c1: "Aerotermia", c2: "Garaje"},
        primary_cups=c1,
    )

    ctx = build_story_context(
        opt_result=opt_result,
        ingestion_summary=summary,
        cups_configs=cups_configs,
        consumption_df=cons_df,
        aligned_dataset=aligned,
    )

    expected_hours = len(ts_2025)
    assert ctx.consumption_history.reconciled_hours_count == expected_hours
    assert ctx.consumption_history.recovered_kwh == round(8.0 * expected_hours, 2)
    # 2024 untouched, 2025 updated for primary CUPS
    assert ctx.consumption_history.by_cups[c1][2024].values[4] == round(5.0 * 744, 2)
    assert ctx.consumption_history.by_cups[c1][2025].values[4] == round(8.0 * 744, 2)
    assert ctx.consumption_history.by_cups[c2][2025].values[4] == round(2.0 * 744, 2)


def test_story_data_multi_year_generation_and_incomplete_detection() -> None:
    """Multi-year generation history preserves complete, incomplete [Inc], and missing months."""
    import pandas as pd

    from src.presentation.story_data import build_story_context

    opt_result, summary = _create_mock_optimization_result()
    gen_rows = [
        {"timestamp": ts, "generation": 4.0} for ts in _build_hourly_timestamps(2025, 6, 30)
    ]
    gen_rows.extend(
        {"timestamp": ts, "generation": 3.5} for ts in _build_hourly_timestamps(2026, 6, 12)
    )
    gen_df = pd.DataFrame(gen_rows)

    ctx = build_story_context(
        opt_result=opt_result,
        ingestion_summary=summary,
        generation_df=gen_df,
    )

    assert ctx.has_multi_year_generation is True
    assert ctx.generation_history.years == [2025, 2026]
    assert ctx.generation_history.by_year[2025].statuses[5] == "complete"
    assert ctx.generation_history.by_year[2026].statuses[5] == "incomplete"
    assert ctx.generation_history.by_year[2026].days[5] == (12, 30)
    assert ctx.generation_history.by_year[2025].statuses[0] == "no_data"


def test_story_seasonal_spotlight_contrasting_and_single_month() -> None:
    """Spotlight selects contrasting Winter/Summer months and falls back gracefully on 1 month."""
    from src.presentation.story_data import build_story_context

    opt_single, summary = _create_mock_optimization_result()
    ctx_single = build_story_context(opt_single, summary)
    assert ctx_single.seasonal_spotlight.winter is None
    assert ctx_single.seasonal_spotlight.summer is not None
    assert ctx_single.seasonal_spotlight.summer.month_code == "05"
    html_single = generate_interactive_html_report(
        opt_single, summary, lang="en", story_context=ctx_single
    )
    assert "spotlight_single_note" in html_single

    # Contrasting Jan (Winter: Heating 85% / Pool 15%) and Jul (Summer: Heating 25% / Pool 75%)
    c1, c2 = "ES0021000000000001AA", "ES0021000000000002BB"
    jan = CommunityMonthlyMetrics(
        month="01",
        strategy=OptimizationStrategy.OPTIMAL.value,
        total_consumption_kwh=2000.0,
        total_generation_kwh=600.0,
        total_self_consumed_kwh=550.0,
        total_surplus_kwh=50.0,
        total_grid_demand_kwh=1450.0,
        self_consumption_rate=91.7,
        solar_coverage_rate=27.5,
        beta_sum=1.0,
        cups_metrics=[
            CupsMonthlyMetrics(
                c1, "01", 0.85, 1800.0, 510.0, 480.0, 30.0, 1320.0, 94.1, 26.7, use="Aerotermia"
            ),
            CupsMonthlyMetrics(
                c2, "01", 0.15, 200.0, 90.0, 70.0, 20.0, 130.0, 77.8, 35.0, use="Piscina"
            ),
        ],
        has_data=True,
    )
    jul = CommunityMonthlyMetrics(
        month="07",
        strategy=OptimizationStrategy.OPTIMAL.value,
        total_consumption_kwh=1600.0,
        total_generation_kwh=3000.0,
        total_self_consumed_kwh=1400.0,
        total_surplus_kwh=1600.0,
        total_grid_demand_kwh=200.0,
        self_consumption_rate=46.7,
        solar_coverage_rate=87.5,
        beta_sum=1.0,
        cups_metrics=[
            CupsMonthlyMetrics(
                c1, "07", 0.25, 400.0, 750.0, 350.0, 400.0, 50.0, 46.7, 87.5, use="Aerotermia"
            ),
            CupsMonthlyMetrics(
                c2, "07", 0.75, 1200.0, 2250.0, 1050.0, 1200.0, 150.0, 46.7, 87.5, use="Piscina"
            ),
        ],
        has_data=True,
    )
    opt_multi = OptimizationResult(
        strategy=OptimizationStrategy.OPTIMAL.value,
        monthly_results=[jan, jul],
        total_summary=opt_single.total_summary,
        cups_list=[c1, c2],
        cups_uses={c1: "Aerotermia", c2: "Piscina"},
    )
    ctx_multi = build_story_context(opt_multi, summary)
    assert ctx_multi.seasonal_spotlight.winter is not None
    assert ctx_multi.seasonal_spotlight.summer is not None
    assert ctx_multi.seasonal_spotlight.winter.month_code == "01"
    assert ctx_multi.seasonal_spotlight.summer.month_code == "07"
    assert (
        ctx_multi.seasonal_spotlight.top_mover_winter_pct
        != ctx_multi.seasonal_spotlight.top_mover_summer_pct
    )


def test_story_fortnight_matrix_rendering_and_fallback() -> None:
    """Fortnight matrix renders 24 period columns with 100% totals and hides fallback note when populated."""
    opt_result, summary = _create_mock_optimization_result()

    # 1. Without fortnight_results -> fallback banner shown
    html_fallback = generate_interactive_html_report(opt_result, summary, lang="en", precision=2)
    assert "class='fn-note'" in html_fallback
    assert "id='fortnightTable'" in html_fallback
    assert "data-fortnight='05-1'" in html_fallback
    assert "data-fortnight='05-2'" in html_fallback

    # 2. With real fortnight_results -> fallback banner hidden, 100.00% totals shown
    c1, c2 = opt_result.cups_list
    f1 = CommunityMonthlyMetrics(
        month="05-1",
        strategy=OptimizationStrategy.OPTIMAL.value,
        total_consumption_kwh=700.0,
        total_generation_kwh=1000.0,
        total_self_consumed_kwh=600.0,
        total_surplus_kwh=400.0,
        total_grid_demand_kwh=100.0,
        self_consumption_rate=60.0,
        solar_coverage_rate=85.7,
        beta_sum=1.0,
        cups_metrics=[
            CupsMonthlyMetrics(
                c1, "05-1", 0.65, 500.0, 650.0, 420.0, 230.0, 80.0, 64.6, 84.0, use="Aerotermia"
            ),
            CupsMonthlyMetrics(
                c2, "05-1", 0.35, 200.0, 350.0, 180.0, 170.0, 20.0, 51.4, 90.0, use="Garaje"
            ),
        ],
        has_data=True,
    )
    opt_result.fortnight_results = [f1]
    html_real = generate_interactive_html_report(opt_result, summary, lang="en", precision=2)
    assert "class='fn-note'" not in html_real
    assert "100.00%" in html_real


def test_story_html_escaping_prevents_script_breakout() -> None:
    """Malicious HTML/script sequences in CUPS use labels are escaped in HTML and embedded JSON."""
    opt_result, summary = _create_mock_optimization_result()
    payload = "</script><img src=x onerror=alert(1)> & Co"
    opt_result.cups_uses["ES0021000000000001AA"] = payload
    opt_result.total_summary.cups_metrics[0] = CupsMonthlyMetrics(
        cups="ES0021000000000001AA",
        month="Total",
        beta=0.70,
        consumption_kwh=1000.0,
        generation_allocated_kwh=1400.0,
        self_consumed_kwh=800.0,
        surplus_kwh=600.0,
        grid_demand_kwh=200.0,
        self_consumption_rate=57.1,
        solar_coverage_rate=80.0,
        use=payload,
    )

    html_doc = generate_interactive_html_report(opt_result, summary, lang="en")
    assert "</script><img" not in html_doc
    assert "&lt;/script&gt;&lt;img" in html_doc
    assert "<\\/script>" in html_doc


def test_calculation_service_multi_year_story_integration(tmp_path: Path) -> None:
    """CalculationService reads multi-year curated consumption/generation and cached weather CSVs into story HTML."""
    import json
    import re

    curated_dir = tmp_path / "curated"
    output_dir = tmp_path / "output"
    weather_dir = tmp_path / "weather"
    cups_file = tmp_path / "cups.json"
    curated_dir.mkdir()
    output_dir.mkdir()
    weather_dir.mkdir()

    c1 = "ES0021000000000001AA"
    c2 = "ES0021000000000002BB"
    cups_file.write_text(
        json.dumps(
            [
                {
                    "cups": c1,
                    "use": "Aerotermia",
                    "primary": True,
                    "latitude": 40.4168,
                    "longitude": -3.7038,
                },
                {"cups": c2, "use": "Garaje"},
            ]
        ),
        encoding="utf-8",
    )

    cons_lines = ["timestamp;year;month;day;hour;day_of_week;is_weekend;cups_id;use;consumption"]
    for yr in (2024, 2025):
        for d in range(1, 4):
            cons_lines.append(
                f"{yr}-05-{d:02d} 12:00:00;{yr};5;{d};12;Thursday;False;{c1};Aerotermia;6,0"
            )
            cons_lines.append(
                f"{yr}-05-{d:02d} 12:00:00;{yr};5;{d};12;Thursday;False;{c2};Garaje;2,0"
            )
    (curated_dir / "consumption.csv").write_text("\n".join(cons_lines) + "\n", encoding="utf-8")

    gen_lines = [
        "timestamp;year;month;day;hour;day_of_week;is_weekend;generation;consumption;self_consumption;exported_energy;imported_energy"
    ]
    for yr in (2024, 2025):
        for d in range(1, 4):
            gen_lines.append(
                f"{yr}-05-{d:02d} 12:00:00;{yr};5;{d};12;Thursday;False;10,0;6,0;6,0;4,0;0,0"
            )
    (curated_dir / "generation.csv").write_text("\n".join(gen_lines) + "\n", encoding="utf-8")

    for yr, base_t in ((2024, 19.5), (2025, 22.0)):
        w_lines = ["timestamp,temperature,cloud_cover,weather_code"]
        for d in range(1, 4):
            w_lines.append(f"{yr}-05-{d:02d} 12:00:00,{base_t},15,1")
        (weather_dir / f"{yr}_40.4168_-3.7038_weather.csv").write_text(
            "\n".join(w_lines) + "\n", encoding="utf-8"
        )

    esd_lines = [
        "timestamp;year;month;day;hour;day_of_week;is_weekend;cups_id;use;consumption;community_demand;generation;self_consumption;exported_energy;imported_energy;temperature;cloud_cover"
    ]
    for d in range(1, 4):
        esd_lines.append(
            f"2025-05-{d:02d} 12:00:00;2025;5;{d};12;Thursday;False;{c1};Aerotermia;6,0;8,0;10,0;6,0;4,0;0,0;22,0;10"
        )
        esd_lines.append(
            f"2025-05-{d:02d} 12:00:00;2025;5;{d};12;Thursday;False;{c2};Garaje;2,0;8,0;10,0;0,0;0,0;0,0;22,0;10"
        )
    esd_csv = curated_dir / "esd.csv"
    esd_csv.write_text("\n".join(esd_lines) + "\n", encoding="utf-8")

    from src.services.calculation_service import CalculationRequest, CalculationService

    res = CalculationService.execute(
        CalculationRequest(
            consumption_dir=tmp_path / "missing_cons",
            generation_dir=tmp_path / "missing_gen",
            curated_dir=esd_csv,
            output_dir=output_dir,
            weather_dir=weather_dir,
            cups_config_path=cups_file,
            strategy=OptimizationStrategy.OPTIMAL,
            precision=1,
        )
    )

    html_files = [p for p in res.exported_paths if p.suffix == ".html"]
    assert len(html_files) == 1
    content = html_files[0].read_text(encoding="utf-8")
    assert '"years": [2024, 2025]' in content
    assert c1 in content
    assert c2 in content
    assert "Aerotermia" in content
    assert "Garaje" in content
    story_match = re.search(r"const STORY_DATA = (.+?);\n", content)
    assert story_match is not None
    story_data = json.loads(story_match.group(1))
    assert story_data["weather"]["has_data"] is True
    assert story_data["weather"]["years"] == [2024, 2025]


def test_story_data_weather_multi_year_and_analyzed_years_filter() -> None:
    """Weather history scopes strictly to analyzed years, computes temp/clear-sky stats, and marks [Inc]."""
    import pandas as pd

    from src.presentation.story_data import build_story_context

    opt_result, summary = _create_mock_optimization_result()
    c1, c2 = opt_result.cups_list

    cons_rows = []
    for yr in (2024, 2025):
        for ts in _build_hourly_timestamps(yr, 1, 31) + _build_hourly_timestamps(yr, 2, 10):
            cons_rows.append({"timestamp": ts, "cups_id": c1, "consumption": 3.0})
            cons_rows.append({"timestamp": ts, "cups_id": c2, "consumption": 1.0})
    cons_df = pd.DataFrame(cons_rows)

    # Include 2023 (outside analyzed years), 2024 complete Jan, 2025 complete Jan + incomplete Feb
    w_rows = []
    for ts in _build_hourly_timestamps(2023, 1, 31):
        w_rows.append({"timestamp": ts, "temperature": 5.0, "cloud_cover": 50, "weather_code": 2})
    for ts in _build_hourly_timestamps(2024, 1, 31):
        w_rows.append({"timestamp": ts, "temperature": 10.0, "cloud_cover": 20, "weather_code": 0})
    for ts in _build_hourly_timestamps(2025, 1, 31):
        w_rows.append({"timestamp": ts, "temperature": 12.0, "cloud_cover": 80, "weather_code": 61})
    for ts in _build_hourly_timestamps(2025, 2, 10):
        w_rows.append({"timestamp": ts, "temperature": 14.0, "cloud_cover": 10, "weather_code": 1})
    weather_df = pd.DataFrame(w_rows)

    ctx = build_story_context(
        opt_result=opt_result,
        ingestion_summary=summary,
        consumption_df=cons_df,
        weather_df=weather_df,
    )

    wh = ctx.weather_history
    assert wh.has_data is True
    assert wh.years == [2024, 2025]
    assert 2023 not in wh.by_year
    assert wh.by_year[2024].temp_avg[0] == 10.0
    assert wh.by_year[2024].clear_sky_pct[0] == 80.0
    assert wh.by_year[2024].sunny_days == 31
    assert wh.by_year[2024].statuses[0] == "complete"
    assert wh.by_year[2025].statuses[1] == "incomplete"
    assert wh.by_year[2025].rainy_days == 31
    assert wh.by_year[2025].sunny_days == 10


def test_story_data_weather_fallback_to_aligned_and_empty() -> None:
    """Weather falls back to aligned_dataset columns when weather_df is None, and disables gracefully if absent."""
    import pandas as pd

    from src.ingestion.schema import AlignedDataset
    from src.presentation.story_data import build_story_context

    opt_result, summary = _create_mock_optimization_result()
    c1, c2 = opt_result.cups_list

    # 1. Empty fallback when neither weather_df nor aligned weather columns exist
    ctx_empty = build_story_context(opt_result, summary)
    assert ctx_empty.weather_history.has_data is False
    assert ctx_empty.weather_history.years == []

    # 2. AlignedDataset fallback
    ts_list = _build_hourly_timestamps(2026, 5, 31)
    df_aln = pd.DataFrame(
        {
            c1: [5.0] * len(ts_list),
            c2: [2.0] * len(ts_list),
            "generation_kwh": [8.0] * len(ts_list),
            "temperature": [21.5] * len(ts_list),
            "cloud_cover": [25.0] * len(ts_list),
        },
        index=ts_list,
    )
    aligned = AlignedDataset(
        data=df_aln,
        cups_list=[c1, c2],
        metadata=summary,
        monthly_groups={"2026-05": df_aln},
        cups_uses={c1: "Aerotermia", c2: "Garaje"},
        primary_cups=c1,
    )
    ctx_aln = build_story_context(opt_result, summary, aligned_dataset=aligned)
    assert ctx_aln.weather_history.has_data is True
    assert ctx_aln.weather_history.years == [2026]
    assert ctx_aln.weather_history.by_year[2026].temp_avg[4] == 21.5
    assert ctx_aln.weather_history.by_year[2026].clear_sky_pct[4] == 75.0
    assert ctx_aln.weather_history.by_year[2026].has_weather_codes is False


def test_story_embedded_json_and_js_integrity() -> None:
    """Validate embedded I18N, STORY_DATA, PREVISION_CTX, and SPOTLIGHT_META JSON and theme button mapping."""
    import json
    import re

    import pandas as pd

    from src.domain.models import SupplyPoint
    from src.presentation.story_data import build_story_context

    opt_result, summary = _create_mock_optimization_result()
    c1, c2 = opt_result.cups_list
    cups_configs = {
        c1: SupplyPoint(cups=c1, use="Aerotermia", primary=True),
        c2: SupplyPoint(cups=c2, use="Garaje"),
    }
    rows = []
    for yr in (2024, 2025):
        for ts in _build_hourly_timestamps(yr, 5, 31):
            rows.append({"timestamp": ts, "cups_id": c1, "consumption": 3.0})
            rows.append({"timestamp": ts, "cups_id": c2, "consumption": 1.0})
    cons_df = pd.DataFrame(rows)

    ctx = build_story_context(
        opt_result=opt_result,
        ingestion_summary=summary,
        cups_configs=cups_configs,
        consumption_df=cons_df,
    )
    html_doc = generate_interactive_html_report(opt_result, summary, lang="en", story_context=ctx)

    for var_name in ("I18N", "STORY_DATA", "PREVISION_CTX", "SPOTLIGHT_META"):
        m = re.search(rf"const {var_name} = (.+?);\n", html_doc)
        assert m is not None, f"Missing embedded JS constant {var_name}"
        parsed = json.loads(m.group(1))
        assert isinstance(parsed, dict)

    story_match = re.search(r"const STORY_DATA = (.+?);\n", html_doc)
    assert story_match is not None
    story_data = json.loads(story_match.group(1))
    assert story_data["consumption"]["years"] == [2024, 2025]
    assert set(story_data["consumption"]["community"].keys()) == {"2024", "2025"}
    assert "weather" in story_data
    assert set(story_data["weather"].keys()) == {"has_data", "years", "by_year"}
    assert len(story_data["cups"]) == 2

    i18n_match = re.search(r"const I18N = (.+?);\n", html_doc)
    assert i18n_match is not None
    i18n_data = json.loads(i18n_match.group(1))
    assert set(i18n_data.keys()) == {"es", "en"}
    assert set(i18n_data["es"].keys()) == set(i18n_data["en"].keys())

    # Theme button mapping properly targets high-contrast button ID 'btn-theme-hc'
    assert "'high-contrast': 'btn-theme-hc'" in html_doc
    assert "el.namespaceURI === 'http://www.w3.org/2000/svg'" in html_doc
    assert "data-i18n-title" in html_doc
    assert "data-i18n-aria" in html_doc
