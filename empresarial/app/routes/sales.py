"""Rutas para registro de ventas, consulta de historial y anulación atómica (Sprint 2, Act. 3.3)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.commercial_service import create_sale_atomic, void_sale_atomic
from app.core.dependencies import get_current_context, get_db
from app.core.jinja_filters import serialize_sale
from app.core.models import Sale, Tenant, User
from app.core.schemas import SaleCreateRequest

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.post("", status_code=201)
def create_sale(
    payload: SaleCreateRequest,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    from app.core.company_tax import sale_tax_policy

    sale_tax_policy(db, tenant.id, payload.tax_revision)
    items_data = [
        {
            "product_id": it.product_id,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "discount": it.discount,
        }
        for it in payload.items
    ]
    try:
        sale = create_sale_atomic(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
            customer_label=payload.customer_label,
            payment_method=payload.payment_method,
            items_input=items_data,
            source="manual",
            tax_revision=payload.tax_revision,
        )
        db.commit()
        return serialize_sale(sale)
    except HTTPException:
        db.rollback()
        raise


@router.get("")
def list_sales(
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    sales = db.query(Sale).filter_by(tenant_id=tenant.id).order_by(Sale.sale_number.desc()).all()
    return [serialize_sale(s) for s in sales]


@router.get("/{sale_id}")
def get_sale(
    sale_id: str,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    sale = db.query(Sale).filter_by(tenant_id=tenant.id, id=sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    return serialize_sale(sale)


@router.post("/{sale_id}/void")
def void_sale(
    sale_id: str,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    sale = void_sale_atomic(db=db, tenant_id=tenant.id, user_id=user.id, sale_id=sale_id)
    db.commit()
    return serialize_sale(sale)
