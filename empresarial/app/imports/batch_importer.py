"""Procesador de importaciones masivas tabulares (CSV y Excel XLSX) para Datapyme Empresarial."""

import csv
import io
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.commercial_service import (
    THREE_PLACES,
    TWO_PLACES,
    create_product_with_initial_stock,
    create_sale_atomic,
    parse_colombian_decimal,
    sanitize_cell_text,
)
from app.core.models import ImportJob, Product, UsageEvent
from app.core.security import sha256_hex

ALLOWED_UPLOAD_EXTS = {".csv", ".xlsx"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_UPLOAD_ROWS = 20_000


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
            raise HTTPException(
                status_code=422, detail="El archivo .xlsx no tiene una firma ZIP válida."
            )
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 25 * 1024 * 1024:
                    raise HTTPException(
                        status_code=422, detail="Archivo XLSX excede límite descomprimido."
                    )
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
                category = (
                    sanitize_cell_text(r.get("category", "") or r.get("categoria", "General"), 90)
                    or "General"
                )
                unit = sanitize_cell_text(r.get("unit", "") or r.get("unidad", "und"), 20) or "und"
                cost_price = parse_colombian_decimal(
                    r.get("cost_price") or r.get("costo", "0"), TWO_PLACES
                )
                sale_price = parse_colombian_decimal(
                    r.get("sale_price") or r.get("precio", "0"), TWO_PLACES
                )
                vat_rate = parse_colombian_decimal(r.get("vat_rate") or r.get("iva", "19"), TWO_PLACES)
                initial_stock = parse_colombian_decimal(
                    r.get("initial_stock") or r.get("stock", "0"), THREE_PLACES
                )
                min_stock = parse_colombian_decimal(
                    r.get("min_stock") or r.get("stock_minimo", "0"), THREE_PLACES
                )

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
