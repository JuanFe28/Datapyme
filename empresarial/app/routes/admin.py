"""Rutas de auditoría de impacto para SuperAdmin y derechos de Habeas Data (Sprint 5, F-DC-125 y Ley 1581)."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import (
    SESSION_COOKIE,
    _as_aware,
    get_current_context,
    get_db,
    get_superadmin_user,
)
from app.core.models import SessionToken, Tenant, User, utcnow
from app.core.schemas import DeletionRequestPayload
from app.core.security import sha256_hex
from app.telemetry.impact_service import (
    compute_platform_impact_telemetry,
    export_habeas_data_bundle,
    request_habeas_data_deletion,
)

router = APIRouter(tags=["admin"])


@router.get("/admin/impacto", response_class=HTMLResponse, include_in_schema=False)
def render_superadmin_impact(
    request: Request,
    db: Session = Depends(get_db),
):
    root_path = request.scope.get("root_path", "").rstrip("/")
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.removeprefix("Bearer ").strip()
    if not raw_token:
        return RedirectResponse(f"{root_path}/login", status_code=303)
    tok_hash = sha256_hex(raw_token)
    sess = db.query(SessionToken).filter_by(token_hash=tok_hash).first()
    if not sess or sess.revoked_at is not None or _as_aware(sess.expires_at) <= utcnow():
        return RedirectResponse(f"{root_path}/login", status_code=303)
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        return RedirectResponse(f"{root_path}/login", status_code=303)
    if user.role != "superadmin":
        return RedirectResponse(f"{root_path}/dashboard", status_code=303)

    telemetry = compute_platform_impact_telemetry(db=db, k_threshold=3)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="superadmin_impact.html",
        context={
            "title": "Auditoría de Impacto (F-DC-125) · Datapyme Empresarial",
            "current_user": user,
            "telemetry": telemetry,
            "root_path": root_path,
        },
    )


@router.get("/api/admin/impact")
def get_admin_impact_telemetry(
    k_threshold: int = Query(default=3, ge=3, le=10),
    _admin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db),
):
    return compute_platform_impact_telemetry(db=db, k_threshold=k_threshold)


@router.get("/api/me/export")
def export_my_tenant_data(
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    return export_habeas_data_bundle(db=db, tenant_id=tenant.id, user_id=user.id)


@router.post("/api/me/deletion-request")
def request_my_tenant_deletion(
    payload: DeletionRequestPayload,
    request: Request,
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    ip_raw = request.client.host if request.client else "127.0.0.1"
    ua_raw = request.headers.get("user-agent", "testclient")
    return request_habeas_data_deletion(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        reason=payload.reason,
        ip_raw=ip_raw,
        ua_raw=ua_raw,
    )
