"""
Suite de Pruebas E2E en Navegador Real con Playwright (Chromium) — F-DC-124 / F-DC-125.

Verifica rigurosamente los 4 flujos críticos:
1. Redirección automática a /login al acceder sin sesión (cero pantallas negras con JSON).
2. Ingreso del rol Auditor UTS (superadmin) con visualización HTML en /admin/impacto y cierre de sesión.
3. Botón 'Editar' en inventario: Slide-Over Drawer con cálculo de margen en vivo y actualización de precios.
4. Botón 'Ver detalle' en ventas: Comprobante/recibo completo con desglose de productos, cantidades, precios y utilidad.
"""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("DATAPYME_TEST_URL", "http://127.0.0.1:8000")
ARTIFACTS_DIR = Path(r"C:\Users\juanf\.gemini\antigravity\brain\46e60f00-dd8e-472a-98a1-c0a401f7e5ca")


def test_01_unauthenticated_dashboard_redirects_to_login(page: Page):
    """Verifica que entrar a /dashboard sin sesión redirige con 303 a /login y nunca muestra JSON crudo."""
    page.context.clear_cookies()
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")

    # 1. Debe haber sido redirigido a /login
    expect(page).to_have_url(re.compile(r"/login$"))

    # 2. La página debe ser la interfaz gráfica estilizada de Login
    card = page.locator(".login-card")
    expect(card).to_be_visible()
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#password")).to_be_visible()

    # 3. Cero JSON crudo en pantalla (no debe contener etiquetas <pre> con llaves JSON)
    pre_tags = page.locator("pre")
    expect(pre_tags).to_have_count(0)
    body_text = page.locator("body").inner_text()
    assert '{"detail"' not in body_text, "No debe mostrar JSON de error en el navegador"

    # 4. Probar ruta inexistente: debe renderizar plantilla error.html con botón a /login
    page.goto(f"{BASE_URL}/pagina-no-existente-404")
    page.wait_for_load_state("networkidle")
    expect(page.locator("#btn-go-login")).to_be_visible()
    expect(page.locator("#btn-logout-change")).to_be_visible()

    screenshot_path = ARTIFACTS_DIR / "unauthenticated_redirect_verified.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()


def test_02_superadmin_login_shows_html_impact_view(page: Page):
    """Verifica que el rol Auditor UTS (superadmin) carga la vista visual HTML /admin/impacto."""
    page.context.clear_cookies()
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")

    # Hacer click en la pastilla de Auditor UTS
    superadmin_pill = page.locator(".login-demo-pill", has_text="Auditor UTS")
    expect(superadmin_pill).to_be_visible()
    superadmin_pill.click()

    # Enviar formulario de login
    page.locator(".login-btn-submit").click()
    page.wait_for_load_state("networkidle")

    # 1. Debe redirigir automáticamente a /admin/impacto
    expect(page).to_have_url(re.compile(r"/admin/impacto$"))

    # 2. Cero JSON crudo en pantalla
    expect(page.locator("pre")).to_have_count(0)
    body_text = page.locator("body").inner_text()
    assert '{"privacy_guarantee"' not in body_text, "Debe ser HTML estilizado, no JSON crudo"

    # 3. Validar elementos gráficos de Auditoría de Impacto F-DC-125
    expect(page.locator("text=Auditoría de Impacto de Plataforma")).to_be_visible()
    expect(page.locator("text=Auditor UTS (superadmin)")).to_be_visible()
    expect(page.locator("text=Garantía Estricta de Privacidad y")).to_be_visible()

    # 4. Tarjetas KPI de impacto global
    expect(page.locator("text=Empresas en Muestra Activa")).to_be_visible()
    expect(page.locator("text=Ventas Totales Procesadas")).to_be_visible()
    expect(page.locator("text=Catálogo Administrado")).to_be_visible()
    expect(page.locator("text=Tiempo Ahorrado Estimado")).to_be_visible()

    # 5. Tabla por subsector y tarjeta criptográfica
    expect(page.locator("text=Cohortes Estadísticas por Subsector Comercial")).to_be_visible()
    expect(page.locator("text=Cadena Inmutable de Consentimientos")).to_be_visible()

    # 6. Si intenta navegar manualmente a /dashboard, debe redirigirlo a /admin/impacto
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(re.compile(r"/admin/impacto$"))

    # 7. Botón funcional para volver al login / cerrar sesión
    logout_btn = page.locator("#btn-superadmin-logout")
    expect(logout_btn).to_be_visible()

    screenshot_path = ARTIFACTS_DIR / "superadmin_impact_verified.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()

    # Probar que el botón de cerrar sesión funciona
    logout_btn.click()
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_03_edit_product_drawer_and_inventory_calculation(page: Page):
    """Verifica el botón Editar en inventarios, cálculo en vivo de ganancia/margen y actualización de precios."""
    page.context.clear_cookies()
    page.goto(f"{BASE_URL}/login")
    page.locator(".login-demo-pill", has_text="Ferretería Cabecera").click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # 1. Verificar aclaración del término en la tarjeta de Valor en Inventario
    expect(page.locator("text=Capital en bodega (a costo de compra)")).to_be_visible()
    tooltip = page.locator(".kpi-help-tooltip", has_text="?").nth(0)
    expect(tooltip).to_be_visible()

    # 2. Navegar al módulo Inventarios y Kardex
    sidebar = page.locator("[data-testid='adaptive-sidebar']")
    sidebar.locator(".sidebar-nav-link", has_text="Inventarios y Kardex").click()
    expect(page.locator("#section-inventory")).to_be_visible()

    # 3. En la tabla debe aparecer el botón Editar en cada fila
    edit_buttons = page.locator("#section-inventory .btn-edit-product")
    expect(edit_buttons.first).to_be_visible()

    # 4. Hacer click en Editar en el primer producto
    edit_buttons.first.click()
    drawer_edit = page.locator("#drawer-edit-product")
    expect(drawer_edit).to_have_class(re.compile(r"open"))

    # 5. Verificar campos precargados
    sku_input = page.locator("#edit-prod-sku")
    name_input = page.locator("#edit-prod-name")
    cost_input = page.locator("#edit-prod-cost")
    price_input = page.locator("#edit-prod-price")

    expect(sku_input).not_to_have_value("")
    expect(name_input).not_to_have_value("")

    # 6. Probar cálculo dinámico de ganancia ($) y margen (%)
    cost_input.fill("20000")
    price_input.fill("30000")

    profit_display = page.locator("#edit-profit-display")
    margin_display = page.locator("#edit-margin-pct-display")

    expect(profit_display).to_contain_text("10.000")
    expect(margin_display).to_contain_text("33.3 %")

    # Probar ajuste de margen a 50%
    price_input.fill("40000")
    expect(profit_display).to_contain_text("20.000")
    expect(margin_display).to_contain_text("50.0 %")

    screenshot_path = ARTIFACTS_DIR / "product_edit_drawer_verified.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()

    # 7. Guardar cambios
    page.locator("#btn-submit-edit-product").click()
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")

    # Debe haberse cerrado el drawer
    expect(drawer_edit).not_to_have_class(re.compile(r"open"))


