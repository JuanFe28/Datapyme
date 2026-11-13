"""Regresiones del recorrido real: formulario de importación y plantilla oficial."""

from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.imports.smart_excel_mapper import inspect_workbook, parse_mapped_workbook_products


class ImportModeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_mode = False
        self.option = None
        self.preview = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.in_mode = attrs.get("id") == "import-mode"
        if self.in_mode and tag == "option":
            self.option = attrs.get("value")

    def handle_data(self, data):
        if self.in_mode and "Solo revisar" in data:
            self.preview = self.option

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_mode = False


def test_preview_option_from_rendered_form_is_accepted_without_creating_products(client):
    registration = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Empresa sintetica QA",
            "subsector": "Ferreteria",
            "email": "qa-import@example.test",
            "full_name": "Usuario sintetico",
            "password": "SoloPrueba13112026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "accept_aggregate_stats": False,
            "diagnosis": {"M10": [], "M12": [], "M17": "Controlar inventario"},
        },
    )
    assert registration.status_code == 201
    headers = {"Authorization": "Bearer " + registration.json()["access_token"]}
    page = client.get("/dashboard", headers=headers)
    assert page.status_code == 200
    parser = ImportModeParser()
    parser.feed(page.text)
    assert parser.preview is not None
    content = b"sku,name,cost_price,sale_price,initial_stock\nQA01,Producto QA,1000,2000,4\n"
    response = client.post(
        "/api/imports/products",
        params={"mode": parser.preview},
        headers=headers,
        files={"file": ("qa.csv", content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows_ok"] == 1
    assert client.get("/api/products", headers=headers).json() == []


def test_official_template_maps_all_business_columns():
    content = (Path(__file__).parents[2] / "static/plantilla_productos_ejemplo.csv").read_bytes()
    result = inspect_workbook("plantilla.csv", content)
    for field in (
        "sku",
        "name",
        "category",
        "cost_price",
        "sale_price",
        "initial_stock",
        "min_stock",
        "unit",
    ):
        assert result["suggested_mapping"][field] == field


@pytest.mark.parametrize("cost", ["no_es_numero", "-100"])
def test_mapped_import_rejects_invalid_cost_instead_of_saving_zero(cost):
    content = f"sku,name,cost_price,sale_price\nQA01,Producto QA,{cost},3500\n".encode()
    with pytest.raises(HTTPException) as error:
        parse_mapped_workbook_products(
            "qa.csv",
            content,
            {
                "sku": "sku",
                "name": "name",
                "cost_price": "cost_price",
                "sale_price": "sale_price",
            },
        )
    assert error.value.status_code == 422
