"""Rutas para inspección e importación masiva de productos y ventas (Sprint 2, Act. 3.3 F-DC-124)."""

import json
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

from app.core.dependencies import get_current_context, get_db
from app.core.models import Tenant, User
from app.imports.batch_importer import MAX_UPLOAD_BYTES, import_products_batch, import_sales_batch
from app.imports.smart_excel_mapper import inspect_workbook

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
