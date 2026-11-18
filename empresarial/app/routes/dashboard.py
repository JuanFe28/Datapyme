"""Rutas del Dashboard Adaptativo, Personalización de UI y Preferencias (Sprint 3, Act. 3.4)."""

import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.analytics.action_advisor import compute_weekly_action_plan
from app.analytics.kpis import get_tenant_kpis_payload
from app.analytics.profitability import get_tenant_profitability_payload
from app.core.commercial_service import serialize_product
from app.core.company_tax import tax_profile
from app.core.dependencies import SESSION_COOKIE, get_current_context, get_db
from app.core.jinja_filters import serialize_sale
from app.core.models import (
    CompanyUIPreference,
    InventoryMovement,
    LegalConsent,
    Product,
    Sale,
    SaleItem,
    SaleTaxSnapshot,
    Tenant,
    User,
    UserViewSetting,
    utcnow,
)
from app.core.schemas import TourCompleteRequest, ViewModeUpdate
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
    sales_page: int | None = Query(default=None, ge=1),
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
    profitability_data = get_tenant_profitability_payload(db=db, tenant_id=tenant.id, period_days=30)
    products = [
        serialize_product(p)
        for p in db.query(Product)
        .filter_by(tenant_id=tenant.id, is_active=True)
        .order_by(Product.stock_qty.asc())
        .all()
    ]
    tenant_sales = db.query(Sale).filter_by(tenant_id=tenant.id)
    ordered_sales = tenant_sales.order_by(Sale.sale_number.desc())
    page_size = 25
    sales_total = tenant_sales.count()
    sales_pages = max(1, (sales_total + page_size - 1) // page_size)
    page = min(sales_page or 1, sales_pages)
    sales_offset = (page - 1) * page_size
    sales_history = [
        serialize_sale(sale)
        for sale in ordered_sales.offset(sales_offset).limit(page_size).all()
    ]
    recent_sales = (
        sales_history[:15]
        if page == 1
        else [serialize_sale(sale) for sale in ordered_sales.limit(15).all()]
    )
    practice_skus = [
        sku
        for (sku,) in db.query(Product.sku)
        .filter(Product.tenant_id == tenant.id, Product.sku.ilike("PRUEBA-%"))
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

    all_sales = tenant_sales.all()
    all_items = db.query(SaleItem).filter(SaleItem.tenant_id == tenant.id).all()
    action_plan = compute_weekly_action_plan(
        products=products,
        sales=[
            {
                "id": s.id,
                "status": s.status,
                "occurred_at": s.occurred_at,
                "subtotal": s.subtotal,
                "discount_total": s.discount_total,
            }
            for s in all_sales
        ],
        sale_items=[
            {
                "sale_id": it.sale_id,
                "product_id": it.product_id,
                "quantity": it.quantity,
            }
            for it in all_items
        ],
        forecast_payload=forecast_data,
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
            "initial_section": "section-sales" if sales_page is not None else "section-home",
            "primary_focus": layout_cfg.get("primary_focus"),
            "density": layout_cfg.get("density"),
            "view_mode": resolved_mode,
            "onboarding_tour_completed": bool(tenant.onboarding_tour_completed),
            "tour_scope": tenant.id,
            "practice_skus": practice_skus,
            "mfa_enabled": bool(user.mfa_enabled),
            "products": products,
            "recent_sales": recent_sales,
            "kpis": kpi_payload.get("kpis", {}),
            "alerts_summary": kpi_payload.get("alerts_summary", {}),
            "forecast": forecast_data,
            "profitability": profitability_data,
            "action_plan": action_plan,
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
            "profitability": profitability_data,
            "action_plan": action_plan,
            "onboarding_tour_completed": bool(tenant.onboarding_tour_completed),
            "products": products,
            "recent_sales": recent_sales,
            "sales_history": sales_history,
            "sales_requested": sales_page is not None,
            "sales_page": page,
            "sales_pages": sales_pages,
            "sales_offset": sales_offset,
            "sales_total": sales_total,
            "forecast_data": forecast_data,
            "dashboard_json": dashboard_json,
            "last_consent": last_consent,
            "root_path": request.scope.get("root_path", "").rstrip("/"),
        },
    )


@router.post("/api/onboarding/complete-tour")
def complete_onboarding_tour(
    payload: TourCompleteRequest,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    _, tenant = ctx
    if payload.action == "purge_training":
        db.query(Tenant).filter_by(id=tenant.id).with_for_update().one()
        training_ids = [
            p.id for p in db.query(Product).filter_by(tenant_id=tenant.id, is_training_data=True)
        ]
        if training_ids:
            real_movement = (
                db.query(InventoryMovement)
                .filter(
                    InventoryMovement.tenant_id == tenant.id,
                    InventoryMovement.product_id.in_(training_ids),
                    InventoryMovement.is_training_data.is_(False),
                )
                .first()
            )
            real_line = (
                db.query(SaleItem)
                .join(Sale, Sale.id == SaleItem.sale_id)
                .filter(
                    SaleItem.tenant_id == tenant.id,
                    SaleItem.product_id.in_(training_ids),
                    Sale.is_training_data.is_(False),
                )
                .first()
            )
            if real_movement or real_line:
                raise HTTPException(
                    status_code=409,
                    detail="Hay operaciones reales relacionadas con productos de práctica. Se conservó toda la información; solicite revisión.",
                )
        training_sales = db.query(Sale).filter_by(tenant_id=tenant.id, is_training_data=True).all()
        t_sale_ids = [s.id for s in training_sales]
        if (
            t_sale_ids
            and db.query(SaleItem)
            .filter(
                SaleItem.tenant_id == tenant.id,
                SaleItem.sale_id.in_(t_sale_ids),
                ~SaleItem.product_id.in_(training_ids),
            )
            .first()
        ):
            raise HTTPException(
                status_code=409,
                detail="Una venta de práctica afecta inventario real. Se conservó toda la información; solicite revisión.",
            )
        if t_sale_ids:
            db.query(SaleTaxSnapshot).filter(
                SaleTaxSnapshot.tenant_id == tenant.id, SaleTaxSnapshot.sale_id.in_(t_sale_ids)
            ).delete(synchronize_session=False)
            db.query(SaleItem).filter(
                SaleItem.tenant_id == tenant.id, SaleItem.sale_id.in_(t_sale_ids)
            ).delete(synchronize_session=False)
        db.query(InventoryMovement).filter_by(tenant_id=tenant.id, is_training_data=True).delete(
            synchronize_session=False
        )
        if t_sale_ids:
            db.query(Sale).filter(Sale.tenant_id == tenant.id, Sale.id.in_(t_sale_ids)).delete(
                synchronize_session=False
            )
        db.query(Product).filter_by(tenant_id=tenant.id, is_training_data=True).delete(
            synchronize_session=False
        )
        tenant.onboarding_tour_completed = True
        db.commit()
        return {"status": "purged", "onboarding_tour_completed": True}

    # Conservar la práctica no la convierte en información comercial real.
    tenant.onboarding_tour_completed = True
    db.commit()
    return {"status": "kept", "onboarding_tour_completed": True}
