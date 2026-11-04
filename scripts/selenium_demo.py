import os
import sys
import time

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ARTIFACTS_DIR = r"C:\Users\juanf\.gemini\antigravity\brain\8b18e9c9-0c5a-4803-9c78-8fca73d1a004"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1280,1000")
opts.add_argument("--disable-gpu")
opts.add_argument("--no-sandbox")

print("1. Iniciando navegador Edge con Selenium...")
driver = webdriver.Edge(options=opts)
wait = WebDriverWait(driver, 15)

try:
    # 1. Acceder al registro público
    url = "https://employed-belong-cannon-each.trycloudflare.com/registro-empresa"
    print(f"2. Navegando a: {url}")
    driver.get(url)
    time.sleep(2)

    # 2. Llenar Paso 1 (Registro de empresa)
    print("3. Diligenciando formulario de registro Paso 1...")
    name_input = driver.find_element(By.NAME, "name")
    name_input.send_keys("Comercio Demo Selenium")
    
    barrio_input = driver.find_element(By.NAME, "barrio")
    barrio_input.send_keys("Cabecera")
    
    contact_input = driver.find_element(By.NAME, "contact_detail")
    contact_input.send_keys("315 888 7766")
    
    # Marcar consentimiento si no está marcado
    consent_cb = driver.find_element(By.NAME, "consent")
    if not consent_cb.is_selected():
        driver.execute_script("arguments[0].click();", consent_cb)

    # Enviar Paso 1
    submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    driver.execute_script("arguments[0].click();", submit_btn)
    time.sleep(3)

    # 3. Llegar a la pantalla de éxito o a la encuesta
    print(f"4. Página posterior al registro: {driver.current_url}")
    survey_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Responder Encuesta")))
    print("5. Ingresando al Paso 2: Encuesta de Estudio de Mercado...")
    driver.execute_script("arguments[0].click();", survey_link)
    time.sleep(3)

    print(f"6. En la Encuesta: {driver.current_url}")
    wait.until(EC.presence_of_element_located((By.ID, "surveyForm")))

    # 4. Probar la selección múltiple en M10 (Dificultades - máximo 3)
    print("7. Probando límite de 3 opciones en M10...")
    m10_tiles = driver.find_elements(By.CSS_SELECTOR, "[data-question='M10'] .option-tile input[type='checkbox']")
    print(f"   Total opciones en M10: {len(m10_tiles)}")
    
    # Seleccionar 3 opciones
    for i in range(3):
        driver.execute_script("arguments[0].click();", m10_tiles[i])
        time.sleep(0.3)

    time.sleep(1)
    
    # Verificar que las demás opciones quedaron deshabilitadas
    disabled_tiles = driver.find_elements(By.CSS_SELECTOR, "[data-question='M10'] .option-tile.disabled-tile")
    badge = driver.find_element(By.CSS_SELECTOR, "[data-question='M10'] .badge-counter")
    print(f"   -> Badge contador en M10: '{badge.text}'")
    print(f"   -> Opciones deshabilitadas automáticamente: {len(disabled_tiles)}")
    assert len(disabled_tiles) > 0, "Las opciones restantes debieron deshabilitarse"

    # Capturar pantalla del límite de 3
    limit_screenshot = os.path.join(ARTIFACTS_DIR, "demo_limite_3_opciones.png")
    m10_elem = driver.find_element(By.CSS_SELECTOR, "[data-question='M10']")
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", m10_elem)
    time.sleep(1)
    driver.save_screenshot(limit_screenshot)
    print(f"   -> Captura guardada: {limit_screenshot}")

    # 5. Intentar enviar la encuesta INCOMPLETA (faltan M05, M06, M07, M08, M09, M11, etc.)
    print("8. Bajando al botón final para intentar enviar la encuesta INCOMPLETA...")
    final_submit = driver.find_element(By.CSS_SELECTOR, "#surveyForm button[type='submit']")
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", final_submit)
    time.sleep(1)

    print("9. Haciendo clic en 'Finalizar y Enviar Encuesta'...")
    driver.execute_script("arguments[0].click();", final_submit)
    time.sleep(2)

    # 6. Verificar que la pantalla se detuvo y no se envió
    assert "public_survey_success" not in driver.current_url, "El formulario no debió enviarse"
    
    # Verificar elementos en rojo y alertas
    error_questions = driver.find_elements(By.CSS_SELECTOR, ".question.question-error")
    error_alerts = driver.find_elements(By.CSS_SELECTOR, ".live-error-alert")
    submit_notice = driver.find_element(By.ID, "submitNotice")
    
    print(f"10. VERIFICACIÓN DE ERROR:")
    print(f"    - Preguntas resaltadas en rojo: {len(error_questions)}")
    print(f"    - Alertas de error específicas mostradas: {len(error_alerts)}")
    print(f"    - Mensaje de aviso en el botón: '{submit_notice.text.strip()}'")

    # Captura de pantalla de la pregunta a la que se hizo scroll automático
    error_screenshot = os.path.join(ARTIFACTS_DIR, "demo_error_scroll_rojo.png")
    time.sleep(1.5)  # Esperar que termine el smooth scroll
    driver.save_screenshot(error_screenshot)
    print(f"    - Captura guardada (primer error enfocado): {error_screenshot}")

    # Captura del aviso inferior
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", submit_notice)
    time.sleep(1)
    notice_screenshot = os.path.join(ARTIFACTS_DIR, "demo_aviso_boton_inferior.png")
    driver.save_screenshot(notice_screenshot)
    print(f"    - Captura guardada (aviso inferior): {notice_screenshot}")

    print("\n✅ DEMOSTRACIÓN CON SELENIUM COMPLETADA CON ÉXITO.")

finally:
    driver.quit()
    print("Navegador cerrado.")
