"""Regresiones del piloto: datos exclusivamente sintéticos y bases temporales."""

import csv
import io
from decimal import Decimal

import pytest
from fastapi import HTTPException
from test_company_tax import account

from app.core.models import InventoryMovement, Product, Tenant, User
from app.core.research_sync_service import sync_research_companies


def product(client, headers, **extra):
    response = client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": "QA-01",
            "name": "=Prueba sintética",
            "cost_price": "60",
            "sale_price": "100",
            "vat_rate": "19",
            "initial_stock": "5",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def confirm_tax(client, headers):
    assert (
        client.put(
            "/api/company/tax",
            headers=headers,
            json={
                "status": "responsible",
                "expected_revision": 0,
                "reason": "Prueba sintética",
            },
        ).status_code
        == 200
    )


def test_repeated_product_cannot_oversell_and_rolls_back(client):
    h = account(client)
    confirm_tax(client, h)
    p = product(client, h)
    r = client.post(
        "/api/sales",
        headers=h,
        json={
            "items": [
                {"product_id": p["id"], "quantity": "3"},
                {"product_id": p["id"], "quantity": "3"},
            ]
        },
    )
    assert r.status_code == 409, r.text
    assert client.get("/api/sales", headers=h).json() == []
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"


@pytest.mark.parametrize(
    "field,value",
    [("cost_price", "-1"), ("sale_price", "-1"), ("min_stock", "-1"), ("sale_price", "abc")],
)
def test_invalid_product_update_does_not_change_catalog(client, field, value):
    h = account(client)
    p = product(client, h)
    r = client.put("/api/products/" + p["id"], headers=h, json={field: value})
    assert r.status_code == 422, r.text
    assert client.get("/api/products/" + p["id"], headers=h).json()[field] == p[field]


def test_training_sale_cannot_use_real_stock(client):
    h = account(client)
    p = product(client, h)
    r = client.post(
        "/api/sales",
        headers=h,
        json={
            "items": [{"product_id": p["id"], "quantity": "1"}],
            "is_training_data": True,
        },
    )
    assert r.status_code == 409, r.text
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"


def test_training_purge_rejects_product_with_real_movements(client):
    h = account(client)
    p = product(client, h, is_training_data=True)
    # Reproduce un movimiento heredado que quedó registrado como real.
    with client.app.state.Session() as db:
        training_product = db.get(Product, p["id"])
        training_product.stock_qty += Decimal(2)
        db.add(
            InventoryMovement(
                tenant_id=training_product.tenant_id,
                product_id=training_product.id,
                movement_type="purchase_in",
                quantity=Decimal(2),
                reason="Movimiento real legado sintético",
                is_training_data=False,
            )
        )
        db.commit()
    r = client.post("/api/onboarding/complete-tour", headers=h, json={"action": "purge_training"})
    assert r.status_code == 409, r.text
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "7.000"


def test_csv_export_is_csv_and_portable_json_has_sale_lines(client):
    h = account(client)
    confirm_tax(client, h)
    p = product(client, h)
    sale = client.post(
        "/api/sales",
        headers=h,
        json={
            "items": [{"product_id": p["id"], "quantity": "1"}],
        },
    ).json()
    r = client.get("/api/me/export?format=csv", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text.lstrip("\ufeff"))))
    assert any(row["section"] == "products" for row in rows)
    bundle = client.get("/api/me/export?format=json", headers=h).json()
    assert bundle["sales"][0]["items"][0]["product_id"] == p["id"]
    assert Decimal(bundle["sales"][0]["items"][0]["line_total"]) == Decimal(119)
    assert bundle["sales"][0]["id"] == sale["id"]


def test_missing_research_source_never_creates_real_companies(client, tmp_path):
    with client.app.state.Session() as db:
        with pytest.raises(HTTPException) as error:
            sync_research_companies(db, sqlite_path=tmp_path / "missing.db")
        assert error.value.status_code == 409
        assert db.query(User).count() == 0


