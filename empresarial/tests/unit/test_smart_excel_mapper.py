"""
Pruebas Unitarias para el Mapeador Inteligente de Excel Multi-Hoja (F-DC-124).
"""

import io
from decimal import Decimal

import openpyxl

from app.imports.smart_excel_mapper import (
    clean_currency_or_number_string,
    inspect_workbook,
    parse_mapped_workbook_products,
)


def create_messy_multi_sheet_excel() -> bytes:
    """Crea un Excel con 3 hojas, títulos en fila 4, formatos COP y columnas sinónimas."""
    wb = openpyxl.Workbook()
    # Hoja 1: Resumen no operativo
    ws1 = wb.active
    ws1.title = "Portada y Notas"
    ws1.append(["EMPRESA COMERCIAL DE SANTANDER S.A.S."])
    ws1.append(["Informe de Inventario 2026"])
    ws1.append([])

    # Hoja 2: Inventario real con encabezados en fila 4
    ws2 = wb.create_sheet(title="Catálogo General")
    ws2.append(["FERRETERÍA CABECERA - BUCARAMANGA"])  # Fila 1
    ws2.append(["Generado el 12 de Noviembre de 2026"])  # Fila 2
    ws2.append([])  # Fila 3 vacía
    # Fila 4: Encabezados con sinónimos colombianos
    ws2.append(["Ref", "Artículo", "Línea", "Costo Unitario", "PVP", "Existencias", "Presentación"])
    # Filas 5+: Datos con moneda colombiana
    ws2.append(
        ["TAL-01", "Taladro Percutor 650W", "Herramientas", "$ 165.000,00", "$ 230.000,00", "15", "und"]
    )
    ws2.append(["CEM-02", "Cemento Gris 50kg", "Obra Gris", "$ 24.500", "$ 32.000", "150", "bulto"])
    ws2.append(
        ["", "Martillo Carpintero 16oz", "Manual", "$ 18.000", "$ 28.000", "24", "und"]
    )  # Sin SKU

    # Hoja 3: Proveedores
    ws3 = wb.create_sheet(title="Proveedores")
    ws3.append(["NIT", "Razón Social"])
    ws3.append(["900123456-1", "Cementos Argos S.A."])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_clean_currency_or_number_string():
    assert clean_currency_or_number_string("$ 1.250.000,50") == "1250000.50"
    assert clean_currency_or_number_string("$ 25.000") == "25000"
    assert clean_currency_or_number_string("$ 165.000,00") == "165000.00"
    assert clean_currency_or_number_string("12000.50") == "12000.50"
    assert clean_currency_or_number_string("-") == "0"
    assert clean_currency_or_number_string(None) == "0"


def test_inspect_workbook_multi_sheet_and_header_detection():
    excel_bytes = create_messy_multi_sheet_excel()
    # Inspeccionar hoja 2 específicamente
    res = inspect_workbook("inventario.xlsx", excel_bytes, target_sheet="Catálogo General")

    assert "Catálogo General" in res["sheets"]
    assert len(res["sheets"]) == 3
    assert res["selected_sheet"] == "Catálogo General"
    assert res["header_row_index"] == 4  # Detectó automáticamente fila 4
    assert "Artículo" in res["columns"]
    assert "PVP" in res["columns"]

    # Verificar auto-mapeo con sinónimos
    mapping = res["suggested_mapping"]
    assert mapping["sku"] == "Ref"
    assert mapping["name"] == "Artículo"
    assert mapping["category"] == "Línea"
    assert mapping["cost_price"] == "Costo Unitario"
    assert mapping["sale_price"] == "PVP"
    assert mapping["initial_stock"] == "Existencias"
    assert mapping["unit"] == "Presentación"

    # Verificar previsualización de 3 filas
    assert len(res["sample_rows"]) == 3
    assert res["sample_rows"][0]["Artículo"] == "Taladro Percutor 650W"


def test_parse_mapped_workbook_products_and_auto_sku():
    excel_bytes = create_messy_multi_sheet_excel()
    inspect_res = inspect_workbook("inventario.xlsx", excel_bytes, target_sheet="Catálogo General")

    products = parse_mapped_workbook_products(
        filename="inventario.xlsx",
        content=excel_bytes,
        mapping=inspect_res["suggested_mapping"],
        sheet_name="Catálogo General",
        header_row_index=inspect_res["header_row_index"],
    )

    assert len(products) == 3
    # Producto 1
    assert products[0]["sku"] == "TAL-01"
    assert products[0]["name"] == "Taladro Percutor 650W"
    assert products[0]["cost_price"] == Decimal("165000.00")
    assert products[0]["sale_price"] == Decimal("230000.00")
    assert products[0]["initial_stock"] == Decimal("15.000")

    # Producto 3: No tenía SKU en el Excel -> Auto-generó SKU consecutivo
    assert products[2]["name"] == "Martillo Carpintero 16oz"
    assert products[2]["sku"].startswith("AUTO-")
    assert products[2]["cost_price"] == Decimal("18000.00")
    assert products[2]["sale_price"] == Decimal("28000.00")
