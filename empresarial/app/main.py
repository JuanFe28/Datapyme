"""Fábrica ASGI de Datapyme Empresarial (MVP SaaS — F-DC-124)."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.analytics.kpis import get_tenant_kpis_payload
from app.core.commercial_service import (
    THREE_PLACES,
    TWO_PLACES,
    classify_inventory_alerts,
    create_product_with_initial_stock,
    create_sale_atomic,
    import_products_batch,
    import_sales_batch,
    parse_colombian_decimal,
    record_inventory_movement,
    sanitize_cell_text,
    serialize_product,
    void_sale_atomic,
)
from app.core.config import ROOT, Settings
from app.core.image_service import save_product_image
from app.core.models import (
    Base,
    CompanyUIPreference,
    LegalConsent,
    Product,
    Sale,
    SessionToken,
    Tenant,
    User,
    UserViewSetting,
    utcnow,
)
from app.core.security import (
    compute_consent_row_hash,
    generate_session_token,
    hash_password,
    sha256_hex,
    verify_password,
)
from app.forecast.stats import get_tenant_forecast_payload
from app.telemetry.impact_service import (
    compute_platform_impact_telemetry,
    export_habeas_data_bundle,
    request_habeas_data_deletion,
)
from app.ui.ui_personalization_service import (
    DiagnosisInput,
    PriorityProfile,
    build_layout_config,
    compute_priority_weights,
)


class DiagnosisPayload(BaseModel):
    M10: list[str] = Field(default_factory=list)
    M12: list[str] = Field(default_factory=list)
    M17: str = ""
    M07: list[str] = Field(default_factory=list)
    M08: list[str] = Field(default_factory=list)
    M13: str = "No"
    M15: list[str] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    legal_name: str
    subsector: str
    size: str = "pequena"
    email: str
    full_name: str
    password: str
    accept_data_policy: bool
    accept_terms_mvp: bool
    accept_aggregate_stats: bool = False
    diagnosis: DiagnosisPayload


SESSION_COOKIE = "dp_session"
SESSION_HOURS = 12
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


class LoginRequest(BaseModel):
    email: str
    password: str


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


class ViewModeUpdate(BaseModel):
    view_mode: Literal["personalized", "general"]


class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    category: str = "General"
    unit: str = "und"
    cost_price: str | float | int
    sale_price: str | float | int
    vat_rate: str | float | int = "19.00"
    initial_stock: str | float | int = "0"
    min_stock: str | float | int = "0"
    image_url: str | None = None


class ProductUpdateRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    cost_price: str | float | int | None = None
    sale_price: str | float | int | None = None
    min_stock: str | float | int | None = None
    image_url: str | None = None
    is_active: bool | None = None


class InventoryMovementRequest(BaseModel):
    product_id: str
    movement_type: Literal["purchase_in", "return_in", "adjustment_in", "adjustment_out"]
    quantity: str | float | int
    unit_cost: str | float | int | None = None
    reason: str


class SaleItemRequest(BaseModel):
    product_id: str
    quantity: str | float | int
    unit_price: str | float | int | None = None
    discount: str | float | int = "0.00"


class SaleCreateRequest(BaseModel):
    customer_label: str | None = "Cliente Mostrador"
    payment_method: Literal["cash", "card", "transfer", "credit", "other"] = "cash"
    items: list[SaleItemRequest]


class DeletionRequestPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=280)


def _serialize_sale(sale: Sale) -> dict[str, Any]:
    return {
        "id": sale.id,
        "tenant_id": sale.tenant_id,
        "sale_number": sale.sale_number,
        "occurred_at": sale.occurred_at.isoformat() if sale.occurred_at else None,
        "customer_label": sale.customer_label,
        "payment_method": sale.payment_method,
        "subtotal": str(Decimal(str(sale.subtotal)).quantize(TWO_PLACES)),
        "discount_total": str(Decimal(str(sale.discount_total)).quantize(TWO_PLACES)),
        "vat_total": str(Decimal(str(sale.vat_total)).quantize(TWO_PLACES)),
        "total": str(Decimal(str(sale.total)).quantize(TWO_PLACES)),
        "cogs_total": str(Decimal(str(sale.cogs_total)).quantize(TWO_PLACES)),
        "status": sale.status,
        "source": sale.source,
        "items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "quantity": str(Decimal(str(it.quantity)).quantize(THREE_PLACES)),
                "unit_price": str(Decimal(str(it.unit_price)).quantize(TWO_PLACES)),
                "unit_cost_snapshot": str(Decimal(str(it.unit_cost_snapshot)).quantize(TWO_PLACES)),
                "vat_rate": str(Decimal(str(it.vat_rate)).quantize(TWO_PLACES)),
                "discount": str(Decimal(str(it.discount)).quantize(TWO_PLACES)),
                "line_total": str(Decimal(str(it.line_total)).quantize(TWO_PLACES)),
            }
            for it in sale.items
        ],
    }


def create_app(database_url: str | None = None, testing: bool = False) -> FastAPI:
    settings = Settings.from_env(database_url)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    engine = create_engine(settings.database_url, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            try:
                cols = [r[1] for r in conn.execute(text("PRAGMA table_info(products)")).fetchall()]
                if cols and "image_url" not in cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(512)"))
                    conn.commit()
            except Exception as exc:
                logging.getLogger("uvicorn.error").warning(f"Auto-migración products.image_url: {exc}")
        (ROOT / "static" / "uploads").mkdir(parents=True, exist_ok=True)
        yield
        engine.dispose()

    application = FastAPI(
        title="Datapyme Empresarial SaaS",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.Session = SessionLocal
    application.state.settings = settings

    @application.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "same-origin",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                    "frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
                ),
            }
        )
        return response

    def get_db():
        with SessionLocal() as db:
            yield db

    def get_current_context(
        request: Request,
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> tuple[User, Tenant]:
        raw_token = _extract_token(request, authorization)
        tok_hash = sha256_hex(raw_token)
        sess = db.query(SessionToken).filter_by(token_hash=tok_hash).first()
        if not sess or sess.revoked_at is not None or _as_aware(sess.expires_at) <= utcnow():
            raise HTTPException(status_code=401, detail="Sesión inválida, expirada o revocada.")
        user = db.get(User, sess.user_id)
        if not user or not user.is_active or not user.tenant_id or user.role == "superadmin":
            raise HTTPException(status_code=403, detail="Acceso operativo denegado.")
        tenant = db.get(Tenant, user.tenant_id)
        if not tenant or tenant.status != "active":
            raise HTTPException(status_code=403, detail="Empresa inactiva.")
        return user, tenant

    @application.get("/health")
    def health():
        return {"status": "ok", "service": "datapyme-empresarial"}

    @application.exception_handler(StarletteHTTPException)
    async def html_login_redirect_handler(request: Request, exc: StarletteHTTPException):
        wants_html = "text/html" in request.headers.get("accept", "")
        if exc.status_code == 401 and wants_html and not request.url.path.startswith("/api"):
            root_path = request.scope.get("root_path", "").rstrip("/")
            return RedirectResponse(f"{root_path}/login", status_code=303)
        return await http_exception_handler(request, exc)

    @application.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger("uvicorn.error")
        logger.exception(f"Error no controlado en {request.url.path}: {exc}")
        if request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", ""):
            return JSONResponse(
                status_code=500,
                content={"detail": "Ocurrió un error inesperado al procesar la solicitud."},
            )
        root_path = request.scope.get("root_path", "").rstrip("/")
        return HTMLResponse(
            status_code=500,
            content=f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>Error del servidor · Datapyme Empresarial</title>
<style>body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #F8FAFC; color: #0F172A; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
.card {{ background: #fff; border: 1px solid rgba(15,23,42,0.1); border-radius: 16px; padding: 36px; max-width: 480px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.06); text-align: center; }}
h2 {{ color: #0F172A; margin: 0 0 12px; font-size: 20px; }} p {{ color: #64748B; font-size: 14px; line-height: 1.5; margin: 0 0 24px; }}
a {{ display: inline-flex; align-items: center; justify-content: center; height: 40px; padding: 0 20px; background: #0D7A6F; color: #fff; font-weight: 500; font-size: 14px; border-radius: 8px; text-decoration: none; }}</style></head>
<body><div class="card"><h2>Error inesperado</h2><p>Se presentó un inconveniente temporal. El servidor sigue en línea y protegido contra caídas.</p><a href="{root_path}/dashboard">Volver al panel</a></div></body></html>""",
        )

    def _authenticate(db: Session, request: Request, email: str, password: str) -> tuple[User, str]:
        """Login con bloqueo temporal tras fallos consecutivos y mensaje genérico (anti-enumeración)."""
        now = utcnow()
        user = db.query(User).filter_by(email=email.strip().lower()).first()
        locked_until = _as_aware(user.locked_until) if user else None
        if user and locked_until and locked_until > now:
            raise HTTPException(status_code=429, detail="Cuenta bloqueada temporalmente por intentos fallidos.")
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            if user:
                user.failed_logins = (user.failed_logins or 0) + 1
                if user.failed_logins >= MAX_FAILED_LOGINS:
                    user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                    user.failed_logins = 0
                db.commit()
            raise HTTPException(status_code=401, detail="Credenciales inválidas.")
        user.failed_logins = 0
        user.locked_until = None
        user.last_login_at = now
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

    @application.post("/api/auth/login")
    def api_login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
        user, raw_token = _authenticate(db, request, payload.email, payload.password)
        return {"access_token": raw_token, "role": user.role, "tenant_id": user.tenant_id}

    login_templates = Jinja2Templates(directory=str(ROOT / "templates"))

    @application.get("/", include_in_schema=False)
    def root_redirect(request: Request):
        root_path = request.scope.get("root_path", "").rstrip("/")
        return RedirectResponse(f"{root_path}/dashboard", status_code=303)

    @application.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_page(request: Request):
        root_path = request.scope.get("root_path", "").rstrip("/")
        return login_templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": None, "root_path": root_path},
        )

    @application.post("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_form(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db),
    ):
        try:
            user, raw_token = _authenticate(db, request, email, password)
        except HTTPException as exc:
            root_path = request.scope.get("root_path", "").rstrip("/")
            return login_templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": exc.detail, "root_path": root_path},
                status_code=exc.status_code,
            )
        root_path = request.scope.get("root_path", "").rstrip("/")
        target = f"{root_path}/api/admin/impact" if user.role == "superadmin" else f"{root_path}/dashboard"
        redirect = RedirectResponse(target, status_code=303)
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

    @application.post("/logout", include_in_schema=False)
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

    @application.post("/api/auth/register", status_code=201)
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

    def _load_profile(db: Session, tenant_id: str) -> PriorityProfile:
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

    @application.get("/api/ui/layout")
    def get_ui_layout(
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        view_setting = db.query(UserViewSetting).filter_by(user_id=user.id, tenant_id=tenant.id).first()
        mode: Literal["personalized", "general"] = (
            view_setting.view_mode if view_setting and view_setting.view_mode == "general" else "personalized"
        )
        profile = _load_profile(db, tenant.id)
        return build_layout_config(profile, view_mode=mode)

    @application.put("/api/ui/view-mode")
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
        profile = _load_profile(db, tenant.id)
        return build_layout_config(profile, view_mode=payload.view_mode)

    @application.get("/api/tenants/{target_tenant_id}/preferences")
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

    # --- SPRINT 2: CATÁLOGO DE PRODUCTOS, KARDEX INMUTABLE Y ALERTAS (ACT. 3.3) ---

    @application.post("/api/products", status_code=201)
    def create_product(
        payload: ProductCreateRequest,
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        try:
            prod = create_product_with_initial_stock(
                db=db,
                tenant_id=tenant.id,
                user_id=user.id,
                sku=payload.sku,
                name=payload.name,
                category=payload.category,
                unit=payload.unit,
                cost_price=parse_colombian_decimal(payload.cost_price, TWO_PLACES),
                sale_price=parse_colombian_decimal(payload.sale_price, TWO_PLACES),
                vat_rate=parse_colombian_decimal(payload.vat_rate, TWO_PLACES),
                initial_stock=parse_colombian_decimal(payload.initial_stock, THREE_PLACES),
                min_stock=parse_colombian_decimal(payload.min_stock, THREE_PLACES),
                image_url=payload.image_url,
            )
            db.commit()
            return serialize_product(prod)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post("/api/products/upload-image", status_code=201)
    async def upload_product_image_endpoint(
        file: UploadFile = File(...),
        ctx: tuple[User, Tenant] = Depends(get_current_context),
    ):
        _, tenant = ctx
        content = await file.read()
        image_url = save_product_image(
            tenant_id=tenant.id,
            filename=file.filename or "",
            content=content,
            static_root=ROOT / "static",
        )
        return {"image_url": image_url}

    @application.get("/api/products")
    def list_products(
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        _, tenant = ctx
        prods = db.query(Product).filter_by(tenant_id=tenant.id).order_by(Product.sku.asc()).all()
        return [serialize_product(p) for p in prods]

    @application.get("/api/products/{product_id}")
    def get_product(
        product_id: str,
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        _, tenant = ctx
        prod = db.query(Product).filter_by(tenant_id=tenant.id, id=product_id).first()
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado.")
        return serialize_product(prod)

    @application.patch("/api/products/{product_id}")
    def update_product(
        product_id: str,
        payload: ProductUpdateRequest,
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        _, tenant = ctx
        prod = db.query(Product).filter_by(tenant_id=tenant.id, id=product_id).first()
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado.")
        if payload.name is not None:
            prod.name = sanitize_cell_text(payload.name, 180)
        if payload.category is not None:
            prod.category = sanitize_cell_text(payload.category, 90)
        if payload.cost_price is not None:
            prod.cost_price = parse_colombian_decimal(payload.cost_price, TWO_PLACES)
        if payload.sale_price is not None:
            prod.sale_price = parse_colombian_decimal(payload.sale_price, TWO_PLACES)
        if payload.min_stock is not None:
            prod.min_stock = parse_colombian_decimal(payload.min_stock, THREE_PLACES)
        if payload.image_url is not None:
            prod.image_url = payload.image_url.strip() if payload.image_url.strip() else None
        if payload.is_active is not None:
            prod.is_active = payload.is_active
        prod.updated_at = utcnow()
        db.commit()
        return serialize_product(prod)

    @application.post("/api/inventory/movements", status_code=201)
    def post_inventory_movement(
        payload: InventoryMovementRequest,
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        qty = parse_colombian_decimal(payload.quantity, THREE_PLACES)
        u_cost = (
            parse_colombian_decimal(payload.unit_cost, TWO_PLACES)
            if payload.unit_cost is not None
            else None
        )
        prod, mov = record_inventory_movement(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
            product_id=payload.product_id,
            movement_type=payload.movement_type,
            quantity=qty,
            reason=payload.reason,
            unit_cost=u_cost,
        )
        db.commit()
        return {
            "movement_id": mov.id,
            "product_id": prod.id,
            "movement_type": mov.movement_type,
            "quantity": str(Decimal(str(mov.quantity)).quantize(THREE_PLACES)),
            "new_stock_qty": str(Decimal(str(prod.stock_qty)).quantize(THREE_PLACES)),
        }

    @application.get("/api/inventory/alerts")
    def get_inventory_alerts(
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        _, tenant = ctx
        return classify_inventory_alerts(db, tenant.id)

    # --- SPRINT 2: VENTAS ATÓMICAS Y ANULACIÓN CON REVERSA (ACT. 3.3) ---

    @application.post("/api/sales", status_code=201)
    def create_sale(
        payload: SaleCreateRequest,
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        items_data = [
            {
                "product_id": it.product_id,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "discount": it.discount,
            }
            for it in payload.items
        ]
        try:
            sale = create_sale_atomic(
                db=db,
                tenant_id=tenant.id,
                user_id=user.id,
                customer_label=payload.customer_label,
                payment_method=payload.payment_method,
                items_input=items_data,
                source="manual",
            )
            db.commit()
            return _serialize_sale(sale)
        except HTTPException:
            db.rollback()
            raise

    @application.get("/api/sales")
    def list_sales(
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        _, tenant = ctx
        sales = db.query(Sale).filter_by(tenant_id=tenant.id).order_by(Sale.sale_number.desc()).all()
        return [_serialize_sale(s) for s in sales]

    @application.get("/api/sales/{sale_id}")
    def get_sale(
        sale_id: str,
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        _, tenant = ctx
        sale = db.query(Sale).filter_by(tenant_id=tenant.id, id=sale_id).first()
        if not sale:
            raise HTTPException(status_code=404, detail="Venta no encontrada.")
        return _serialize_sale(sale)

    @application.post("/api/sales/{sale_id}/void")
    def void_sale(
        sale_id: str,
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        sale = void_sale_atomic(db=db, tenant_id=tenant.id, user_id=user.id, sale_id=sale_id)
        db.commit()
        return _serialize_sale(sale)

    # --- SPRINT 2: IMPORTACIÓN MASIVA CSV / EXCEL (.XLSX) CON SANITIZACIÓN OWASP ---

    @application.post("/api/imports/inspect")
    async def inspect_import_endpoint(
        file: UploadFile = File(...),
        sheet: str | None = Query(default=None),
        ctx: tuple[User, Tenant] = Depends(get_current_context),
    ):
        content = await file.read()
        from app.imports.smart_excel_mapper import inspect_workbook
        return inspect_workbook(
            filename=file.filename or "",
            content=content,
            target_sheet=sheet,
        )

    @application.post("/api/imports/products")
    async def import_products_endpoint(
        response: Response,
        mode: Literal["preview", "commit"] = Query(default="preview"),
        file: UploadFile = File(...),
        mapping: str | None = Form(default=None),
        sheet_name: str | None = Form(default=None),
        header_row: int | None = Form(default=1),
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        content = await file.read()
        col_mapping = None
        if mapping:
            try:
                col_mapping = json.loads(mapping) if isinstance(mapping, str) else None
            except Exception:
                col_mapping = None
        result = import_products_batch(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
            filename=file.filename or "",
            content=content,
            mode=mode,
            mapping=col_mapping,
            sheet_name=sheet_name,
            header_row_index=header_row or 1,
        )
        response.status_code = 201 if mode == "commit" else 200
        return result

    @application.post("/api/imports/sales")
    async def import_sales_endpoint(
        response: Response,
        mode: Literal["preview", "commit"] = Query(default="preview"),
        file: UploadFile = File(...),
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        content = await file.read()
        result = import_sales_batch(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
            filename=file.filename or "",
            content=content,
            mode=mode,
        )
        response.status_code = 201 if mode == "commit" else 200
        return result

    # --- SPRINT 3: ANALÍTICA EMPRESARIAL, KPIS Y DASHBOARD BENTO ADAPTATIVO (ACT. 3.4) ---

    templates_dir = ROOT / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    def format_cop_filter(val: Any) -> str:
        if val is None or val == "" or str(val) == "Undefined":
            return "$ 0"
        try:
            num = float(val)
            rounded = int(round(num))
            formatted = f"{rounded:,}".replace(",", ".")
            return f"$ {formatted}"
        except (ValueError, TypeError, Exception):
            return f"$ {val}"

    def format_qty_filter(val: Any, unit: str = "und") -> str:
        if val is None or val == "":
            return f"0 {unit}"
        try:
            num = float(val)
            if num.is_integer():
                return f"{int(num)} {unit}"
            formatted = f"{num:.1f}".rstrip("0").rstrip(".")
            return f"{formatted} {unit}"
        except (ValueError, TypeError):
            return f"{val} {unit}"

    def format_date_es_filter(val: Any) -> str:
        if not val:
            return "-"
        try:
            if isinstance(val, str):
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            elif isinstance(val, datetime):
                dt = val
            else:
                return str(val)
            months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
            month_name = months[dt.month - 1]
            hour_12 = dt.hour % 12 or 12
            am_pm = "a. m." if dt.hour < 12 else "p. m."
            return f"{dt.day} {month_name} {dt.year} · {hour_12}:{dt.minute:02d} {am_pm}"
        except Exception:
            return str(val)[:16]

    def format_payment_label_filter(val: Any) -> str:
        m = {
            "cash": "Efectivo",
            "card": "Tarjeta",
            "transfer": "Transferencia",
            "credit": "Crédito",
            "other": "Otro",
        }
        return m.get(str(val or "").lower(), "Efectivo")

    def format_pct_filter(val: Any, decimals: int = 1) -> str:
        if val is None or val == "":
            return "0 %"
        try:
            num = float(val) * 100
            if decimals == 0:
                return f"{int(round(num))} %"
            return f"{num:.{decimals}f} %".replace(".", ",")
        except Exception:
            return f"{val} %"

    def format_rnd_filter(val: Any, decimals: int = 0) -> str:
        if val is None or val == "":
            return "0"
        try:
            num = float(val)
            if decimals == 0:
                return str(int(round(num)))
            return f"{num:.{decimals}f}".replace(".", ",")
        except Exception:
            return str(val)

    templates.env.filters["cop"] = format_cop_filter
    templates.env.filters["qty"] = format_qty_filter
    templates.env.filters["date_es"] = format_date_es_filter
    templates.env.filters["payment_label"] = format_payment_label_filter
    templates.env.filters["pct"] = format_pct_filter
    templates.env.filters["rnd"] = format_rnd_filter
    login_templates.env.filters["cop"] = format_cop_filter
    login_templates.env.filters["qty"] = format_qty_filter
    login_templates.env.filters["date_es"] = format_date_es_filter
    login_templates.env.filters["payment_label"] = format_payment_label_filter
    login_templates.env.filters["pct"] = format_pct_filter
    login_templates.env.filters["rnd"] = format_rnd_filter

    @application.get("/api/kpis")
    def get_kpis_endpoint(
        period_days: int = Query(default=30, ge=1, le=365),
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        _, tenant = ctx
        return get_tenant_kpis_payload(db=db, tenant_id=tenant.id, period_days=period_days)

    @application.get("/dashboard", response_class=HTMLResponse)
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

        profile = _load_profile(db, tenant.id)
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
            _serialize_sale(s)
            for s in db.query(Sale)
            .filter_by(tenant_id=tenant.id)
            .order_by(Sale.sale_number.desc())
            .limit(15)
            .all()
        ]
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

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "title": f"Dashboard · {clean_trade_name}",
                "tenant_name": f"{clean_legal_name} · {tenant.municipality}",
                "company_name": clean_trade_name,
                "current_user": user,
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

    # --- SPRINT 4: COMPONENTE BÁSICO DE ANALÍTICA PREDICTIVA OLS Y SMA/WMA (ACT. 3.5) ---

    @application.get("/api/forecast")
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

    # --- SPRINT 5: TELEMETRÍA DE IMPACTO ANONIMIZADA (k >= 3) Y HABEAS DATA (LEY 1581/2012) ---

    def get_superadmin_user(
        request: Request,
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> User:
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
        return user

    @application.get("/api/admin/impact")
    def get_admin_impact_telemetry(
        k_threshold: int = Query(default=3, ge=3, le=10),
        _admin: User = Depends(get_superadmin_user),
        db: Session = Depends(get_db),
    ):
        return compute_platform_impact_telemetry(db=db, k_threshold=k_threshold)

    @application.get("/api/me/export")
    def export_my_tenant_data(
        ctx: tuple[User, Tenant] = Depends(get_current_context),
        db: Session = Depends(get_db),
    ):
        user, tenant = ctx
        return export_habeas_data_bundle(db=db, tenant_id=tenant.id, user_id=user.id)

    @application.post("/api/me/deletion-request")
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

    static_dir = ROOT / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return application


app = create_app()