def test_enabled_mfa_cannot_be_disabled_by_setup(client):
    h = account(client)
    with client.app.state.Session() as db:
        u = db.query(User).one()
        u.mfa_enabled = True
        u.mfa_secret = "JBSWY3DPEHPK3PXP"
        db.commit()
    assert client.post("/api/auth/mfa/setup", headers=h).status_code == 409
    with client.app.state.Session() as db:
        assert db.query(User).one().mfa_enabled is True


def test_inactive_product_cannot_be_sold(client):
    h = account(client)
    confirm_tax(client, h)
    p = product(client, h)
    assert (
        client.put("/api/products/" + p["id"], headers=h, json={"is_active": False}).status_code == 200
    )
    assert (
        client.post(
            "/api/sales",
            headers=h,
            json={
                "items": [{"product_id": p["id"], "quantity": "1"}],
            },
        ).status_code
        == 409
    )


def test_keep_training_preserves_synthetic_flags(client):
    h = account(client)
    p = product(client, h, is_training_data=True)
    r = client.post("/api/onboarding/complete-tour", headers=h, json={"action": "keep_training"})
    assert r.status_code == 200
    with client.app.state.Session() as db:
        assert db.get(Product, p["id"]).is_training_data is True


def test_production_rejects_public_demo_credentials(client):
    from dataclasses import replace

    account(client, "demo.ferreteria@datapyme.co")
    client.app.state.settings = replace(client.app.state.settings, environment="production")
    r = client.post(
        "/api/auth/login",
        json={
            "email": "demo.ferreteria@datapyme.co",
            "password": "PruebaFiscal2026!",
        },
    )
    assert r.status_code == 403


def test_research_password_is_random_and_report_never_recovers_it(client, tmp_path):
    from research_fixture import research_database

    from app.core.research_sync_service import list_real_client_credentials

    source = research_database(tmp_path / "research.db")
    with client.app.state.Session() as db:
        first = sync_research_companies(db, sqlite_path=source)
        password = first[0]["temporary_password"]
        assert len(password) >= 24
        assert password not in str(list_real_client_credentials(db))
        assert password not in str(sync_research_companies(db, sqlite_path=source))


