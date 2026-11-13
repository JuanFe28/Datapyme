from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.company_tax import tax_profile
from app.core.dependencies import get_current_context, get_db
from app.core.models import CompanyTaxChange, Tenant, User

router = APIRouter(prefix="/api/company/tax", tags=["company-tax"])


class TaxChangeRequest(BaseModel):
    status: Literal["responsible", "not_responsible", "pending"]
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=280)


@router.get("")
def get_tax(ctx: tuple[User, Tenant] = Depends(get_current_context), db: Session = Depends(get_db)):
    return tax_profile(db, ctx[1].id)


@router.put("")
def change_tax(
    payload: TaxChangeRequest,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    if user.role != "owner":
        raise HTTPException(
            403, "Solo el administrador de la empresa puede cambiar su condición de IVA."
        )
    db.scalar(select(Tenant).where(Tenant.id == tenant.id).with_for_update())
    current = tax_profile(db, tenant.id)
    if current["revision"] != payload.expected_revision:
        raise HTTPException(409, "La configuración cambió. Recarga antes de guardar.")
    reason = payload.reason.strip()
    if len(reason) < 5:
        raise HTTPException(422, "Indica un motivo de al menos cinco caracteres.")
    db.add(
        CompanyTaxChange(
            tenant_id=tenant.id,
            revision=current["revision"] + 1,
            status=payload.status,
            reason=reason,
            changed_by=user.id,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Otro usuario modificó la configuración. Recarga.") from exc
    return tax_profile(db, tenant.id)
