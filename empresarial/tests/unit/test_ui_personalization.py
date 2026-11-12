"""Tests Unitarios y de Integración del Motor de Personalización UI Basado en Encuesta (map-v1 / layout-v1)."""

from app.ui.ui_personalization_service import (
    ALL_KPIS,
    ALL_WIDGETS,
    DiagnosisInput,
    build_layout_config,
    compute_priority_weights,
)


def test_company_a_inventory_focus_vs_company_b_sales_focus():
    """
    Caso de Oro (§2.5 / §3.1):
    - Empresa A enfocada en quiebres y rotación de inventario (hojas de cálculo).
    - Empresa B enfocada en crecimiento de ventas y tendencias (software + tableros).
    Verifica pesos exactos, primary_focus, densidad y ordenamiento diferenciado del Bento Grid.
    """
    company_a_input = DiagnosisInput(
        M10=["Diferencias en inventario", "No identifica fácilmente la rotación"],
        M12=["Existencias y alertas", "Rotación de productos"],
        M17="Inventarios y existencias",
        M07=["Hojas de cálculo"],
        M08=["Hojas de cálculo"],
        M13="No",
        M15=["Precio"],
    )
    company_b_input = DiagnosisInput(
        M10=["Dificultad para analizar ventas", "Demora preparando informes"],
        M12=["Ventas por periodo", "Comparación entre periodos", "Tendencias o estimaciones"],
        M17="Consulta de ventas e indicadores",
        M07=["Software administrativo / ERP"],
        M08=["Software administrativo integrado"],
        M13="Sí",
        M15=["Precio"],
    )

    prof_a = compute_priority_weights(company_a_input)
    prof_b = compute_priority_weights(company_b_input)

    # Pesos Empresa A: 0 / 6 / 0 con Laplace alpha=0.5 -> 0.5/7.5 = 0.067, 6.5/7.5 = 0.866, 0.5/7.5 = 0.067
    assert prof_a.primary_focus == "inventory"
    assert prof_a.secondary_focus is None
    assert prof_a.preferred_chart_density == "standard"
    assert round(prof_a.weight_sales + prof_a.weight_inventory + prof_a.weight_predictive, 3) == 1.000
    assert prof_a.weight_inventory > 0.80

    # Pesos Empresa B: 6 / 0 / 1 con Laplace alpha=0.5 -> 6.5/8.5 = 0.765, 0.5/8.5 = 0.059, 1.5/8.5 = 0.176
    assert prof_b.primary_focus == "sales"
    assert prof_b.secondary_focus == "predictive"
    assert prof_b.preferred_chart_density == "detailed"
    assert round(prof_b.weight_sales + prof_b.weight_inventory + prof_b.weight_predictive, 3) == 1.000
    assert prof_b.weight_sales == 0.765
    assert prof_b.weight_inventory == 0.059
    assert prof_b.weight_predictive == 0.176

    layout_a = build_layout_config(prof_a, view_mode="personalized")
    layout_b = build_layout_config(prof_b, view_mode="personalized")

    # Orden de navegación y Hero Bento Row diferenciados
    assert layout_a["nav_order"] == ["home", "inventory", "sales", "forecast", "my_data"]
    assert layout_b["nav_order"] == ["home", "sales", "inventory", "forecast", "my_data"]
    assert layout_a["hero_row"][0]["widget"] == "stock_alerts"
    assert layout_b["hero_row"][0]["widget"] == "sales_trend"
    assert layout_a["expanded_kpis"] == ["stockout_risk", "turnover", "overstock"]
    assert layout_b["expanded_kpis"] == ["revenue", "gross_margin", "avg_ticket"]


def test_completeness_invariant_and_manual_override():
    """Ningún widget ni KPI se pierde jamás; cambiar a vista general retorna layout balanceado."""
    manual_notebook_input = DiagnosisInput(
        M10=["Herramientas costosas o complejas"],
        M12=["Tendencias o estimaciones"],
        M17="Tendencias o estimaciones",
        M07=["Registros manuales"],
        M08=["Registros manuales"],
        M13="No",
        M15=["Falta de conocimientos tecnológicos"],
    )
    prof = compute_priority_weights(manual_notebook_input)
    assert prof.primary_focus == "predictive"
    assert prof.preferred_chart_density == "simple"

    personalized = build_layout_config(prof, view_mode="personalized")
    assert personalized["hero_row"][0]["widget"] == "forecast_main"
    assert personalized["hero_row"][0].get("requires_methodology_disclaimer") is True

    # Invariante de completitud de KPIs y Widgets
    kpis_union = set(personalized["expanded_kpis"]) | set(personalized["compact_kpis"])
    assert kpis_union == set(ALL_KPIS)
    assert len(personalized["expanded_kpis"]) + len(personalized["compact_kpis"]) == len(ALL_KPIS)

    hero_widgets = [w["widget"] for w in personalized["hero_row"]]
    widgets_union = set(hero_widgets) | set(personalized["secondary_widgets"])
    assert widgets_union == set(ALL_WIDGETS)

    # Sobreescritura manual a vista general
    general = build_layout_config(prof, view_mode="general")
    assert general["view_mode"] == "general"
    assert general["primary_focus"] == "balanced"
    assert sum(w["cols"] for w in general["hero_row"]) == 12
