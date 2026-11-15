"""Motor detallado de Ganancias, Pérdidas Operativas y Ranking de Productos (F-DC-124 / F-DC-125).

Principios contables y financieros:
- Cálculos monetarios exactos mediante `decimal.Decimal` con `ROUND_HALF_UP`.
- Excluye ventas anuladas (`status == 'voided'`) de ingresos, COGS y utilidades.
- Separa explícitamente las pérdidas por merma (`adjustment_out`) y por ventas bajo costo.
- Todas las cifras de ingresos excluyen el IVA recaudado.
"""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.models import InventoryMovement, Product, Sale, SaleItem, utcnow

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")

_MONTH_NAMES_ES = (
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _q2(val: Decimal) -> Decimal:
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _q3(val: Decimal) -> Decimal:
    return val.quantize(THREE_PLACES, rounding=ROUND_HALF_UP)


def compute_pure_profitability(
    products: list[dict[str, Any]],
    sales: list[dict[str, Any]],
    sale_items: list[dict[str, Any]],
    shrinkage_movements: list[dict[str, Any]],
    period_days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calcula de forma pura y auditable el P&L comercial, pérdidas y rankings de productos."""
    ref_now = _as_aware_utc(now) or utcnow()
    cutoff = ref_now - timedelta(days=max(1, period_days))
    cutoff_30d = ref_now - timedelta(days=30)

    products_by_id: dict[str, dict[str, Any]] = {str(p["id"]): p for p in products}
    confirmed_sales: dict[str, dict[str, Any]] = {}
    period_sales: dict[str, dict[str, Any]] = {}
    last_sale_by_product: dict[str, datetime] = {}
    sold_30d_products: set[str] = set()

    gross_sales_without_vat = Decimal("0.00")
    discount_total = Decimal("0.00")
    net_revenue = Decimal("0.00")
    cogs_total = Decimal("0.00")

    for s in sales:
        if str(s.get("status", "completed")) == "voided":
            continue
        sid = str(s["id"])
        occurred_at = _as_aware_utc(s.get("occurred_at")) or ref_now
        entry = {**s, "_occurred": occurred_at}
        confirmed_sales[sid] = entry
        if occurred_at >= cutoff:
            period_sales[sid] = entry
            sub = _q2(Decimal(str(s.get("subtotal", "0"))))
            disc = _q2(Decimal(str(s.get("discount_total", "0"))))
            cogs = _q2(Decimal(str(s.get("cogs_total", "0"))))
            gross_sales_without_vat += sub
            discount_total += disc
            net_revenue += _q2(sub - disc)
            cogs_total += cogs

    prod_stats: dict[str, dict[str, Any]] = {}
    for pid in products_by_id:
        prod_stats[pid] = {
            "units_sold": Decimal("0.000"),
            "net_revenue": Decimal("0.00"),
            "cogs_total": Decimal("0.00"),
            "below_cost_loss": Decimal("0.00"),
            "shrinkage_loss": Decimal("0.00"),
            "has_below_cost": False,
        }

    below_cost_loss_cop = Decimal("0.00")
    below_cost_items_count = 0

    for item in sale_items:
        sid = str(item["sale_id"])
        sale_row = confirmed_sales.get(sid)
        if not sale_row:
            continue
        pid = str(item["product_id"])
        occurred_at = sale_row["_occurred"]

        prev_dt = last_sale_by_product.get(pid)
        if prev_dt is None or occurred_at > prev_dt:
            last_sale_by_product[pid] = occurred_at
        if occurred_at >= cutoff_30d:
            sold_30d_products.add(pid)

        if sid not in period_sales or pid not in prod_stats:
            continue

        qty = _q3(Decimal(str(item["quantity"])))
        unit_price = Decimal(str(item.get("unit_price", "0")))
        discount = _q2(Decimal(str(item.get("discount", "0"))))
        unit_cost = _q2(Decimal(str(item.get("unit_cost_snapshot", "0"))))

        line_net_rev = _q2(_q2(qty * unit_price) - discount)
        line_cogs = _q2(qty * unit_cost)

        st = prod_stats[pid]
        st["units_sold"] += qty
        st["net_revenue"] += line_net_rev
        st["cogs_total"] += line_cogs

        if line_net_rev < line_cogs:
            loss = _q2(line_cogs - line_net_rev)
            below_cost_loss_cop += loss
            below_cost_items_count += 1
            st["below_cost_loss"] += loss
            st["has_below_cost"] = True

    shrinkage_loss_cop = Decimal("0.00")
    shrinkage_movements_count = 0

    for mov in shrinkage_movements:
        if str(mov.get("movement_type")) != "adjustment_out":
            continue
        occurred_at = _as_aware_utc(mov.get("occurred_at")) or ref_now
        if occurred_at < cutoff:
            continue
        pid = str(mov["product_id"])
        qty_abs = abs(_q3(Decimal(str(mov.get("quantity", "0")))))
        if mov.get("unit_cost") is not None:
            unit_cost = _q2(Decimal(str(mov["unit_cost"])))
        elif pid in products_by_id:
            unit_cost = _q2(Decimal(str(products_by_id[pid]["cost_price"])))
        else:
            unit_cost = Decimal("0.00")

        loss = _q2(qty_abs * unit_cost)
        shrinkage_loss_cop += loss
        shrinkage_movements_count += 1
        if pid in prod_stats:
            prod_stats[pid]["shrinkage_loss"] += loss

    gross_sales_without_vat = _q2(gross_sales_without_vat)
    discount_total = _q2(discount_total)
    net_revenue = _q2(net_revenue)
    cogs_total = _q2(cogs_total)
    gross_profit = _q2(net_revenue - cogs_total)
    gross_margin_pct = (
        _q2((gross_profit / net_revenue) * Decimal(100)) if net_revenue > 0 else Decimal("0.00")
    )
    shrinkage_loss_cop = _q2(shrinkage_loss_cop)
    below_cost_loss_cop = _q2(below_cost_loss_cop)
    total_losses_cop = _q2(shrinkage_loss_cop + below_cost_loss_cop)
    net_profit_after_losses = _q2(gross_profit - shrinkage_loss_cop)
    net_margin_after_losses_pct = (
        _q2((net_profit_after_losses / net_revenue) * Decimal(100))
        if net_revenue > 0
        else Decimal("0.00")
    )

    immobilized_capital_30d = Decimal("0.00")
    top_candidates: list[dict[str, Any]] = []
    product_rows_all: list[dict[str, Any]] = []

    for pid, p in products_by_id.items():
        stock_qty = _q3(Decimal(str(p.get("stock_qty", "0"))))
        cost_price = _q2(Decimal(str(p.get("cost_price", "0"))))
        stock_val = _q2(stock_qty * cost_price) if stock_qty > 0 else Decimal("0.00")
        if stock_qty > 0 and pid not in sold_30d_products:
            immobilized_capital_30d += stock_val

        st = prod_stats[pid]
        units = _q3(st["units_sold"])
        rev = _q2(st["net_revenue"])
        cogs = _q2(st["cogs_total"])
        profit = _q2(rev - cogs)
        margin = _q2((profit / rev) * Decimal(100)) if rev > 0 else Decimal("0.00")
        share = _q2((rev / net_revenue) * Decimal(100)) if net_revenue > 0 else Decimal("0.00")
        shrink_p = _q2(st["shrinkage_loss"])
        below_p = _q2(st["below_cost_loss"])

        last_dt = last_sale_by_product.get(pid)
        days_since: int | None = max(0, (ref_now.date() - last_dt.date()).days) if last_dt else None
        last_sale_label = (
            "Sin ventas registradas"
            if days_since is None
            else ("Hoy" if days_since == 0 else f"Hace {days_since} d")
        )

        row_base = {
            "product_id": pid,
            "image_url": p.get("image_url"),
            "sku": p["sku"],
            "name": p["name"],
            "category": p.get("category") or "General",
            "unit": p.get("unit") or "und",
            "units_sold": str(units),
            "net_revenue": str(rev),
            "cogs_total": str(cogs),
            "profit_cop": str(profit),
            "margin_pct": str(margin),
            "revenue_share_pct": str(share),
            "stock_qty": str(stock_qty),
            "stock_value_cop": str(stock_val),
            "days_since_last_sale": days_since,
            "last_sale_label": last_sale_label,
            "shrinkage_loss_cop": str(shrink_p),
            "below_cost_loss_cop": str(below_p),
            "_units": units,
            "_profit": profit,
            "_rev": rev,
            "_stock_val": stock_val,
            "_shrink": shrink_p,
            "_margin": margin,
            "_has_below": st["has_below_cost"],
        }
        product_rows_all.append(row_base)
        if units > 0:
            top_candidates.append(row_base)

    top_candidates.sort(key=lambda r: (r["_units"], r["_profit"], r["_rev"]), reverse=True)
    top_selling = [{k: v for k, v in r.items() if not k.startswith("_")} for r in top_candidates]

    top_leader_id = top_candidates[0]["product_id"] if len(top_candidates) > 1 else None
    least_candidates: list[dict[str, Any]] = []
    seen_least: set[str] = set()

    for r in product_rows_all:
        is_zero = r["_units"] == Decimal("0.000")
        is_loss = r["_profit"] < 0 or r["_has_below"] or (r["_units"] > 0 and r["_margin"] < 10)
        is_shrink = r["_shrink"] > 0
        if is_zero or is_loss or is_shrink:
            seen_least.add(r["product_id"])
            least_candidates.append(r)

    if len(top_candidates) >= 3:
        for r in sorted(top_candidates, key=lambda x: (x["_units"], x["_rev"])):
            if r["product_id"] in seen_least or r["product_id"] == top_leader_id:
                continue
            seen_least.add(r["product_id"])
            least_candidates.append(r)
            if len(least_candidates) >= 6:
                break

    least_candidates.sort(
        key=lambda r: (r["_units"], -r["_shrink"], -r["_stock_val"]),
    )

    least_selling: list[dict[str, Any]] = []
    for r in least_candidates:
        if r["_profit"] < 0 or r["_has_below"] or (r["_units"] > 0 and r["_margin"] < 10):
            diag, sev = "Margen negativo/bajo", "danger"
        elif r["_shrink"] > 0:
            diag, sev = "Pérdida por merma", "danger"
        elif r["_units"] == 0:
            diag, sev = "Estancado: 0 ventas", "warning"
        else:
            diag, sev = "Rotación crítica", "warning"

        clean_row = {k: v for k, v in r.items() if not k.startswith("_")}
        clean_row["diagnosis"] = diag
        clean_row["diagnosis_severity"] = sev
        least_selling.append(clean_row)

    series = _build_period_series(
        period_sales=list(period_sales.values()),
        shrinkage_movements=shrinkage_movements,
        products_by_id=products_by_id,
        period_days=period_days,
        ref_now=ref_now,
    )

    return {
        "period_days": period_days,
        "pnl": {
            "gross_sales_without_vat": str(gross_sales_without_vat),
            "discount_total": str(discount_total),
            "net_revenue": str(net_revenue),
            "cogs_total": str(cogs_total),
            "gross_profit": str(gross_profit),
            "gross_margin_pct": str(gross_margin_pct),
            "shrinkage_loss_cop": str(shrinkage_loss_cop),
            "shrinkage_movements_count": shrinkage_movements_count,
            "below_cost_loss_cop": str(below_cost_loss_cop),
            "below_cost_items_count": below_cost_items_count,
            "total_losses_cop": str(total_losses_cop),
            "net_profit_after_losses_cop": str(net_profit_after_losses),
            "net_margin_after_losses_pct": str(net_margin_after_losses_pct),
            "immobilized_capital_30d_cop": str(_q2(immobilized_capital_30d)),
        },
        "top_selling_products": top_selling,
        "least_selling_and_loss_products": least_selling,
        "series": series,
    }


def _build_period_series(
    period_sales: list[dict[str, Any]],
    shrinkage_movements: list[dict[str, Any]],
    products_by_id: dict[str, dict[str, Any]],
    period_days: int,
    ref_now: datetime,
) -> dict[str, list[Any]]:
    """Agrupa ingresos, ganancia neta real y costos/pérdidas en cubetas reales del periodo."""
    today = ref_now.date()
    buckets: list[tuple[str, datetime, datetime]] = []

    if period_days <= 7:
        for d_off in range(6, -1, -1):
            day = today - timedelta(days=d_off)
            start = datetime(day.year, day.month, day.day, tzinfo=UTC)
            end = start + timedelta(days=1)
            buckets.append((f"{day.day:02d} {_MONTH_NAMES_ES[day.month - 1]}", start, end))
    elif period_days <= 31:
        n_buckets = 4
        start_day = today - timedelta(days=period_days - 1)
        span_days = period_days
        for i in range(n_buckets):
            off_start = (i * span_days) // n_buckets
            off_end = ((i + 1) * span_days) // n_buckets
            b_start_d = start_day + timedelta(days=off_start)
            b_end_d = (
                today + timedelta(days=1) if i == n_buckets - 1 else start_day + timedelta(days=off_end)
            )
            start = datetime(b_start_d.year, b_start_d.month, b_start_d.day, tzinfo=UTC)
            end = datetime(b_end_d.year, b_end_d.month, b_end_d.day, tzinfo=UTC)
            buckets.append((f"{b_start_d.day:02d} {_MONTH_NAMES_ES[b_start_d.month - 1]}", start, end))
    elif period_days <= 95:
        n_buckets = 6
        step = max(1, period_days // n_buckets)
        start_day = today - timedelta(days=period_days - 1)
        for i in range(n_buckets):
            b_start_d = start_day + timedelta(days=i * step)
            b_end_d = (
                today + timedelta(days=1) if i == n_buckets - 1 else b_start_d + timedelta(days=step)
            )
            start = datetime(b_start_d.year, b_start_d.month, b_start_d.day, tzinfo=UTC)
            end = datetime(b_end_d.year, b_end_d.month, b_end_d.day, tzinfo=UTC)
            label = f"{b_start_d.day:02d} {_MONTH_NAMES_ES[b_start_d.month - 1]}"
            buckets.append((label, start, end))
    else:
        yr, mo = today.year, today.month
        months_list: list[tuple[int, int]] = []
        for _ in range(12):
            months_list.append((yr, mo))
            mo -= 1
            if mo == 0:
                mo = 12
                yr -= 1
        months_list.reverse()
        for y, m in months_list:
            start = datetime(y, m, 1, tzinfo=UTC)
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            end = datetime(ny, nm, 1, tzinfo=UTC)
            buckets.append((f"{_MONTH_NAMES_ES[m - 1]} {str(y)[2:]}", start, end))

    labels = [b[0] for b in buckets]
    revs = [Decimal("0.00")] * len(buckets)
    cogs = [Decimal("0.00")] * len(buckets)
    shrinks = [Decimal("0.00")] * len(buckets)

    for s in period_sales:
        occ = s["_occurred"]
        for idx, (_, b_start, b_end) in enumerate(buckets):
            if b_start <= occ < b_end:
                sub = _q2(Decimal(str(s.get("subtotal", "0"))))
                disc = _q2(Decimal(str(s.get("discount_total", "0"))))
                revs[idx] += _q2(sub - disc)
                cogs[idx] += _q2(Decimal(str(s.get("cogs_total", "0"))))
                break

    for mov in shrinkage_movements:
        if str(mov.get("movement_type")) != "adjustment_out":
            continue
        occ = _as_aware_utc(mov.get("occurred_at")) or ref_now
        pid = str(mov["product_id"])
        qty_abs = abs(_q3(Decimal(str(mov.get("quantity", "0")))))
        uc = (
            _q2(Decimal(str(mov["unit_cost"])))
            if mov.get("unit_cost") is not None
            else _q2(Decimal(str(products_by_id.get(pid, {}).get("cost_price", "0"))))
        )
        loss = _q2(qty_abs * uc)
        for idx, (_, b_start, b_end) in enumerate(buckets):
            if b_start <= occ < b_end:
                shrinks[idx] += loss
                break

    return {
        "labels": labels,
        "revenue": [float(_q2(v)) for v in revs],
        "net_profit": [float(_q2(r - c - sh)) for r, c, sh in zip(revs, cogs, shrinks, strict=True)],
        "losses_and_costs": [float(_q2(c + sh)) for c, sh in zip(cogs, shrinks, strict=True)],
    }


def get_tenant_profitability_payload(
    db: Session,
    tenant_id: str,
    period_days: int = 30,
) -> dict[str, Any]:
    """Obtiene el informe completo de rentabilidad, pérdidas y rankings para un comercio."""
    products = db.query(Product).filter_by(tenant_id=tenant_id, is_active=True).all()
    sales = db.query(Sale).filter_by(tenant_id=tenant_id).all()
    sale_items = db.query(SaleItem).filter(SaleItem.tenant_id == tenant_id).all()
    shrink_movs = (
        db.query(InventoryMovement).filter_by(tenant_id=tenant_id, movement_type="adjustment_out").all()
    )

    prod_dicts = [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "unit": p.unit,
            "cost_price": p.cost_price,
            "stock_qty": p.stock_qty,
            "image_url": p.image_url,
        }
        for p in products
    ]
    sale_dicts = [
        {
            "id": s.id,
            "status": s.status,
            "occurred_at": s.occurred_at,
            "subtotal": s.subtotal,
            "discount_total": s.discount_total,
            "cogs_total": s.cogs_total,
        }
        for s in sales
    ]
    item_dicts = [
        {
            "sale_id": it.sale_id,
            "product_id": it.product_id,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "discount": it.discount,
            "unit_cost_snapshot": it.unit_cost_snapshot,
        }
        for it in sale_items
    ]
    mov_dicts = [
        {
            "product_id": m.product_id,
            "movement_type": m.movement_type,
            "quantity": m.quantity,
            "unit_cost": m.unit_cost,
            "occurred_at": m.occurred_at,
        }
        for m in shrink_movs
    ]

    result = compute_pure_profitability(
        products=prod_dicts,
        sales=sale_dicts,
        sale_items=item_dicts,
        shrinkage_movements=mov_dicts,
        period_days=period_days,
    )
    result["tenant_id"] = tenant_id
    return result
