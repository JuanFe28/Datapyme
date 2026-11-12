"""
Componente Básico de Analítica Predictiva Transparente (F-DC-124 Actividad 3.5).

Restricción Normativa Inquebrantable (F-DC-124):
- Exclusivamente Regresión Lineal Simple por Mínimos Cuadrados Ordinarios (OLS: y_hat = beta_0 + beta_1 * x, R^2)
  y Promedios Móviles de 3 periodos (SMA-3 y WMA-3 con pesos [1, 2, 3]).
- PROHIBIDO conectar APIs externas de IA o modelos opacos de Deep Learning.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.models import Sale, SaleItem, UsageEvent

MANDATORY_FDC124_DISCLAIMER = (
    "Proyección estadística orientativa basada en Regresión Lineal Simple por Mínimos Cuadrados "
    "Ordinarios (OLS) y Promedios Móviles de 3 periodos (SMA-3 / WMA-3) sobre el histórico "
    "registrado (F-DC-124 Act. 3.5). No constituye asesoría financiera ni emplea modelos opacos de IA."
)

TWO_PLACES = Decimal("0.01")
SIX_PLACES = Decimal("0.000001")


def compute_ols_and_moving_averages(
    series: list[float | int | Decimal],
    horizon: int = 1,
    period_labels: list[str] | None = None,
) -> dict[str, Any]:
    """
    Calcula en Python puro:
      - Regresión Lineal Simple por Mínimos Cuadrados Ordinarios (beta_0, beta_1, R^2)
      - Promedio Móvil Simple de 3 periodos (SMA-3)
      - Promedio Móvil Ponderado de 3 periodos (WMA-3 con pesos 1, 2, 3)
      - Proyección a `horizon` periodos futuros (1..3)
      - Tabla de auditoría periodo a periodo con valores ajustados y residuos
    """
    if horizon < 1 or horizon > 6:
        raise ValueError("El horizonte de proyección debe estar entre 1 y 6 periodos.")

    n = len(series)
    if n < 3:
        return {
            "status": "insufficient_data",
            "minimum_periods_required": 3,
            "observed_periods": n,
            "message": (
                "Se requieren al menos 3 periodos históricos cerrados para calcular "
                "Regresión Lineal Simple (OLS) y Promedios Móviles de 3 periodos (SMA-3 / WMA-3)."
            ),
            "methodological_disclaimer": MANDATORY_FDC124_DISCLAIMER,
        }

    y_vals = [float(v) for v in series]
    x_vals = [float(i) for i in range(1, n + 1)]

    sum_x = sum(x_vals)
    sum_y = sum(y_vals)
    sum_xy = sum(x * y for x, y in zip(x_vals, y_vals, strict=True))
    sum_x2 = sum(x * x for x in x_vals)

    denom = (n * sum_x2) - (sum_x * sum_x)
    if abs(denom) < 1e-12:
        beta_1 = 0.0
    else:
        beta_1 = ((n * sum_xy) - (sum_x * sum_y)) / denom

    x_bar = sum_x / n
    y_bar = sum_y / n
    beta_0 = y_bar - (beta_1 * x_bar)

    y_hat_vals = [beta_0 + (beta_1 * x) for x in x_vals]
    ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(y_vals, y_hat_vals, strict=True))
    ss_tot = sum((y - y_bar) ** 2 for y in y_vals)

    if abs(ss_tot) < 1e-12:
        r_squared = 1.0
    else:
        r_squared = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot)))

    if r_squared >= 0.70:
        fit_quality_label = "alto"
    elif r_squared >= 0.40:
        fit_quality_label = "moderado"
    else:
        fit_quality_label = "bajo"

    # SMA-3 y WMA-3 para el siguiente periodo t = n + 1
    last_3 = y_vals[-3:]
    sma_3 = (last_3[0] + last_3[1] + last_3[2]) / 3.0
    wma_3 = ((1.0 * last_3[0]) + (2.0 * last_3[1]) + (3.0 * last_3[2])) / 6.0

    # Tabla histórica auditable (con SMA-3 y WMA-3 deslizantes)
    labels = (
        period_labels
        if (period_labels and len(period_labels) == n)
        else [f"P{i}" for i in range(1, n + 1)]
    )
    audit_rows: list[dict[str, Any]] = []
    for idx in range(n):
        x_i = idx + 1
        y_i = y_vals[idx]
        yh_i = y_hat_vals[idx]
        res_i = y_i - yh_i
        if idx >= 2:
            win = y_vals[idx - 2 : idx + 1]
            row_sma3 = round(sum(win) / 3.0, 2)
            row_wma3 = round((1.0 * win[0] + 2.0 * win[1] + 3.0 * win[2]) / 6.0, 2)
        else:
            row_sma3 = None
            row_wma3 = None
        audit_rows.append(
            {
                "period_index": x_i,
                "period_label": labels[idx],
                "observed_y": round(y_i, 2),
                "ols_fitted_y": round(yh_i, 2),
                "residual": round(res_i, 2),
                "sma_3": row_sma3,
                "wma_3": row_wma3,
            }
        )

    projections: list[dict[str, Any]] = []
    for step in range(1, horizon + 1):
        future_x = n + step
        ols_proj = beta_0 + (beta_1 * future_x)
        projections.append(
            {
                "period_index": future_x,
                "period_label": f"Proyección t+{step}",
                "ols_forecast": round(ols_proj, 2),
                "sma_3_forecast": round(sma_3, 2) if step == 1 else None,
                "wma_3_forecast": round(wma_3, 2) if step == 1 else None,
            }
        )

    sign_str = "+" if beta_1 >= 0 else "-"
    equation_str = f"y_hat = {beta_0:.2f} {sign_str} {abs(beta_1):.2f} * x"

    return {
        "status": "ok",
        "observed_periods": n,
        "horizon": horizon,
        "equation": equation_str,
        "beta_0": round(beta_0, 6),
        "beta_1": round(beta_1, 6),
        "r_squared": round(r_squared, 6),
        "fit_quality_label": fit_quality_label,
        "sma_3": round(sma_3, 2),
        "wma_3": round(wma_3, 2),
        "next_period_ols": round(beta_0 + (beta_1 * (n + 1)), 2),
        "projections": projections,
        "audit_table": audit_rows,
        "methodological_disclaimer": MANDATORY_FDC124_DISCLAIMER,
    }


def get_tenant_forecast_payload(
    db: Session,
    tenant_id: str,
    metric: str = "net_revenue",
    horizon: int = 1,
    product_id: str | None = None,
    record_event: bool = True,
) -> dict[str, Any]:
    """
    Agrega la serie histórica de la PyME (`tenant_id`) por mes calendario (`YYYY-MM`) o
    por secuencia de ventas confirmadas cuando hay múltiples periodos, y ejecuta
    `compute_ols_and_moving_averages`.
    """
    sales = (
        db.query(Sale)
        .filter(Sale.tenant_id == tenant_id, Sale.status != "voided")
        .order_by(Sale.occurred_at.asc(), Sale.sale_number.asc())
        .all()
    )

    bucket_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

    if metric == "units_sold" and product_id:
        sale_map = {s.id: s for s in sales}
        items = db.query(SaleItem).filter_by(tenant_id=tenant_id, product_id=product_id).all()
        for item in items:
            parent_sale = sale_map.get(item.sale_id)
            if not parent_sale:
                continue
            period_key = parent_sale.occurred_at.strftime("%Y-%m")
            bucket_totals[period_key] += Decimal(str(item.quantity))
    else:
        for s in sales:
            period_key = s.occurred_at.strftime("%Y-%m")
            net_val = (Decimal(str(s.subtotal)) - Decimal(str(s.discount_total))).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            bucket_totals[period_key] += net_val

    sorted_keys = sorted(bucket_totals.keys())
    # Si todas las ventas de prueba cayeron en menos de 3 meses pero hay >= 3 ventas confirmadas,
    # agrupamos por transacción individual para permitir la proyección operativa inmediata.
    if len(sorted_keys) < 3 and len(sales) >= 3 and metric == "net_revenue":
        labels = [f"V-{s.sale_number}" for s in sales]
        values = [
            float((Decimal(str(s.subtotal)) - Decimal(str(s.discount_total))).quantize(TWO_PLACES))
            for s in sales
        ]
    else:
        labels = sorted_keys
        values = [float(bucket_totals[k]) for k in sorted_keys]

    result = compute_ols_and_moving_averages(series=values, horizon=horizon, period_labels=labels)
    result["tenant_id"] = tenant_id
    result["metric"] = metric

    if record_event:
        db.add(UsageEvent(tenant_id=tenant_id, event_type="forecast_executed"))
        db.commit()

    return result
