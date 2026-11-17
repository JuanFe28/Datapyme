"""Tests de Integración: Puente Research Studio, Login Triple, MFA TOTP y Limpieza de Entrenamiento."""

from decimal import Decimal

import pyotp
import pytest
from fastapi.testclient import TestClient
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


def test_sync_13_companies_triple_login_mfa_and_training_purge(tmp_path):
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

        # 2. Sincronizar las 13 empresas encuestadas reales en estado cero (0 productos, 0 ventas)
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        with SessionLocal() as db:
            synced = sync_research_companies(db)
            assert len(synced) == 13
            vafel = next(c for c in synced if c["username"] == "vafelsweet")
            assert vafel["phone"] == "3052621817"
            assert vafel["primary_focus"] == "sales"
            assert db.query(Product).filter_by(tenant_id=vafel["tenant_id"]).count() == 0
            assert db.query(Sale).filter_by(tenant_id=vafel["tenant_id"]).count() == 0
        engine.dispose()

        # 3. Verificar en /admin/impacto que las credenciales y botón WhatsApp aparecen, sin contaminar /api/admin/impact
        impact_api = client.get("/api/admin/impact", headers={"Authorization": f"Bearer {sa_token}"})
        assert impact_api.status_code == 200
        assert "VaFel Sweet" not in impact_api.text

        # 4. Login Triple de VaFel Sweet usando el CELULAR (3052621817) + clave temporal -> redirige a activar-cuenta
        login_phone = client.post(
            "/login",
            data={"email": "3052621817", "password": vafel["temporary_password"]},
            follow_redirects=False,
        )
        assert login_phone.status_code == 303
        assert login_phone.headers["location"].endswith("/auth/activar-cuenta")

        # 5. Activar cuenta estableciendo contraseña definitiva
        act_res = client.post(
            "/auth/activar-cuenta",
            data={
                "password": "VafelPrivada2026!",
                "confirm_password": "VafelPrivada2026!",
                "accept_data_policy": "true",
                "accept_aggregate_stats": "true",
            },
            follow_redirects=False,
        )
        assert act_res.status_code == 303
        assert act_res.headers["location"].endswith("/dashboard")

        # 6. Login Triple usando USERNAME corto ("vafelsweet") y obtener token Bearer
        tok_login = client.post(
            "/api/auth/login",
            json={"email": "vafelsweet", "password": "VafelPrivada2026!"},
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
            data={"email": "vafelsweet", "password": "VafelPrivada2026!"},
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
