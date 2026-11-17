"""Rutas de autenticación, sesión y registro de empresas (Sprints 1 y 7, F-DC-124)."""

from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from sqlalchemy.orm import Session

from app.core.dependencies import (
    SESSION_COOKIE,
    SESSION_HOURS,
    _as_aware,
    _extract_token,
    authenticate_user,
    get_db,
    get_session_user_from_request,
)
from app.core.mfa_service import (
    build_totp_uri,
    generate_backup_codes,
    generate_totp_secret,
    render_qr_svg_inline,
    verify_or_consume_backup_code,
    verify_totp_code,
)
from app.core.models import (
    CompanyTaxChange,
    CompanyUIPreference,
    SessionToken,
    Tenant,
    User,
    UserViewSetting,
    utcnow,
)
from app.core.provisioning_service import (
    DENSITY_LABELS,
    FOCUS_LABELS,
    record_legal_consents_chain,
)
from app.core.research_sync_service import extract_phone_and_email, make_unique_username
from app.core.schemas import LoginRequest, MfaConfirmRequest, RegisterRequest
from app.core.security import (
    generate_session_token,
    hash_password,
    sha256_hex,
    verify_password,
)
from app.ui.ui_personalization_service import (
    DiagnosisInput,
    build_layout_config,
    compute_priority_weights,
)

router = APIRouter(tags=["auth"])
MFA_PENDING_COOKIE = "dp_mfa_pending"


def _is_https_request(request: Request) -> bool:
    settings = request.app.state.settings
    return (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
        or settings.environment in ("production", "review")
    )


def _issue_user_session(db: Session, request: Request, user: User) -> str:
    raw_token, tok_hash = generate_session_token()
    ip_raw = request.client.host if request.client else "127.0.0.1"
    db.add(
        SessionToken(
            user_id=user.id,
            token_hash=tok_hash,
            csrf_secret=sha256_hex(raw_token + "|csrf"),
            expires_at=utcnow() + timedelta(hours=SESSION_HOURS),
            ip_hash=sha256_hex(ip_raw),
        )
    )
    db.commit()
    return raw_token


def _target_after_login(root_path: str, user: User) -> str:
    if user.role == "superadmin":
        return f"{root_path}/admin/impacto"
    if user.must_change_password:
        return f"{root_path}/auth/activar-cuenta"
    return f"{root_path}/dashboard"


def _set_session_cookie_and_redirect(request: Request, target: str, raw_token: str) -> RedirectResponse:
    redirect = RedirectResponse(target, status_code=303)
    redirect.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        secure=_is_https_request(request),
        samesite="lax",
        path="/",
    )
    return redirect


@router.post("/api/auth/login")
def api_login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user, _ = authenticate_user(db, request, payload.email, payload.password, create_session=False)
    if user.mfa_enabled:
        code = (payload.totp_code or "").strip()
        if not code:
            raise HTTPException(
                status_code=403,
                detail="Se requiere el código temporal de verificación en dos pasos (2FA).",
            )
        if not (verify_totp_code(user.mfa_secret, code) or verify_or_consume_backup_code(user, code)):
            raise HTTPException(status_code=401, detail="Código de verificación en dos pasos inválido.")
    raw_token = _issue_user_session(db, request, user)
    return {
        "access_token": raw_token,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "must_change_password": bool(user.must_change_password),
        "mfa_enabled": bool(user.mfa_enabled),
    }


@router.get("/", include_in_schema=False)
def root_redirect(request: Request, db: Session = Depends(get_db)):
    root_path = request.scope.get("root_path", "").rstrip("/")
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        tok_hash = sha256_hex(raw_token)
        sess = db.query(SessionToken).filter_by(token_hash=tok_hash).first()
        if sess and sess.revoked_at is None and _as_aware(sess.expires_at) > utcnow():
            user = db.get(User, sess.user_id)
            if user and user.is_active:
                if user.role == "superadmin":
                    return RedirectResponse(f"{root_path}/admin/impacto", status_code=303)
                if user.must_change_password:
                    return RedirectResponse(f"{root_path}/auth/activar-cuenta", status_code=303)
    return RedirectResponse(f"{root_path}/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, modo: str | None = None):
    templates = request.app.state.templates
    root_path = request.scope.get("root_path", "").rstrip("/")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
            "root_path": root_path,
            "audit_mode": (modo == "auditor"),
        },
    )


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    root_path = request.scope.get("root_path", "").rstrip("/")
    audit_mode = request.query_params.get("modo") == "auditor" or "modo=auditor" in request.headers.get(
        "referer", ""
    )
    try:
        user, _ = authenticate_user(db, request, email, password, create_session=False)
    except HTTPException as exc:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": exc.detail, "root_path": root_path, "audit_mode": audit_mode},
            status_code=exc.status_code,
        )

    if user.mfa_enabled:
        signer = TimestampSigner(request.app.state.settings.secret_key)
        signed_uid = signer.sign(user.id).decode("utf-8")
        redirect = RedirectResponse(f"{root_path}/login/mfa", status_code=303)
        redirect.set_cookie(
            MFA_PENDING_COOKIE,
            signed_uid,
            max_age=300,
            httponly=True,
            secure=_is_https_request(request),
            samesite="lax",
            path="/",
        )
        return redirect

    raw_token = _issue_user_session(db, request, user)
    target = _target_after_login(root_path, user)
    return _set_session_cookie_and_redirect(request, target, raw_token)


