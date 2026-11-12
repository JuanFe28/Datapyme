# ESTADO DE ORQUESTACIÓN Y ARQUITECTURA LIMPIA: DATAPYME (F-DC-124 / F-DC-125)

**Fecha de Actualización:** 12 de Noviembre de 2026  
**Entidad Académica:** Unidades Tecnológicas de Santander (UTS)  
**Proyecto:** Datapyme - Plataforma de Analítica Comercial para PyMEs de Bucaramanga  
**Agente Orquestador Principal:** Antigravity (Google DeepMind) + OpenCode Engine (`deepseek-v4.1-flash-free --variant max`)  

---

## 1. RESUMEN EJECUTIVO Y ARQUITECTURA MODULAR DESACOPLADA

La plataforma ha sido completamente auditada, saneada de código monolítico ("cero código por chorrera") y estructurada en capas limpias de responsabilidad única según los principios de Clean Architecture y las directrices de la UTS para el formato **F-DC-124**.

```
empresarial/
├── app/
│   ├── main.py                     # Fábrica ASGI (create_app), lifespan, middlewares y error handlers (<200 líneas)
│   ├── core/                       # Núcleo del dominio y persistencia
│   │   ├── config.py               # Configuración tipada Pydantic / Twelve-Factor
│   │   ├── dependencies.py         # Inyección de dependencias (get_db, get_current_context, auth)
│   │   ├── jinja_filters.py        # Serializadores y filtros de formato colombiano (COP, %, fechas)
│   │   ├── models.py               # Modelos SQLAlchemy relacionales multi-tenant
│   │   ├── schemas.py              # Esquemas de validación Pydantic v2
│   │   ├── security.py             # Argon2id, SHA-256, tokens de sesión y hashing anti-CSRF
│   │   ├── commercial_service.py   # Lógica pura de inventario (Kardex) y ventas atómicas
│   │   ├── image_service.py        # Validación estricta y aislamiento de imágenes de productos
│   │   └── demo_seed.py            # Sembrado determinístico de tenants de contraste F-DC-125
│   ├── routes/                     # Enrutadores modulares desacoplados (APIRouter)
│   │   ├── auth.py                 # Login, logout, sesiones y registro con consentimiento Ley 1581
│   │   ├── products.py             # Catálogo de productos, edición, consulta y fotos
│   │   ├── inventory.py            # Movimientos Kardex, ajustes y alertas de existencias
│   │   ├── sales.py                # Facturación atómica multi-producto, comprobantes y anulación
│   │   ├── imports.py              # Inspección e importación inteligente de Excel/CSV
│   │   ├── dashboard.py            # Dashboard adaptativo según encuesta y preferencias
│   │   ├── forecast.py             # Pronósticos estadísticos OLS y KPIs comerciales
│   │   └── admin.py                # Panel HTML de impacto SuperAdmin (UTS) y Habeas Data
│   ├── imports/                    # Procesamiento y mapeo masivo
│   │   ├── smart_excel_mapper.py   # Mapeador heurístico inteligente multi-hoja (openpyxl puro)
│   │   └── batch_importer.py       # Importación por lotes con sanitización anti-fórmulas
│   ├── analytics/                  # Inteligencia de negocios
│   │   └── kpis.py                 # Pareto 80/20, rotación, margen y productos estancados
│   ├── forecast/                   # Analítica predictiva
│   │   └── stats.py                # Regresión Lineal OLS exacta (y = a + bx), R², SMA-3 y WMA-3
│   ├── telemetry/                  # Gobernanza y auditoría
│   │   └── impact_service.py       # Agregador de impacto F-DC-125 con k-anonimato (k >= 3)
│   └── ui/                         # Personalización adaptativa
│       └── ui_personalization_service.py # Ponderador de interfaz basado en diagnóstico
├── static/                         # Activos web estáticos
│   ├── css/tokens.css              # Sistema de diseño Apple HIG / Polaris (variables OKLCH/Hex)
│   ├── js/                         # JavaScript modular desacoplado
│   └── vendor/                     # Librerías locales (Chart.js, Lucide, sin CDNs externos)
├── templates/                      # Plantillas Jinja2 semánticas y accesibles
│   ├── dashboard.html              # Bento Grid adaptable (Ventas, Inventario, Predicción)
│   ├── login.html                  # Autenticación con acceso a credenciales demo de prueba
│   ├── superadmin_impact.html      # Panel visual para Auditor UTS (telemetría agregada F-DC-125)
│   └── error.html                  # Vistas gráficas para 401, 403, 404 y 500 (cero JSON crudo)
└── tests/                          # Suite automatizada (100% verde)
    ├── unit/                       # Pruebas matemáticas, heurísticas y de fundamentos
    ├── security/                   # Aislamiento multi-tenant, sesiones, CSRF y subida de archivos
    ├── integration/                # Flujos completos de base de datos y conciliación Kardex
    └── e2e/                        # Pruebas con navegador real Playwright (escritorio y móvil)
```

