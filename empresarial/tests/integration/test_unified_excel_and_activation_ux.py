"""Tests de Integración para Privacidad en Login, Activación en Vivo e Importador Unificado Excel."""

import io
from decimal import Decimal

import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.models import User
from app.core.security import hash_password
from app.imports.smart_excel_mapper import analyze_unified_workbook
from app.main import create_app


def _build_multi_sheet_excel() -> bytes:
    wb = openpyxl.Workbook()
    ws_prod = wb.active
    ws_prod.title = "Inventario"
    ws_prod.append(["Código", "Producto", "Categoría", "Costo", "Precio", "Stock"])
    ws_prod.append(["CAF-01", "Café Especial 500g", "Bebidas", "$ 12.000", "$ 22.000", 15])
    ws_prod.append(["PAN-02", "Panela Pulverizada", "Endulzantes", "$ 4.000", "$ 7.500", 20])

    ws_sales = wb.create_sheet("Ventas")
    ws_sales.append(
        ["Factura", "Fecha", "Producto", "Cantidad Vendida", "Precio Venta", "Cliente", "Medio Pago"]
    )
    ws_sales.append(
        ["F-101", "2026-10-15", "Café Especial 500g", 2, 22000, "María Pérez", "Transferencia"]
    )
    ws_sales.append(["F-102", "2026-10-18", "Panela Pulverizada", 3, 7500, "Carlos Ruiz", "Efectivo"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_login_privacy_placeholder_and_subtitle(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "vafelsweet" not in resp.text
    assert "3052621817" not in resp.text
    assert "Entorno de validación" not in resp.text
    assert "Ej. micomercio, 3001234567 o gerencia@miempresa.co" in resp.text
    assert "Gestión comercial, inventarios y rentabilidad para PyMEs" in resp.text


def test_activation_password_complexity_and_both_consents_required(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'act_ux.db').as_posix()}"
    app = create_app(db_url, testing=True)
    with TestClient(app) as client:
        engine = create_engine(db_url)
        with sessionmaker(bind=engine, expire_on_commit=False)() as db:
            db.add(
                User(
                    tenant_id=None,
                    email="admin.qa@example.test",
                    full_name="Admin QA",
                    password_hash=hash_password("SuperAdmin2026!"),
                    role="superadmin",
                    is_active=True,
                    must_change_password=False,
                )
            )
            db.commit()
        engine.dispose()

        sa = client.post(
            "/api/auth/login", json={"email": "admin.qa@example.test", "password": "SuperAdmin2026!"}
        ).json()
        prov = client.post(
            "/api/admin/tenants/provision",
            headers={"Authorization": f"Bearer {sa['access_token']}"},
            json={
                "trade_name": "Comercio UX Test",
                "owner_full_name": "Owner UX",
                "email": "ux.owner@example.test",
                "temporary_password": "TempPass2026!!",
            },
        )
        assert prov.status_code == 201

        r_login = client.post(
            "/login",
            data={"email": "ux.owner@example.test", "password": "TempPass2026!!"},
            follow_redirects=False,
        )
        assert r_login.status_code == 303 and r_login.headers["location"].endswith(
            "/auth/activar-cuenta"
        )

        page = client.get("/auth/activar-cuenta")
        assert page.status_code == 200
        assert "Blindaje contra accesos no autorizados (Recomendado)" in page.text
        assert "Nivel de seguridad: Alta protección" in page.text
        assert 'id="password-checklist"' in page.text
        assert 'id="btn-activate-submit"' in page.text and "disabled" in page.text

        # Contraseña sin símbolo especial -> rechazada con 422
        weak = client.post(
            "/auth/activar-cuenta",
            data={
                "password": "ClaveSinSimbolo123",
                "confirm_password": "ClaveSinSimbolo123",
                "accept_data_policy": "true",
                "accept_aggregate_stats": "true",
            },
        )
        assert weak.status_code == 422

        # Falta el segundo checkbox obligatorio -> rechazada con 422
        missing_stats = client.post(
            "/auth/activar-cuenta",
            data={
                "password": "ClaveSegura2026!",
                "confirm_password": "ClaveSegura2026!",
                "accept_data_policy": "true",
            },
        )
        assert missing_stats.status_code == 422

        # Todos los requisitos y ambos checkboxes marcados -> activa y entra al dashboard
        ok = client.post(
            "/auth/activar-cuenta",
            data={
                "password": "ClaveSegura2026!",
                "confirm_password": "ClaveSegura2026!",
                "accept_data_policy": "true",
                "accept_aggregate_stats": "true",
            },
            follow_redirects=False,
        )
        assert ok.status_code == 303 and ok.headers["location"].endswith("/dashboard")


def test_unified_excel_analyzer_and_endpoint_preview_commit(client):
    raw_xlsx = _build_multi_sheet_excel()
    analysis = analyze_unified_workbook("negocio_completo.xlsx", raw_xlsx)
    assert analysis["products_count"] == 2
    assert analysis["sales_count"] == 2
    assert "Se encontraron 2 productos y 2 ventas registradas" in analysis["summary_text"]

    reg = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Tienda Unificada QA",
            "subsector": "minimercado",
            "email": "unificada@example.test",
            "full_name": "Usuario QA",
            "password": "ClaveUnificada2026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "diagnosis": {"M10": [], "M12": [], "M17": "Ventas"},
        },
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    prev = client.post(
        "/api/imports/unified?mode=preview",
        headers=headers,
        files={
            "file": (
                "negocio_completo.xlsx",
                raw_xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert prev.status_code == 200
    assert prev.json()["products_count"] == 2
    assert prev.json()["sales_count"] == 2
    assert client.get("/api/products", headers=headers).json() == []

    commit = client.post(
        "/api/imports/unified?mode=commit",
        headers=headers,
        files={
            "file": (
                "negocio_completo.xlsx",
                raw_xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert commit.status_code == 201, commit.text
    assert commit.json()["products_created"] == 2
    assert commit.json()["sales_created"] == 2

    prods = client.get("/api/products", headers=headers).json()
    sales = client.get("/api/sales", headers=headers).json()
    assert len(prods) == 2
    assert len(sales) == 2
    assert all(Decimal(p["stock_qty"]) >= Decimal("0.000") for p in prods)
