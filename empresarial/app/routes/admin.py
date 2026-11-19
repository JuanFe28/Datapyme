"""Rutas de auditoría de impacto para SuperAdmin y derechos de Habeas Data."""

import csv
import io
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import ROOT
from app.core.dependencies import (
    SESSION_COOKIE,
    check_and_touch_session,
    ensure_production_account,
    get_current_context,
    get_db,
    get_superadmin_user,
)
from app.core.models import SessionToken, Tenant, User, utcnow
from app.core.provisioning_service import provision_real_client_tenant
from app.core.research_sync_service import (
    build_credentials_report_csv,
    generate_temp_password,
    list_real_client_credentials,
    sync_research_companies,
)
from app.core.schemas import DeletionRequestPayload, ProvisionTenantRequest
from app.core.security import hash_password, sha256_hex
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
    if not check_and_touch_session(db, sess, request):
        if getattr(request.state, "session_expired_inactivity", False):
            redirect = RedirectResponse(f"{root_path}/login?motivo=inactividad", status_code=303)
            redirect.delete_cookie(SESSION_COOKIE, path="/")
            return redirect
        return RedirectResponse(f"{root_path}/login", status_code=303)
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        return RedirectResponse(f"{root_path}/login", status_code=303)
    if user.role != "superadmin":
        return RedirectResponse(f"{root_path}/dashboard", status_code=303)
    ensure_production_account(request, db, user)

    telemetry = compute_platform_impact_telemetry(db=db, k_threshold=3)
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    base_url = f"{scheme}://{host}{root_path}" if host else root_path
    real_clients = list_real_client_credentials(db, access_url=base_url)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="superadmin_impact.html",
        context={
            "title": "Auditoría de Impacto (F-DC-125) · Datapyme Empresarial",
            "current_user": user,
            "telemetry": telemetry,
            "real_clients": real_clients,
            "active_token": raw_token,
            "root_path": root_path,
        },
    )


@router.post("/api/admin/tenants/provision", status_code=201)
def provision_tenant_endpoint(
    payload: ProvisionTenantRequest,
    request: Request,
    _admin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db),
):
    root_path = request.scope.get("root_path", "").rstrip("/")
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    base_url = f"{scheme}://{host}{root_path}" if host else root_path
    return provision_real_client_tenant(
        db,
        trade_name=payload.trade_name,
        legal_name=payload.legal_name,
        subsector=payload.subsector,
        size=payload.size,
        municipality=payload.municipality,
        owner_full_name=payload.owner_full_name,
        email=payload.email,
        phone=payload.phone,
        temporary_password=payload.temporary_password,
        priority_focus=payload.priority_focus,
        density=payload.density,
        tax_status=payload.tax_status,
        starter_catalog=payload.starter_catalog,
        access_url=base_url,
    )


@router.post("/api/admin/tenants/sync-research")
def sync_from_research_studio_endpoint(
    request: Request,
    _admin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db),
):
    root_path = request.scope.get("root_path", "").rstrip("/")
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    base_url = f"{scheme}://{host}{root_path}" if host else root_path
    research_db_url = (os.getenv("RESEARCH_DATABASE_URL") or "").strip() or None
    research_db = None if research_db_url else (ROOT.parent / "datapyme_local.db")
    results = sync_research_companies(
        db,
        database_url=research_db_url,
        sqlite_path=research_db,
        access_url=base_url,
    )
    created_count = sum(1 for r in results if r.get("created_now"))
    return {"synced_count": len(results), "created_count": created_count, "clients": results}


@router.get("/api/admin/tenants/credentials-report")
def export_credentials_report(
    request: Request,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    _admin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db),
):
    root_path = request.scope.get("root_path", "").rstrip("/")
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    base_url = f"{scheme}://{host}{root_path}" if host else root_path
    rows = list_real_client_credentials(db, access_url=base_url)
    if format == "csv":
        csv_body = build_credentials_report_csv(rows)
        return PlainTextResponse(
            content=csv_body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="datapyme_credenciales_clientes.csv"'},
        )
    return {"clients": rows}


@router.post("/api/admin/users/{user_id}/reset-mfa")
def reset_client_mfa_endpoint(
    user_id: str,
    _admin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.role == "superadmin":
        raise HTTPException(status_code=404, detail="Usuario de empresa no encontrado.")
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_backup_codes = None
    db.commit()
    return {"user_id": user.id, "mfa_enabled": False}


@router.post("/api/admin/users/{user_id}/reset-temporary-password")
def reset_pending_password(
    user_id: str,
    _admin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.role != "owner" or not user.is_active:
        raise HTTPException(status_code=404, detail="Usuario de empresa no encontrado.")
    if not user.must_change_password:
        raise HTTPException(
            status_code=409,
            detail="La cuenta ya fue activada; este control solo renueva claves iniciales.",
        )
    password = generate_temp_password()
    user.password_hash = hash_password(password)
    user.failed_logins, user.locked_until = 0, None
    for session in db.query(SessionToken).filter_by(user_id=user.id, revoked_at=None):
        session.revoked_at = utcnow()
    db.commit()
    return {"user_id": user.id, "temporary_password": password, "shown_once": True}


@router.get("/api/admin/impact")
def get_admin_impact_telemetry(
    k_threshold: int = Query(default=3, ge=3, le=10),
    _admin: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db),
):
    return compute_platform_impact_telemetry(db=db, k_threshold=k_threshold)


@router.get("/api/me/export")
def export_my_tenant_data(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    ctx: tuple[User, Tenant] = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, tenant = ctx
    bundle = export_habeas_data_bundle(db=db, tenant_id=tenant.id, user_id=user.id)
    if format == "json":
        return bundle
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["section", "record_id", "field", "value"])

    def cell(value):
        text = str(value) if value is not None else ""
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text

    for section, records in bundle.items():
        for record in records if isinstance(records, list) else [records]:
            fields = record if isinstance(record, dict) else {"value": record}
            for field, value in fields.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                writer.writerow([cell(section), cell(fields.get("id", "")), cell(field), cell(value)])
    return PlainTextResponse(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="datapyme_datos.csv"',
            "Cache-Control": "no-store",
        },
    )


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
