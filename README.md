# Estado del piloto — 17/11/2026

Revisión vigente en [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md). La versión candidata
aprobó 76 pruebas Python y cuatro JavaScript; todavía requiere instalación y
verificación en el servidor de Juan Felipe. No interpretar las declaraciones
históricas siguientes como validación del despliegue o de pruebas con empresas.
Guía: [entrega del piloto](empresarial/docs/ENTREGA_PILOTO_2026_11_17.md).
Las cuentas demo públicas se admiten en desarrollo y se bloquean en producción.

# Datapyme — Plataforma de Analítica Comercial y Entorno de Investigación (UTS F-DC-124 / F-DC-125)

Sistema integral desarrollado para las **Unidades Tecnológicas de Santander (UTS)** en el marco del proyecto de investigación aplicada para la digitalización y analítica de micro y pequeñas empresas comerciales en Bucaramanga.

El repositorio contiene dos componentes perfectamente integrados y desacoplados:

1. **Datapyme Empresarial (`empresarial/` | Ruta: `/empresarial` o puerto 8000/8010):**
   * **Objetivo 3 del formato F-DC-124:** Plataforma SaaS multi-tenant en **Modo Producción Real** para comercios de Bucaramanga.
   * Módulos de Ventas POS atómicas (con IVA editable por empresa), Catálogo con imágenes, Kardex inmutable (con soporte para limpieza de datos de entrenamiento), Mapeador inteligente de Excel multi-hoja, Motor P&L de Ganancias/Pérdidas, **Plan de Acción Comercial de la Semana** (`action_advisor.py`), Bento Dashboard adaptativo, Proyecciones OLS/SMA/WMA, Verificación en Dos Pasos **MFA TOTP RFC 6238** con QR SVG offline, Tour Interactivo **Spotlight** y Panel SuperAdmin con $k$-anonimato ($k \ge 3$).
   * Puente de sincronización desde `Research Studio` (`research_sync_service.py`) y autenticación por identificador triple (**usuario corto**, **celular** o **correo electrónico**).
   * Diseñado bajo lineamientos **Apple Human Interface Guidelines (HIG)**, **Impeccable** y **Shopify Polaris** con diseño responsivo para celulares y computadores.

2. **Datapyme Research Studio (`app.py` | Ruta: `/`):**
   * **Objetivos 1 y 2 del formato F-DC-124:** Plataforma privada para recopilar, estructurar y contrastar las encuestas diagnósticas, entrevistas a profundidad, Business Model Canvas y escenarios de viabilidad financiera.

---

## Arranque Rápido en 1 Minuto

### Opción 1: En este computador local (Windows)
Hacer doble clic en **`iniciar_datapyme.bat`** en la raíz o ejecutar:
```powershell
.\.venv\Scripts\python.exe -m uvicorn empresarial.app.main:app --host 0.0.0.0 --port 8000
```
Abrir en el navegador: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Opción 2: Servidor en la Nube 24/7 (Oracle Cloud VM)
La aplicación cuenta con despliegue permanente mediante Docker Compose y Cloudflare Tunnel:
* **URL Pública Oficial (HTTPS):** [https://driving-where-bicycle-indiana.trycloudflare.com](https://driving-where-bicycle-indiana.trycloudflare.com)
* **Base de datos:** PostgreSQL 16 Alpine persistente.

---

## Cuentas Demo y Modo Auditor (`/login?modo=auditor`)

La vista pública (`/login`) presenta una interfaz limpia exclusiva para empresas reales (con acceso directo por usuario corto, celular o correo y enlace de registro `/registro`). Para evaluación técnica y sustentación F-DC-125, accede a **`/login?modo=auditor`** para habilitar las cuentas de demostración:

| Perfil Demo | Usuario Corto | Correo Electrónico | Contraseña | Enfoque Evaluado |
|:---|:---|:---|:---|:---|
| **Auditor UTS (SuperAdmin)** | `auditoruts` | `superadmin.demo@datapyme.co` | `SuperAdmin2026!` | Panel Visual `/admin/impacto` ($k \ge 3$), CSV y Soporte MFA |
| **Ferretería Cabecera** | `ferreteriacabecera` | `demo.ferreteria@datapyme.co` | `DemoFerreteria2026!` | Enfoque Inventarios y Alertas |
| **Boutique San Pío** | `boutiquesanpio` | `demo.boutique@datapyme.co` | `DemoBoutique2026!` | Enfoque Ventas y P&L |
| **Minimercado Real** | `minimercadoreal` | `demo.minimercado@datapyme.co` | `DemoMinimercado2026!` | Enfoque Pronóstico OLS |

---

## Arquitectura y Calidad de Código

* **Estructura Modular:** Dividida limpiamente en `routes/`, `core/`, `imports/`, `analytics/`, `forecast/` y `telemetry/`.
* **Cero Código Monolítico:** Separación estricta de responsabilidades entre capa HTTP, lógica financiera (`Decimal`), seguridad (`Argon2id`, TOTP RFC 6238, SHA-256 encadenado) y frontend Vanilla JS compatible con CSP.
* **Linter & Formatter:** 100% de cumplimiento con `ruff check` (0 errores/advertencias) y `ruff format` (79 archivos limpios).
* **Suite de Pruebas Automatizadas:** **70 pruebas `pytest`** (unitarias, seguridad, integración y E2E en navegador real Playwright desktop/móvil) + **2 pruebas frontend Node** (`vat.test.cjs`), 100% en verde.
  ```powershell
  .\.venv\Scripts\python.exe -m pytest empresarial/tests/
  node --test empresarial/tests/frontend/vat.test.cjs
  ```

Consulte la documentación técnica detallada en:
* [PLANNING_PRODUCCION_FINAL.md](PLANNING_PRODUCCION_FINAL.md): Plan maestro de arquitectura de los 7 pilares de producción.
* [PLANNING_ORQUESTADOR_F-DC-124.md](PLANNING_ORQUESTADOR_F-DC-124.md): Plan de trabajo y requerimientos por actividad.
* [ESTADO_ORQUESTACION.md](ESTADO_ORQUESTACION.md): Estado actual de la arquitectura, pruebas e infraestructura.