@router.get("/login/mfa", response_class=HTMLResponse, include_in_schema=False)
def login_mfa_page(request: Request, db: Session = Depends(get_db)):
    root_path = request.scope.get("root_path", "").rstrip("/")
    pending = request.cookies.get(MFA_PENDING_COOKIE)
    if not pending:
        return RedirectResponse(f"{root_path}/login", status_code=303)
    signer = TimestampSigner(request.app.state.settings.secret_key)
    try:
        uid = signer.unsign(pending, max_age=300).decode("utf-8")
    except (BadSignature, SignatureExpired):
        return RedirectResponse(f"{root_path}/login", status_code=303)
    user = db.get(User, uid)
    if not user or not user.is_active or not user.mfa_enabled:
        return RedirectResponse(f"{root_path}/login", status_code=303)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="login_mfa.html",
        context={
            "root_path": root_path,
            "error": None,
            "account_hint": user.username or user.email,
        },
    )


@router.post("/login/mfa", response_class=HTMLResponse, include_in_schema=False)
def login_mfa_submit(
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    root_path = request.scope.get("root_path", "").rstrip("/")
    pending = request.cookies.get(MFA_PENDING_COOKIE)
    if not pending:
        return RedirectResponse(f"{root_path}/login", status_code=303)
    signer = TimestampSigner(request.app.state.settings.secret_key)
    try:
        uid = signer.unsign(pending, max_age=300).decode("utf-8")
    except (BadSignature, SignatureExpired):
        return RedirectResponse(f"{root_path}/login", status_code=303)
    user = db.get(User, uid)
    if not user or not user.is_active or not user.mfa_enabled:
        return RedirectResponse(f"{root_path}/login", status_code=303)

    if not (verify_totp_code(user.mfa_secret, code) or verify_or_consume_backup_code(user, code)):
        db.commit()
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="login_mfa.html",
            context={
                "root_path": root_path,
                "error": "Código incorrecto o expirado. Verifica tu app autenticadora o usa un código de recuperación.",
                "account_hint": user.username or user.email,
            },
            status_code=401,
        )

    raw_token = _issue_user_session(db, request, user)
    target = _target_after_login(root_path, user)
    resp = _set_session_cookie_and_redirect(request, target, raw_token)
    resp.delete_cookie(MFA_PENDING_COOKIE, path="/")
    return resp


@router.post("/api/auth/mfa/setup")
def mfa_setup(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw_token = _extract_token(request, authorization)
    sess = db.query(SessionToken).filter_by(token_hash=sha256_hex(raw_token)).first()
    if not sess or sess.revoked_at is not None or _as_aware(sess.expires_at) <= utcnow():
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Sesión inválida.")

    secret = generate_totp_secret()
    account_label = user.username or user.email
    uri = build_totp_uri(secret, account_label)
    qr_svg = render_qr_svg_inline(uri)
    plain_codes, hashed_codes = generate_backup_codes(count=5)

    user.mfa_secret = secret
    user.mfa_backup_codes = hashed_codes
    user.mfa_enabled = False
    db.commit()

    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_svg": qr_svg,
        "backup_codes": plain_codes,
    }


