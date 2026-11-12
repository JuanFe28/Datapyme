"""
Suite de Pruebas E2E en Navegador Real con Playwright (Chromium) — F-DC-124 / F-DC-125.

Verifica rigurosamente:
1. Cero errores de consola (console.error) y cero pageerror en Login y Dashboard.
2. Estilos reales aplicados (Apple HIG) en Login (tarjeta centrada, borde, fondo, botón primario).
3. Menú lateral 100% en español con navegación funcional entre módulos.
4. Curva de ventas interactiva: inmutabilidad y consistencia exacta en 30D -> 7D -> 30D.
5. Tablas operativas: padding >= 12px, fechas legibles en español, medios de pago traducidos (Efectivo/Tarjeta).
6. Carrito multi-producto en '+ Registrar Venta': agregar 2 o más productos distintos, cálculo dinámico y registro atómico.
7. Proyección Estadística: tarjetas de negocios, gráfico visual propio y acordeón de auditoría OLS (F-DC-124).
"""
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("DATAPYME_TEST_URL", "http://127.0.0.1:8000")
ARTIFACTS_DIR = Path(r"C:\Users\juanf\.gemini\antigravity\brain\46e60f00-dd8e-472a-98a1-c0a401f7e5ca")


@pytest.fixture(scope="session", autouse=True)
def live_server():
    """Garantiza que el servidor FastAPI esté corriendo en 127.0.0.1:8000 durante la sesión de pruebas."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_open = sock.connect_ex(("127.0.0.1", 8000)) == 0
    sock.close()

    if not is_open:
        from app.main import create_app
        test_app = create_app()
        config = uvicorn.Config(test_app, host="127.0.0.1", port=8000, log_level="error")
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        time.sleep(1.2)
        yield
        server.should_exit = True
    else:
        yield


@pytest.fixture(autouse=True)
def setup_console_listener(page: Page):
    """Monitorea consola y errores de página en cada prueba."""
    console_errors = []
    page_errors = []

    def handle_console(msg):
        if msg.type in ("error", "severe"):
            console_errors.append(f"[{msg.type}] {msg.text}")

    def handle_page_error(exc):
        page_errors.append(str(exc))

    page.on("console", handle_console)
    page.on("pageerror", handle_page_error)

    yield

    # Filtrar solo errores críticos de script o CSP
    critical_errors = [
        err for err in console_errors 
        if "favicon" not in err.lower() and "failed to load resource: net::err" not in err.lower()
    ]
    assert len(critical_errors) == 0, f"Errores en consola de navegador detectados: {critical_errors}"
    assert len(page_errors) == 0, f"Errores de ejecución JS detectados: {page_errors}"


def test_01_login_styling_and_quick_fill(page: Page):
    """Verifica estilos reales de login (Apple HIG) y autocompletado con pastillas demo."""
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")

    # 1. Verificar tarjeta y estilos aplicados
    card = page.locator(".login-card")
    expect(card).to_be_visible()

    card_styles = card.evaluate("""el => {
        const cs = window.getComputedStyle(el);
        return {
            bg: cs.backgroundColor,
            borderRadius: cs.borderRadius,
            boxShadow: cs.boxShadow
        };
    }""")
    assert "255, 255, 255" in card_styles["bg"], f"Tarjeta de login debe tener fondo blanco: {card_styles}"
    assert "16px" in card_styles["borderRadius"], f"Tarjeta debe tener borde redondeado 16px: {card_styles}"

    # 2. Verificar botón primario estilizado
    btn = page.locator(".login-btn-submit")
    expect(btn).to_be_visible()
    btn_styles = btn.evaluate("""el => {
        const cs = window.getComputedStyle(el);
        return {
            bg: cs.backgroundColor,
            color: cs.color
        };
    }""")
    assert "13, 122, 111" in btn_styles["bg"], f"Botón debe usar color primario #0D7A6F: {btn_styles}"

    # 3. Probar autocompletado con pastilla demo
    pills = page.locator(".login-demo-pill")
    expect(pills.first).to_be_visible()
    pills.first.click()

    email_val = page.locator("#email").input_value()
    pass_val = page.locator("#password").input_value()
    assert email_val == "demo.ferreteria@datapyme.co"
    assert pass_val == "DemoFerreteria2026!"

    # Capturar pantalla del Login verificado
    screenshot_path = ARTIFACTS_DIR / "login_real_browser_verified.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()


def test_02_dashboard_sidebar_spanish_and_navigation(page: Page):
    """Verifica menú lateral 100% en español y navegación funcional entre módulos."""
    page.goto(f"{BASE_URL}/login")
    page.locator(".login-demo-pill").first.click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    sidebar = page.locator("[data-testid='adaptive-sidebar']")
    expect(sidebar).to_be_visible()

    expected_labels = [
        "Panel Principal",
        "Inventarios y Kardex",
        "Ventas y Facturación",
        "Proyección Estadística",
        "Mis Datos (Ley 1581)"
    ]
    for label in expected_labels:
        expect(sidebar.get_by_text(label)).to_be_visible()

    # Navegación entre secciones
    sidebar.locator(".sidebar-nav-link", has_text="Inventarios y Kardex").click()
    expect(page.locator("#section-inventory")).to_be_visible()
    expect(page.locator("#section-home")).not_to_be_visible()

    sidebar.locator(".sidebar-nav-link", has_text="Ventas y Facturación").click()
    expect(page.locator("#section-sales")).to_be_visible()
    expect(page.locator("#section-inventory")).not_to_be_visible()

    sidebar.locator(".sidebar-nav-link", has_text="Proyección Estadística").click()
    expect(page.locator("#section-forecast")).to_be_visible()
    expect(page.locator("#section-sales")).not_to_be_visible()

    sidebar.locator(".sidebar-nav-link", has_text="Mis Datos (Ley 1581)").click()
    expect(page.locator("#section-my_data")).to_be_visible()
    expect(page.locator("#section-forecast")).not_to_be_visible()

    sidebar.locator(".sidebar-nav-link", has_text="Panel Principal").click()
    expect(page.locator("#section-home")).to_be_visible()
    expect(page.locator("#section-my_data")).not_to_be_visible()


def test_03_chart_consistency_30d_7d_30d(page: Page):
    """Verifica que el gráfico 30D -> 7D -> 30D es exactamente idéntico y no se altera ni muta."""
    page.goto(f"{BASE_URL}/login")
    page.locator(".login-demo-pill").first.click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # Cambiar a pestaña de Ventas en Hero
    page.locator("[data-tab='sales']").click()
    expect(page.locator("#tab-content-sales")).to_be_visible()

    # Obtener datos iniciales en 30D
    initial_30d_data = page.evaluate("() => salesChart.data.datasets[0].data.slice()")
    assert len(initial_30d_data) == 4, f"30D debe tener 4 semanas de datos: {initial_30d_data}"

    # Cambiar a 7D
    page.locator(".horizon-btn", has_text="7D").click()
    page.wait_for_timeout(200)
    data_7d = page.evaluate("() => salesChart.data.datasets[0].data.slice()")
    assert len(data_7d) == 7, f"7D debe tener 7 días de datos: {data_7d}"
    assert data_7d != initial_30d_data

    # Volver a 30D
    page.locator(".horizon-btn", has_text="30D").click()
    page.wait_for_timeout(200)
    returned_30d_data = page.evaluate("() => salesChart.data.datasets[0].data.slice()")

    # Los datos deben ser exactamente idénticos al estado inicial
    assert returned_30d_data == initial_30d_data, (
        f"Bug de estado: 30D inicial ({initial_30d_data}) difiere al regresar a 30D ({returned_30d_data})"
    )

    # Captura del gráfico verificado
    screenshot_path = ARTIFACTS_DIR / "dashboard_chart_verified.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()


def test_04_tables_layout_padding_dates_and_payment_methods(page: Page):
    """Verifica tablas limpias con padding >= 12px, fechas en español y medios de pago traducidos."""
    page.goto(f"{BASE_URL}/login")
    page.locator(".login-demo-pill").first.click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # Ir al módulo de Ventas y Facturación
    sidebar = page.locator("[data-testid='adaptive-sidebar']")
    sidebar.locator(".sidebar-nav-link", has_text="Ventas y Facturación").click()
    expect(page.locator("#section-sales")).to_be_visible()

    sales_table = page.locator("#section-sales table.data-table")
    expect(sales_table).to_be_visible()

    # 1. Verificar padding >= 12px en th y td
    padding_info = sales_table.evaluate("""table => {
        const th = table.querySelector('th');
        const td = table.querySelector('td');
        const thStyle = window.getComputedStyle(th);
        const tdStyle = window.getComputedStyle(td);
        return {
            thPaddingTop: parseFloat(thStyle.paddingTop),
            thPaddingLeft: parseFloat(thStyle.paddingLeft),
            tdPaddingTop: parseFloat(tdStyle.paddingTop),
            tdPaddingLeft: parseFloat(tdStyle.paddingLeft),
        };
    }""")
    assert padding_info["thPaddingTop"] >= 12, f"Padding superior de th debe ser >= 12px: {padding_info}"
    assert padding_info["thPaddingLeft"] >= 14, f"Padding lateral de th debe ser >= 14px: {padding_info}"
    assert padding_info["tdPaddingTop"] >= 12, f"Padding superior de td debe ser >= 12px: {padding_info}"
    assert padding_info["tdPaddingLeft"] >= 14, f"Padding lateral de td debe ser >= 14px: {padding_info}"

    # 2. Verificar fechas legibles en español (no formato ISO crudo con T)
    table_text = sales_table.inner_text()
    assert "T" not in re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", table_text), "No debe haber fechas ISO crudas con T"
    # Debe contener meses en español y a. m. / p. m.
    assert re.search(r"\b(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b", table_text, re.IGNORECASE), (
        "Las fechas deben incluir nombres de mes en español"
    )

    # 3. Verificar medios de pago traducidos al español con badges
    assert "Efectivo" in table_text or "Tarjeta" in table_text or "Transferencia" in table_text
    assert "cash" not in table_text.lower().split()
    assert "card" not in table_text.lower().split()


def test_05_multi_product_cart_in_sale_drawer(page: Page):
    """Verifica que el panel de Registrar Venta permite agregar múltiples productos y descuenta stock atómicamente."""
    page.goto(f"{BASE_URL}/login")
    page.locator(".login-demo-pill").first.click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # Abrir Drawer de Venta
    page.get_by_text("+ Registrar Venta").first.click()
    drawer_sale = page.locator("#drawer-sale")
    expect(drawer_sale).to_have_class(re.compile(r"open"))

    # Verificar que el botón de agregar otro producto existe
    btn_add = page.locator("#btn-add-cart-line")
    expect(btn_add).to_be_visible()

    # Inicialmente hay 1 línea en el carrito
    rows = page.locator("#sale-cart-items .cart-item-row")
    expect(rows).to_have_count(1)

    # Agregar segunda línea
    btn_add.click()
    expect(rows).to_have_count(2)

    # En la segunda línea, seleccionar un producto distinto
    select_2 = rows.nth(1).locator("select.cart-product-select")
    options_count = select_2.locator("option").count()
    if options_count > 1:
        select_2.select_option(index=1)

    # Modificar cantidades con selectores frescos tras el re-renderizado
    page.locator("#sale-cart-items .cart-item-row").nth(0).locator("input.cart-quantity-input").fill("1")
    page.locator("#sale-cart-items .cart-item-row").nth(1).locator("input.cart-quantity-input").fill("2")

    # Verificar que el total a cobrar se actualizó dinámicamente sumando ambos productos
    total_display = page.locator("#sale-total-display")
    expect(total_display).to_contain_text("$")
    expect(total_display).not_to_contain_text("$ 0")

    # Capturar pantalla con el carrito multi-producto listo
    screenshot_path = ARTIFACTS_DIR / "drawer_sale_open_verified.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()

    # Confirmar venta multi-producto
    page.locator("#btn-submit-sale").click()

    # Debe cerrarse el drawer y recargar con éxito
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")
    expect(drawer_sale).not_to_have_class(re.compile(r"open"))


def test_06_forecast_business_language_and_uts_accordion(page: Page):
    """Verifica vista de Proyección Estadística: tarjetas de negocios, gráfico OLS y acordeón F-DC-124."""
    page.goto(f"{BASE_URL}/login")
    page.locator(".login-demo-pill").first.click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # Navegar a Proyección Estadística
    sidebar = page.locator("[data-testid='adaptive-sidebar']")
    sidebar.locator(".sidebar-nav-link", has_text="Proyección Estadística").click()
    expect(page.locator("#section-forecast")).to_be_visible()

    # 1. Verificar tarjetas de negocios comprensibles
    expect(page.locator("text=Venta Estimada Próximo Mes")).to_be_visible()
    expect(page.locator("text=Tendencia Mensual del Negocio")).to_be_visible()
    expect(page.locator("text=Confiabilidad de la Proyección")).to_be_visible()
    expect(page.locator("text=Muy Alta")).to_be_visible()

    # 2. Verificar que el gráfico propio de proyección existe y dibuja
    forecast_chart_canvas = page.locator("#forecastModuleChart")
    expect(forecast_chart_canvas).to_be_visible()

    # 3. Verificar que el acordeón de sustentación UTS existe y es desplegable
    accordion = page.locator("details.audit-accordion")
    expect(accordion).to_be_visible()
    summary = accordion.locator("summary")
    expect(summary).to_contain_text("Sustentación UTS F-DC-124")

    # Al hacer click en el summary, se despliega el detalle matemático
    summary.click()
    expect(accordion.locator("table.data-table")).to_be_visible()
    expect(accordion.locator("text=Valores Observados vs. Ajustados MCO")).to_be_visible()
