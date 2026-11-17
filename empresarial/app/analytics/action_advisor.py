"""Asesor Determinista de Plan de Acción Comercial de la Semana (Act. 3.4 y 3.5 F-DC-124)."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any

from app.core.models import utcnow

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")


def _q2(val: Decimal) -> Decimal:
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def compute_weekly_action_plan(
    *,
    products: list[dict[str, Any]],
    sales: list[dict[str, Any]],
    sale_items: list[dict[str, Any]],
    forecast_payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Calcula mediante estadística descriptiva y tendencia OLS las 3 recomendaciones accionables:
    1. Sugerencia exacta de reabastecimiento (Punto de reorden y días restantes).
    2. Simulador de liberación de efectivo para productos estancados sin vender a pérdida.
    3. Termómetro de meta mensual comparado contra la proyección estadística del mes.
    """
    ref_now = _as_utc(now) or utcnow()
    cutoff_30d = ref_now - timedelta(days=30)

    confirmed_sales: dict[str, dict[str, Any]] = {}
    sales_30d_ids: set[str] = set()
    current_month_revenue = Decimal("0.00")

    for s in sales:
        if str(s.get("status", "completed")) == "voided":
            continue
        sid = str(s["id"])
        occ = _as_utc(s.get("occurred_at")) or ref_now
        confirmed_sales[sid] = {**s, "_occ": occ}
        if occ >= cutoff_30d:
            sales_30d_ids.add(sid)
        if occ.year == ref_now.year and occ.month == ref_now.month:
            sub = Decimal(str(s.get("subtotal", "0")))
            disc = Decimal(str(s.get("discount_total", "0")))
            current_month_revenue += _q2(sub - disc)

    units_sold_30d: dict[str, Decimal] = {str(p["id"]): Decimal("0.000") for p in products}
    for it in sale_items:
        sid = str(it["sale_id"])
        pid = str(it["product_id"])
        if sid in sales_30d_ids and pid in units_sold_30d:
            units_sold_30d[pid] += Decimal(str(it.get("quantity", "0")))

    # 1. Tarjeta 1: Sugerencias Exactas de Reabastecimiento (Punto de Reorden)
    restock_suggestions: list[dict[str, Any]] = []
    # 2. Tarjeta 2: Candidatos a Liberación de Efectivo (Productos Estancados > 30D)
    stagnant_candidates: list[dict[str, Any]] = []

    for p in products:
        if p.get("is_active") is False:
            continue
        pid = str(p["id"])
        stock_qty = Decimal(str(p.get("stock_qty", "0")))
        min_stock = Decimal(str(p.get("min_stock", "0")))
        cost_price = Decimal(str(p.get("cost_price", "0")))
        sale_price = Decimal(str(p.get("sale_price", "0")))
        sold_30 = units_sold_30d.get(pid, Decimal("0.000"))

        daily_rate = sold_30 / Decimal(30)
        if daily_rate > Decimal(0) and stock_qty > Decimal(0):
            days_left = int(stock_qty // daily_rate)
        elif stock_qty <= Decimal(0):
            days_left = 0
        else:
            days_left = 999

        needs_restock = stock_qty <= min_stock or (daily_rate > Decimal(0) and days_left <= 14)
        if needs_restock and (sold_30 > Decimal(0) or stock_qty <= min_stock):
            target_qty = (daily_rate * Decimal(15)) + min_stock - stock_qty
            if target_qty < Decimal(1):
                target_qty = Decimal(5) if stock_qty <= min_stock else Decimal(1)
            suggested_units = int(target_qty.to_integral_value(rounding=ROUND_CEILING))
            investment = _q2(Decimal(suggested_units) * cost_price)
            restock_suggestions.append(
                {
                    "product_id": pid,
                    "sku": p["sku"],
                    "name": p["name"],
                    "unit": p.get("unit") or "und",
                    "stock_qty": str(stock_qty),
                    "min_stock": str(min_stock),
                    "daily_rate": str(_q2(daily_rate)),
                    "days_remaining": min(days_left, 365),
                    "suggested_units": suggested_units,
                    "investment_cop": str(investment),
                    "urgency": "critical" if stock_qty <= Decimal(0) or days_left <= 3 else "warning",
                }
            )

        if stock_qty > Decimal(0) and sold_30 <= Decimal(0):
            regular_value = _q2(stock_qty * sale_price)
            cost_value = _q2(stock_qty * cost_price)
            stagnant_candidates.append(
                {
                    "product_id": pid,
                    "sku": p["sku"],
                    "name": p["name"],
                    "unit": p.get("unit") or "und",
                    "stock_qty": float(stock_qty),
                    "cost_price": float(cost_price),
                    "sale_price": float(sale_price),
                    "cost_value_cop": str(cost_value),
                    "regular_value_cop": str(regular_value),
                }
            )

    restock_suggestions.sort(key=lambda r: (r["days_remaining"], -float(r["investment_cop"])))
    stagnant_candidates.sort(key=lambda r: -float(r["cost_value_cop"]))

    # Simulación precalculada para 10%, 15% y 20% asegurando precio promocional >= 1.05 * costo
    scenarios: dict[str, dict[str, Any]] = {}
    for pct in (10, 15, 20):
        disc_factor = Decimal(1) - (Decimal(pct) / Decimal(100))
        total_cash = Decimal("0.00")
        total_cost = Decimal("0.00")
        safe_capped_count = 0
        for item in stagnant_candidates:
            qty_d = Decimal(str(item["stock_qty"]))
            cost_d = Decimal(str(item["cost_price"]))
            sale_d = Decimal(str(item["sale_price"]))
            floor_price = _q2(cost_d * Decimal("1.05"))
            discounted = _q2(sale_d * disc_factor)
            promo_price = max(discounted, floor_price) if sale_d >= floor_price else sale_d
            if discounted < floor_price:
                safe_capped_count += 1
            total_cash += _q2(qty_d * promo_price)
            total_cost += _q2(qty_d * cost_d)

        scenarios[str(pct)] = {
            "discount_pct": pct,
            "cash_released_cop": str(_q2(total_cash)),
            "retained_profit_cop": str(_q2(total_cash - total_cost)),
            "protected_at_cost_floor": safe_capped_count,
        }

    # 3. Tarjeta 3: Termómetro de Meta Mensual OLS
    target_revenue = Decimal("0.00")
    forecast_source = "Sin historial suficiente"
    if forecast_payload:
        next_ols = forecast_payload.get("next_period_ols")
        projections = forecast_payload.get("projections") or []
        audit_rows = forecast_payload.get("audit_table") or []
        ols_vals = forecast_payload.get("forecast_ols") or []
        hist_vals = forecast_payload.get("historical") or []

        if next_ols is not None and Decimal(str(next_ols)) > Decimal("0.00"):
            target_revenue = _q2(Decimal(str(next_ols)))
            forecast_source = "Proyección tendencia lineal"
        elif projections and projections[0].get("ols_forecast") is not None:
            target_revenue = _q2(Decimal(str(projections[0]["ols_forecast"])))
            forecast_source = "Proyección tendencia lineal"
        elif ols_vals:
            target_revenue = _q2(Decimal(str(ols_vals[0].get("value", "0"))))
            forecast_source = "Proyección tendencia lineal"
        elif audit_rows:
            avg_audit = sum(
                (Decimal(str(r.get("observed_y", "0"))) for r in audit_rows), Decimal("0.00")
            ) / Decimal(len(audit_rows))
            target_revenue = _q2(avg_audit)
            forecast_source = "Promedio histórico"
        elif hist_vals:
            avg_hist = sum(
                (Decimal(str(h.get("value", "0"))) for h in hist_vals), Decimal("0.00")
            ) / Decimal(len(hist_vals))
            target_revenue = _q2(avg_hist)
            forecast_source = "Promedio histórico"

    if target_revenue <= Decimal("0.00") and current_month_revenue > Decimal("0.00"):
        target_revenue = _q2(current_month_revenue * Decimal("1.15"))
        forecast_source = "Meta sugerida (+15% mes)"

    next_month = (
        datetime(ref_now.year + 1, 1, 1, tzinfo=UTC)
        if ref_now.month == 12
        else datetime(ref_now.year, ref_now.month + 1, 1, tzinfo=UTC)
    )
    days_in_month = (next_month - datetime(ref_now.year, ref_now.month, 1, tzinfo=UTC)).days
    days_left_in_month = max(1, days_in_month - ref_now.day + 1)
    remaining_cop = max(Decimal("0.00"), _q2(target_revenue - current_month_revenue))
    daily_target_cop = (
        _q2(remaining_cop / Decimal(days_left_in_month)) if target_revenue > 0 else Decimal("0.00")
    )
    progress_pct = (
        min(Decimal("100.00"), _q2((current_month_revenue / target_revenue) * Decimal(100)))
        if target_revenue > Decimal("0.00")
        else Decimal("0.00")
    )

    return {
        "restock_suggestions": restock_suggestions[:5],
        "restock_total_alerts": len(restock_suggestions),
        "cash_release_simulator": {
            "stagnant_products_count": len(stagnant_candidates),
            "top_stagnant_items": stagnant_candidates[:4],
            "total_immobilized_cost_cop": str(
                _q2(
                    sum(
                        (Decimal(str(i["cost_value_cop"])) for i in stagnant_candidates), Decimal("0.00")
                    )
                )
            ),
            "default_discount_pct": 15,
            "scenarios": scenarios,
        },
        "monthly_goal_thermometer": {
            "current_month_revenue_cop": str(_q2(current_month_revenue)),
            "target_revenue_cop": str(target_revenue),
            "remaining_cop": str(remaining_cop),
            "progress_pct": str(progress_pct),
            "days_left_in_month": days_left_in_month,
            "daily_target_cop": str(daily_target_cop),
            "source_label": forecast_source,
        },
    }
