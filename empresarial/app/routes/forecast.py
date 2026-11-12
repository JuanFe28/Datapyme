"""Rutas para analítica predictiva OLS y cálculo de KPIs comerciales (Sprints 3 y 4, Act. 3.4 y 3.5)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.kpis import get_tenant_kpis_payload
from app.core.dependencies import get_current_context, get_db
from app.core.models import Tenant, User
from app.forecast.stats import get_tenant_forecast_payload

router = APIRouter(tags=["forecast"])


@router.get("/api/kpis")
def get_kpis_endpoint(
    period_days: int = Query(default=30, ge=1, le=365),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    return get_tenant_kpis_payload(db=db, tenant_id=tenant.id, period_days=period_days)


@router.get("/api/forecast")
def get_forecast_endpoint(
    metric: Literal["net_revenue", "units_sold"] = Query(default="net_revenue"),
    horizon: int = Query(default=1, ge=1, le=3),
    product_id: str | None = Query(default=None),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    return get_tenant_forecast_payload(
        db=db,
        tenant_id=tenant.id,
        metric=metric,
        horizon=horizon,
        product_id=product_id,
    )
