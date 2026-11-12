"""Rutas de autenticación, sesión y registro de empresas (Sprints 1 y 7, F-DC-124)."""

from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import (
    SESSION_COOKIE,
    SESSION_HOURS,
    _as_aware,
    authenticate_user,
    get_db,
)
from app.core.models import (
    CompanyUIPreference,
    LegalConsent,
    SessionToken,
    Tenant,
    User,
    UserViewSetting,
    utcnow,
)
from app.core.schemas import LoginRequest, RegisterRequest
from app.core.security import (
    compute_consent_row_hash,
    generate_session_token,
    hash_password,
    sha256_hex,
)
from app.ui.ui_personalization_service import (
    DiagnosisInput,
    build_layout_config,
    compute_priority_weights,
)

router = APIRouter(tags=["auth"])


@router.post("/api/auth/login")
def api_login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user, raw_token = authenticate_user(db, request, payload.email, payload.password)
    return {"access_token": raw_token, "role": user.role, "tenant_id": user.tenant_id}


@router.get("/", include_in_schema=False)
def root_redirect(request: Request, db: Session = Depends(get_db)):
    root_path = request.scope.get("root_path", "").rstrip("/")
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        tok_hash = sha256_hex(raw_token)
        sess = db.query(SessionToken).filter_by(token_hash=tok_hash).first()
        if sess and sess.revoked_at is None and _as_aware(sess.expires_at) > utcnow():
            user = db.get(User, sess.user_id)
            if user and user.is_active and user.role == "superadmin":
                return RedirectResponse(f"{root_path}/admin/impacto", status_code=303)
    return RedirectResponse(f"{root_path}/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    templates = request.app.state.templates
    root_path = request.scope.get("root_path", "").rstrip("/")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "root_path": root_path},
    )


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    try:
        user, raw_token = authenticate_user(db, request, email, password)
    except HTTPException as exc:
        root_path = request.scope.get("root_path", "").rstrip("/")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": exc.detail, "root_path": root_path},
            status_code=exc.status_code,
        )
    root_path = request.scope.get("root_path", "").rstrip("/")
    target = f"{root_path}/admin/impacto" if user.role == "superadmin" else f"{root_path}/dashboard"
    redirect = RedirectResponse(target, status_code=303)
    settings = request.app.state.settings
    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
        or settings.environment in ("production", "review")
    )
    redirect.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        secure=is_https,
        samesite="lax",
        path="/",
    )
    return redirect


@router.post("/logout", include_in_schema=False)
def logout(request: Request, db: Session = Depends(get_db)):
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        sess = db.query(SessionToken).filter_by(token_hash=sha256_hex(raw_token)).first()
        if sess and sess.revoked_at is None:
            sess.revoked_at = utcnow()
            db.commit()
    root_path = request.scope.get("root_path", "").rstrip("/")
    redirect = RedirectResponse(f"{root_path}/login", status_code=303)
    redirect.delete_cookie(SESSION_COOKIE, path="/")
    return redirect


@router.post("/api/auth/register", status_code=201)
def register_tenant(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if not (payload.accept_data_policy and payload.accept_terms_mvp):
        raise HTTPException(
            status_code=422,
            detail="Debe aceptar la Política de Tratamiento de Datos (Ley 1581) y los Términos del MVP.",
        )
    norm_email = payload.email.strip().lower()
    if db.query(User).filter_by(email=norm_email).first():
        raise HTTPException(status_code=409, detail="El correo ya está registrado.")

    tenant = Tenant(
        legal_name=payload.legal_name.strip(),
        subsector=payload.subsector,
        size=payload.size,
        research_stats_opt_in=payload.accept_aggregate_stats,
    )
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=norm_email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    db.flush()

    ip_raw = request.client.host if request.client else "127.0.0.1"
    ua_raw = request.headers.get("user-agent", "testclient")
    ip_h = sha256_hex(ip_raw)
    ua_h = sha256_hex(ua_raw)

    docs = [
        ("data_policy", "v1.0", "accept"),
        ("terms_mvp", "v1.0", "accept"),
        (
            "aggregate_stats_research",
            "v1.0",
            "accept" if payload.accept_aggregate_stats else "revoke",
        ),
    ]
    prev_h = "0" * 64
    for idx, (doc_type, doc_ver, action) in enumerate(docs):
        ts = utcnow() + timedelta(milliseconds=idx)
        doc_sha = sha256_hex(f"{doc_type}:{doc_ver}")
        row_h = compute_consent_row_hash(
            tenant_id=tenant.id,
            user_id=user.id,
            document_type=doc_type,
            document_version=doc_ver,
            document_sha256=doc_sha,
            action=action,
            accepted_iso=ts.isoformat(),
            prev_hash=prev_h,
        )
        consent = LegalConsent(
            tenant_id=tenant.id,
            user_id=user.id,
            document_type=doc_type,
            document_version=doc_ver,
            document_sha256=doc_sha,
            action=action,
            accepted_at=ts,
            ip_hash=ip_h,
            user_agent_hash=ua_h,
            prev_hash=prev_h,
            row_hash=row_h,
        )
        db.add(consent)
        prev_h = row_h

    diag_in = DiagnosisInput(
        M10=payload.diagnosis.M10,
        M12=payload.diagnosis.M12,
        M17=payload.diagnosis.M17,
        M07=payload.diagnosis.M07,
        M08=payload.diagnosis.M08,
        M13=payload.diagnosis.M13,
        M15=payload.diagnosis.M15,
    )
    profile = compute_priority_weights(diag_in)
    ui_pref = CompanyUIPreference(
        tenant_id=tenant.id,
        source="onboarding_quiz",
        diagnosis_answers=diag_in.to_dict(),
        mapping_version=profile.mapping_version,
        priority_weights={
            "weight_sales": profile.weight_sales,
            "weight_inventory": profile.weight_inventory,
            "weight_predictive": profile.weight_predictive,
        },
        weight_sales=Decimal(str(profile.weight_sales)),
        weight_inventory=Decimal(str(profile.weight_inventory)),
        weight_predictive=Decimal(str(profile.weight_predictive)),
        primary_focus=profile.primary_focus,
        secondary_focus=profile.secondary_focus,
        preferred_chart_density=profile.preferred_chart_density,
    )
    db.add(ui_pref)

    view_setting = UserViewSetting(
        user_id=user.id,
        tenant_id=tenant.id,
        view_mode="personalized",
    )
    db.add(view_setting)

    raw_token, tok_hash = generate_session_token()
    sess = SessionToken(
        user_id=user.id,
        token_hash=tok_hash,
        csrf_secret=sha256_hex(raw_token + "|csrf"),
        expires_at=utcnow() + timedelta(hours=12),
        ip_hash=ip_h,
    )
    db.add(sess)
    db.commit()

    return {
        "tenant_id": tenant.id,
        "user_id": user.id,
        "access_token": raw_token,
        "layout_config": build_layout_config(profile, view_mode="personalized"),
    }