---

## 2. COMANDOS DE ARRANQUE Y DESPLIEGUE

### A. Ejecución en Computador Local (Windows)
* **Script de Un Clic:** Ejecutar el archivo `iniciar_datapyme.bat` en la raíz.
* **Arranque manual por terminal:**
  ```powershell
  .\.venv\Scripts\python.exe -m uvicorn empresarial.app.main:app --host 0.0.0.0 --port 8000
  ```
* **Acceso local:** [http://127.0.0.1:8000](http://127.0.0.1:8000)

### B. Servidor en la Nube 24/7 (Oracle Cloud VM)
* **IP de la Instancia:** `150.136.74.164` (Ubuntu 24.04 LTS / Docker Compose).
* **Base de Datos:** PostgreSQL 16 Alpine en contenedor aislado `datapyme_empresarial_db`.
* **Aplicación:** Contenedor `datapyme_empresarial_app` (FastAPI / Uvicorn).
* **Túnel Seguro Cloudflare 24/7:** Contenedor `datapyme_empresarial_tunnel`.
* **URL Pública Oficial con HTTPS:**
  **`https://driving-where-bicycle-indiana.trycloudflare.com`**

---

## 3. RESUMEN DE PRUEBAS AUTOMATIZADAS

| Categoría de Prueba | Archivo de Pruebas | Casos | Estado |
|:---|:---|:---:|:---:|
| **Fundamentos & Tokens** | `tests/unit/test_sprint0_foundations.py` | 4 | **100% Verde** |
| **Matemática de KPIs** | `tests/unit/test_sprint3_kpis_math.py` | 4 | **100% Verde** |
| **Regresión Predictiva OLS** | `tests/unit/test_sprint4_forecast_ols.py` | 5 | **100% Verde** |
| **Personalización UI** | `tests/unit/test_ui_personalization.py` | 4 | **100% Verde** |
| **Mapeador Inteligente Excel** | `tests/unit/test_smart_excel_mapper.py` | 3 | **100% Verde** |
| **Seguridad de Archivos e Imágenes** | `tests/security/test_product_image_upload.py` | 6 | **100% Verde** |
| **Aislamiento Multi-Tenant & Fórmulas** | `tests/security/test_sprint2_upload_and_isolation.py` | 2 | **100% Verde** |
| **Habeas Data & k-Anonimato** | `tests/security/test_sprint5_telemetry_and_habeas_data.py` | 1 | **100% Verde** |
| **Sesiones, Cookies y Anti-Fuerza Bruta** | `tests/security/test_sprint7_login_and_sessions.py` | 2 | **100% Verde** |
| **Integración Ventas & Kardex** | `tests/integration/test_sprint2_sales_and_inventory.py` | 2 | **100% Verde** |
| **Integración Bento Dashboard** | `tests/integration/test_sprint3_bento_dashboard.py` | 1 | **100% Verde** |
| **Sembrado de Contraste F-DC-125** | `tests/integration/test_sprint6_contrast_seed_and_e2e.py` | 1 | **100% Verde** |
| **E2E Playwright Escritorio** | `tests/e2e/test_critical_flows_and_superadmin.py` | 4 | **100% Verde** |
| **E2E Playwright Móvil** | `tests/e2e/test_mobile_responsive.py` | 3 | **100% Verde** |
| **E2E Imágenes y Excel Mapper** | `tests/e2e/test_images_and_excel_mapper.py` | 2 | **100% Verde** |
| **TOTAL GENERAL** | **42 pruebas automatizadas** | **42** | **100% PASADAS** |

---

## 4. AUDITORÍA DE CALIDAD DE CÓDIGO (LINTERS & FORMATTERS)
* **Linter:** `ruff check empresarial` -> **0 errores, 0 advertencias**.
* **Formatter:** `ruff format --check empresarial` -> **100% formateado (62 archivos limpios)**.
* **Archivos basura eliminados:** Eliminadas capturas temporales sueltas, bases de datos de prueba `.db`, archivos `.log` y documentos duplicados.