@router.post("/api/auth/mfa/confirm")
def mfa_confirm(
    payload: MfaConfirmRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw_token = _extract_token(request, authorization)
    sess = db.query(SessionToken).filter_by(token_hash=sha256_hex(raw_token)).first()
    if not sess or sess.revoked_at is not None or _as_aware(sess.expires_at) <= utcnow():
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="Primero inicia la configuración del código QR 2FA.")

    if not verify_totp_code(user.mfa_secret, payload.code):
        raise HTTPException(
            status_code=422,
            detail="El código de 6 dígitos no coincide. Verifica la hora de tu celular e intenta de nuevo.",
        )
    user.mfa_enabled = True
    db.commit()
    return {"mfa_enabled": True}


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

    norm_phone, _ = extract_phone_and_email(payload.phone or "", "cliente")
    username = make_unique_username(db, payload.legal_name.strip())
    user = User(
        tenant_id=tenant.id,
        email=norm_email,
        username=username,
        phone=norm_phone,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    db.flush()

    if payload.tax_status != "pending":
        db.add(
            CompanyTaxChange(
                tenant_id=tenant.id,
                revision=1,
                status=payload.tax_status,
                reason="Condición declarada al registrar empresa",
                changed_by=user.id,
            )
        )

    ip_raw = request.client.host if request.client else "127.0.0.1"
    ua_raw = request.headers.get("user-agent", "testclient")
    ip_h = sha256_hex(ip_raw)
    record_legal_consents_chain(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        accept_aggregate_stats=payload.accept_aggregate_stats,
        ip_raw=ip_raw,
        ua_raw=ua_raw,
    )

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


def _activation_context(db: Session, request: Request, user: User, error: str | None = None) -> dict:
    root_path = request.scope.get("root_path", "").rstrip("/")
    tenant = db.get(Tenant, user.tenant_id)
    pref = db.query(CompanyUIPreference).filter_by(tenant_id=user.tenant_id).first()
    focus = pref.primary_focus if pref else "balanced"
    density = pref.preferred_chart_density if pref else "standard"
    company_name = ((tenant.trade_name or tenant.legal_name) if tenant else "Tu Empresa").strip()
    return {
        "error": error,
        "root_path": root_path,
        "active_token": request.cookies.get(SESSION_COOKIE, ""),
        "user": user,
        "company_name": company_name,
        "focus_label": FOCUS_LABELS.get(focus, focus),
        "density_label": DENSITY_LABELS.get(density, density),
    }


@router.get("/auth/activar-cuenta", response_class=HTMLResponse, include_in_schema=False)
def activate_account_page(request: Request, db: Session = Depends(get_db)):
    root_path = request.scope.get("root_path", "").rstrip("/")
    user = get_session_user_from_request(request, db, request.headers.get("authorization"))
    if not user or user.role == "superadmin" or not user.tenant_id:
        return RedirectResponse(f"{root_path}/login", status_code=303)
    if not user.must_change_password:
        return RedirectResponse(f"{root_path}/dashboard", status_code=303)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="activate_account.html",
        context=_activation_context(db, request, user),
    )


@router.post("/auth/activar-cuenta", response_class=HTMLResponse, include_in_schema=False)
def activate_account_submit(
    request: Request,
    password: str = Form(...),
    confirm_password: str = Form(...),
    accept_data_policy: bool = Form(False),
    accept_aggregate_stats: bool = Form(False),
    db: Session = Depends(get_db),
):
    root_path = request.scope.get("root_path", "").rstrip("/")
    user = get_session_user_from_request(request, db, request.headers.get("authorization"))
    if not user or user.role == "superadmin" or not user.tenant_id:
        return RedirectResponse(f"{root_path}/login", status_code=303)

    templates = request.app.state.templates
    if len(password) < 10:
        return templates.TemplateResponse(
            request=request,
            name="activate_account.html",
            context=_activation_context(
                db, request, user, "La nueva contraseña debe tener al menos 10 caracteres."
            ),
            status_code=422,
        )
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="activate_account.html",
            context=_activation_context(db, request, user, "Las contraseñas ingresadas no coinciden."),
            status_code=422,
        )
    if verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="activate_account.html",
            context=_activation_context(
                db,
                request,
                user,
                "Debes elegir una contraseña privada distinta a la clave temporal entregada.",
            ),
            status_code=422,
        )
    if not accept_data_policy:
        return templates.TemplateResponse(
            request=request,
            name="activate_account.html",
            context=_activation_context(
                db,
                request,
                user,
                "Debes aceptar la Política de Tratamiento de Datos (Ley 1581 de 2012) para continuar.",
            ),
            status_code=422,
        )

    tenant = db.get(Tenant, user.tenant_id)
    if not tenant:
        return RedirectResponse(f"{root_path}/login", status_code=303)

    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    tenant.research_stats_opt_in = bool(accept_aggregate_stats)

    ip_raw = request.client.host if request.client else "127.0.0.1"
    ua_raw = request.headers.get("user-agent", "browser")
    record_legal_consents_chain(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        accept_aggregate_stats=bool(accept_aggregate_stats),
        ip_raw=ip_raw,
        ua_raw=ua_raw,
    )
    db.commit()
    return RedirectResponse(f"{root_path}/dashboard", status_code=303)


@router.get("/registro", response_class=HTMLResponse, include_in_schema=False)
def register_page(request: Request):
    root_path = request.scope.get("root_path", "").rstrip("/")
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"root_path": root_path},
    )
