"""Fábrica ASGI de Datapyme Empresarial (MVP SaaS — F-DC-124).

Arquitectura modular desacoplada por capas:
- app.core: Modelos, esquemas, seguridad y dependencias de sesión.
- app.routes: Enrutadores modulares de autenticación, productos, ventas, inventario, importaciones y analítica.
- app.imports: Mapeo inteligente y procesamiento por lotes de CSV/Excel.
- app.analytics / app.forecast: Cálculo de KPIs comerciales y regresión predictiva OLS.
- app.telemetry: Métricas agregadas con k-anonimato (F-DC-125) y Habeas Data.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import ROOT, Settings
from app.core.dependencies import SESSION_COOKIE, _as_aware
from app.core.jinja_filters import register_jinja_filters
from app.core.models import Base, SessionToken, User, utcnow
from app.core.security import sha256_hex
from app.routes import (
    admin,
    auth,
    company_tax,
    dashboard,
    forecast,
    imports,
    inventory,
    products,
    sales,
)


def create_app(database_url: str | None = None, testing: bool = False) -> FastAPI:
    """Fábrica de aplicaciones FastAPI desacoplada para producción y pruebas."""
    settings = Settings.from_env(database_url)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    engine = create_engine(settings.database_url, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            try:
                if engine.dialect.name == "sqlite":
                    cols = [r[1] for r in conn.execute(text("PRAGMA table_info(products)")).fetchall()]
                    if cols and "image_url" not in cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(512)"))
                        conn.commit()
                elif engine.dialect.name == "postgresql":
                    conn.execute(
                        text("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(512)")
                    )
                    conn.commit()
            except Exception as exc:  # noqa: BLE001
                logging.getLogger("uvicorn.error").warning(f"Auto-migración products.image_url: {exc}")

        with SessionLocal() as db:
            try:
                from app.core.demo_seed import seed_contrast_demo_tenants

                if not testing and db.query(User).count() == 0:
                    logging.getLogger("uvicorn.error").info(
                        "Base de datos sin usuarios: sembrando empresas demo [DEMO-FDC125]..."
                    )
                    seed_contrast_demo_tenants(db)
            except Exception as exc:  # noqa: BLE001
                logging.getLogger("uvicorn.error").warning(
                    f"Auto-seeder demo tenants en arranque: {exc}"
                )

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

    templates_dir = ROOT / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    register_jinja_filters(templates)
    application.state.templates = templates

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

    @application.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "service": "datapyme-empresarial"}

    @application.exception_handler(StarletteHTTPException)
    async def html_login_redirect_handler(request: Request, exc: StarletteHTTPException):
        wants_html = "text/html" in request.headers.get("accept", "")
        root_path = request.scope.get("root_path", "").rstrip("/")
        if wants_html and not request.url.path.startswith("/api"):
            if exc.status_code == 401:
                return RedirectResponse(f"{root_path}/login", status_code=303)
            if exc.status_code == 403:
                raw_token = request.cookies.get(SESSION_COOKIE)
                if raw_token:
                    with SessionLocal() as sdb:
                        tok_hash = sha256_hex(raw_token)
                        sess = sdb.query(SessionToken).filter_by(token_hash=tok_hash).first()
                        if sess and sess.revoked_at is None and _as_aware(sess.expires_at) > utcnow():
                            u = sdb.get(User, sess.user_id)
                            if u and u.role == "superadmin":
                                return RedirectResponse(f"{root_path}/admin/impacto", status_code=303)
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "status_code": exc.status_code,
                    "title": (
                        f"Acceso Restringido ({exc.status_code})"
                        if exc.status_code == 403
                        else f"Página No Encontrada ({exc.status_code})"
                    ),
                    "detail": (
                        exc.detail
                        if isinstance(exc.detail, str)
                        else "No tiene permisos para acceder a esta vista o el recurso solicitado no existe."
                    ),
                    "root_path": root_path,
                },
                status_code=exc.status_code,
            )
        return await http_exception_handler(request, exc)

    @application.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger("uvicorn.error")
        logger.exception(f"Error no controlado en {request.url.path}: {exc}")
        if request.url.path.startswith("/api/") or "application/json" in request.headers.get(
            "accept", ""
        ):
            return JSONResponse(
                status_code=500,
                content={"detail": "Ocurrió un error inesperado al procesar la solicitud."},
            )
        root_path = request.scope.get("root_path", "").rstrip("/")
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "status_code": 500,
                "title": "Error del Servidor (500)",
                "detail": (
                    "Se presentó un inconveniente temporal. El servidor sigue en línea y protegido contra caídas."
                ),
                "root_path": root_path,
            },
            status_code=500,
        )

    # Registro de enrutadores desacoplados
    application.include_router(auth.router)
    application.include_router(company_tax.router)
    application.include_router(products.router)
    application.include_router(inventory.router)
    application.include_router(sales.router)
    application.include_router(imports.router)
    application.include_router(dashboard.router)
    application.include_router(forecast.router)
    application.include_router(admin.router)

    static_dir = ROOT / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return application


app = create_app()
