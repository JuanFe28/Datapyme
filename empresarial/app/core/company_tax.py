"""Condición tributaria declarada por empresa; sin reescribir ventas previas."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import CompanyTaxChange, Tenant


def tax_profile(db: Session, tenant_id: str) -> dict:
    rows = db.scalars(
        select(CompanyTaxChange)
        .where(CompanyTaxChange.tenant_id == tenant_id)
        .order_by(CompanyTaxChange.revision.desc())
    ).all()
    latest = rows[0] if rows else None
    return {
        "status": latest.status if latest else "pending",
        "revision": latest.revision if latest else 0,
        "history": [
            {
                "revision": r.revision,
                "status": r.status,
                "reason": r.reason,
                "changed_at": r.changed_at.isoformat(),
                "changed_by": r.changed_by,
            }
            for r in rows
        ],
    }


def sale_tax_policy(db: Session, tenant_id: str, expected_revision: int | None = None) -> dict:
    db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    profile = tax_profile(db, tenant_id)
    if expected_revision is not None and expected_revision != profile["revision"]:
        raise HTTPException(
            409, "Cambió la condición de IVA. Recarga y revisa el total antes de vender."
        )
    if profile["status"] == "pending":
        raise HTTPException(409, "Confirma la condición de IVA de la empresa antes de registrar ventas.")
    return profile


def effective_vat_rate(profile: dict, product_rate: Decimal) -> Decimal:
    return product_rate if profile["status"] == "responsible" else Decimal("0.00")
