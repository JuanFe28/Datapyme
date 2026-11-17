"""Fábrica ASGI de Datapyme Empresarial (MVP SaaS — F-DC-124).

Arquitectura modular desacoplada por capas:
- app.core: Modelos, esquemas, seguridad y dependencias de sesión.
- app.routes: Enrutadores modulares de autenticación, productos, ventas, inventario, importaciones y analítica.
- app.imports: Mapeo inteligente y procesamiento por lotes de CSV/Excel.
- app.analytics / app.forecast: Cálculo de KPIs comerciales y regresión predictiva OLS.
- app.telemetry: Métricas agregadas con k-anonimato (F-DC-125) y Habeas Data.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import ROOT, Settings
from app.core.dependencies import SESSION_COOKIE, _as_aware
from app.core.jinja_filters import register_jinja_filters
from app.core.models import (
    Base,
    SessionToken,
    User,
    _install_pg_immutability,
    utcnow,
)
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
                    tcols = {r[1] for r in conn.execute(text("PRAGMA table_info(tenants)")).fetchall()}
                    if tcols:
                        if "research_company_id" not in tcols:
                            conn.execute(
                                text("ALTER TABLE tenants ADD COLUMN research_company_id INTEGER")
                            )
                            conn.execute(
                                text(
                                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_research_company_id ON tenants (research_company_id)"
                                )
                            )
                        if "onboarding_tour_completed" not in tcols:
                            conn.execute(
                                text(
                                    "ALTER TABLE tenants ADD COLUMN onboarding_tour_completed BOOLEAN NOT NULL DEFAULT 0"
                                )
                            )

                    ucols = {r[1] for r in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
                    if ucols:
                        if "must_change_password" not in ucols:
                            conn.execute(
                                text(
                                    "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0"
                                )
                            )
                        if "username" not in ucols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(64)"))
                            conn.execute(
                                text(
                                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"
                                )
                            )
                        if "phone" not in ucols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(24)"))
                            conn.execute(
                                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)")
                            )
                        if "mfa_enabled" not in ucols:
                            conn.execute(
                                text(
                                    "ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT 0"
                                )
                            )
                        if "mfa_secret" not in ucols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN mfa_secret VARCHAR(128)"))
                        if "mfa_backup_codes" not in ucols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN mfa_backup_codes JSON"))

                    pcols = {r[1] for r in conn.execute(text("PRAGMA table_info(products)")).fetchall()}
                    if pcols:
                        if "image_url" not in pcols:
                            conn.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(512)"))
                        if "is_training_data" not in pcols:
                            conn.execute(
                                text(
                                    "ALTER TABLE products ADD COLUMN is_training_data BOOLEAN NOT NULL DEFAULT 0"
                                )
                            )

                    mcols = {
                        r[1]
                        for r in conn.execute(text("PRAGMA table_info(inventory_movements)")).fetchall()
                    }
                    if mcols and "is_training_data" not in mcols:
                        conn.execute(
                            text(
                                "ALTER TABLE inventory_movements ADD COLUMN is_training_data BOOLEAN NOT NULL DEFAULT 0"
                            )
                        )
                    # Reinstalar trigger condicional de inventory_movements para permitir limpieza de datos de prueba
                    conn.execute(text("DROP TRIGGER IF EXISTS trg_inventory_movements_no_delete"))
                    conn.execute(
                        text(
                            """
                            CREATE TRIGGER IF NOT EXISTS trg_inventory_movements_no_delete
                            BEFORE DELETE ON inventory_movements
                            WHEN OLD.is_training_data = 0
                            BEGIN
                                SELECT RAISE(ABORT, 'inventory_movements es append-only: prohibido DELETE en Kardex');
                            END;
                            """
                        )
                    )

                    scols = {r[1] for r in conn.execute(text("PRAGMA table_info(sales)")).fetchall()}
                    if scols and "is_training_data" not in scols:
                        conn.execute(
                            text(
                                "ALTER TABLE sales ADD COLUMN is_training_data BOOLEAN NOT NULL DEFAULT 0"
                            )
                        )
                    conn.commit()
                elif engine.dialect.name == "postgresql":
                    stmts = [
                        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS research_company_id INTEGER",
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_research_company_id ON tenants (research_company_id)",
                        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS onboarding_tour_completed BOOLEAN NOT NULL DEFAULT FALSE",
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE",
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(64)",
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)",
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(24)",
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)",
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE",
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret VARCHAR(128)",
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_backup_codes JSONB",
                        "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(512)",
                        "ALTER TABLE products ADD COLUMN IF NOT EXISTS is_training_data BOOLEAN NOT NULL DEFAULT FALSE",
                        "ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS is_training_data BOOLEAN NOT NULL DEFAULT FALSE",
                        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS is_training_data BOOLEAN NOT NULL DEFAULT FALSE",
                    ]
                    for s in stmts:
                        conn.execute(text(s))
                    _install_pg_immutability(conn, "inventory_movements")
                    conn.commit()
            except Exception as exc:
                raise RuntimeError(
                    "No se pudo actualizar el esquema; arranque cancelado para proteger los datos."
                ) from exc

        with SessionLocal() as db:
            try:
                from app.core.demo_seed import seed_contrast_demo_tenants

                if not testing and settings.environment == "development" and db.query(User).count() == 0:
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
        response.headers["Cache-Control"] = "no-store"
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

    @application.get("/ready", tags=["health"])
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT username, mfa_enabled FROM users LIMIT 1"))
                invalid = connection.execute(
                    text("SELECT id FROM products WHERE stock_qty < 0 LIMIT 1")
                ).first()
                if invalid:
                    return JSONResponse(
                        status_code=503,
                        content={"status": "review_required", "database": "inventory_inconsistent"},
                    )
            return {
                "status": "ok",
                "database": "ok",
                "release": os.getenv("DATAPYME_RELEASE", "local-piloto-20261117"),
            }
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "unavailable", "database": "error"})

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
                            if u and u.must_change_password:
                                return RedirectResponse(
                                    f"{root_path}/auth/activar-cuenta", status_code=303
                                )
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
