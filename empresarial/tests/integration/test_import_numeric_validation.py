import pytest


def account(client):
    response = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Empresa sintética revisión archivos",
            "subsector": "Comercio",
            "email": "archivo-numerico@example.test",
            "full_name": "Prueba sintética",
            "password": "PruebaArchivos2026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "diagnosis": {"M10": [], "M12": [], "M17": "Ventas"},
        },
    )
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.mark.parametrize("bad", ["-3000", "no_es_numero", "NaN", "Infinity"])
def test_unified_rejects_explicit_invalid_cost_in_preview_and_commit(client, bad):
    headers = account(client)
    csv = (
        "sku,name,cost_price,sale_price,initial_stock\n"
        f"VALIDO,Artículo válido,100,200,3\nINVALIDO,Artículo inválido,{bad},200,3\n"
    ).encode()
    for mode in ("preview", "commit"):
        response = client.post(
            "/api/imports/unified?mode=" + mode,
            headers=headers,
            files={"file": ("qa.csv", csv, "text/csv")},
        )
        assert response.status_code == 422, response.text
    assert client.get("/api/products", headers=headers).json() == []


def test_unified_rejects_invalid_manual_override_instead_of_replacing_it(client):
    headers = account(client)
    csv = b"sku,name,cost_price,sale_price,initial_stock\nAJUSTE,Articulo,100,200,3\n"
    response = client.post(
        "/api/imports/unified?mode=commit",
        headers=headers,
        files={"file": ("qa.csv", csv, "text/csv")},
        data={"product_overrides": '{"AJUSTE":{"cost_price":"-1"}}'},
    )
    assert response.status_code == 422, response.text
    assert client.get("/api/products", headers=headers).json() == []


def test_unified_file_cannot_be_applied_twice(client):
    headers = account(client)
    csv = b"sku,name,cost_price,sale_price,initial_stock\nUNICO,Articulo,100,200,3\n"
    for expected in (201, 409):
        response = client.post(
            "/api/imports/unified?mode=commit",
            headers=headers,
            files={"file": ("qa.csv", csv, "text/csv")},
        )
        assert response.status_code == expected, response.text
    assert len(client.get("/api/products", headers=headers).json()) == 1


def test_unified_sales_require_tax_confirmation_without_partial_import(client):
    headers = account(client)
    csv = b"fecha,producto,cantidad_vendida,precio_venta\n2026-10-01,Producto sintetico,2,1000\n"
    response = client.post(
        "/api/imports/unified?mode=commit",
        headers=headers,
        files={"file": ("ventas.csv", csv, "text/csv")},
    )
    assert response.status_code == 409, response.text
    assert client.get("/api/company/tax", headers=headers).json()["status"] == "pending"
    assert client.get("/api/products", headers=headers).json() == []
    assert client.get("/api/sales", headers=headers).json() == []


def test_unified_inferred_gross_price_becomes_base_and_next_sale_is_not_taxed_twice(client):
    headers = account(client)
    tax = client.put(
        "/api/company/tax",
        headers=headers,
        json={
            "status": "responsible",
            "reason": "Condición sintética confirmada",
            "expected_revision": 0,
        },
    ).json()
    csv = b"fecha,producto,cantidad_vendida,total_venta,vat_rate\n2026-10-01,Producto sintetico,1,11900,19\n"
    response = client.post(
        "/api/imports/unified?mode=commit",
        headers=headers,
        files={"file": ("ventas.csv", csv, "text/csv")},
    )
    assert response.status_code == 201, response.text
    products = client.get("/api/products", headers=headers).json()
    assert products[0]["sale_price"] == "10000.00"
    # La siguiente venta usa la misma base; añadir solo stock sintético para la comprobación.
    from app.core.models import Product

    with client.app.state.Session() as db:
        db.get(Product, products[0]["id"]).stock_qty = 2
        db.commit()
    sale = client.post(
        "/api/sales",
        headers=headers,
        json={
            "items": [{"product_id": products[0]["id"], "quantity": "1"}],
            "tax_revision": tax["revision"],
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["total"] == "11900.00"
