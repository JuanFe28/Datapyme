"""Archivos sintéticos representativos del piloto; sin respuestas de empresas."""

import pytest
from test_company_tax import account

from app.imports.smart_excel_mapper import inspect_workbook, parse_mapped_workbook_products


def test_mapped_csv_keeps_quoted_commas_and_colombian_decimals():
    content = b'sku;name;cost_price;sale_price;initial_stock;vat_rate\nQA1;"Tuerca, acero";"1.234,50";"2.000,00";"1,250";19\n'
    inspection = inspect_workbook("qa.csv", content)
    assert inspection["sample_rows"][0]["name"] == "Tuerca, acero"
    rows = parse_mapped_workbook_products(
        "qa.csv",
        content,
        {k: k for k in ["sku", "name", "cost_price", "sale_price", "initial_stock", "vat_rate"]},
    )
    assert rows[0]["cost_price"] == 1234.50
    assert str(rows[0]["initial_stock"]) == "1.250"


def test_mapped_csv_rejects_number_with_embedded_letters():
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        parse_mapped_workbook_products(
            "qa.csv",
            b"name,cost_price,sale_price\nPrueba,1O00,2000\n",
            {"name": "name", "cost_price": "cost_price", "sale_price": "sale_price"},
        )


def test_duplicate_sku_is_a_row_error_in_preview_and_commit(client):
    h = account(client)
    data = b"sku,name,cost_price,sale_price\nQA1,Primero,100,200\nQA1,Repetido,100,200\n"
    for mode in ["preview", "commit"]:
        r = client.post(
            "/api/imports/products?mode=" + mode, headers=h, files={"file": ("qa.csv", data, "text/csv")}
        )
        assert r.status_code in (200, 201), r.text
        assert r.json()["rows_ok"] == 1
        assert r.json()["rows_rejected"] == 1
    assert len(client.get("/api/products", headers=h).json()) == 1


def test_committed_sales_file_cannot_be_applied_twice(client):
    h = account(client)
    assert (
        client.put(
            "/api/company/tax",
            headers=h,
            json={"status": "not_responsible", "expected_revision": 0, "reason": "Prueba sintética"},
        ).status_code
        == 200
    )
    p = client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "QA1",
            "name": "Prueba",
            "cost_price": "60",
            "sale_price": "100",
            "initial_stock": "5",
        },
    ).json()
    content = b"sku,quantity\nQA1,1\n"
    first = client.post(
        "/api/imports/sales?mode=commit", headers=h, files={"file": ("qa.csv", content, "text/csv")}
    )
    assert first.status_code == 201
    second = client.post(
        "/api/imports/sales?mode=commit",
        headers=h,
        files={"file": ("otra-copia.csv", content, "text/csv")},
    )
    assert second.status_code == 409
    assert len(client.get("/api/sales", headers=h).json()) == 1
    assert client.get("/api/products/" + p["id"], headers=h).json()["stock_qty"] == "4.000"


@pytest.mark.parametrize("mapping", ["[]", '{"name":[]}', "invalid"])
def test_invalid_mapping_is_rejected_before_import(client, mapping):
    h = account(client)
    r = client.post(
        "/api/imports/products?mode=commit",
        headers=h,
        data={"mapping": mapping},
        files={"file": ("qa.csv", b"sku,name\nQA1,Prueba\n", "text/csv")},
    )
    assert r.status_code == 422, r.text
    assert client.get("/api/products", headers=h).json() == []


def test_sales_preview_checks_total_stock_for_the_file(client):
    h = account(client)
    client.post(
        "/api/products",
        headers=h,
        json={
            "sku": "QA1",
            "name": "Prueba",
            "cost_price": "60",
            "sale_price": "100",
            "initial_stock": "5",
        },
    )
    data = b"sku,quantity\nQA1,3\nQA1,3\n"
    result = client.post(
        "/api/imports/sales?mode=preview", headers=h, files={"file": ("qa.csv", data, "text/csv")}
    )
    assert result.status_code == 200
    assert result.json()["rows_ok"] == 1
    assert result.json()["rows_rejected"] == 1
    assert client.get("/api/products", headers=h).json()[0]["stock_qty"] == "5.000"
