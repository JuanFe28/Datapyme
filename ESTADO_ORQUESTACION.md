# Corte técnico vigente — 17/11/2026

Consultar [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md) y la
[guía del piloto](empresarial/docs/ENTREGA_PILOTO_2026_11_17.md).
96 pruebas Python y once JavaScript aprobadas. PostgreSQL local: concurrencia,
restauración e históricos comprobados; recorrido visible de cuatro perfiles y móvil.
Falta instalar y comprobar esta revisión en el servidor; no se declara producción validada.
Los informes anteriores de este archivo se conservan como historia.

# ESTADO DE ORQUESTACIÓN Y ARQUITECTURA LIMPIA: DATAPYME (F-DC-124 / F-DC-125)

> **IVA por empresa implementado 13/11/2026:** condición editable, historial y
> aplicación a operaciones nuevas. Pendiente bloquea ventas; no responsable no
> adiciona IVA; responsable usa la tarifa del artículo. Ventas anteriores conservadas.
> [Uso, actualización y pruebas](empresarial/docs/IVA_POR_EMPRESA.md).

> **Revisión de IVA 13/11/2026:** corregidos IVA visual uniforme, pérdida de tarifas
> en importación/edición y utilidad sin descuentos. [Informe y fuentes oficiales](empresarial/docs/REVISION_IVA_COLOMBIA_2026_11_13.md).
> Condiciones tributarias de los comercios parcialmente desconocidas: falta
> configuración por empresa; no anunciar cumplimiento fiscal integral ni facturación DIAN.

> **Revisión funcional del 13/11/2026:** el recorrido por las cuatro cuentas demo
> confirmó dos roles efectivos, encontró errores de importación y mensajes de
> consentimiento, y mantiene pendientes de CSV, supresión y series temporales.
> Ver [pruebas, correcciones y límites](empresarial/docs/QA_ROLES_2026_11_13.md).
> Las afirmaciones históricas de finalización siguientes no sustituyen esta
> evidencia ni autorizan a afirmar que el proyecto completo está validado.

**Fecha de Actualización:** 16 de Noviembre de 2026  
**Entidad Académica:** Unidades Tecnológicas de Santander (UTS)  
**Proyecto:** Datapyme - Plataforma de Analítica Comercial para PyMEs de Bucaramanga  
**Agente Orquestador Principal:** Antigravity (Google DeepMind) — Modo Producción Real (7 Pilares)  

---

## 1. RESUMEN EJECUTIVO Y ARQUITECTURA MODULAR DESACOPLADA

La plataforma ha sido completamente auditada, saneada de código monolítico ("cero código por chorrera") y estructurada en capas limpias de responsabilidad única según los principios de Clean Architecture y las directrices de la UTS para el formato **F-DC-124**.