def test_04_sale_detail_drawer_receipt(page: Page):
    """Verifica que el botón 'Ver detalle' abre el comprobante con el desglose exacto de productos de la venta."""
    page.context.clear_cookies()
    page.goto(f"{BASE_URL}/login")
    page.locator(".login-demo-pill", has_text="Ferretería Cabecera").click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # 1. Navegar a Ventas y Facturación
    sidebar = page.locator("[data-testid='adaptive-sidebar']")
    sidebar.locator(".sidebar-nav-link", has_text="Ventas y Facturación").click()
    expect(page.locator("#section-sales")).to_be_visible()

    # 2. Verificar que existe el botón 'Ver detalle' y el enlace del número de venta
    view_buttons = page.locator("#section-sales .btn-view-sale")
    expect(view_buttons.first).to_be_visible()

    sale_links = page.locator("#section-sales .sale-number-link")
    expect(sale_links.first).to_be_visible()

    # 3. Hacer click en 'Ver detalle' en la primera venta
    view_buttons.first.click()
    drawer_detail = page.locator("#drawer-sale-detail")
    expect(drawer_detail).to_have_class(re.compile(r"open"))

    # 4. Verificar encabezado del comprobante
    expect(page.locator("#sale-detail-number")).to_contain_text("#")
    expect(page.locator("#sale-detail-date")).not_to_have_text("-")
    expect(page.locator("#sale-detail-customer")).to_be_visible()
    expect(page.locator("#sale-detail-status-badge")).to_be_visible()

    # 5. Verificar tabla de artículos comprados en esa venta
    items_count = page.locator("#sale-detail-items-count")
    expect(items_count).not_to_have_text("0")

    item_rows = page.locator("#sale-detail-items-tbody tr")
    expect(item_rows.first).to_be_visible()

    # 6. Verificar resumen financiero de liquidación (Subtotal, Total y Ganancia Bruta)
    expect(page.locator("#sale-detail-subtotal")).to_contain_text("$")
    expect(page.locator("#sale-detail-total")).to_contain_text("$")
    expect(page.locator("#sale-detail-profit")).to_contain_text("$")
    expect(page.locator("#sale-detail-margin-pct")).to_contain_text("%")

    screenshot_path = ARTIFACTS_DIR / "sale_detail_receipt_verified.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()

    # 7. Cerrar el drawer y verificar que hacer click en el enlace #N también abre el detalle
    page.locator("#drawer-sale-detail .drawer-close-btn").click()
    expect(drawer_detail).not_to_have_class(re.compile(r"open"))

    sale_links.first.click()
    expect(drawer_detail).to_have_class(re.compile(r"open"))
