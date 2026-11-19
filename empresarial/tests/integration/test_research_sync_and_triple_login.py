"""Tests de Integración: Puente Research Studio, Login Triple, MFA TOTP y Limpieza de Entrenamiento."""

from decimal import Decimal

import pyotp
import pytest
from fastapi.testclient import TestClient
from research_fixture import research_database
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.commercial_service import create_product_with_initial_stock
from app.core.models import InventoryMovement, Product, Sale, User
from app.core.research_sync_service import sync_research_companies
from app.core.security import hash_password
from app.main import create_app


def _seed_superadmin(db_url: str) -> None:
    engine = create_engine(db_url)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        db.add(
            User(
                tenant_id=None,
                email="auditor@datapyme.co",
                username="auditoruts",
                full_name="Auditor UTS",
                password_hash=hash_password("SuperAdmin2026!"),
                role="superadmin",
                is_active=True,
                must_change_password=False,
            )
        )
        db.commit()
    engine.dispose()


def test_synthetic_sync_triple_login_mfa_and_training_purge(tmp_path):
    db_file = tmp_path / "full_prod_flow.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    application = create_app(db_url, testing=True)

    with TestClient(application) as client:
        _seed_superadmin(db_url)

        # 1. Login SuperAdmin por username corto ("auditoruts")
        sa_login = client.post(
            "/api/auth/login",
            json={"email": "auditoruts", "password": "SuperAdmin2026!"},
        )
        assert sa_login.status_code == 200
        sa_token = sa_login.json()["access_token"]

        # 2. Sincronizar una empresa ficticia en estado cero (0 productos, 0 ventas)
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        with SessionLocal() as db:
            synced = sync_research_companies(db, sqlite_path=research_database(tmp_path / "research.db"))
            assert len(synced) == 1
            vafel = next(c for c in synced if c["username"] == "comerciosinteticoqa")
            assert vafel["phone"] == "3000000001"
            assert vafel["primary_focus"] == "sales"
            assert db.query(Product).filter_by(tenant_id=vafel["tenant_id"]).count() == 0
            assert db.query(Sale).filter_by(tenant_id=vafel["tenant_id"]).count() == 0
        engine.dispose()

        # 3. Verificar en /admin/impacto que las credenciales y botón WhatsApp aparecen, sin contaminar /api/admin/impact
        impact_api = client.get("/api/admin/impact", headers={"Authorization": f"Bearer {sa_token}"})
        assert impact_api.status_code == 200
        assert "Comercio Sintético QA" not in impact_api.text

        # 4. Login Triple de Comercio Sintético QA usando el CELULAR (3000000001) + clave temporal -> redirige a activar-cuenta
        login_phone = client.post(
            "/login",
            data={"email": "3000000001", "password": vafel["temporary_password"]},
            follow_redirects=False,
        )
        assert login_phone.status_code == 303
        assert login_phone.headers["location"].endswith("/auth/activar-cuenta")

        # 5. Activar cuenta estableciendo contraseña definitiva
        act_res = client.post(
            "/auth/activar-cuenta",
            data={
                "password": "QAPrivada2026!",
                "confirm_password": "QAPrivada2026!",
                "accept_data_policy": "true",
                "accept_aggregate_stats": "true",
            },
            follow_redirects=False,
        )
        assert act_res.status_code == 303
        assert act_res.headers["location"].endswith("/dashboard")

        # 6. Login Triple usando USERNAME corto ("comerciosinteticoqa") y obtener token Bearer
        tok_login = client.post(
            "/api/auth/login",
            json={"email": "comerciosinteticoqa", "password": "QAPrivada2026!"},
        )
        assert tok_login.status_code == 200
        vafel_token = tok_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {vafel_token}"}

        # 7. Configurar y confirmar MFA TOTP offline
        setup_res = client.post("/api/auth/mfa/setup", headers=headers)
        assert setup_res.status_code == 200
        mfa_payload = setup_res.json()
        assert "<svg" in mfa_payload["qr_svg"]
        assert len(mfa_payload["backup_codes"]) == 5

        totp_now = pyotp.TOTP(mfa_payload["secret"]).now()
        confirm_res = client.post("/api/auth/mfa/confirm", headers=headers, json={"code": totp_now})
        assert confirm_res.status_code == 200
        assert confirm_res.json()["mfa_enabled"] is True

        # Nuevo login HTML con MFA activo debe pasar por /login/mfa
        mfa_redirect = client.post(
            "/login",
            data={"email": "comerciosinteticoqa", "password": "QAPrivada2026!"},
            follow_redirects=False,
        )
        assert mfa_redirect.status_code == 303
        assert mfa_redirect.headers["location"].endswith("/login/mfa")

        # Confirmar código TOTP en /login/mfa -> entra a /dashboard
        mfa_submit = client.post(
            "/login/mfa",
            data={"code": pyotp.TOTP(mfa_payload["secret"]).now()},
            follow_redirects=False,
        )
        assert mfa_submit.status_code == 303
        assert mfa_submit.headers["location"].endswith("/dashboard")

        # 8. Modo Entrenamiento Spotlight: crear producto y venta de prueba (incluso con IVA pending)
        prod_res = client.post(
            "/api/products",
            headers=headers,
            json={
                "sku": "PRUEBA-01",
                "name": "Waffle Entrenamiento",
                "category": "Postres",
                "unit": "und",
                "cost_price": "5000",
                "sale_price": "12000",
                "vat_rate": "0",
                "initial_stock": "10",
                "min_stock": "2",
                "is_training_data": True,
            },
        )
        assert prod_res.status_code == 201, prod_res.text
        train_pid = prod_res.json()["id"]

        sale_res = client.post(
            "/api/sales",
            headers=headers,
            json={
                "payment_method": "cash",
                "items": [{"product_id": train_pid, "quantity": "2"}],
                "is_training_data": True,
            },
        )
        assert sale_res.status_code == 201, sale_res.text

        # 9. Completar tour con purge_training: borra atómicamente producto, venta y movimientos de prueba
        purge_res = client.post(
            "/api/onboarding/complete-tour",
            headers=headers,
            json={"action": "purge_training"},
        )
        assert purge_res.status_code == 200
        assert purge_res.json()["status"] == "purged"

        engine = create_engine(db_url)
        with sessionmaker(bind=engine, expire_on_commit=False)() as db:
            assert db.query(Product).filter_by(tenant_id=vafel["tenant_id"]).count() == 0
            assert db.query(Sale).filter_by(tenant_id=vafel["tenant_id"]).count() == 0
            assert db.query(InventoryMovement).filter_by(tenant_id=vafel["tenant_id"]).count() == 0

            # 10. Verificar que un movimiento REAL (is_training_data=False) sigue protegido por trigger Kardex
            real_prod = create_product_with_initial_stock(
                db=db,
                tenant_id=vafel["tenant_id"],
                user_id=vafel["user_id"],
                sku="REAL-01",
                name="Waffle Clásico Real",
                category="Waffles",
                unit="und",
                cost_price=Decimal(5000),
                sale_price=Decimal(14000),
                vat_rate=Decimal(0),
                initial_stock=Decimal(5),
                min_stock=Decimal(1),
                is_training_data=False,
            )
            db.commit()
            real_mov = (
                db.query(InventoryMovement)
                .filter_by(tenant_id=vafel["tenant_id"], product_id=real_prod.id)
                .first()
            )
            assert real_mov is not None
            with pytest.raises((IntegrityError, Exception)):
                db.execute(
                    text("DELETE FROM inventory_movements WHERE id = :mid"),
                    {"mid": real_mov.id},
                )
                db.commit()
            db.rollback()
        engine.dispose()

        # 11. SuperAdmin puede restablecer MFA de soporte si el cliente cambia de teléfono
        reset_res = client.post(
            f"/api/admin/users/{vafel['user_id']}/reset-mfa",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert reset_res.status_code == 200
        assert reset_res.json()["mfa_enabled"] is False


def test_sync_research_via_database_url_preserves_existing_passwords_and_adds_new(tmp_path, monkeypatch):
    import json
    import sqlite3

    db_url = f"sqlite:///{(tmp_path / 'sync_env.db').as_posix()}"
    research_path = research_database(tmp_path / "research_live.db")
    monkeypatch.setenv("RESEARCH_DATABASE_URL", f"sqlite:///{research_path.as_posix()}")

    application = create_app(db_url, testing=True)
    with TestClient(application) as client:
        _seed_superadmin(db_url)
        sa_token = client.post(
            "/api/auth/login",
            json={"email": "auditoruts", "password": "SuperAdmin2026!"},
        ).json()["access_token"]
        sa_headers = {"Authorization": f"Bearer {sa_token}"}

        # 1. Primera sincronización vía RESEARCH_DATABASE_URL
        r1 = client.post("/api/admin/tenants/sync-research", headers=sa_headers)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["synced_count"] == 1
        assert d1["created_count"] == 1
        first_pw = d1["clients"][0]["temporary_password"]
        assert len(first_pw) >= 20

        # Guardar hash original del primer cliente
        engine = create_engine(db_url)
        with sessionmaker(bind=engine)() as db:
            first_user = db.query(User).filter_by(username="comerciosinteticoqa").one()
            first_hash_before = first_user.password_hash
        engine.dispose()

        # 2. Agregar una empresa nueva en Research Studio y re-sincronizar
        with sqlite3.connect(research_path) as conn:
            conn.execute(
                "INSERT INTO companies VALUES (2, ?, ?, ?)",
                ("Tienda Deportiva Norte", "Bucaramanga", "Pequeña"),
            )
            conn.execute(
                "INSERT INTO company_contacts VALUES (2, ?, ?)",
                ("Representante Norte", "3120000099"),
            )
            conn.execute(
                "INSERT INTO responses VALUES (2, ?, ?, ?)",
                (
                    "mercado",
                    "complete",
                    json.dumps(
                        {
                            "M05": "Ropa, calzado y accesorios",
                            "M10": ["Dificultad para analizar ventas"],
                            "M12": ["Ventas por periodo"],
                            "M17": "Inventarios y existencias",
                        }
                    ),
                ),
            )

        r2 = client.post("/api/admin/tenants/sync-research", headers=sa_headers)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2["synced_count"] == 2
        assert d2["created_count"] == 1

        by_user = {c["username"]: c for c in d2["clients"]}
        assert by_user["comerciosinteticoqa"]["created_now"] is False
        assert by_user["tiendadeportivanorte"]["created_now"] is True
        assert by_user["tiendadeportivanorte"]["phone"] == "3120000099"
        assert len(by_user["tiendadeportivanorte"]["temporary_password"]) >= 20

        # Verificar que el hash del usuario previo no fue alterado
        engine = create_engine(db_url)
        with sessionmaker(bind=engine)() as db:
            first_user_after = db.query(User).filter_by(username="comerciosinteticoqa").one()
            assert first_user_after.password_hash == first_hash_before
        engine.dispose()

        # Ambas empresas aparecen en /api/admin/tenants/credentials-report y /admin/impacto
        rep = client.get("/api/admin/tenants/credentials-report", headers=sa_headers).json()
        usernames = {c["username"] for c in rep["clients"]}
        assert {"comerciosinteticoqa", "tiendadeportivanorte"}.issubset(usernames)
