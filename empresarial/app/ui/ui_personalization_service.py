"""
Motor de Interfaz Adaptativa Basado en Encuesta (Survey-Driven Adaptive UI).
Implementa el mapeo determinista `map-v1` y el generador de layout `layout-v1` (Bento Grid Adaptativo).
"""
from dataclasses import dataclass, field
from typing import Any, Literal

MAPPING_VERSION = "map-v1"
LAYOUT_VERSION = "layout-v1"

ALL_KPIS = (
    "revenue",
    "gross_margin",
    "avg_ticket",
    "stockout_risk",
    "turnover",
    "overstock",
)

ALL_WIDGETS = (
    "stock_alerts",
    "turnover_coverage",
    "sales_trend",
    "top_products",
    "category_mix",
    "forecast_main",
)

FocusType = Literal["sales", "inventory", "predictive", "balanced"]
DensityType = Literal["simple", "standard", "detailed"]
ViewModeType = Literal["personalized", "general"]


@dataclass
class DiagnosisInput:
    M10: list[str] = field(default_factory=list)
    M12: list[str] = field(default_factory=list)
    M17: str = ""
    M07: list[str] = field(default_factory=list)
    M08: list[str] = field(default_factory=list)
    M13: str = "No"
    M15: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "M10": list(self.M10),
            "M12": list(self.M12),
            "M17": self.M17,
            "M07": list(self.M07),
            "M08": list(self.M08),
            "M13": self.M13,
            "M15": list(self.M15),
        }


@dataclass(frozen=True)
class PriorityProfile:
    weight_sales: float
    weight_inventory: float
    weight_predictive: float
    primary_focus: FocusType
    secondary_focus: str | None
    preferred_chart_density: DensityType
    mapping_version: str = MAPPING_VERSION
    explanations: list[dict[str, str]] = field(default_factory=list)


def compute_priority_weights(diagnosis: DiagnosisInput) -> PriorityProfile:
    """Calcula los pesos normalizados con suavizado de Laplace (alpha=0.5) bajo map-v1."""
    pts_sales = 0.0
    pts_inv = 0.0
    pts_pred = 0.0
    explanations: list[dict[str, str]] = []

    # 1. M10 — Dolores principales identificados en la encuesta
    for item in diagnosis.M10:
        if item in ("Dificultad para analizar ventas", "Demora preparando informes"):
            pts_sales += 1.0
            explanations.append({"widget": "sales_trend", "reason_code": f"M10:{item}"})
        elif item in ("Diferencias en inventario", "No identifica fácilmente la rotación"):
            pts_inv += 1.0
            explanations.append({"widget": "stock_alerts", "reason_code": f"M10:{item}"})
        elif item in ("Datos dispersos", "Información desactualizada"):
            pts_sales += 0.5
            pts_inv += 0.5

    # 2. M12 — Información más útil para tomar decisiones
    for item in diagnosis.M12:
        if item in ("Ventas por periodo", "Comparación entre periodos", "Productos más y menos vendidos"):
            pts_sales += 1.0
        elif item in ("Existencias y alertas", "Rotación de productos"):
            pts_inv += 1.0
        elif item == "Tendencias o estimaciones":
            pts_pred += 1.0
            explanations.append({"widget": "forecast_main", "reason_code": "M12:Tendencias o estimaciones"})

    # 3. M17 — Capacidad prioritaria declarada (doble peso = 2.0)
    if diagnosis.M17 == "Consulta de ventas e indicadores":
        pts_sales += 2.0
        explanations.append({"widget": "sales_trend", "reason_code": "M17:Consulta de ventas e indicadores"})
    elif diagnosis.M17 in ("Inventarios y existencias", "Rotación de productos"):
        pts_inv += 2.0
        explanations.append({"widget": "turnover_coverage", "reason_code": f"M17:{diagnosis.M17}"})
    elif diagnosis.M17 == "Tendencias o estimaciones":
        pts_pred += 2.0
        explanations.append({"widget": "forecast_main", "reason_code": "M17:Tendencias o estimaciones"})

    # Normalización con suavizado de Laplace alpha = 0.5
    alpha = 0.5
    denom = pts_sales + pts_inv + pts_pred + (3.0 * alpha)
    w_sales = round((pts_sales + alpha) / denom, 3)
    w_inv = round((pts_inv + alpha) / denom, 3)
    w_pred = round((pts_pred + alpha) / denom, 3)

    # Ajuste exacto de milésimas en el eje dominante para garantizar suma == 1.000
    diff = round(1.000 - (w_sales + w_inv + w_pred), 3)
    if diff != 0:
        if w_inv >= w_sales and w_inv >= w_pred:
            w_inv = round(w_inv + diff, 3)
        elif w_sales >= w_inv and w_sales >= w_pred:
            w_sales = round(w_sales + diff, 3)
        else:
            w_pred = round(w_pred + diff, 3)

    # Ordenamiento con desempate determinista: inventory > sales > predictive
    tie_rank = {"inventory": 3, "sales": 2, "predictive": 1}
    ranked = sorted(
        [("inventory", w_inv), ("sales", w_sales), ("predictive", w_pred)],
        key=lambda x: (x[1], tie_rank[x[0]]),
        reverse=True,
    )
    top_axis, top_w = ranked[0]
    second_axis, second_w = ranked[1]

    if top_w >= 0.40 and (top_w - second_w) >= 0.15:
        primary_focus: FocusType = top_axis  # type: ignore[assignment]
    else:
        primary_focus = "balanced"

    secondary_focus: str | None = None
    if primary_focus != "balanced" and second_w >= 0.15:
        secondary_focus = second_axis

    # Cálculo de densidad según madurez digital declarada (M07/M08/M13/M10/M15)
    tools = set(diagnosis.M07) | set(diagnosis.M08)
    software_markers = {
        "Facturación / punto de venta",
        "Software administrativo / ERP",
        "Software de inventarios",
        "Software administrativo integrado",
        "Comercio electrónico",
    }
    if tools & software_markers:
        level = 2
    elif "Hojas de cálculo" in tools:
        level = 1
    else:
        level = 0

    if diagnosis.M13 == "Sí":
        level += 1
    if (
        "Herramientas costosas o complejas" in diagnosis.M10
        or "Falta de conocimientos tecnológicos" in diagnosis.M15
    ):
        level -= 1

    level = max(0, min(2, level))
    density_map: dict[int, DensityType] = {0: "simple", 1: "standard", 2: "detailed"}

    return PriorityProfile(
        weight_sales=w_sales,
        weight_inventory=w_inv,
        weight_predictive=w_pred,
        primary_focus=primary_focus,
        secondary_focus=secondary_focus,
        preferred_chart_density=density_map[level],
        mapping_version=MAPPING_VERSION,
        explanations=explanations,
    )


