"""Históricos con fecha/costo/IVA de origen; no alteran el inventario actual."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.commercial_service import (
    THREE_PLACES,
    TWO_PLACES,
    parse_colombian_decimal,
    sanitize_cell_text,
)
from app.core.models import (
    HistoricalSaleReference,
    ImportJob,
    Product,
    Sale,
    SaleItem,
    SaleTaxSnapshot,
    Tenant,
    utcnow,
)
from app.core.security import sha256_hex
from app.imports.batch_importer import parse_tabular_upload


def import_historical_sales(
    db: Session, tenant_id: str, user_id: str, filename: str, content: bytes, mode: str
):
    rows = parse_tabular_upload(filename, content)
    if not rows:
        raise HTTPException(422, "El archivo histórico está vacío.")
    db.query(Tenant).filter_by(id=tenant_id).with_for_update().one()
    groups = {}
    for idx, row in enumerate(rows, 2):
        try:
            required = (
                "sale_number",
                "occurred_at",
                "sku",
                "quantity",
                "unit_price",
                "unit_cost",
                "vat_rate",
            )
            if any(not row.get(key) for key in required):
                raise ValueError(
                    "Se requieren referencia, fecha, SKU, cantidad, precio base, costo histórico e IVA efectivo de origen."
                )
            ref = sanitize_cell_text(row["sale_number"], 128)
            if not ref:
                raise ValueError("La referencia de origen no puede estar vacía.")
            occurred = datetime.fromisoformat(row["occurred_at"])
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=timezone(timedelta(hours=-5)))
            occurred = occurred.astimezone(UTC)
            if occurred > utcnow():
                raise ValueError("La fecha histórica no puede ser futura.")
            product = (
                db.query(Product)
                .filter_by(tenant_id=tenant_id, sku=row["sku"].strip().upper(), is_training_data=False)
                .first()
            )
            if not product:
                raise ValueError("SKU no encontrado en el catálogo real de esta empresa.")
            qty = parse_colombian_decimal(row["quantity"], THREE_PLACES)
            price = parse_colombian_decimal(row["unit_price"])
            cost = parse_colombian_decimal(row["unit_cost"])
            rate = parse_colombian_decimal(row["vat_rate"])
            discount = parse_colombian_decimal(row.get("discount") or "0")
            subtotal = (qty * price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            if (
                qty <= 0
                or qty >= Decimal(100000000000)
                or min(price, cost, rate, discount) < 0
                or rate > 100
                or discount > subtotal
            ):
                raise ValueError("Cantidad, importe, descuento o IVA inválido.")
            method = row.get("payment_method") or "other"
            if method not in ("cash", "card", "transfer", "credit", "other"):
                raise ValueError("Medio de pago inválido.")
            customer = sanitize_cell_text(
                row.get("customer_label") or "Histórico sin cliente identificado", 80
            )
            group = groups.setdefault(
                ref, {"occurred": occurred, "method": method, "customer": customer, "items": []}
            )
            if (group["occurred"], group["method"], group["customer"]) != (occurred, method, customer):
                raise ValueError(
                    "Las líneas de una misma referencia deben tener la misma fecha, cliente y medio de pago."
                )
            group["items"].append((product, qty, price, cost, rate, discount, subtotal))
        except (ValueError, TypeError, HTTPException) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            raise HTTPException(422, f"Fila {idx}: {detail} No se importó ninguna venta.") from exc
    for ref in groups:
        if db.query(HistoricalSaleReference).filter_by(tenant_id=tenant_id, reference=ref).first():
            raise HTTPException(
                409, "Una referencia histórica del archivo ya fue importada. No se duplicaron registros."
            )
    result = {
        "mode": mode,
        "rows_total": len(rows),
        "rows_ok": len(rows),
        "rows_rejected": 0,
        "errors": [],
        "sales_created": 0,
    }
    if mode == "preview":
        return result
    job = ImportJob(
        tenant_id=tenant_id,
        kind="historical_sales",
        filename_safe=sanitize_cell_text(Path(filename).name),
        sha256=sha256_hex(content.hex()),
        status="committed",
        rows_total=len(rows),
        rows_ok=len(rows),
        rows_rejected=0,
        errors=[],
        created_by=user_id,
    )
    db.add(job)
    db.flush()
    number = db.query(func.max(Sale.sale_number)).filter_by(tenant_id=tenant_id).scalar() or 0
    for ref, group in groups.items():
        number += 1
        sale = Sale(
            tenant_id=tenant_id,
            sale_number=number,
            occurred_at=group["occurred"],
            customer_label=group["customer"],
            payment_method=group["method"],
            subtotal=Decimal(0),
            discount_total=Decimal(0),
            vat_total=Decimal(0),
            total=Decimal(0),
            cogs_total=Decimal(0),
            status="completed",
            source="historical",
            is_training_data=False,
            import_job_id=job.id,
            created_by=user_id,
        )
        db.add(sale)
        db.flush()
        for p, qty, price, cost, rate, discount, subtotal in group["items"]:
            vat = ((subtotal - discount) * rate / Decimal(100)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            cogs = (qty * cost).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            total = subtotal - discount + vat
            if max(subtotal, cogs, total, sale.total + total, sale.subtotal + subtotal) >= Decimal(
                1000000000000
            ):
                db.rollback()
                raise HTTPException(
                    422, "Importe histórico fuera del rango permitido. No se importó el archivo."
                )
            db.add(
                SaleItem(
                    tenant_id=tenant_id,
                    sale_id=sale.id,
                    product_id=p.id,
                    quantity=qty,
                    unit_price=price,
                    unit_cost_snapshot=cost,
                    vat_rate=rate,
                    discount=discount,
                    line_total=total,
                )
            )
            sale.subtotal += subtotal
            sale.discount_total += discount
            sale.vat_total += vat
            sale.total += total
            sale.cogs_total += cogs
        db.add(HistoricalSaleReference(tenant_id=tenant_id, sale_id=sale.id, reference=ref))
        db.add(SaleTaxSnapshot(tenant_id=tenant_id, sale_id=sale.id, revision=0, status="historical"))
        result["sales_created"] += 1
    db.commit()
    return result
