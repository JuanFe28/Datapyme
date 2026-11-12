"""Rutas para el Catálogo de Productos y Carga de Imágenes (Sprint 2, Act. 3.3 F-DC-124)."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.commercial_service import (
    THREE_PLACES,
    TWO_PLACES,
    create_product_with_initial_stock,
    parse_colombian_decimal,
    sanitize_cell_text,
    serialize_product,
)
from app.core.config import ROOT
from app.core.dependencies import get_current_context, get_db
from app.core.image_service import save_product_image
from app.core.models import Product, Tenant, User, utcnow
from app.core.schemas import ProductCreateRequest, ProductUpdateRequest

router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("", status_code=201)
def create_product(
    payload: ProductCreateRequest,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    try:
        prod = create_product_with_initial_stock(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
            sku=payload.sku,
            name=payload.name,
            category=payload.category,
            unit=payload.unit,
            cost_price=parse_colombian_decimal(payload.cost_price, TWO_PLACES),
            sale_price=parse_colombian_decimal(payload.sale_price, TWO_PLACES),
            vat_rate=parse_colombian_decimal(payload.vat_rate, TWO_PLACES),
            initial_stock=parse_colombian_decimal(payload.initial_stock, THREE_PLACES),
            min_stock=parse_colombian_decimal(payload.min_stock, THREE_PLACES),
            image_url=payload.image_url,
        )
        db.commit()
        return serialize_product(prod)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/upload-image", status_code=201)
async def upload_product_image_endpoint(
    file: UploadFile = File(...),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
):
    _, tenant = ctx
    content = await file.read()
    image_url = save_product_image(
        tenant_id=tenant.id,
        filename=file.filename or "",
        content=content,
        static_root=ROOT / "static",
    )
    return {"image_url": image_url}


@router.get("")
def list_products(
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    prods = db.query(Product).filter_by(tenant_id=tenant.id).order_by(Product.sku.asc()).all()
    return [serialize_product(p) for p in prods]


@router.get("/{product_id}")
def get_product(
    product_id: str,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    prod = db.query(Product).filter_by(tenant_id=tenant.id, id=product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return serialize_product(prod)


@router.patch("/{product_id}")
@router.put("/{product_id}")
def update_product(
    product_id: str,
    payload: ProductUpdateRequest,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    prod = db.query(Product).filter_by(tenant_id=tenant.id, id=product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    if payload.sku is not None:
        clean_sku = sanitize_cell_text(payload.sku, 64)
        exist_sku = (
            db.query(Product)
            .filter(Product.tenant_id == tenant.id, Product.sku == clean_sku, Product.id != product_id)
            .first()
        )
        if exist_sku:
            raise HTTPException(
                status_code=409, detail="El SKU ya existe en otro producto del catálogo."
            )
        prod.sku = clean_sku
    if payload.name is not None:
        prod.name = sanitize_cell_text(payload.name, 180)
    if payload.category is not None:
        prod.category = sanitize_cell_text(payload.category, 90)
    if payload.unit is not None:
        prod.unit = sanitize_cell_text(payload.unit, 20)
    if payload.cost_price is not None:
        prod.cost_price = parse_colombian_decimal(payload.cost_price, TWO_PLACES)
    if payload.sale_price is not None:
        prod.sale_price = parse_colombian_decimal(payload.sale_price, TWO_PLACES)
    if payload.min_stock is not None:
        prod.min_stock = parse_colombian_decimal(payload.min_stock, THREE_PLACES)
    if payload.image_url is not None:
        prod.image_url = payload.image_url.strip() if payload.image_url.strip() else None
    if payload.is_active is not None:
        prod.is_active = payload.is_active
    prod.updated_at = utcnow()
    db.commit()
    return serialize_product(prod)