def build_layout_config(
    profile: PriorityProfile, view_mode: ViewModeType = "personalized"
) -> dict[str, Any]:
    """
    Función pura que construye el contrato `layout-v1` para el Bento Grid Adaptativo.
    Garantiza el invariante de completitud (el 100 % de los widgets y KPIs están siempre presentes).
    """
    effective_focus: FocusType = "balanced" if view_mode == "general" else profile.primary_focus

    if effective_focus == "inventory":
        nav_order = ["home", "inventory", "sales", "forecast", "my_data"]
        hero_row = [
            {"widget": "stock_alerts", "size": "xl", "cols": 8},
            {"widget": "turnover_coverage", "size": "m", "cols": 4},
        ]
        expanded_kpis = ["stockout_risk", "turnover", "overstock"]
        compact_kpis = ["revenue", "gross_margin", "avg_ticket"]
    elif effective_focus == "sales":
        nav_order = ["home", "sales", "inventory", "forecast", "my_data"]
        hero_row = [
            {"widget": "sales_trend", "size": "xl", "cols": 8},
            {"widget": "top_products", "size": "m", "cols": 4},
        ]
        expanded_kpis = ["revenue", "gross_margin", "avg_ticket"]
        compact_kpis = ["stockout_risk", "turnover", "overstock"]
    elif effective_focus == "predictive":
        nav_order = ["home", "forecast", "sales", "inventory", "my_data"]
        hero_row = [
            {
                "widget": "forecast_main",
                "size": "xl",
                "cols": 8,
                "requires_methodology_disclaimer": True,
            },
            {"widget": "sales_trend", "size": "m", "cols": 4},
        ]
        expanded_kpis = ["revenue", "stockout_risk", "turnover"]
        compact_kpis = ["gross_margin", "avg_ticket", "overstock"]
    else:
        nav_order = ["home", "sales", "inventory", "forecast", "my_data"]
        hero_row = [
            {"widget": "sales_trend", "size": "l", "cols": 6},
            {"widget": "stock_alerts", "size": "l", "cols": 6},
        ]
        expanded_kpis = ["revenue", "gross_margin", "stockout_risk", "turnover"]
        compact_kpis = ["avg_ticket", "overstock"]

    hero_names = {w["widget"] for w in hero_row}
    secondary_widgets = [w for w in ALL_WIDGETS if w not in hero_names]

    return {
        "version": LAYOUT_VERSION,
        "view_mode": view_mode,
        "primary_focus": effective_focus,
        "diagnosed_focus": profile.primary_focus,
        "secondary_focus": profile.secondary_focus,
        "density": profile.preferred_chart_density,
        "priority_weights": {
            "weight_sales": profile.weight_sales,
            "weight_inventory": profile.weight_inventory,
            "weight_predictive": profile.weight_predictive,
        },
        "nav_order": nav_order,
        "hero_row": hero_row,
        "expanded_kpis": expanded_kpis,
        "compact_kpis": compact_kpis,
        "secondary_widgets": secondary_widgets,
        "explanations": profile.explanations,
    }