```
empresarial/
├── app/
│   ├── main.py                     # Fábrica ASGI (create_app), lifespan, middlewares y error handlers (<200 líneas)
│   ├── core/                       # Núcleo del dominio y persistencia
│   │   ├── config.py               # Configuración tipada Pydantic / Twelve-Factor
│   │   ├── dependencies.py         # Inyección de dependencias, sesiones y login triple (user/tel/correo)
│   │   ├── jinja_filters.py        # Serializadores y filtros de formato colombiano (COP, %, fechas)
│   │   ├── models.py               # Modelos relacionales multi-tenant y triggers Kardex/Ley 1581
│   │   ├── schemas.py              # Esquemas de validación Pydantic v2
│   │   ├── security.py             # Argon2id, SHA-256, tokens de sesión y hashing anti-CSRF
│   │   ├── mfa_service.py          # MFA TOTP RFC 6238 offline, QR SVG en memoria y códigos de respaldo
│   │   ├── provisioning_service.py # Entrega de perfiles reales, primer ingreso y consentimientos
│   │   ├── research_sync_service.py# Puente idempotente desde Research Studio hacia Empresarial
│   │   ├── commercial_service.py   # Lógica pura de inventario (Kardex) y ventas atómicas
│   │   ├── image_service.py        # Validación estricta y aislamiento de imágenes de productos
│   │   └── demo_seed.py            # Sembrado determinístico de tenants de contraste F-DC-125
│   ├── routes/                     # Enrutadores modulares desacoplados (APIRouter)
│   │   ├── auth.py                 # Login triple, MFA /login/mfa, primer ingreso, registro y sesiones
│   │   ├── products.py             # Catálogo de productos, edición, consulta y fotos
│   │   ├── inventory.py            # Movimientos Kardex, ajustes y alertas de existencias
│   │   ├── sales.py                # Facturación atómica multi-producto, comprobantes y anulación
│   │   ├── imports.py              # Inspección e importación inteligente de Excel/CSV
│   │   ├── dashboard.py            # Dashboard adaptativo, Plan de Acción y Tour Onboarding
│   │   ├── forecast.py             # Pronósticos OLS, KPIs y endpoint de rentabilidad P&L
│   │   └── admin.py                # Panel HTML SuperAdmin, sincronización Research Studio y reset MFA
│   ├── imports/                    # Procesamiento y mapeo masivo
│   │   ├── smart_excel_mapper.py   # Mapeador heurístico inteligente multi-hoja (openpyxl puro)
│   │   └── batch_importer.py       # Importación por lotes con sanitización anti-fórmulas
│   ├── analytics/                  # Inteligencia de negocios determinista
│   │   ├── kpis.py                 # Pareto 80/20, rotación, margen y productos estancados
│   │   ├── profitability.py        # P&L exacto (COGS, mermas, bajo costo) y rankings de productos
│   │   └── action_advisor.py       # Plan de Acción Comercial (reorden, liberación de efectivo, meta OLS)
│   ├── forecast/                   # Analítica predictiva
│   │   └── stats.py                # Regresión Lineal OLS exacta (y = a + bx), R², SMA-3 y WMA-3
│   ├── telemetry/                  # Gobernanza y auditoría
│   │   └── impact_service.py       # Agregador de impacto F-DC-125 con k-anonimato (k >= 3)
│   └── ui/                         # Personalización adaptativa
│       └── ui_personalization_service.py # Ponderador de interfaz basado en diagnóstico
├── static/                         # Activos web estáticos
│   ├── css/
│   │   ├── tokens.css              # Sistema de diseño Apple HIG / Impeccable / Polaris
│   │   └── spotlight_tour.css      # Estilos del Tour Interactivo Spotlight
│   ├── js/
│   │   ├── app.js                  # Controlador principal y gráficas Chart.js
│   │   └── spotlight_tour.js       # Motor de tutorial guiado con práctica autolimpiable
│   └── vendor/                     # Librerías locales (Chart.js, Lucide, sin CDNs externos)
├── templates/                      # Plantillas Jinja2 semánticas y accesibles
│   ├── dashboard.html              # Bento Grid adaptable, P&L, Plan de Acción y 2FA
│   ├── login.html                  # Login corporativo limpio (modo auditor bajo ?modo=auditor)
│   ├── login_mfa.html              # Verificación en Dos Pasos (TOTP / respaldo)
│   ├── activate_account.html       # Primer ingreso obligatorio (clave privada + Ley 1581 + 2FA)
│   ├── register.html               # Auto-registro guiado en 2 pasos
│   ├── superadmin_impact.html      # Panel visual Auditor UTS (F-DC-125, sincronización y soporte)
│   └── error.html                  # Vistas gráficas limpias para 401, 403, 404 y 500
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

## 3. RESUMEN DE PRUEBAS AUTOMATIZADAS (ESTADO ACTUAL: 72/72 EN VERDE)

| Categoría de Prueba | Archivos de Pruebas Principales | Casos | Estado |
|:---|:---|:---:|:---:|
| **Unitarias (Core, KPIs, P&L, MFA, Advisor, OLS, Mapper, UI)** | `tests/unit/test_*.py` | 17 | **100% Verde** |
| **Seguridad (Aislamiento, CSRF, Ley 1581, k-Anonimato, Sin IA, Sesiones, Uploads)** | `tests/security/test_*.py` | 15 | **100% Verde** |
| **Integración (Sync Research Studio, Login Triple, MFA, IVA, Ventas/Kardex, Primer Ingreso)** | `tests/integration/test_*.py` | 19 | **100% Verde** |
| **E2E Playwright (Escritorio, Móvil 390px, Spotlight Tour, P&L, Auditoría)** | `tests/e2e/test_*.py` | 19 | **100% Verde** |
| **Frontend JS Unit (`node --test`)** | `tests/frontend/vat.test.cjs` | 2 | **100% Verde** |
| **TOTAL VERIFICADO** | **70 `pytest` + 2 `node --test`** | **72** | **100% PASADAS** |

---

## 4. AUDITORÍA DE CALIDAD DE CÓDIGO (LINTERS & FORMATTERS)
* **Linter:** `ruff check empresarial` -> **0 errores, 0 advertencias**.
* **Formatter:** `ruff format --check empresarial` -> **100% formateado (79 archivos limpios)**.
* **Archivos privados:** `CREDENCIALES_PRIVADAS_PRODUCCION.md` y `USO_PRIVADO_EQUIPO.txt` excluidos estrictamente mediante `.gitignore` (nunca rastreados en Git).

---

## 5. RELEASE PRODUCCIÓN REAL (F-DC-124 / F-DC-125 · LOS 7 PILARES)

* **Login Corporativo Limpio + Modo Auditor (`/login` vs `/login?modo=auditor`):** Pastillas demo ocultadas en la vista pública del comerciante y jerga interna eliminada de plantillas operativas (`base.html`, `dashboard.html`, `activate_account.html`, `register.html`, `error.html`).
* **Puente `Research Studio` -> `Datapyme Empresarial` (`app/core/research_sync_service.py`):** Sincronización idempotente de las 13 PyMEs reales con encuesta de mercado completa (incluyendo **VaFel Sweet** bajo usuario `vafelsweet` y celular `3052621817`), todas inicializadas con `0` productos y `0` ventas, `must_change_password=True`, pesos adaptativos `map-v1` y login triple (`username`, `phone`, `email`).
* **MFA TOTP RFC 6238 Gratuito y Offline (`app/core/mfa_service.py`):** QR SVG generado en memoria (`segno` + `pyotp`), ventana de tolerancia `+-30s`, 5 códigos de respaldo SHA-256 de un solo uso, ruta `/login/mfa` y botón de soporte `POST /api/admin/users/{user_id}/reset-mfa` en `/admin/impacto`.
* **Tour Interactivo "Spotlight" (`static/js/spotlight_tour.js`):** 5 pasos guiados desde cuenta en cero con recorte dinámico, práctica de creación de producto y venta marcados como `is_training_data=True`, y borrado atómico en `POST /api/onboarding/complete-tour` conservando intacta la inmutabilidad del Kardex real (`WHEN OLD.is_training_data = 0`).
* **Plan de Acción Comercial de la Semana (`app/analytics/action_advisor.py`) + Nuevas Gráficas:** Reabastecimiento por punto de reorden, simulador de liberación de efectivo (`10%`, `15%`, `20%` protegido sobre costo), termómetro de meta mensual OLS, barras por categoría, distribución por método de pago y mapa visual de salud de stock.
