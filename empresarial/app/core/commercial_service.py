"""
Servicios de Dominio Comercial (Actividad 3.3 F-DC-124):
- Catálogo de Productos, Kardex Inmutable y Alertas de Stock
- Registro Atómico de Ventas y Anulación con Reversa
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.models import (
    InventoryMovement,
    Product,
    Sale,
    SaleItem,
    UsageEvent,
    utcnow,
)

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
ALLOWED_UPLOAD_EXTS = {".csv", ".xlsx"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 20_000


def sanitize_cell_text(value: Any, max_len: int = 180) -> str:
    """Neutraliza ataques de CSV/Excel Formula Injection eliminando prefijos ejecutables."""
    raw = str(value or "").strip()
    while raw and raw.startswith(FORMULA_PREFIXES):
        raw = raw[1:].strip()
    clean = "".join(ch for ch in raw if ch.isprintable() or ch in ("\n", " "))
    return clean[:max_len].strip()


def parse_colombian_decimal(value: Any, places: Decimal = TWO_PLACES) -> Decimal:
    """Normaliza formatos numéricos colombianos ($ 1.250.000,50 o 1250000.50)."""
    if value is None:
        return Decimal(0).quantize(places)
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(places, rounding=ROUND_HALF_UP)
    s = str(value).strip().replace("$", "").replace("COP", "").replace(" ", "")
    if not s:
        return Decimal(0).quantize(places)
    s = "".join(ch for ch in s if ch.isdigit() or ch in (",", ".", "-"))
    if not s or s == "-":
        return Decimal(0).quantize(places)
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s).quantize(places, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Formato numérico inválido: {value}") from exc


def serialize_product(p: Product) -> dict[str, Any]:
    stock = Decimal(str(p.stock_qty)).quantize(THREE_PLACES)
    min_s = Decimal(str(p.min_stock)).quantize(THREE_PLACES)
    if stock == Decimal("0.000"):
        status_label = "out_of_stock"
    elif stock <= min_s:
        status_label = "stockout_risk"
    elif min_s > Decimal("0.000") and stock >= (min_s * Decimal(3)):
        status_label = "overstock"
    else:
        status_label = "optimal"

    return {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "sku": p.sku,
        "name": p.name,
        "category": p.category,
        "unit": p.unit,
        "cost_price": str(Decimal(str(p.cost_price)).quantize(TWO_PLACES)),
        "sale_price": str(Decimal(str(p.sale_price)).quantize(TWO_PLACES)),
        "vat_rate": str(Decimal(str(p.vat_rate)).quantize(TWO_PLACES)),
        "stock_qty": str(stock),
        "min_stock": str(min_s),
        "image_url": p.image_url,
        "stock_status": status_label,
        "is_active": p.is_active,
    }


def create_product_with_initial_stock(
    db: Session,
    tenant_id: str,
    user_id: str,
    sku: str,
    name: str,
    category: str,
    unit: str,
    cost_price: Decimal,
    sale_price: Decimal,
    vat_rate: Decimal,
    initial_stock: Decimal,
    min_stock: Decimal,
    import_job_id: str | None = None,
    image_url: str | None = None,
) -> Product:
    clean_sku = sanitize_cell_text(sku, 64).upper()
    clean_name = sanitize_cell_text(name, 180)
    clean_cat = sanitize_cell_text(category, 90) or "General"
    clean_unit = sanitize_cell_text(unit, 20) or "und"

    if not clean_sku or not clean_name:
        raise ValueError("SKU y Nombre de producto son obligatorios.")

    existing = db.query(Product).filter_by(tenant_id=tenant_id, sku=clean_sku).first()
    if existing:
        raise ValueError(f"El SKU '{clean_sku}' ya está registrado en este comercio.")

    prod = Product(
        tenant_id=tenant_id,
        sku=clean_sku,
        name=clean_name,
        category=clean_cat,
        unit=clean_unit,
        cost_price=cost_price,
        sale_price=sale_price,
        vat_rate=vat_rate,
        stock_qty=Decimal("0.000"),
        min_stock=min_stock,
        image_url=image_url.strip() if image_url and image_url.strip() else None,
        is_active=True,
    )
    db.add(prod)
    db.flush()

    if initial_stock > Decimal("0.000"):
        prod.stock_qty = initial_stock
        mov = InventoryMovement(
            tenant_id=tenant_id,
            product_id=prod.id,
            movement_type="initial_load",
            quantity=initial_stock,
            unit_cost=cost_price,
            reason="Carga inicial de inventario",
            import_job_id=import_job_id,
            created_by=user_id,
        )
        db.add(mov)

    db.add(UsageEvent(tenant_id=tenant_id, event_type="product_created"))
    return prod


def record_inventory_movement(
    db: Session,
    tenant_id: str,
    user_id: str,
    product_id: str,
    movement_type: str,
    quantity: Decimal,
    reason: str,
    unit_cost: Decimal | None = None,
) -> tuple[Product, InventoryMovement]:
    prod = db.query(Product).filter_by(tenant_id=tenant_id, id=product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    if quantity == Decimal(0):
        raise HTTPException(status_code=422, detail="La cantidad del movimiento no puede ser cero.")

    if movement_type in ("purchase_in", "return_in", "adjustment_in", "initial_load"):
        signed_qty = abs(quantity).quantize(THREE_PLACES)
    elif movement_type in ("sale_out", "adjustment_out"):
        signed_qty = -abs(quantity).quantize(THREE_PLACES)
    else:
        raise HTTPException(status_code=422, detail="Tipo de movimiento de inventario inválido.")

    old_stock = Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)
    min_s = Decimal(str(prod.min_stock)).quantize(THREE_PLACES)
    new_stock = (old_stock + signed_qty).quantize(THREE_PLACES)
    if new_stock < Decimal("0.000"):
        raise HTTPException(
            status_code=409,
            detail=f"Stock insuficiente para '{prod.sku}': actual {old_stock}, solicitado {signed_qty}.",
        )

    was_at_risk = old_stock <= min_s
    now_at_risk = new_stock <= min_s
    if not was_at_risk and now_at_risk:
        db.add(UsageEvent(tenant_id=tenant_id, event_type="stock_alert_raised"))
    elif was_at_risk and not now_at_risk:
        db.add(UsageEvent(tenant_id=tenant_id, event_type="stock_alert_resolved"))

    prod.stock_qty = new_stock
    if unit_cost is not None and unit_cost > 0 and movement_type == "purchase_in":
        prod.cost_price = unit_cost

    mov = InventoryMovement(
        tenant_id=tenant_id,
        product_id=prod.id,
        movement_type=movement_type,
        quantity=signed_qty,
        unit_cost=unit_cost if unit_cost is not None else prod.cost_price,
        reason=sanitize_cell_text(reason, 180),
        created_by=user_id,
    )
    db.add(mov)
    return prod, mov


def create_sale_atomic(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    customer_label: str | None,
    payment_method: str,
    items_input: list[dict[str, Any]],
    source: str = "manual",
    import_job_id: str | None = None,
) -> Sale:
    if not items_input:
        raise HTTPException(status_code=422, detail="La venta debe incluir al menos un ítem.")

    resolved_items: list[tuple[Product, Decimal, Decimal, Decimal]] = []
    for item in items_input:
        prod = db.query(Product).filter_by(tenant_id=tenant_id, id=item["product_id"]).first()
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado en el catálogo.")
        qty = parse_colombian_decimal(item["quantity"], THREE_PLACES)
        if qty <= Decimal(0):
            raise HTTPException(status_code=422, detail="La cantidad de venta debe ser mayor a cero.")
        current_stock = Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)
        if current_stock < qty:
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente para SKU '{prod.sku}': disponible {current_stock}, solicitado {qty}.",
            )
        unit_price = (
            parse_colombian_decimal(item["unit_price"], TWO_PLACES)
            if item.get("unit_price") is not None
            else Decimal(str(prod.sale_price)).quantize(TWO_PLACES)
        )
        discount = parse_colombian_decimal(item.get("discount", "0"), TWO_PLACES)
        resolved_items.append((prod, qty, unit_price, discount))

    max_num = db.query(func.max(Sale.sale_number)).filter_by(tenant_id=tenant_id).scalar() or 0
    next_number = int(max_num) + 1

    subtotal_acc = Decimal("0.00")
    discount_acc = Decimal("0.00")
    vat_acc = Decimal("0.00")
    cogs_acc = Decimal("0.00")

    sale = Sale(
        tenant_id=tenant_id,
        sale_number=next_number,
        customer_label=sanitize_cell_text(customer_label or "Cliente Mostrador", 80),
        payment_method=payment_method
        if payment_method in ("cash", "card", "transfer", "credit", "other")
        else "cash",
        subtotal=Decimal("0.00"),
        discount_total=Decimal("0.00"),
        vat_total=Decimal("0.00"),
        total=Decimal("0.00"),
        cogs_total=Decimal("0.00"),
        status="completed",
        source=source,
        import_job_id=import_job_id,
        created_by=user_id,
    )
    db.add(sale)
    db.flush()

    for prod, qty, unit_price, discount in resolved_items:
        vat_r = Decimal(str(prod.vat_rate)).quantize(TWO_PLACES)
        line_subtotal = (qty * unit_price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        line_discount = min(discount, line_subtotal)
        taxable_base = line_subtotal - line_discount
        line_vat = (taxable_base * (vat_r / Decimal(100))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        line_total = taxable_base + line_vat
        unit_cost = Decimal(str(prod.cost_price)).quantize(TWO_PLACES)
        line_cogs = (qty * unit_cost).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        subtotal_acc += line_subtotal
        discount_acc += line_discount
        vat_acc += line_vat
        cogs_acc += line_cogs

        sale_item = SaleItem(
            tenant_id=tenant_id,
            sale_id=sale.id,
            product_id=prod.id,
            quantity=qty,
            unit_price=unit_price,
            unit_cost_snapshot=unit_cost,
            vat_rate=vat_r,
            discount=line_discount,
            line_total=line_total,
        )
        db.add(sale_item)

        old_stock = Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)
        new_stock = (old_stock - qty).quantize(THREE_PLACES)
        min_s = Decimal(str(prod.min_stock)).quantize(THREE_PLACES)
        if old_stock > min_s and new_stock <= min_s:
            db.add(UsageEvent(tenant_id=tenant_id, event_type="stock_alert_raised"))

        prod.stock_qty = new_stock
        prod.updated_at = utcnow()

        mov = InventoryMovement(
            tenant_id=tenant_id,
            product_id=prod.id,
            movement_type="sale_out",
            quantity=-qty,
            unit_cost=unit_cost,
            reason=f"Venta N° {next_number}",
            sale_id=sale.id,
            import_job_id=import_job_id,
            created_by=user_id,
        )
        db.add(mov)

    net_after_discount = (subtotal_acc - discount_acc).quantize(TWO_PLACES)
    sale.subtotal = subtotal_acc.quantize(TWO_PLACES)
    sale.discount_total = discount_acc.quantize(TWO_PLACES)
    sale.vat_total = vat_acc.quantize(TWO_PLACES)
    sale.total = (net_after_discount + vat_acc).quantize(TWO_PLACES)
    sale.cogs_total = cogs_acc.quantize(TWO_PLACES)
    db.flush()
    return sale


def void_sale_atomic(db: Session, tenant_id: str, user_id: str, sale_id: str) -> Sale:
    """Anula una venta e inserta movimientos compensatorios return_in en el Kardex."""
    sale = db.query(Sale).filter_by(tenant_id=tenant_id, id=sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    if sale.status == "voided":
        raise HTTPException(status_code=409, detail="La venta ya fue anulada previamente.")

    for item in sale.items:
        prod = db.query(Product).filter_by(tenant_id=tenant_id, id=item.product_id).first()
        if prod:
            qty = Decimal(str(item.quantity)).quantize(THREE_PLACES)
            old_stock = Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)
            new_stock = (old_stock + qty).quantize(THREE_PLACES)
            min_s = Decimal(str(prod.min_stock)).quantize(THREE_PLACES)
            if old_stock <= min_s and new_stock > min_s:
                db.add(UsageEvent(tenant_id=tenant_id, event_type="stock_alert_resolved"))
            prod.stock_qty = new_stock
            prod.updated_at = utcnow()

            rev = InventoryMovement(
                tenant_id=tenant_id,
                product_id=prod.id,
                movement_type="return_in",
                quantity=qty,
                unit_cost=Decimal(str(item.unit_cost_snapshot)).quantize(TWO_PLACES),
                reason=f"Reversa por anulación de Venta N° {sale.sale_number}",
                sale_id=sale.id,
                created_by=user_id,
            )
            db.add(rev)

    sale.status = "voided"
    db.add(UsageEvent(tenant_id=tenant_id, event_type="sale_voided"))
    db.flush()
    return sale


def classify_inventory_alerts(db: Session, tenant_id: str) -> dict[str, list[dict[str, Any]]]:
    products = (
        db.query(Product)
        .filter_by(tenant_id=tenant_id, is_active=True)
        .order_by(Product.sku.asc())
        .all()
    )
    out_of_stock: list[dict[str, Any]] = []
    stockout_risk: list[dict[str, Any]] = []
    overstock: list[dict[str, Any]] = []

    for prod in products:
        serialized = serialize_product(prod)
        st = serialized["stock_status"]
        if st == "out_of_stock":
            out_of_stock.append(serialized)
        elif st == "stockout_risk":
            stockout_risk.append(serialized)
        elif st == "overstock":
            overstock.append(serialized)

    return {
        "out_of_stock": out_of_stock,
        "stockout_risk": stockout_risk,
        "overstock": overstock,
    }


def parse_tabular_upload(*args, **kwargs):
    from app.imports.batch_importer import parse_tabular_upload as _fn

    return _fn(*args, **kwargs)


def import_products_batch(*args, **kwargs):
    from app.imports.batch_importer import import_products_batch as _fn

    return _fn(*args, **kwargs)


def import_sales_batch(*args, **kwargs):
    from app.imports.batch_importer import import_sales_batch as _fn

    return _fn(*args, **kwargs)


__all__ = [
    "ALLOWED_UPLOAD_EXTS",
    "MAX_UPLOAD_BYTES",
    "MAX_UPLOAD_ROWS",
    "THREE_PLACES",
    "TWO_PLACES",
    "classify_inventory_alerts",
    "create_product_with_initial_stock",
    "create_sale_atomic",
    "import_products_batch",
    "import_sales_batch",
    "parse_colombian_decimal",
    "parse_tabular_upload",
    "record_inventory_movement",
    "sanitize_cell_text",
    "serialize_product",
    "void_sale_atomic",
]
