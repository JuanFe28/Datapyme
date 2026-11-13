"""Rutas del Dashboard Adaptativo, Personalización de UI y Preferencias (Sprint 3, Act. 3.4)."""

import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.analytics.kpis import get_tenant_kpis_payload
from app.core.commercial_service import serialize_product
from app.core.company_tax import tax_profile
from app.core.dependencies import SESSION_COOKIE, get_current_context, get_db
from app.core.jinja_filters import serialize_sale
from app.core.models import (
    CompanyUIPreference,
    LegalConsent,
    Product,
    Sale,
    Tenant,
    User,
    UserViewSetting,
    utcnow,
)
from app.core.schemas import ViewModeUpdate
from app.forecast.stats import get_tenant_forecast_payload
from app.ui.ui_personalization_service import (
    DiagnosisInput,
    PriorityProfile,
    build_layout_config,
    compute_priority_weights,
)

router = APIRouter(tags=["dashboard"])


def load_tenant_profile(db: Session, tenant_id: str) -> PriorityProfile:
    """Carga el perfil de ponderación adaptativa calculado a partir del diagnóstico."""
    pref = db.query(CompanyUIPreference).filter_by(tenant_id=tenant_id).first()
    if not pref:
        return compute_priority_weights(DiagnosisInput())
    diag_dict = pref.diagnosis_answers or {}
    diag_in = DiagnosisInput(
        M10=diag_dict.get("M10", []),
        M12=diag_dict.get("M12", []),
        M17=diag_dict.get("M17", ""),
        M07=diag_dict.get("M07", []),
        M08=diag_dict.get("M08", []),
        M13=diag_dict.get("M13", "No"),
        M15=diag_dict.get("M15", []),
    )
    return compute_priority_weights(diag_in)


@router.get("/api/ui/layout")
def get_ui_layout(
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    view_setting = db.query(UserViewSetting).filter_by(user_id=user.id, tenant_id=tenant.id).first()
    mode: Literal["personalized", "general"] = (
        view_setting.view_mode
        if view_setting and view_setting.view_mode == "general"
        else "personalized"
    )
    profile = load_tenant_profile(db, tenant.id)
    return build_layout_config(profile, view_mode=mode)


@router.put("/api/ui/view-mode")
def update_view_mode(
    payload: ViewModeUpdate,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    view_setting = db.query(UserViewSetting).filter_by(user_id=user.id, tenant_id=tenant.id).first()
    if not view_setting:
        view_setting = UserViewSetting(
            user_id=user.id,
            tenant_id=tenant.id,
            view_mode=payload.view_mode,
        )
        db.add(view_setting)
    else:
        view_setting.view_mode = payload.view_mode
        view_setting.updated_at = utcnow()
    db.commit()
    profile = load_tenant_profile(db, tenant.id)
    return build_layout_config(profile, view_mode=payload.view_mode)


@router.get("/api/tenants/{target_tenant_id}/preferences")
def get_tenant_preferences(
    target_tenant_id: str,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    if target_tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")
    pref = db.query(CompanyUIPreference).filter_by(tenant_id=tenant.id).first()
    if not pref:
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")
    return {
        "tenant_id": pref.tenant_id,
        "primary_focus": pref.primary_focus,
        "priority_weights": pref.priority_weights,
        "preferred_chart_density": pref.preferred_chart_density,
    }


@router.get("/dashboard", response_class=HTMLResponse)
def render_adaptive_dashboard(
    request: Request,
    view_mode: Literal["personalized", "general"] | None = Query(default=None),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    view_setting = db.query(UserViewSetting).filter_by(user_id=user.id, tenant_id=tenant.id).first()
    if view_mode in ("personalized", "general"):
        resolved_mode: Literal["personalized", "general"] = view_mode
    elif view_setting and view_setting.view_mode == "general":
        resolved_mode = "general"
    else:
        resolved_mode = "personalized"

    profile = load_tenant_profile(db, tenant.id)
    layout_cfg = build_layout_config(profile, view_mode=resolved_mode)
    kpi_payload = get_tenant_kpis_payload(db=db, tenant_id=tenant.id, period_days=30)
    products = [
        serialize_product(p)
        for p in db.query(Product)
        .filter_by(tenant_id=tenant.id, is_active=True)
        .order_by(Product.stock_qty.asc())
        .all()
    ]
    recent_sales = [
        serialize_sale(s)
        for s in db.query(Sale)
        .filter_by(tenant_id=tenant.id)
        .order_by(Sale.sale_number.desc())
        .limit(15)
        .all()
    ]
    current_tax = tax_profile(db, tenant.id)
    for product in products:
        rate = Decimal(product["vat_rate"]) if current_tax["status"] == "responsible" else Decimal(0)
        product["final_price"] = str(
            (Decimal(product["sale_price"]) * (1 + rate / 100)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        if current_tax["status"] == "pending":
            product["final_price"] = None
    forecast_data = get_tenant_forecast_payload(
        db=db,
        tenant_id=tenant.id,
        metric="net_revenue",
        horizon=2,
        record_event=False,
    )

    last_consent = (
        db.query(LegalConsent)
        .filter_by(tenant_id=tenant.id)
        .order_by(LegalConsent.accepted_at.desc())
        .first()
    )

    clean_trade_name = (tenant.trade_name or tenant.legal_name).replace("[DEMO-FDC125]", "").strip()
    clean_legal_name = tenant.legal_name.replace("[DEMO-FDC125]", "").strip()

    raw_auth = request.headers.get("authorization", "")
    if raw_auth.startswith("Bearer "):
        active_token = raw_auth.removeprefix("Bearer ").strip()
    else:
        active_token = request.cookies.get(SESSION_COOKIE, "")

    dashboard_json = json.dumps(
        {
            "company_tax": tax_profile(db, tenant.id),
            "token": active_token,
            "primary_focus": layout_cfg.get("primary_focus"),
            "density": layout_cfg.get("density"),
            "view_mode": resolved_mode,
            "products": products,
            "recent_sales": recent_sales,
            "kpis": kpi_payload.get("kpis", {}),
            "alerts_summary": kpi_payload.get("alerts_summary", {}),
            "forecast": forecast_data,
        },
        default=str,
    )

    templates = request.app.state.templates
    dashboard_json = (
        dashboard_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "title": f"Dashboard · {clean_trade_name}",
            "tenant_name": f"{clean_legal_name} · {tenant.municipality}",
            "company_name": clean_trade_name,
            "current_user": user,
            "company_tax": tax_profile(db, tenant.id),
            "layout_config": layout_cfg,
            "kpi_payload": kpi_payload,
            "products": products,
            "recent_sales": recent_sales,
            "forecast_data": forecast_data,
            "dashboard_json": dashboard_json,
            "last_consent": last_consent,
            "root_path": request.scope.get("root_path", "").rstrip("/"),
        },
    )
