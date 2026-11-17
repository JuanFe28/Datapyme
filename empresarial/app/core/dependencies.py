"""Dependencias de autenticación, sesión y contexto de base de datos para FastAPI."""

import re
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.models import SessionToken, Tenant, User, utcnow
from app.core.security import generate_session_token, sha256_hex, verify_password

SESSION_COOKIE = "dp_session"
SESSION_HOURS = 12
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite devuelve datetimes sin zona horaria; se normalizan a UTC para comparar."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _extract_token(request: Request, authorization: str | None) -> str:
    """Bearer para la API; cookie HttpOnly solo para lecturas (GET/HEAD) del navegador (anti-CSRF)."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    cookie_token = request.cookies.get(SESSION_COOKIE)
    if cookie_token:
        if request.method not in ("GET", "HEAD"):
            raise HTTPException(
                status_code=403,
                detail="La sesión por cookie solo permite consultas de lectura; use Authorization: Bearer.",
            )
        return cookie_token
    raise HTTPException(status_code=401, detail="Autenticación requerida.")


def get_db(request: Request):
    """Generador de sesión de base de datos desacoplado del motor global."""
    SessionLocal = request.app.state.Session
    with SessionLocal() as db:
        yield db


def ensure_production_account(request: Request, db: Session, user: User) -> None:
    """Las credenciales públicas de demostración no habilitan acceso al piloto real."""
    if request.app.state.settings.environment not in ("production", "review"):
        return
    tenant = db.get(Tenant, user.tenant_id) if user.tenant_id else None
    if (
        user.email == "superadmin.demo@datapyme.co"
        or user.email.startswith("demo.")
        or (tenant and tenant.legal_name.startswith("[DEMO-FDC125]"))
    ):
        raise HTTPException(
            status_code=403,
            detail="Cuenta de demostración deshabilitada en producción. Use su cuenta privada.",
        )


def get_session_user_from_request(
    request: Request,
    db: Session,
    authorization: str | None = None,
) -> User | None:
    """Resuelve el usuario autenticado vía cookie o Bearer sin lanzar excepción."""
    raw_token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.removeprefix("Bearer ").strip()
    else:
        raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return None
    sess = db.query(SessionToken).filter_by(token_hash=sha256_hex(raw_token)).first()
    if not sess or sess.revoked_at is not None or _as_aware(sess.expires_at) <= utcnow():
        return None
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        return None
    ensure_production_account(request, db, user)
    return user


def get_current_context(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> tuple[User, Tenant]:
    """Obtiene el usuario operativo y su empresa asociada para la petición actual."""
    raw_token = _extract_token(request, authorization)
    tok_hash = sha256_hex(raw_token)
    sess = db.query(SessionToken).filter_by(token_hash=tok_hash).first()
    if not sess or sess.revoked_at is not None or _as_aware(sess.expires_at) <= utcnow():
        raise HTTPException(status_code=401, detail="Sesión inválida, expirada o revocada.")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active or not user.tenant_id or user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso operativo denegado.")
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail="Activación pendiente: defina su contraseña definitiva en /auth/activar-cuenta.",
        )
    ensure_production_account(request, db, user)
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant or tenant.status != "active":
        raise HTTPException(status_code=403, detail="Empresa inactiva.")
    return user, tenant


def get_superadmin_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Obtiene el usuario con rol de auditoría SuperAdmin (F-DC-125)."""
    raw_token = _extract_token(request, authorization)
    tok_hash = sha256_hex(raw_token)
    sess = db.query(SessionToken).filter_by(token_hash=tok_hash).first()
    if not sess or sess.revoked_at is not None or _as_aware(sess.expires_at) <= utcnow():
        raise HTTPException(status_code=401, detail="Sesión inválida, expirada o revocada.")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active or user.role != "superadmin" or user.tenant_id is not None:
        raise HTTPException(
            status_code=403,
            detail="Acceso exclusivo para el rol de auditoría SuperAdmin (F-DC-125).",
        )
    ensure_production_account(request, db, user)
    return user


def _find_user_by_identifier(db: Session, identifier: str) -> User | None:
    """Resuelve usuario por correo, nombre de usuario corto o celular (10 dígitos)."""
    ident = (identifier or "").strip().lower()
    if not ident:
        return None
    digits = re.sub(r"\D", "", ident)
    if digits.startswith("57") and len(digits) == 12:
        digits = digits[2:]
    if "@" in ident:
        return db.query(User).filter(User.email == ident).first()
    if len(digits) == 10 and re.fullmatch(r"[\d\s+\-().]+", ident):
        return db.query(User).filter(or_(User.phone == digits, User.username == ident)).first()
    return db.query(User).filter(or_(User.username == ident, User.email == ident)).first()


def authenticate_user(
    db: Session,
    request: Request,
    email: str,
    password: str,
    create_session: bool = True,
) -> tuple[User, str]:
    """Login triple (usuario, correo o celular) con bloqueo temporal tras fallos."""
    now = utcnow()
    user = _find_user_by_identifier(db, email)
    if user:
        ensure_production_account(request, db, user)
        if user.must_change_password and user.tenant_id:
            tenant = db.get(Tenant, user.tenant_id)
            if tenant and tenant.research_company_id:
                from app.core.research_sync_service import normalize_username

                # Bloquear únicamente el esquema heredado; nunca recuperar ni mostrar esa clave.
                prefix = (
                    re.sub(r"[^a-zA-Z]", "", normalize_username(tenant.trade_name or tenant.legal_name))[
                        :6
                    ].capitalize()
                    or "Cliente"
                )
                legacy = f"Dp{prefix}{2026 + tenant.research_company_id}!"
                if verify_password(legacy, user.password_hash):
                    raise HTTPException(
                        status_code=403,
                        detail="La clave temporal antigua debe renovarse. Solicite una nueva al administrador.",
                    )
    locked_until = _as_aware(user.locked_until) if user else None
    if user and locked_until and locked_until > now:
        raise HTTPException(
            status_code=429, detail="Cuenta bloqueada temporalmente por intentos fallidos."
        )
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_logins = 0
            db.commit()
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    user.last_login_at = now
    if not create_session:
        db.commit()
        return user, ""
    user.failed_logins = 0
    user.locked_until = None
    raw_token, tok_hash = generate_session_token()
    ip_raw = request.client.host if request.client else "127.0.0.1"
    db.add(
        SessionToken(
            user_id=user.id,
            token_hash=tok_hash,
            csrf_secret=sha256_hex(raw_token + "|csrf"),
            expires_at=now + timedelta(hours=SESSION_HOURS),
            ip_hash=sha256_hex(ip_raw),
        )
    )
    db.commit()
    return user, raw_token
