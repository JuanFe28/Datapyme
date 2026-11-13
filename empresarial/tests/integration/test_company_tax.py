from decimal import Decimal


def account(client, email="tax-company@example.test"):
    r = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Empresa sintetica",
            "subsector": "Comercio",
            "email": email,
            "full_name": "Prueba",
            "password": "PruebaFiscal2026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "diagnosis": {"M10": [], "M12": [], "M17": "Ventas"},
        },
    )
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_company_tax_transition_and_historical_snapshots(client):
    h = account(client)
    p = client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "VAT19",
            "name": "Articulo sintetico",
            "cost_price": "60",
            "sale_price": "100",
            "vat_rate": "19",
            "initial_stock": "10",
        },
    ).json()
    payload = {"items": [{"product_id": p["id"], "quantity": "1"}]}
    assert client.post("/api/sales", headers=h, json=payload).status_code == 409
    state = client.get("/api/company/tax", headers=h).json()
    assert state["status"] == "pending"
    revision = state["revision"]
    historical = []
    for status, expected in [
        ("not_responsible", "0.00"),
        ("responsible", "19.00"),
        ("not_responsible", "0.00"),
    ]:
        r = client.put(
            "/api/company/tax",
            headers=h,
            json={
                "status": status,
                "reason": "Cambio sintetico verificado",
                "expected_revision": revision,
            },
        )
        assert r.status_code == 200, r.text
        revision = r.json()["revision"]
        sale = client.post("/api/sales", headers=h, json={**payload, "tax_revision": revision})
        assert sale.status_code == 201, sale.text
        s = sale.json()
        assert s["vat_total"] == expected
        assert s["tax_status"] == status
        historical.append((s["id"], expected, status))
    for sale_id, amount, status in historical:
        s = client.get("/api/sales/" + sale_id, headers=h).json()
        assert (s["vat_total"], s["tax_status"]) == (amount, status)
    assert client.get("/api/products/" + p["id"], headers=h).json()["vat_rate"] == "19.00"
    assert len(client.get("/api/company/tax", headers=h).json()["history"]) == 3
    stale = client.post("/api/sales", headers=h, json={**payload, "tax_revision": revision - 1})
    assert stale.status_code == 409
    stale_change = client.put(
        "/api/company/tax",
        headers=h,
        json={
            "status": "responsible",
            "reason": "Pantalla obsoleta",
            "expected_revision": revision - 1,
        },
    )
    assert stale_change.status_code == 409


def test_company_tax_isolation_and_import_uses_same_policy(client):
    h = account(client)
    other = account(client, "other-tax@example.test")
    assert (
        client.put(
            "/api/company/tax",
            headers=h,
            json={
                "status": "not_responsible",
                "reason": "Prueba de no responsable",
                "expected_revision": 0,
            },
        ).status_code
        == 200
    )
    assert client.get("/api/company/tax", headers=other).json()["status"] == "pending"
    p = client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "CSV19",
            "name": "Articulo QA",
            "cost_price": "60",
            "sale_price": "100",
            "vat_rate": "19",
            "initial_stock": "10",
        },
    ).json()
    data = b"sku,quantity,unit_price\nCSV19,1,100\n"
    r = client.post(
        "/api/imports/sales?mode=commit", headers=h, files={"file": ("qa.csv", data, "text/csv")}
    )
    assert r.status_code == 201, r.text
    sales = client.get("/api/sales", headers=h).json()
    assert sales[0]["vat_total"] == "0.00"
    assert Decimal(client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"]) == 9
    assert client.get("/api/company/tax").status_code == 401


def test_pending_import_and_permissions(client):
    from app.core.models import User

    h = account(client)
    p = client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "PENDING",
            "name": "Articulo QA",
            "cost_price": "60",
            "sale_price": "100",
            "initial_stock": "5",
        },
    ).json()
    data = b"sku,quantity\nPENDING,1\n"
    r = client.post(
        "/api/imports/sales?mode=commit", headers=h, files={"file": ("qa.csv", data, "text/csv")}
    )
    assert r.status_code == 409
    assert client.get("/api/sales", headers=h).json() == []
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"
    with client.app.state.Session() as db:
        user = db.query(User).filter_by(email="tax-company@example.test").one()
        user.role = "operator"
        db.commit()
    r = client.put(
        "/api/company/tax",
        headers=h,
        json={
            "status": "responsible",
            "reason": "Cambio no autorizado",
            "expected_revision": 0,
        },
    )
    assert r.status_code == 403
    assert client.get("/api/company/tax", headers=h).json()["revision"] == 0


def test_return_to_pending_and_foreign_company_cannot_change_history(client):
    h = account(client)
    other = account(client, "tax-other@example.test")
    r = client.put(
        "/api/company/tax",
        headers=h,
        json={
            "status": "responsible",
            "reason": "Condicion verificada",
            "expected_revision": 0,
        },
    )
    assert r.status_code == 200
    r = client.put(
        "/api/company/tax",
        headers=h,
        json={
            "status": "pending",
            "reason": "Revision de documentos",
            "expected_revision": 1,
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert client.get("/api/company/tax", headers=other).json()["history"] == []


def test_tax_reason_cannot_inject_script_into_dashboard(client):
    import json

    h = account(client)
    reason = '</script><script>alert("QA")</script>'
    r = client.put(
        "/api/company/tax",
        headers=h,
        json={
            "status": "not_responsible",
            "reason": reason,
            "expected_revision": 0,
        },
    )
    assert r.status_code == 200
    page = client.get("/dashboard", headers=h)
    opening = '<script id="dashboard-data" type="application/json">'
    payload = page.text.split(opening, 1)[1].split("</script>", 1)[0]
    data = json.loads(payload)
    assert data["company_tax"]["history"][0]["reason"] == reason
    assert "<script>" not in payload
