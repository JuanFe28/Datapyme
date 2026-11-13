from decimal import Decimal

from app.imports.smart_excel_mapper import inspect_workbook, parse_mapped_workbook_products


def setup_company(client):
    r = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Empresa sintetica IVA",
            "subsector": "Comercio",
            "email": "qa-iva@example.test",
            "full_name": "Prueba",
            "password": "PruebaIVA2026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "diagnosis": {"M10": [], "M12": [], "M17": "Ventas"},
        },
    )
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_update_tax_rate_and_sale_snapshot(client):
    h = setup_company(client)
    p = client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "IVA05",
            "name": "Articulo sintetico",
            "cost_price": "60",
            "sale_price": "100",
            "vat_rate": "19",
            "initial_stock": "4",
        },
    ).json()
    r = client.put("/api/products/" + p["id"], headers=h, json={"vat_rate": "5"})
    assert r.status_code == 200
    assert Decimal(r.json()["vat_rate"]) == Decimal(5)
    sale = client.post(
        "/api/sales",
        headers=h,
        json={
            "items": [
                {"product_id": p["id"], "quantity": "1", "discount": "10"},
            ]
        },
    ).json()
    assert Decimal(sale["vat_total"]) == Decimal("4.50")
    assert Decimal(sale["total"]) == Decimal("94.50")
    client.put("/api/products/" + p["id"], headers=h, json={"vat_rate": "19"})
    assert Decimal(
        client.get("/api/sales/" + sale["id"], headers=h).json()["items"][0]["vat_rate"]
    ) == Decimal(5)


def test_mixed_rates_discount_rounding_and_void(client):
    h = setup_company(client)
    items = []
    for i, rate in enumerate(["19", "5", "0"]):
        r = client.post(
            "/api/products",
            headers=h,
            json={
                "sku": f"MIX{i}",
                "name": "Articulo sintetico",
                "cost_price": "50",
                "sale_price": "100",
                "vat_rate": rate,
                "initial_stock": "10",
            },
        )
        assert r.status_code == 201
        items.append({"product_id": r.json()["id"], "quantity": "1.5", "discount": "10"})
    r = client.post("/api/sales", headers=h, json={"items": items})
    assert r.status_code == 201
    s = r.json()
    assert (s["subtotal"], s["discount_total"], s["vat_total"], s["total"], s["cogs_total"]) == (
        "450.00",
        "30.00",
        "33.60",
        "453.60",
        "225.00",
    )
    assert client.post("/api/sales/" + s["id"] + "/void", headers=h).status_code == 200
    assert all(Decimal(p["stock_qty"]) == 10 for p in client.get("/api/products", headers=h).json())


def test_mapped_import_preserves_tax_rate():
    data = b"sku,name,cost_price,sale_price,vat_rate\nIVA05,Articulo QA,60,100,5\n"
    info = inspect_workbook("qa.csv", data)
    products = parse_mapped_workbook_products("qa.csv", data, info["suggested_mapping"])
    assert products[0]["vat_rate"] == Decimal(5)


def test_negative_sale_price_is_rejected(client):
    h = setup_company(client)
    p = client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "NEG",
            "name": "Articulo QA",
            "cost_price": "50",
            "sale_price": "100",
            "initial_stock": "10",
        },
    ).json()
    r = client.post(
        "/api/sales",
        headers=h,
        json={
            "items": [
                {"product_id": p["id"], "quantity": "1", "unit_price": "-100"},
            ]
        },
    )
    assert r.status_code == 422
    assert client.get("/api/sales", headers=h).json() == []
