"""Tests de Integración para Provisión Real de Clientes PyME y Flujo de Primer Ingreso."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.models import LegalConsent, User
from app.core.security import hash_password
from app.main import create_app


def _get_session_factory(db_url: str):
    engine = create_engine(db_url)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed_superadmin(db_url: str, email: str = "auditor@datapyme.co", password: str = "SuperAdmin2026!"):
    session_factory = _get_session_factory(db_url)
    with session_factory() as db:
        u = User(
            tenant_id=None,
            email=email,
            full_name="Auditor UTS",
            password_hash=hash_password(password),
            role="superadmin",
            is_active=True,
            must_change_password=False,
        )
        db.add(u)
        db.commit()


def test_superadmin_provision_and_first_login_activation_flow(tmp_path):
    db_file = tmp_path / "provisioning_flow.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    application = create_app(db_url, testing=True)

    with TestClient(application) as client:
        _seed_superadmin(db_url)
        # 1. Login SuperAdmin
        sa_login = client.post(
            "/api/auth/login",
            json={"email": "auditor@datapyme.co", "password": "SuperAdmin2026!"},
        )
        assert sa_login.status_code == 200
        sa_token = sa_login.json()["access_token"]

        # 2. Provisionar nueva empresa cliente real
        prov = client.post(
            "/api/admin/tenants/provision",
            headers={"Authorization": f"Bearer {sa_token}"},
            json={
                "trade_name": "Tienda La Aurora Real",
                "subsector": "minimercado",
                "size": "micro",
                "municipality": "Piedecuesta",
                "owner_full_name": "Lucía Gómez",
                "email": "lucia@aurora.co",
                "temporary_password": "TemporalPassword2026!",
                "priority_focus": "sales",
                "density": "simple",
                "tax_status": "not_responsible",
                "starter_catalog": True,
            },
        )
        assert prov.status_code == 201, prov.text
        prov_body = prov.json()
        assert prov_body["must_change_password"] is True
        assert prov_body["primary_focus"] == "sales"
        assert prov_body["starter_products_created"] >= 1
        assert "lucia@aurora.co" in prov_body["whatsapp_handoff_text"]

        # 3. Primer login del cliente real vía HTML debe redirigir 303 a /auth/activar-cuenta
        login_html = client.post(
            "/login",
            data={"email": "lucia@aurora.co", "password": "TemporalPassword2026!"},
            follow_redirects=False,
        )
        assert login_html.status_code == 303
        assert login_html.headers["location"].endswith("/auth/activar-cuenta")

        # 4. Antes de activar cuenta, el cliente NO puede operar el API ni entrar directo a /dashboard
        dash_blocked = client.get(
            "/dashboard",
            headers={"accept": "text/html"},
            follow_redirects=False,
        )
        assert dash_blocked.status_code == 303
        assert dash_blocked.headers["location"].endswith("/auth/activar-cuenta")

        prods_blocked = client.get("/api/products")
        assert prods_blocked.status_code == 403

        # 5. Activar cuenta estableciendo contraseña definitiva y aceptando Habeas Data
        activate = client.post(
            "/auth/activar-cuenta",
            data={
                "password": "MiPasswordPrivada2026!",
                "confirm_password": "MiPasswordPrivada2026!",
                "accept_data_policy": "true",
                "accept_aggregate_stats": "true",
            },
            follow_redirects=False,
        )
        assert activate.status_code == 303
        assert activate.headers["location"].endswith("/dashboard")

        # 6. Ahora /dashboard carga correctamente y /api/analytics/profitability responde con aislamiento
        dash_ok = client.get("/dashboard")
        assert dash_ok.status_code == 200
        assert "Tienda La Aurora Real" in dash_ok.text
        assert "Ganancia Neta Comercial" in dash_ok.text

        prof_res = client.get("/api/analytics/profitability?period_days=30")
        assert prof_res.status_code == 200
        assert "pnl" in prof_res.json()

        # Verificar en BD que quedaron los 3 consentimientos encadenados para esa empresa
        session_factory = _get_session_factory(db_url)
        with session_factory() as db:
            consents = db.query(LegalConsent).filter_by(tenant_id=prov_body["tenant_id"]).all()
            assert len(consents) == 3

        # 7. Verificar que GET /registro responde limpio sin requerir sesión
        reg_page = client.get("/registro")
        assert reg_page.status_code == 200
        assert "Crea la cuenta de tu empresa" in reg_page.text

        # 8. Verificar que el cliente operacional NO puede provisionar empresas (RBAC)
        forbidden = client.post(
            "/api/admin/tenants/provision",
            json={
                "trade_name": "Intruso SAS",
                "owner_full_name": "Intruso",
                "email": "intruso@hack.co",
                "temporary_password": "Password12345!",
            },
        )
        assert forbidden.status_code == 403
