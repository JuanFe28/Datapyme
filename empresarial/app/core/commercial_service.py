"""
Servicios de Dominio Comercial (Actividad 3.3 F-DC-124):
- Catálogo de Productos, Kardex Inmutable y Alertas de Stock
- Registro Atómico de Ventas y Anulación con Reversa
- Importador Masivo CSV / Excel (.xlsx) con Sanitización OWASP y soporte es-CO
"""
import csv
import io
import zipfile
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.models import (
    ImportJob,
    InventoryMovement,
    Product,
    Sale,
    SaleItem,
    UsageEvent,
    utcnow,
)
from app.core.security import sha256_hex

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
ALLOWED_UPLOAD_EXTS = (".csv", ".xlsx")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 20000


def sanitize_cell_text(value: Any, max_len: int = 180) -> str:
    """Neutraliza ataques de CSV/Excel Formula Injection eliminando prefijos ejecutables."""
    raw = str(value or "").strip()
    while raw and raw[0] in FORMULA_PREFIXES:
        raw = raw[1:].strip()
    return raw[:max_len]


def parse_colombian_decimal(value: Any, places: Decimal = TWO_PLACES) -> Decimal:
    """
    Convierte cadenas numéricas en formato estándar o colombiano ("28.500,50" o "28500.50")
    a Decimal exacto.
    """
    if isinstance(value, (int, Decimal)):
        return Decimal(str(value)).quantize(places, rounding=ROUND_HALF_UP)
    if isinstance(value, float):
        return Decimal(str(value)).quantize(places, rounding=ROUND_HALF_UP)
    s = str(value or "").strip().replace("$", "").replace("COP", "").strip()
    if not s:
        raise ValueError("Valor numérico vacío.")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Formato es-CO: 28.500,50
            s = s.replace(".", "").replace(",", ".")
        else:
            # Formato anglosajón: 28,500.50
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s).quantize(places, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Formato numérico inválido: {value}") from exc


def parse_tabular_upload(filename: str, content: bytes) -> list[dict[str, str]]:
    """Lee y valida un archivo CSV o XLSX verificando límites, extensión y bombas ZIP."""
    if not filename:
        raise HTTPException(status_code=422, detail="Nombre de archivo requerido.")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(
            status_code=422,
            detail=f"Extensión '{ext}' no permitida. Solo se aceptan archivos .csv y .xlsx sin macros.",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 5 MiB.")

    rows: list[dict[str, str]] = []
    if ext == ".csv":
        try:
            text_data = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text_data = content.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text_data))
        for row in reader:
            norm = {(k or "").strip().lower(): str(v or "").strip() for k, v in row.items()}
            if any(norm.values()):
                rows.append(norm)
            if len(rows) > MAX_UPLOAD_ROWS:
                raise HTTPException(status_code=422, detail="El archivo supera las 20.000 filas.")
    else:
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(status_code=422, detail="El archivo .xlsx no tiene una firma ZIP válida.")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 25 * 1024 * 1024:
                    raise HTTPException(status_code=422, detail="Archivo XLSX excede límite descomprimido.")
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=422, detail="Archivo XLSX corrupto.") from exc

        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        iterator = ws.iter_rows(values_only=True)
        try:
            header_row = next(iterator)
        except StopIteration:
            return []
        headers = [str(h or "").strip().lower() for h in header_row]
        for raw_row in iterator:
            row_dict = {
                headers[idx]: "" if val is None else str(val).strip()
                for idx, val in enumerate(raw_row)
                if idx < len(headers) and headers[idx]
            }
            if any(row_dict.values()):
                rows.append(row_dict)
            if len(rows) > MAX_UPLOAD_ROWS:
                raise HTTPException(status_code=422, detail="El archivo supera las 20.000 filas.")
        wb.close()
    return rows


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
    user_id: str | None,
    sku: str,
    name: str,
    category: str,
    unit: str,
    cost_price: Decimal,
    sale_price: Decimal,
    vat_rate: Decimal,
    initial_stock: Decimal,
    min_stock: Decimal,
    image_url: str | None = None,
    import_job_id: str | None = None,
) -> Product:
    if cost_price < 0 or sale_price < 0 or initial_stock < 0 or min_stock < 0:
        raise ValueError("Los precios y cantidades de stock no pueden ser negativos.")
    clean_sku = sanitize_cell_text(sku, 64).upper()
    clean_name = sanitize_cell_text(name, 180)
    clean_cat = sanitize_cell_text(category or "General", 90)
    if not clean_sku or not clean_name:
        raise ValueError("El SKU y el nombre del producto son obligatorios.")

    existing = db.query(Product).filter_by(tenant_id=tenant_id, sku=clean_sku).first()
    if existing:
        raise ValueError(f"El SKU '{clean_sku}' ya existe en el catálogo de la empresa.")

    prod = Product(
        tenant_id=tenant_id,
        sku=clean_sku,
        name=clean_name,
        category=clean_cat,
        unit=sanitize_cell_text(unit or "und", 20) or "und",
        cost_price=cost_price.quantize(TWO_PLACES),
        sale_price=sale_price.quantize(TWO_PLACES),
        vat_rate=vat_rate.quantize(TWO_PLACES),
        stock_qty=initial_stock.quantize(THREE_PLACES),
        min_stock=min_stock.quantize(THREE_PLACES),
        image_url=image_url.strip() if image_url and image_url.strip() else None,
    )
    db.add(prod)
    db.flush()

    if initial_stock > Decimal("0.000"):
        mov = InventoryMovement(
            tenant_id=tenant_id,
            product_id=prod.id,
            movement_type="initial_load",
            quantity=initial_stock.quantize(THREE_PLACES),
            unit_cost=cost_price.quantize(TWO_PLACES),
            reason="Inventario inicial al crear producto",
            import_job_id=import_job_id,
            created_by=user_id,
        )
        db.add(mov)

    if Decimal(str(prod.stock_qty)) <= Decimal(str(prod.min_stock)):
        db.add(UsageEvent(tenant_id=tenant_id, event_type="stock_alert_raised"))

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

    # Normalizar signo según el tipo de movimiento
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
    if unit_cost is not None and unit_cost >= Decimal(0) and signed_qty > Decimal(0):
        prod.cost_price = unit_cost.quantize(TWO_PLACES)
    prod.updated_at = utcnow()

    mov = InventoryMovement(
        tenant_id=tenant_id,
        product_id=prod.id,
        movement_type=movement_type,
        quantity=signed_qty,
        unit_cost=unit_cost.quantize(TWO_PLACES) if unit_cost is not None else prod.cost_price,
        reason=sanitize_cell_text(reason, 200) or "Movimiento operativo",
        created_by=user_id,
    )
    db.add(mov)
    db.flush()
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
    """
    Registra una venta y descuenta el inventario de forma 100 % atómica.
    Si cualquier ítem no pertenece al tenant (404) o no tiene stock suficiente (409),
    toda la transacción hace rollback sin alterar ningún producto.
    """
    if not items_input:
        raise HTTPException(status_code=422, detail="La venta debe incluir al menos un ítem.")

    # Primera pasada de validación completa antes de mutar stock
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
        payment_method=payment_method if payment_method in ("cash", "card", "transfer", "credit", "other") else "cash",
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
        gross_line = (qty * unit_price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        line_total = (gross_line - discount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if line_total < Decimal("0.00"):
            raise HTTPException(status_code=422, detail="El descuento no puede superar el valor de la línea.")
        vat_rate = Decimal(str(prod.vat_rate)).quantize(TWO_PLACES)
        line_vat = (line_total * (vat_rate / Decimal(100))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        unit_cost = Decimal(str(prod.cost_price)).quantize(TWO_PLACES)
        line_cogs = (qty * unit_cost).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        subtotal_acc += gross_line
        discount_acc += discount
        vat_acc += line_vat
        cogs_acc += line_cogs

        sale_item = SaleItem(
            tenant_id=tenant_id,
            sale_id=sale.id,
            product_id=prod.id,
            quantity=qty,
            unit_price=unit_price,
            unit_cost_snapshot=unit_cost,
            vat_rate=vat_rate,
            discount=discount,
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
    db.flush()
    return sale


def classify_inventory_alerts(db: Session, tenant_id: str) -> dict[str, list[dict[str, Any]]]:
    products = db.query(Product).filter_by(tenant_id=tenant_id, is_active=True).order_by(Product.sku.asc()).all()
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


def import_products_batch(
    db: Session,
    tenant_id: str,
    user_id: str,
    filename: str,
    content: bytes,
    mode: str = "preview",
    mapping: dict[str, str] | None = None,
    sheet_name: str | None = None,
    header_row_index: int = 1,
) -> dict[str, Any]:
    valid_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if mapping:
        from app.imports.smart_excel_mapper import parse_mapped_workbook_products
        parsed = parse_mapped_workbook_products(
            filename=filename,
            content=content,
            mapping=mapping,
            sheet_name=sheet_name,
            header_row_index=header_row_index,
        )
        raw_rows: list[dict[str, Any]] = list(parsed)
        for item in parsed:
            valid_rows.append(
                {
                    "sku": item["sku"],
                    "name": item["name"],
                    "category": item["category"],
                    "unit": item["unit"],
                    "cost_price": item["cost_price"],
                    "sale_price": item["sale_price"],
                    "vat_rate": item["vat_rate"],
                    "initial_stock": item["initial_stock"],
                    "min_stock": item["min_stock"],
                }
            )
    else:
        raw_rows = parse_tabular_upload(filename, content)
        for idx, r in enumerate(raw_rows, start=2):
            try:
                sku = sanitize_cell_text(r.get("sku", ""), 64).upper()
                name = sanitize_cell_text(r.get("name", "") or r.get("nombre", ""), 180)
                category = sanitize_cell_text(r.get("category", "") or r.get("categoria", "General"), 90) or "General"
                unit = sanitize_cell_text(r.get("unit", "") or r.get("unidad", "und"), 20) or "und"
                cost_price = parse_colombian_decimal(r.get("cost_price") or r.get("costo", "0"), TWO_PLACES)
                sale_price = parse_colombian_decimal(r.get("sale_price") or r.get("precio", "0"), TWO_PLACES)
                vat_rate = parse_colombian_decimal(r.get("vat_rate") or r.get("iva", "19"), TWO_PLACES)
                initial_stock = parse_colombian_decimal(r.get("initial_stock") or r.get("stock", "0"), THREE_PLACES)
                min_stock = parse_colombian_decimal(r.get("min_stock") or r.get("stock_minimo", "0"), THREE_PLACES)

                if not sku or not name:
                    raise ValueError("SKU y nombre son obligatorios.")
                if cost_price < 0 or sale_price < 0 or initial_stock < 0 or min_stock < 0:
                    raise ValueError("No se permiten precios ni existencias negativas.")

                valid_rows.append(
                    {
                        "sku": sku,
                        "name": name,
                        "category": category,
                        "unit": unit,
                        "cost_price": cost_price,
                        "sale_price": sale_price,
                        "vat_rate": vat_rate,
                        "initial_stock": initial_stock,
                        "min_stock": min_stock,
                    }
                )
            except (ValueError, KeyError, TypeError, HTTPException) as exc:
                errors.append({"row": idx, "message": str(exc)})

    job = ImportJob(
        tenant_id=tenant_id,
        kind="products",
        filename_safe=sanitize_cell_text(Path(filename).name, 180),
        sha256=sha256_hex(content.hex()),
        status="committed" if mode == "commit" else "preview",
        rows_total=len(raw_rows),
        rows_ok=len(valid_rows),
        rows_rejected=len(errors),
        errors=errors,
        created_by=user_id,
    )
    db.add(job)
    db.flush()

    if mode == "commit":
        for item in valid_rows:
            create_product_with_initial_stock(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                import_job_id=job.id,
                **item,
            )
        db.add(UsageEvent(tenant_id=tenant_id, event_type="import_completed"))
        db.commit()
    else:
        db.commit()

    return {
        "job_id": job.id,
        "mode": mode,
        "rows_total": len(raw_rows),
        "rows_ok": len(valid_rows),
        "rows_rejected": len(errors),
        "errors": errors,
    }


def import_sales_batch(
    db: Session,
    tenant_id: str,
    user_id: str,
    filename: str,
    content: bytes,
    mode: str = "preview",
) -> dict[str, Any]:
    raw_rows = parse_tabular_upload(filename, content)
    valid_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, r in enumerate(raw_rows, start=2):
        try:
            sku = sanitize_cell_text(r.get("sku", ""), 64).upper()
            prod = db.query(Product).filter_by(tenant_id=tenant_id, sku=sku).first()
            if not prod:
                raise ValueError(f"SKU '{sku}' no existe en el catálogo de la empresa.")
            qty = parse_colombian_decimal(r.get("quantity") or r.get("cantidad", "0"), THREE_PLACES)
            unit_price = (
                parse_colombian_decimal(r["unit_price"], TWO_PLACES)
                if r.get("unit_price")
                else Decimal(str(prod.sale_price)).quantize(TWO_PLACES)
            )
            discount = parse_colombian_decimal(r.get("discount") or r.get("descuento", "0"), TWO_PLACES)
            payment_method = sanitize_cell_text(r.get("payment_method", "cash"), 20).lower() or "cash"
            customer_label = sanitize_cell_text(r.get("customer_label", "Cliente Importado"), 80)

            if qty <= 0 or unit_price < 0 or discount < 0:
                raise ValueError("Cantidades o importes inválidos en fila de venta.")

            valid_rows.append(
                {
                    "product_id": prod.id,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "discount": discount,
                    "payment_method": payment_method,
                    "customer_label": customer_label,
                }
            )
        except (ValueError, KeyError, TypeError, HTTPException) as exc:
            errors.append({"row": idx, "message": str(exc)})

    job = ImportJob(
        tenant_id=tenant_id,
        kind="sales",
        filename_safe=sanitize_cell_text(Path(filename).name, 180),
        sha256=sha256_hex(content.hex()),
        status="committed" if mode == "commit" else "preview",
        rows_total=len(raw_rows),
        rows_ok=len(valid_rows),
        rows_rejected=len(errors),
        errors=errors,
        created_by=user_id,
    )
    db.add(job)
    db.flush()

    if mode == "commit":
        for row in valid_rows:
            create_sale_atomic(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                customer_label=row["customer_label"],
                payment_method=row["payment_method"],
                items_input=[
                    {
                        "product_id": row["product_id"],
                        "quantity": row["quantity"],
                        "unit_price": row["unit_price"],
                        "discount": row["discount"],
                    }
                ],
                source="import",
                import_job_id=job.id,
            )
        db.add(UsageEvent(tenant_id=tenant_id, event_type="import_completed"))
        db.commit()
    else:
        db.commit()

    return {
        "job_id": job.id,
        "mode": mode,
        "rows_total": len(raw_rows),
        "rows_ok": len(valid_rows),
        "rows_rejected": len(errors),
        "errors": errors,
    }
