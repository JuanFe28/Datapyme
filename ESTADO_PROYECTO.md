# ESTADO DEL PROYECTO: DATAPYME (F-DC-124 / F-DC-125)

**Fecha de Actualización:** 12 de Noviembre de 2026  
**Entidad:** Unidades Tecnológicas de Santander (UTS)  
**Proyecto:** Datapyme - Plataforma de Analítica Comercial para PyMEs de Bucaramanga  
**Agente Orquestador:** Antigravity (Google DeepMind) + OpenCode Engine  

---

## 1. DIAGNÓSTICO DEL SISTEMA Y REPARACIÓN ANTI-CAÍDAS

### ¿Por qué se cayó el servidor previamente?
1. **Reinicio de Sesión / Sistema Operativo:** Al reiniciar el equipo o apagarse la sesión, los procesos en segundo plano de `uvicorn` y `cloudflared` finalizaron automáticamente.
2. **Falta de Manejador Global de Excepciones:** Las aplicaciones FastAPI carecían de un `exception_handler(Exception)` general, lo cual arriesgaba que un error no previsto en una petición aislada desestabilizara el proceso de trabajo.

### Medidas de Blindaje Implementadas:
* **Global Exception Handlers:** Integrados en `app.py` y `empresarial/app/main.py`. Cualquier excepción inesperada es capturada, registrada en `uvicorn.error` y respondida limpiamente (JSON o HTML de contingencia) sin detener el servidor.
* **Auto-Recuperación en Scripts Ejecutables:**
  * `iniciar_datapyme.bat`: Inicia Uvicorn escuchando en `0.0.0.0:8000` con proxy headers activados.
  * `iniciar_tunel_https.bat`: Levanta el túnel seguro de Cloudflare hacia `http://127.0.0.1:8000` con protocolo HTTP/2.

---

## 2. MEJORAS OPERATIVAS INCORPORADAS

### A. Imágenes de Producto en Inventario (Actividades 3.3 y 3.7 F-DC-124)
* **Modelo y Migración:** Columna `image_url` en la tabla `products`, con auto-migración en SQLite.
* **Seguridad F-DC-124 (`image_service.py`):**
  * Validación estricta de extensiones (`.jpg`, `.jpeg`, `.png`, `.webp`).
  * Validación binaria de *magic bytes* (evita extensiones falsificadas y bloquea scripts maliciosos en SVGs o binarios `.exe`).
  * Límite de tamaño: 2 MB.
  * Aislamiento Multi-Tenant: Almacenamiento en `static/uploads/tenants/{tenant_id}/products/{uuid}.{ext}`.
* **Interfaz de Usuario (Apple HIG):**
  * Miniaturas cuadradas de `40x40px` con bordes redondeados (`8px`) en la tabla de Catálogo e Inventario.
  * Insignias vectoriales SVG de respaldo en caso de no adjuntar imagen.
  * Miniatura visual integrada en el Carrito Multi-Producto de `+ Registrar Venta`.
  * Generador de 15 íconos SVG de alta fidelidad para productos de demostración (`demo_seed.py`).

### B. Importador Inteligente de Excel Multi-Hoja (`smart_excel_mapper.py`)
* **100% Python Puro:** Basado en `openpyxl` y `csv` sin dependencias de APIs externas.
* **Inspección Multi-Hoja:** Lee todas las pestañas del libro y permite seleccionar qué hoja procesar.
* **Detección Automática de Encabezados:** Escanea las primeras 15 filas identificando dónde inician los títulos reales, ignorando membretes o filas vacías.
* **Diccionario de Sinónimos Comerciales Colombianos:**
  * Reconoce automáticamente variantes: *Ref/Código/SKU*, *Artículo/Producto/Descripción*, *Línea/Categoría*, *Costo/Costo Unitario*, *PVP/Precio Venta*, *Existencias/Stock*, *Presentación/Unidad*.
  * Generación automática de SKU consecutivo (`AUTO-0001`, `AUTO-0002`...) si la empresa no maneja códigos propios.
  * Limpieza contable de monedas colombianas (`$ 1.250.000,00` -> `1250000.00`).
* **Experiencia en Drawer:**
  * Vista previa interactiva de las primeras filas.
  * Desplegables para ajustar el mapeo de columnas si el comerciante lo desea.

---

## 3. RESUMEN DE PRUEBAS AUTOMATIZADAS

| Suite de Pruebas | Archivo | Estado |
|---|---|---|
| Fundamentos & Reglas (Cero Emojis) | `tests/unit/test_sprint0_foundations.py` | 4/4 Pasadas |
| Mapeador Inteligente Excel | `tests/unit/test_smart_excel_mapper.py` | 3/3 Pasadas |
| Seguridad Subida de Imágenes | `tests/security/test_product_image_upload.py` | 6/6 Pasadas |
| Sesiones, CSRF y Cookies HTTPS | `tests/security/test_sprint7_login_and_sessions.py` | 4/4 Pasadas |
| Playwright E2E Miniaturas & Mapper | `tests/e2e/test_images_and_excel_mapper.py` | 2/2 Pasadas |
| Playwright E2E Móvil (iPhone 14) | `tests/e2e/test_mobile_responsive.py` | 3/3 Pasadas |
| **Total Global** | **40 pruebas automatizadas** | **100% Verde** |

---

## 4. ESTADO DE GIT Y DESPLIEGUE
* **Repositorio:** `https://github.com/JuanFe28/Datapyme.git`
* **Rama Principal:** `main`
* **Integración en Render:** `app.py` monta la aplicación SaaS bajo el prefijo `/empresarial`, compartiendo dominio HTTPS oficial.
