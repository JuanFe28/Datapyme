"""Rutas para inspección e importación masiva de productos y ventas (Sprint 2, Act. 3.3 F-DC-124)."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.commercial_service import (
    THREE_PLACES,
    TWO_PLACES,
    create_product_with_initial_stock,
    create_sale_atomic,
    record_inventory_movement,
    sanitize_cell_text,
)
from app.core.company_tax import tax_profile
from app.core.dependencies import get_current_context, get_db
from app.core.models import CompanyTaxChange, ImportJob, Product, Tenant, UsageEvent, User, utcnow
from app.core.security import sha256_hex
from app.imports.batch_importer import MAX_UPLOAD_BYTES, import_products_batch, import_sales_batch
from app.imports.smart_excel_mapper import analyze_unified_workbook, inspect_workbook

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("/historical-sales")
async def import_history_endpoint(
    response: Response,
    mode: Literal["preview", "commit"] = Query(default="preview"),
    file: UploadFile = File(...),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    from app.imports.historical_sales import import_historical_sales

    user, tenant = ctx
    result = import_historical_sales(
        db, tenant.id, user.id, file.filename or "", await file.read(MAX_UPLOAD_BYTES + 1), mode
    )
    response.status_code = 201 if mode == "commit" else 200
    return result


@router.post("/unified")
async def import_unified_endpoint(
    response: Response,
    mode: Literal["preview", "commit"] = Query(default="preview"),
    file: UploadFile = File(...),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    analysis = analyze_unified_workbook(file.filename or "", content)
    if mode == "preview":
        response.status_code = 200
        return {**analysis, "mode": "preview"}

    if analysis["products_count"] == 0 and analysis["sales_count"] == 0:
        raise HTTPException(
            status_code=422,
            detail="No se detectaron productos ni ventas válidas en el archivo subido.",
        )

    db.query(Tenant).filter_by(id=tenant.id).with_for_update().one()
    existing_by_sku = {
        p.sku.upper(): p
        for p in db.query(Product).filter_by(tenant_id=tenant.id, is_training_data=False).all()
    }

    job = ImportJob(
        tenant_id=tenant.id,
        kind="unified",
        filename_safe=sanitize_cell_text(Path(file.filename or "archivo.xlsx").name, 180),
        sha256=sha256_hex(content.hex()),
        status="committed",
        rows_total=analysis["products_count"] + analysis["sales_count"],
        rows_ok=0,
        rows_rejected=0,
        errors=[],
        created_by=user.id,
    )
    db.add(job)
    db.flush()

    products_created = 0
    for item in analysis["products"]:
        sku_key = item["sku"].upper()
        if sku_key in existing_by_sku:
            continue
        prod = create_product_with_initial_stock(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
            sku=sku_key,
            name=item["name"],
            category=item["category"],
            unit=item["unit"],
            cost_price=Decimal(item["cost_price"]).quantize(TWO_PLACES),
            sale_price=Decimal(item["sale_price"]).quantize(TWO_PLACES),
            vat_rate=Decimal(item["vat_rate"]).quantize(TWO_PLACES),
            initial_stock=Decimal(item["initial_stock"]).quantize(THREE_PLACES),
            min_stock=Decimal(item["min_stock"]).quantize(THREE_PLACES),
            import_job_id=job.id,
        )
        db.flush()
        existing_by_sku[sku_key] = prod
        products_created += 1

    sales_created = 0
    if analysis["sales"]:
        if tax_profile(db, tenant.id)["status"] == "pending":
            db.add(
                CompanyTaxChange(
                    tenant_id=tenant.id,
                    revision=1,
                    status="not_responsible",
                    reason="Condición inicial asignada al importar Excel unificado",
                    changed_by=user.id,
                )
            )
            db.flush()

        for s_item in analysis["sales"]:
            sku_key = s_item["sku"].upper()
            prod = existing_by_sku.get(sku_key)
            if not prod or not prod.is_active:
                continue
            qty = Decimal(s_item["quantity"]).quantize(THREE_PLACES)
            if qty <= 0:
                continue
            current_stock = Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)
            if current_stock < qty:
                record_inventory_movement(
                    db=db,
                    tenant_id=tenant.id,
                    user_id=user.id,
                    product_id=prod.id,
                    movement_type="purchase_in",
                    quantity=(qty - current_stock).quantize(THREE_PLACES),
                    reason="Reposición automática inferida al importar archivo unificado",
                    unit_cost=prod.cost_price,
                )
            sale = create_sale_atomic(
                db=db,
                tenant_id=tenant.id,
                user_id=user.id,
                customer_label=s_item["customer_label"],
                payment_method=s_item["payment_method"],
                items_input=[
                    {
                        "product_id": prod.id,
                        "quantity": qty,
                        "unit_price": Decimal(s_item["unit_price"]).quantize(TWO_PLACES),
                        "discount": Decimal(s_item["discount"]).quantize(TWO_PLACES),
                    }
                ],
                source="import",
                import_job_id=job.id,
            )
            if s_item.get("occurred_at"):
                try:
                    parsed_dt = datetime.fromisoformat(
                        f"{s_item['occurred_at']}T12:00:00-05:00"
                    ).astimezone(UTC)
                    if parsed_dt <= utcnow():
                        sale.occurred_at = parsed_dt
                except ValueError:
                    pass
            sales_created += 1

    job.rows_ok = products_created + sales_created
    db.add(UsageEvent(tenant_id=tenant.id, event_type="import_completed"))
    db.commit()

    response.status_code = 201
    return {
        **analysis,
        "mode": "commit",
        "job_id": job.id,
        "products_created": products_created,
        "sales_created": sales_created,
        "rows_ok": products_created + sales_created,
        "rows_rejected": 0,
        "errors": [],
    }


@router.post("/inspect")
async def inspect_import_endpoint(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
    _ctx: tuple[User, Tenant] = Depends(get_current_context),
):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    return inspect_workbook(
        filename=file.filename or "",
        content=content,
        target_sheet=sheet,
    )


@router.post("/products")
async def import_products_endpoint(
    response: Response,
    mode: Literal["preview", "commit"] = Query(default="preview"),
    file: UploadFile = File(...),
    mapping: str | None = Form(default=None),
    sheet_name: str | None = Form(default=None),
    header_row: int | None = Form(default=1),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    col_mapping = None
    if mapping:
        try:
            col_mapping = json.loads(mapping) if isinstance(mapping, str) else None
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Mapeo de columnas inválido.") from exc
        if (
            not isinstance(col_mapping, dict)
            or not col_mapping.get("name")
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in col_mapping.items())
        ):
            raise HTTPException(
                status_code=422,
                detail="Seleccione columnas válidas y una columna de nombre de producto.",
            )
    result = import_products_batch(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        filename=file.filename or "",
        content=content,
        mode=mode,
        mapping=col_mapping,
        sheet_name=sheet_name,
        header_row_index=header_row or 1,
    )
    response.status_code = 201 if mode == "commit" else 200
    return result


@router.post("/sales")
async def import_sales_endpoint(
    response: Response,
    mode: Literal["preview", "commit"] = Query(default="preview"),
    file: UploadFile = File(...),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    result = import_sales_batch(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        filename=file.filename or "",
        content=content,
        mode=mode,
    )
    response.status_code = 201 if mode == "commit" else 200
    return result
