"""
Pruebas E2E en Navegador Real con Playwright (F-DC-124 / F-DC-125):
Verificación de miniaturas visuales de productos y flujo interactivo del mapeador inteligente de Excel.
"""

import os
from pathlib import Path

import openpyxl
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("DATAPYME_TEST_URL", "http://127.0.0.1:8000")
ARTIFACTS_DIR = Path(r"C:\Users\juanf\.gemini\antigravity\brain\46e60f00-dd8e-472a-98a1-c0a401f7e5ca")


def create_sample_excel_path(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lista de Precios"
    ws.append(["FERRETERÍA CABECERA"])
    ws.append([])
    ws.append(["Código", "Descripción", "Línea", "Costo", "Precio Venta", "Stock"])
    ws.append(["HER-001", "Destornillador Estrella Pro", "Herramientas", "$ 6.500", "$ 11.000", "25"])
    ws.append(["PIN-002", "Brocha 2 Pulgadas Cerda Mono", "Pinturas", "$ 4.200", "$ 7.500", "40"])
    ws.append(["", "Tijera Cortatodo Industrial", "Manual", "$ 15.000", "$ 24.000", "12"])

    ws_sales = wb.create_sheet("Ventas")
    ws_sales.append(["Factura", "Fecha", "Producto", "Cantidad Vendida", "Precio Venta", "Total"])
    ws_sales.append(["FAC-10", "2026-10-12", "Destornillador Estrella Pro", 2, "$ 11.000", "$ 22.000"])
    ws_sales.append(["FAC-11", "2026-10-14", "Brocha 2 Pulgadas Cerda Mono", 3, "$ 7.500", "$ 22.500"])

    excel_file = tmp_path / "inventario_prueba.xlsx"
    wb.save(excel_file)
    return excel_file


def test_inventory_thumbnails_visible_in_catalogue(page: Page):
    """Verifica que las miniaturas de producto o fallbacks SVG se rendericen en el catálogo."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#email", "demo.ferreteria@datapyme.co")
    page.fill("#password", "DemoFerreteria2026!")
    page.click("button[type='submit']")

    expect(page).to_have_url(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")

    # Verificar que existen miniaturas en la tabla de inventario
    avatars = page.locator(".product-avatar-img, .product-avatar-fallback")
    expect(avatars.first).to_be_visible()
    count = avatars.count()
    assert count >= 5, f"Se esperaban al menos 5 miniaturas de productos, encontrados: {count}"

    # Capturar pantalla del catálogo con miniaturas
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = ARTIFACTS_DIR / "e2e_inventory_thumbnails_verified.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    assert screenshot_path.exists()


def test_smart_excel_mapper_drawer_interaction(page: Page, tmp_path: Path):
    """Verifica que al subir un Excel en el Drawer de Importación, se detecten las columnas y se muestre el mapeo."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#email", "demo.ferreteria@datapyme.co")
    page.fill("#password", "DemoFerreteria2026!")
    page.click("button[type='submit']")
    expect(page).to_have_url(f"{BASE_URL}/dashboard")

    # Abrir Drawer de Importación
    page.click("button[data-open-drawer='drawer-import']")
    expect(page.locator("#drawer-import")).to_be_visible()

    # Verificar botones de plantilla con flex-wrap sin desbordamiento dentro del desplegable opcional
    page.locator("#drawer-import details summary").click()
    links_box = page.locator("#import-template-links")
    expect(links_box).to_be_visible()
    wrap_info = links_box.evaluate(
        "el => ({ wrap: window.getComputedStyle(el).flexWrap, sw: el.scrollWidth, cw: el.clientWidth })"
    )
    assert wrap_info["wrap"] == "wrap" and wrap_info["sw"] <= wrap_info["cw"] + 2, wrap_info

    # Generar y cargar archivo Excel multi-hoja
    sample_excel = create_sample_excel_path(tmp_path)
    page.set_input_files("#import-file", str(sample_excel))

    # Verificar el Resumen Visual Unificado (Productos + Ventas)
    unified_panel = page.locator("#unified-import-summary-panel")
    expect(unified_panel).to_be_visible(timeout=5000)
    expect(page.locator("#unified-analysis-banner")).to_contain_text(
        "Se encontraron 3 productos y 2 ventas registradas"
    )
    expect(page.locator("#unified-products-preview-table")).to_be_visible()
    expect(page.locator("#unified-sales-preview-table")).to_be_visible()

    # Esperar a que el panel de mapeo inteligente también aparezca
    mapper_panel = page.locator("#smart-mapper-panel")
    expect(mapper_panel).to_be_visible(timeout=5000)

    # Verificar que los selectores de mapeo se hayan poblado con las columnas detectadas
    expect(page.locator("#map-col-name")).to_be_visible()
    expect(page.locator("#map-col-sale_price")).to_be_visible()

    # Verificar tabla de previsualización
    preview_table = page.locator("#mapper-preview-table")
    expect(preview_table).to_be_visible()

    # Capturar screenshot del mapeador interactivo
    screenshot_path = ARTIFACTS_DIR / "e2e_smart_excel_mapper_verified.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    assert screenshot_path.exists()
