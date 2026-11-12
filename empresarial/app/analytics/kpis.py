"""
Motor de Cálculo Exacto de KPIs Comerciales y Clasificación Pareto (F-DC-124 Act. 3.4).

Reglas Financieras Inquebrantables:
- Toda operación monetaria utiliza `decimal.Decimal` con `ROUND_HALF_UP`.
- Las ventas en estado `voided` se excluyen estrictamente de ingresos, margen, ticket promedio y rotación.
- División segura por cero cuando una PyME recién creada aún no registra ventas o inventario.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.commercial_service import classify_inventory_alerts
from app.core.models import Product, Sale, SaleItem, UsageEvent

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")


def compute_pure_kpis(
    sales_records: list[dict[str, Decimal | str]],
    inventory_value_at_cost: Decimal,
    period_days: int = 30,
) -> dict[str, Any]:
    """
    Función pura auditable para pruebas unitarias matemáticas (Golden Math Tests).
    Recibe una lista de diccionarios de ventas con:
      - status: 'confirmed' | 'voided'
      - subtotal: Decimal (bruto antes de descuento, sin IVA)
      - discount_total: Decimal
      - vat_total: Decimal
      - total: Decimal
      - cogs_total: Decimal
    """
    net_revenue = Decimal(0)
    gross_total_with_vat = Decimal(0)
    cogs_total = Decimal(0)
    confirmed_count = 0
    voided_count = 0

    for s in sales_records:
        status = str(s.get("status", "confirmed"))
        if status == "voided":
            voided_count += 1
            continue
        confirmed_count += 1
        sub = Decimal(str(s.get("subtotal", "0"))).quantize(TWO_PLACES)
        disc = Decimal(str(s.get("discount_total", "0"))).quantize(TWO_PLACES)
        tot = Decimal(str(s.get("total", "0"))).quantize(TWO_PLACES)
        cogs = Decimal(str(s.get("cogs_total", "0"))).quantize(TWO_PLACES)

        net_sale = (sub - disc).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        net_revenue += net_sale
        gross_total_with_vat += tot
        cogs_total += cogs

    net_revenue = net_revenue.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    gross_total_with_vat = gross_total_with_vat.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    cogs_total = cogs_total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    gross_profit = (net_revenue - cogs_total).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    if net_revenue > Decimal(0):
        gross_margin_pct = ((gross_profit / net_revenue) * Decimal(100)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        gross_margin_pct = Decimal("0.00")

    if confirmed_count > 0:
        avg_ticket = (net_revenue / Decimal(confirmed_count)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        avg_ticket = Decimal("0.00")

    inv_val = Decimal(str(inventory_value_at_cost)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if inv_val > Decimal(0):
        inventory_turnover = (cogs_total / inv_val).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    else:
        inventory_turnover = Decimal("0.00")

    days_dec = Decimal(max(period_days, 1))
    daily_cogs = cogs_total / days_dec if cogs_total > Decimal(0) else Decimal(0)
    if daily_cogs > Decimal(0):
        days_of_coverage = (inv_val / daily_cogs).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    else:
        days_of_coverage = None

    return {
        "net_revenue": str(net_revenue),
        "gross_total_with_vat": str(gross_total_with_vat),
        "cogs_total": str(cogs_total),
        "gross_profit": str(gross_profit),
        "gross_margin_pct": str(gross_margin_pct),
        "avg_ticket": str(avg_ticket),
        "confirmed_sales_count": confirmed_count,
        "voided_sales_count": voided_count,
        "inventory_value_at_cost": str(inv_val),
        "inventory_turnover": str(inventory_turnover),
        "days_of_coverage": str(days_of_coverage) if days_of_coverage is not None else None,
    }


def compute_pareto_and_stagnant(
    products: list[dict[str, Any]],
    sold_by_product: dict[str, dict[str, Decimal]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Clasifica el catálogo de la PyME en:
    - `star_products`: Productos con ventas confirmadas ordenados descendentemente por ingresos netos,
      con participación porcentual y marca `is_pareto_80` (acumulado <= 80% o primer producto).
    - `stagnant_products`: Productos activos con stock > 0 y 0 unidades vendidas en el periodo,
      ordenados por capital inmovilizado (`stock_qty * cost_price`) descendente.
    """
    total_revenue = sum(
        (v["net_revenue"] for v in sold_by_product.values()),
        start=Decimal("0.00"),
    )

    star_candidates: list[dict[str, Any]] = []
    stagnant_candidates: list[dict[str, Any]] = []

    for p in products:
        pid = str(p["id"])
        stock_qty = Decimal(str(p["stock_qty"])).quantize(THREE_PLACES)
        cost_price = Decimal(str(p["cost_price"])).quantize(TWO_PLACES)
        immobilized_cop = (stock_qty * cost_price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        sales_info = sold_by_product.get(pid)
        units_sold = sales_info["units_sold"] if sales_info else Decimal("0.000")
        prod_rev = sales_info["net_revenue"] if sales_info else Decimal("0.00")

        if units_sold > Decimal(0):
            share_pct = (
                ((prod_rev / total_revenue) * Decimal(100)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                if total_revenue > Decimal(0)
                else Decimal("0.00")
            )
            star_candidates.append(
                {
                    "product_id": pid,
                    "sku": p["sku"],
                    "name": p["name"],
                    "category": p.get("category", "General"),
                    "units_sold": str(units_sold.quantize(THREE_PLACES)),
                    "net_revenue": str(prod_rev.quantize(TWO_PLACES)),
                    "revenue_share_pct": str(share_pct),
                    "_rev_dec": prod_rev,
                    "_share_dec": share_pct,
                }
            )
        elif stock_qty > Decimal(0):
            stagnant_candidates.append(
                {
                    "product_id": pid,
                    "sku": p["sku"],
                    "name": p["name"],
                    "category": p.get("category", "General"),
                    "stock_qty": str(stock_qty),
                    "cost_price": str(cost_price),
                    "immobilized_capital_cop": str(immobilized_cop),
                    "_imm_dec": immobilized_cop,
                }
            )

    star_candidates.sort(key=lambda item: item["_rev_dec"], reverse=True)
    cumulative = Decimal("0.00")
    star_products: list[dict[str, Any]] = []
    for idx, item in enumerate(star_candidates):
        prev_cum = cumulative
        cumulative = min(Decimal("100.00"), (cumulative + item["_share_dec"]).quantize(TWO_PLACES))
        is_pareto = idx == 0 or prev_cum < Decimal("80.00")
        star_products.append(
            {
                "product_id": item["product_id"],
                "sku": item["sku"],
                "name": item["name"],
                "category": item["category"],
                "units_sold": item["units_sold"],
                "net_revenue": item["net_revenue"],
                "revenue_share_pct": item["revenue_share_pct"],
                "cumulative_share_pct": str(cumulative),
                "is_pareto_80": is_pareto,
            }
        )

    stagnant_candidates.sort(key=lambda item: item["_imm_dec"], reverse=True)
    stagnant_products = [
        {k: v for k, v in item.items() if not k.startswith("_")}
        for item in stagnant_candidates
    ]

    return {
        "star_products": star_products,
        "stagnant_products": stagnant_products,
    }


def get_tenant_kpis_payload(
    db: Session,
    tenant_id: str,
    period_days: int = 30,
    record_event: bool = True,
) -> dict[str, Any]:
    """
    Calcula todos los KPIs comerciales, alertas de stock y clasificación Pareto/Estancados
    para un `tenant_id` específico (Row-Level Isolation obligatorio).
    """
    sales = db.query(Sale).filter_by(tenant_id=tenant_id).all()
    products = db.query(Product).filter_by(tenant_id=tenant_id, is_active=True).all()

    inv_val_cost = Decimal("0.00")
    product_dicts: list[dict[str, Any]] = []
    for p in products:
        sq = Decimal(str(p.stock_qty)).quantize(THREE_PLACES)
        cp = Decimal(str(p.cost_price)).quantize(TWO_PLACES)
        if sq > Decimal(0):
            inv_val_cost += (sq * cp).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        product_dicts.append(
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "category": p.category,
                "stock_qty": sq,
                "cost_price": cp,
            }
        )

    sales_records = [
        {
            "status": s.status,
            "subtotal": Decimal(str(s.subtotal)),
            "discount_total": Decimal(str(s.discount_total)),
            "vat_total": Decimal(str(s.vat_total)),
            "total": Decimal(str(s.total)),
            "cogs_total": Decimal(str(s.cogs_total)),
        }
        for s in sales
    ]
    core_kpis = compute_pure_kpis(
        sales_records=sales_records,
        inventory_value_at_cost=inv_val_cost,
        period_days=period_days,
    )

    confirmed_sale_ids = {s.id for s in sales if s.status != "voided"}
    sale_items = (
        db.query(SaleItem)
        .filter(SaleItem.tenant_id == tenant_id)
        .all()
    )
    sold_by_product: dict[str, dict[str, Decimal]] = {}
    for item in sale_items:
        if item.sale_id not in confirmed_sale_ids:
            continue
        entry = sold_by_product.setdefault(
            item.product_id,
            {"units_sold": Decimal("0.000"), "net_revenue": Decimal("0.00")},
        )
        entry["units_sold"] += Decimal(str(item.quantity)).quantize(THREE_PLACES)
        entry["net_revenue"] += Decimal(str(item.line_total)).quantize(TWO_PLACES)

    pareto = compute_pareto_and_stagnant(product_dicts, sold_by_product)
    alerts = classify_inventory_alerts(db, tenant_id)
    alerts_summary = {
        "out_of_stock": len(alerts["out_of_stock"]),
        "stockout_risk": len(alerts["stockout_risk"]),
        "overstock": len(alerts["overstock"]),
        "total_alerts": len(alerts["out_of_stock"]) + len(alerts["stockout_risk"]) + len(alerts["overstock"]),
    }
    alerts_items = (alerts["out_of_stock"] + alerts["stockout_risk"] + alerts["overstock"])[:10]

    if record_event:
        db.add(UsageEvent(tenant_id=tenant_id, event_type="kpi_dashboard_viewed"))
        db.commit()

    return {
        "tenant_id": tenant_id,
        "period_days": period_days,
        "kpis": core_kpis,
        "star_products": pareto["star_products"],
        "stagnant_products": pareto["stagnant_products"],
        "alerts_summary": alerts_summary,
        "alerts_items": alerts_items,
    }
