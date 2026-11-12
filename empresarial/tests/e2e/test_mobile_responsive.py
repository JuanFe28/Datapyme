"""
Pruebas E2E de Responsividad Móvil con Playwright (Emulación iPhone 14 - 390x844)
UTS F-DC-124 / F-DC-125.
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

BASE_URL = os.environ.get("DATAPYME_TEST_URL", "http://127.0.0.1:8010")
ARTIFACTS_DIR = Path(r"C:\Users\juanf\.gemini\antigravity\brain\46e60f00-dd8e-472a-98a1-c0a401f7e5ca")


@pytest.fixture(scope="session", autouse=True)
def live_server():
    """Garantiza que el servidor de pruebas esté activo."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_open = sock.connect_ex(("127.0.0.1", 8010)) == 0
    sock.close()

    if not is_open:
        from app.main import create_app

        test_app = create_app()
        config = uvicorn.Config(test_app, host="127.0.0.1", port=8010, log_level="error")
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        time.sleep(1.2)
        yield
        server.should_exit = True
    else:
        yield


def test_01_mobile_login_no_overflow_and_screenshot(page: Page):
    """Verifica que la pantalla de Login no tenga scroll horizontal en pantalla móvil de 390px."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")

    # Verificar CERO scroll horizontal
    scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
    assert scroll_w <= 390, f"Desbordamiento horizontal detectado en Login: {scroll_w}px > 390px"

    # Captura vertical móvil
    screenshot_path = ARTIFACTS_DIR / "mobile_login.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()


def test_02_mobile_dashboard_navigation_and_zero_overflow(page: Page):
    """Verifica navegación móvil por Bottom Tab Bar y ausencia de desbordamiento horizontal en todas las secciones."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE_URL}/login")
    page.locator("button[data-demo-email='demo.ferreteria@datapyme.co']").click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # En móvil, el sidebar tradicional debe estar oculto
    sidebar = page.locator("[data-testid='adaptive-sidebar']")
    expect(sidebar).not_to_be_visible()

    # La barra inferior móvil debe estar visible
    bottom_bar = page.locator(".mobile-bottom-bar")
    expect(bottom_bar).to_be_visible()

    # Verificar que en el Panel Principal no hay desbordamiento horizontal
    scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
    assert scroll_w <= 390, f"Desbordamiento horizontal en Inicio: {scroll_w}px > 390px"

    # Captura de pantalla de Inicio en móvil
    screenshot_path = ARTIFACTS_DIR / "mobile_dashboard.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()

    # Probar navegación a cada módulo con la barra inferior
    modules = [
        ("Inventario", "#section-inventory"),
        ("Ventas", "#section-sales"),
        ("Proyección", "#section-forecast"),
        ("Mis Datos", "#section-my_data"),
        ("Inicio", "#section-home"),
    ]

    for label, section_id in modules:
        tab = bottom_bar.locator(".mobile-tab-item", has_text=label)
        expect(tab).to_be_visible()
        tab.click()
        page.wait_for_timeout(300)
        expect(page.locator(section_id)).to_be_visible()

        # Verificar CERO desbordamiento en cada sección
        sw = page.evaluate("() => document.documentElement.scrollWidth")
        assert sw <= 390, f"Desbordamiento horizontal en sección {label}: {sw}px > 390px"


def test_03_mobile_sale_drawer_full_width_and_interaction(page: Page):
    """Verifica que el Drawer de Registrar Venta se abra al 100% de ancho en móvil y sea completamente operativo."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE_URL}/login")
    page.locator("button[data-demo-email='demo.ferreteria@datapyme.co']").click()
    page.locator(".login-btn-submit").click()
    page.wait_for_url("**/dashboard")
    page.wait_for_load_state("networkidle")

    # Abrir Drawer de Venta
    page.locator("button:has-text('+ Registrar Venta')").first.click()
    drawer = page.locator("#drawer-sale")
    expect(drawer).to_have_class(re.compile(r"open"))

    # Ancho del panel debe cubrir la pantalla completa del celular
    panel_w = page.evaluate(
        "() => document.querySelector('#drawer-sale .drawer-panel').getBoundingClientRect().width"
    )
    assert panel_w >= 380, f"El drawer debe ocupar el 100% de la pantalla móvil: {panel_w}px"

    # Captura vertical de celular con el drawer abierto
    screenshot_path = ARTIFACTS_DIR / "mobile_drawer_venta.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.exists()

    # Cerrar drawer
    page.locator("button[data-close-drawer='drawer-sale']").first.click()
    page.wait_for_timeout(400)
    expect(drawer).not_to_have_class(re.compile(r"open"))
