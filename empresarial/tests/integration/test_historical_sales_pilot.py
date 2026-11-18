from test_company_tax import account


def test_new_predictive_account_has_no_invented_metrics(client):
    from app.core.models import CompanyUIPreference

    h = account(client)
    with client.app.state.Session() as db:
        pref = db.query(CompanyUIPreference).one()
        pref.diagnosis_answers = {"M12": ["Tendencias o estimaciones"]}
        db.commit()
    html = client.get("/dashboard", headers=h).text
    assert "Datos insuficientes" in html
    assert "Muy Alta" not in html
    assert "+$ 39.200" not in html


def catalog(client, h):
    return client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "HIST1",
            "name": "Producto QA",
            "cost_price": "90",
            "sale_price": "150",
            "vat_rate": "19",
            "initial_stock": "5",
        },
    ).json()


def upload(client, h, data, mode="commit"):
    return client.post(
        "/api/imports/historical-sales?mode=" + mode,
        headers=h,
        files={"file": ("historial.csv", data, "text/csv")},
    )


def test_historical_invoice_preserves_date_cost_tax_without_changing_inventory(client):
    h = account(client)
    p = catalog(client, h)
    data = b"sale_number,occurred_at,sku,quantity,unit_price,unit_cost,vat_rate,discount\nORIG-001,2026-08-15T12:00:00-05:00,HIST1,2,100,60,5,10\nORIG-001,2026-08-15T12:00:00-05:00,HIST1,1,100,60,0,0\n"
    preview = upload(client, h, data, "preview")
    assert preview.status_code == 200, preview.text
    assert client.get("/api/sales", headers=h).json() == []
    result = upload(client, h, data)
    assert result.status_code == 201, result.text
    sales = client.get("/api/sales", headers=h).json()
    assert len(sales) == 1
    s = sales[0]
    assert s["source"] == "historical" and s["external_reference"] == "ORIG-001"
    assert s["occurred_at"].startswith("2026-08-15")
    assert (s["subtotal"], s["discount_total"], s["vat_total"], s["total"], s["cogs_total"]) == (
        "300.00",
        "10.00",
        "9.50",
        "299.50",
        "180.00",
    )
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"
    changed = data.replace(b",2,100,60,5,10", b",3,100,60,5,10")
    assert upload(client, h, changed).status_code == 409
    assert len(client.get("/api/sales", headers=h).json()) == 1
    assert client.post("/api/sales/" + s["id"] + "/void", headers=h).status_code == 200
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"


def test_invalid_historical_row_rejects_whole_file_instead_of_creating_partial_invoice(client):
    h = account(client)
    catalog(client, h)
    data = b"sale_number,occurred_at,sku,quantity,unit_price,unit_cost,vat_rate\nORIG-001,2026-08-15,HIST1,1,100,60,19\nORIG-001,2026-08-15,MISSING,1,100,60,19\n"
    assert upload(client, h, data).status_code == 422
    assert client.get("/api/sales", headers=h).json() == []
    assert (
        upload(
            client, h, data.replace(b"MISSING", b"HIST1").replace(b"2026-08-15", b"2099-01-01")
        ).status_code
        == 422
    )


def test_historical_reference_is_scoped_to_its_company(client):
    first = account(client)
    second = account(client, "history-other@example.test")
    catalog(client, first)
    catalog(client, second)
    data = b"sale_number,occurred_at,sku,quantity,unit_price,unit_cost,vat_rate\nORIG-001,2026-08-15,HIST1,1,100,60,19\n"
    assert upload(client, first, data).status_code == 201
    assert upload(client, second, data).status_code == 201
    sale = client.get("/api/sales", headers=first).json()[0]
    assert client.get("/api/sales/" + sale["id"], headers=second).status_code == 404


def test_historical_cost_and_effective_vat_are_required_not_inferred_from_today(client):
    h = account(client)
    catalog(client, h)
    data = b"sale_number,occurred_at,sku,quantity,unit_price\nORIG-001,2026-08-15,HIST1,1,100\n"
    assert upload(client, h, data).status_code == 422


def test_operational_import_does_not_silently_ignore_historical_dates(client):
    h = account(client)
    catalog(client, h)
    client.put(
        "/api/company/tax",
        headers=h,
        json={
            "status": "responsible",
            "expected_revision": 0,
            "reason": "Condición sintética confirmada",
        },
    )
    data = b"sale_number,occurred_at,sku,quantity\nORIG-001,2026-08-15,HIST1,1\n"
    result = client.post(
        "/api/imports/sales?mode=commit", headers=h, files={"file": ("hist.csv", data, "text/csv")}
    )
    assert result.status_code == 422
    assert client.get("/api/sales", headers=h).json() == []


def test_imported_closed_months_produce_forecast_and_cleanup_does_not_affect_history(client):
    h = account(client)
    p = catalog(client, h)
    data = b"sale_number,occurred_at,sku,quantity,unit_price,unit_cost,vat_rate\nH01,2026-07-15,HIST1,1,100,60,0\nH02,2026-08-15,HIST1,1,200,60,0\nH03,2026-09-15,HIST1,1,300,60,0\n"
    assert upload(client, h, data).status_code == 201
    forecast = client.get("/api/forecast", headers=h).json()
    assert forecast["status"] == "ok"
    assert forecast["projections"][0]["ols_forecast"] == 400
    assert (
        client.post(
            "/api/onboarding/complete-tour", headers=h, json={"action": "purge_training"}
        ).status_code
        == 200
    )
    assert len(client.get("/api/sales", headers=h).json()) == 3
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "5.000"


def test_sales_module_pages_past_recent_sales_and_accepts_zero_minimum_stock(client):
    headers = account(client)
    catalog(client, headers)
    data = "sale_number,occurred_at,sku,quantity,unit_price,unit_cost,vat_rate\n" + "\n".join(
        f"REF-{number},2026-08-15,HIST1,1,100,60,0" for number in range(26)
    )
    response = upload(client, headers, data.encode())
    assert response.status_code == 201

    first = client.get("/dashboard?sales_page=1", headers=headers)
    second = client.get("/dashboard?sales_page=2", headers=headers)
    assert first.status_code == second.status_code == 200

    first_history = first.text.split('id="section-sales"', 1)[1].split('id="section-forecast"', 1)[0]
    second_history = second.text.split('id="section-sales"', 1)[1].split('id="section-forecast"', 1)[0]
    assert first_history.count('class="btn btn-secondary btn-view-sale"') == 25
    assert second_history.count('class="btn btn-secondary btn-view-sale"') == 1
    assert "25 de 26 ventas" in first_history
    assert "26 de 26 ventas" in second_history
    assert "Histórica" in second_history