def test_mfa_wrong_codes_are_limited_even_when_password_is_correct(client):
    import pyotp

    from app.core.mfa_service import generate_totp_secret

    account(client)
    secret = generate_totp_secret()
    wrong = "000000" if not pyotp.TOTP(secret).verify("000000", valid_window=1) else "000001"
    with client.app.state.Session() as db:
        u = db.query(User).one()
        u.mfa_enabled, u.mfa_secret = True, secret
        db.commit()
    codes = [
        client.post(
            "/api/auth/login",
            json={
                "email": "tax-company@example.test",
                "password": "PruebaFiscal2026!",
                "totp_code": wrong,
            },
        ).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


def test_admin_can_reissue_pending_password_once_and_revoke_old_session(client):
    admin = account(client, "admin@example.test")
    with client.app.state.Session() as db:
        u = db.query(User).one()
        u.tenant_id, u.role = None, "superadmin"
        db.commit()
    old = account(client)
    with client.app.state.Session() as db:
        user = db.query(User).filter_by(email="tax-company@example.test").one()
        user.must_change_password = True
        uid = user.id
        db.commit()
    r = client.post("/api/admin/users/" + uid + "/reset-temporary-password", headers=admin)
    assert r.status_code == 200, r.text
    password = r.json()["temporary_password"]
    assert len(password) >= 24
    assert client.get("/api/products", headers=old).status_code == 401
    report = client.get("/api/admin/tenants/credentials-report", headers=admin)
    assert password not in report.text
    assert (
        client.post(
            "/api/auth/login",
            json={
                "email": "tax-company@example.test",
                "password": password,
            },
        ).status_code
        == 200
    )


def test_legacy_predictable_research_password_requires_reissue(client):
    from app.core.security import hash_password

    account(client)
    with client.app.state.Session() as db:
        u = db.query(User).one()
        tenant = db.get(Tenant, u.tenant_id)
        tenant.trade_name = "Comercio Sintético QA"
        tenant.research_company_id = 1
        u.must_change_password = True
        u.password_hash = hash_password("DpComerc2027!")
        db.commit()
    assert (
        client.post(
            "/api/auth/login",
            json={
                "email": "tax-company@example.test",
                "password": "DpComerc2027!",
            },
        ).status_code
        == 403
    )


def test_kpi_window_and_product_income_exclude_old_sales_and_vat(client):
    from datetime import timedelta

    from app.core.models import Sale, utcnow

    h = account(client)
    confirm_tax(client, h)
    p = product(client, h)
    ids = []
    for _ in range(2):
        ids.append(
            client.post(
                "/api/sales",
                headers=h,
                json={
                    "items": [{"product_id": p["id"], "quantity": "1"}],
                },
            ).json()["id"]
        )
    with client.app.state.Session() as db:
        db.get(Sale, ids[0]).occurred_at = utcnow() - timedelta(days=60)
        db.commit()
    result = client.get("/api/kpis?period_days=30", headers=h).json()
    assert result["kpis"]["net_revenue"] == "100.00"
    assert result["star_products"][0]["net_revenue"] == "100.00"


def test_three_transactions_in_one_month_are_not_three_monthly_observations(client):
    h = account(client)
    confirm_tax(client, h)
    p = product(client, h)
    for _ in range(3):
        assert (
            client.post(
                "/api/sales",
                headers=h,
                json={
                    "items": [{"product_id": p["id"], "quantity": "1"}],
                },
            ).status_code
            == 201
        )
    result = client.get("/api/forecast", headers=h).json()
    assert result["status"] != "ok"
    assert result["projections"] == []


def test_ready_checks_database_and_release(client):
    result = client.get("/ready")
    assert result.status_code == 200
    assert result.json()["database"] == "ok"


def test_backup_restore_recovers_sales_and_stock(client, tmp_path):
    import sqlite3

    from fastapi.testclient import TestClient

    from app.main import create_app

    h = account(client)
    confirm_tax(client, h)
    p = product(client, h)
    sale = client.post(
        "/api/sales",
        headers=h,
        json={
            "items": [{"product_id": p["id"], "quantity": "1"}],
        },
    ).json()
    backup = tmp_path / "restore.db"
    with (
        sqlite3.connect(client.app.state.engine.url.database) as source,
        sqlite3.connect(backup) as target,
    ):
        source.backup(target)
        assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with TestClient(create_app("sqlite:///" + backup.as_posix(), testing=True)) as restored:
        assert restored.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "4.000"
        result = restored.get("/api/sales/" + sale["id"], headers=h).json()
        assert result["total"] == "119.00"
        assert result["items"][0]["product_id"] == p["id"]


def test_training_stock_adjustment_stays_out_of_real_profitability_and_can_be_purged(client):
    headers = account(client)
    training = product(client, headers, is_training_data=True)
    real = product(client, headers, sku="REAL-01")

    result = client.post(
        "/api/inventory/movements",
        headers=headers,
        json={
            "product_id": training["id"],
            "movement_type": "adjustment_out",
            "quantity": "0.125",
            "reason": "Ajuste sintético de práctica",
        },
    )
    assert result.status_code == 201, result.text
    assert result.json()["new_stock_qty"] == "4.875"
    report = client.get("/api/analytics/profitability", headers=headers).json()
    assert report["pnl"]["shrinkage_loss_cop"] == "0.00"

    result = client.post(
        "/api/onboarding/complete-tour", headers=headers, json={"action": "purge_training"}
    )
    assert result.status_code == 200, result.text
    assert client.get("/api/products/" + training["id"], headers=headers).status_code == 404
    assert client.get("/api/products/" + real["id"], headers=headers).json()["stock_qty"] == "5.000"


def test_unified_import_reports_practice_sku_conflict_without_changing_inventory(client):
    headers = account(client)
    training = product(client, headers, sku="PRUEBA-01", is_training_data=True)
    data = b"sku,nombre,costo,precio,stock\nPRUEBA-01,Producto comercial,25,100,30\n"
    response = client.post(
        "/api/imports/unified?mode=commit",
        headers=headers,
        files={"file": ("catalogo.csv", data, "text/csv")},
    )
    assert response.status_code == 409, response.text
    assert "producto de práctica" in response.json()["detail"]
    assert client.get("/api/products", headers=headers).json() == [training]
