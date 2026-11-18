"""Rutas para inspección e importación masiva de productos y ventas (Sprint 2, Act. 3.3 F-DC-124)."""

import json
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

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
from app.core.company_tax import effective_vat_rate, sale_tax_policy, tax_profile
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
    product_overrides: str | None = Form(default=None),
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

    overrides_map: dict[str, dict[str, Any]] = {}
    if product_overrides:
        try:
            parsed_overrides = json.loads(product_overrides)
            if isinstance(parsed_overrides, dict):
                overrides_map = {
                    str(k).strip().upper(): v for k, v in parsed_overrides.items() if isinstance(v, dict)
                }
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422, detail="Formato inválido en ajustes de productos."
            ) from exc

    db.query(Tenant).filter_by(id=tenant.id).with_for_update().one()
    existing_products = db.query(Product).filter_by(tenant_id=tenant.id).all()
    practice_skus = {p.sku.upper() for p in existing_products if p.is_training_data}
    if any(item["sku"].upper() in practice_skus for item in analysis["products"]):
        raise HTTPException(
            status_code=409,
            detail="El archivo contiene un código reservado por un producto de práctica. "
            "Cambia ese código en el archivo o elimina la práctica antes de importar.",
        )
    existing_by_sku = {p.sku.upper(): p for p in existing_products if not p.is_training_data}
    existing_by_name = {
        sanitize_cell_text(p.name, 180).casefold(): p for p in existing_by_sku.values() if p.is_active
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

    def _safe_dec(raw: Any, q: Decimal, default: Decimal) -> Decimal:
        if raw is None or str(raw).strip() == "":
            return default
        try:
            val = Decimal(str(raw).replace(",", ".").strip())
            if not val.is_finite() or val < 0:
                return default
            return val.quantize(q)
        except (InvalidOperation, ValueError):
            return default

    products_created = 0
    sku_alias_map: dict[str, Product] = {}
    desired_final_stock_by_prod_id: dict[str, Decimal] = {}

    for item in analysis["products"]:
        sku_key = item["sku"].upper()
        name_cf = sanitize_cell_text(item["name"], 180).casefold()
        ov = overrides_map.get(sku_key) or overrides_map.get(item["name"].upper()) or {}

        cost_val = _safe_dec(
            ov.get("cost_price"), TWO_PLACES, Decimal(item["cost_price"]).quantize(TWO_PLACES)
        )
        init_stock_val = _safe_dec(
            ov.get("initial_stock"),
            THREE_PLACES,
            Decimal(item["initial_stock"]).quantize(THREE_PLACES),
        )
        if "current_stock" in ov and str(ov["current_stock"]).strip() != "":
            target_final_stock = _safe_dec(ov.get("current_stock"), THREE_PLACES, Decimal("0.000"))
        else:
            target_final_stock = None

        matched_prod = existing_by_sku.get(sku_key)
        if not matched_prod and sku_key.startswith("AUTO-") and name_cf in existing_by_name:
            matched_prod = existing_by_name[name_cf]

        if matched_prod:
            sku_alias_map[sku_key] = matched_prod
            if "cost_price" in ov:
                matched_prod.cost_price = cost_val
            if "sale_price" in ov and _safe_dec(ov.get("sale_price"), TWO_PLACES, Decimal(0)) > 0:
                matched_prod.sale_price = _safe_dec(ov.get("sale_price"), TWO_PLACES, Decimal(0))
            if "initial_stock" in ov and matched_prod.is_active:
                cur_s = Decimal(str(matched_prod.stock_qty)).quantize(THREE_PLACES)
                if init_stock_val != cur_s:
                    diff = (init_stock_val - cur_s).quantize(THREE_PLACES)
                    record_inventory_movement(
                        db=db,
                        tenant_id=tenant.id,
                        user_id=user.id,
                        product_id=matched_prod.id,
                        movement_type="adjustment_in" if diff > 0 else "adjustment_out",
                        quantity=abs(diff),
                        reason="Ajuste de stock inicial al importar Excel unificado",
                        unit_cost=matched_prod.cost_price,
                    )
            if target_final_stock is not None:
                desired_final_stock_by_prod_id[matched_prod.id] = target_final_stock
            continue

        prod = create_product_with_initial_stock(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
            sku=sku_key,
            name=item["name"],
            category=item["category"],
            unit=item["unit"],
            cost_price=cost_val,
            sale_price=Decimal(item["sale_price"]).quantize(TWO_PLACES),
            vat_rate=Decimal(item["vat_rate"]).quantize(TWO_PLACES),
            initial_stock=init_stock_val,
            min_stock=Decimal(item["min_stock"]).quantize(THREE_PLACES),
            import_job_id=job.id,
        )
        db.flush()
        existing_by_sku[sku_key] = prod
        existing_by_name[name_cf] = prod
        sku_alias_map[sku_key] = prod
        if target_final_stock is not None:
            desired_final_stock_by_prod_id[prod.id] = target_final_stock
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

        policy = sale_tax_policy(db, tenant.id, None)

        for s_item in analysis["sales"]:
            sub_items = s_item.get("items") or [
                {
                    "sku": s_item["sku"],
                    "quantity": s_item["quantity"],
                    "unit_price": s_item["unit_price"],
                    "line_total": s_item["line_total"],
                }
            ]
            resolved_sub_items: list[tuple[Product, Decimal, Decimal]] = []
            needed_by_prod: dict[str, tuple[Product, Decimal]] = {}

            for sub in sub_items:
                sub_sku = str(sub.get("sku") or "").upper()
                prod = sku_alias_map.get(sub_sku) or existing_by_sku.get(sub_sku)
                if not prod or not prod.is_active:
                    continue
                qty = Decimal(str(sub["quantity"])).quantize(THREE_PLACES)
                if qty <= 0:
                    continue
                target_line = Decimal(str(sub.get("line_total", s_item["line_total"]))).quantize(
                    TWO_PLACES
                )
                resolved_sub_items.append((prod, qty, target_line))
                prev_qty = needed_by_prod[prod.id][1] if prod.id in needed_by_prod else Decimal(0)
                needed_by_prod[prod.id] = (prod, prev_qty + qty)

            if not resolved_sub_items:
                continue

            for prod, req_qty in needed_by_prod.values():
                current_stock = Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)
                if current_stock < req_qty:
                    record_inventory_movement(
                        db=db,
                        tenant_id=tenant.id,
                        user_id=user.id,
                        product_id=prod.id,
                        movement_type="purchase_in",
                        quantity=(req_qty - current_stock).quantize(THREE_PLACES),
                        reason="Reposición automática inferida al importar archivo unificado",
                        unit_cost=prod.cost_price,
                    )

            sale_items_input: list[dict[str, Any]] = []
            for prod, qty, target_line in resolved_sub_items:
                vat_r = effective_vat_rate(policy, Decimal(str(prod.vat_rate)).quantize(TWO_PLACES))
                if vat_r > 0:
                    target_base = (target_line / (Decimal(1) + vat_r / Decimal(100))).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    )
                else:
                    target_base = target_line
                unit_p = (target_base / qty).quantize(TWO_PLACES, rounding=ROUND_CEILING)
                gross = (qty * unit_p).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                line_disc = max(Decimal("0.00"), (gross - target_base).quantize(TWO_PLACES))
                sale_items_input.append(
                    {
                        "product_id": prod.id,
                        "quantity": qty,
                        "unit_price": unit_p,
                        "discount": line_disc,
                    }
                )

            sale = create_sale_atomic(
                db=db,
                tenant_id=tenant.id,
                user_id=user.id,
                customer_label=s_item["customer_label"],
                payment_method=s_item["payment_method"],
                items_input=sale_items_input,
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

    # Aplicar stock final editado manualmente en la vista previa (Stock Actual) tras procesar históricos
    if desired_final_stock_by_prod_id:
        for prod_id, target_stock in desired_final_stock_by_prod_id.items():
            prod = db.query(Product).filter_by(tenant_id=tenant.id, id=prod_id).first()
            if not prod or not prod.is_active:
                continue
            cur_s = Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)
            if cur_s != target_stock:
                diff = (target_stock - cur_s).quantize(THREE_PLACES)
                record_inventory_movement(
                    db=db,
                    tenant_id=tenant.id,
                    user_id=user.id,
                    product_id=prod.id,
                    movement_type="adjustment_in" if diff > 0 else "adjustment_out",
                    quantity=abs(diff),
                    reason="Stock actual definido manualmente al importar archivo unificado",
                    unit_cost=prod.cost_price,
                )

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
