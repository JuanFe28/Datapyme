# Datapyme — Plataforma de Analítica Comercial y Entorno de Investigación (UTS F-DC-124 / F-DC-125)

Sistema integral desarrollado para las **Unidades Tecnológicas de Santander (UTS)** en el marco del proyecto de investigación aplicada para la digitalización y analítica de micro y pequeñas empresas comerciales en Bucaramanga.

El repositorio contiene dos componentes perfectamente integrados y desacoplados:

1. **Datapyme Empresarial (`empresarial/` | Ruta: `/empresarial` o puerto 8000/8010):**
   * **Objetivo 3 del formato F-DC-124:** Plataforma SaaS multi-tenant para comerciantes reales de Bucaramanga.
   * Módulos de Ventas POS atómicas, Catálogo de productos con imágenes, Kardex inmutable, Mapeador inteligente de Excel multi-hoja, Alertas de stock, Bento Dashboard adaptativo según diagnóstico, Proyecciones de regresión lineal OLS y Panel de impacto para Auditor UTS con $k$-anonimato ($k \ge 3$).
   * Diseñado bajo lineamientos **Apple Human Interface Guidelines (HIG)** y **Shopify Polaris** con 100% diseño responsivo para celulares y computadores.

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

## Cuentas Demo de Prueba (F-DC-125)

| Perfil Demo | Correo Electrónico | Contraseña | Enfoque Evaluado |
|:---|:---|:---|:---|
| **Auditor UTS (SuperAdmin)** | `superadmin.demo@datapyme.co` | `SuperAdmin2026!` | Panel Visual `/admin/impacto` ($k \ge 3$) |
| **Ferretería Cabecera** | `demo.ferreteria@datapyme.co` | `DemoFerreteria2026!` | Enfoque Inventarios y Alertas |
| **Boutique San Pío** | `demo.boutique@datapyme.co` | `DemoBoutique2026!` | Enfoque Ventas y Facturación |
| **Minimercado Real** | `demo.minimercado@datapyme.co` | `DemoMinimercado2026!` | Enfoque Pronóstico OLS |

---

## Arquitectura y Calidad de Código

* **Estructura Modular:** Dividida limpiamente en `routes/`, `core/`, `imports/`, `analytics/`, `forecast/` y `telemetry/`.
* **Cero Código Monolítico:** Archivos concisos (< 350 líneas) con separación estricta de responsabilidades.
* **Linter & Formatter:** 100% de cumplimiento con `ruff check` (0 errores/advertencias) y `ruff format`.
* **Suite de Pruebas Automatizadas:** 42 pruebas (unitarias, seguridad, integración y E2E en navegador real Playwright) 100% en verde.
  ```powershell
  .\.venv\Scripts\python.exe -m pytest empresarial/tests/
  ```

Consulte la documentación técnica detallada en:
* [PLANNING_ORQUESTADOR_F-DC-124.md](PLANNING_ORQUESTADOR_F-DC-124.md): Plan de trabajo y requerimientos por actividad.
* [ESTADO_ORQUESTACION.md](ESTADO_ORQUESTACION.md): Estado actual de la arquitectura, servicios e infraestructura.
