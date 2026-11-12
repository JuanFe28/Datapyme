"""Rutas de movimientos de inventario (Kardex) y alertas de existencias (Sprint 2, Act. 3.3)."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.commercial_service import (
    THREE_PLACES,
    TWO_PLACES,
    classify_inventory_alerts,
    parse_colombian_decimal,
    record_inventory_movement,
)
from app.core.dependencies import get_current_context, get_db
from app.core.models import Tenant, User
from app.core.schemas import InventoryMovementRequest

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post("/movements", status_code=201)
def post_inventory_movement(
    payload: InventoryMovementRequest,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    qty = parse_colombian_decimal(payload.quantity, THREE_PLACES)
    u_cost = (
        parse_colombian_decimal(payload.unit_cost, TWO_PLACES) if payload.unit_cost is not None else None
    )
    prod, mov = record_inventory_movement(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        product_id=payload.product_id,
        movement_type=payload.movement_type,
        quantity=qty,
        reason=payload.reason,
        unit_cost=u_cost,
    )
    db.commit()
    return {
        "movement_id": mov.id,
        "product_id": prod.id,
        "movement_type": mov.movement_type,
        "quantity": str(Decimal(str(mov.quantity)).quantize(THREE_PLACES)),
        "new_stock_qty": str(Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)),
    }


@router.get("/alerts")
def get_inventory_alerts(
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    return classify_inventory_alerts(db, tenant.id)
