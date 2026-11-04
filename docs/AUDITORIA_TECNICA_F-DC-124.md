# INFORME DE AUDITORÍA TÉCNICA Y DE ALINEACIÓN INSTITUCIONAL F-DC-124
**Proyecto:** Datapyme — Plataforma de Analítica Empresarial para PyMEs Comerciales de Bucaramanga  
**Modalidad:** Emprendimiento (Plan de Negocios) — Formato Aprobado: F-DC-124 hacia Informe Final F-DC-125  
**Institución:** Unidades Tecnológicas de Santander (UTS)  
**Rol del Auditor:** Auditor Técnico de Software Senior & Arquitecto de Soluciones  
**Fecha de Auditoría:** 24 de Octubre de 2026  

---

## RESUMEN EJECUTIVO PARA EL EQUIPO

Tras una exhaustiva revisión estática y dinámica de la totalidad de archivos, configuraciones, modelos de datos, rutas, plantillas, suites de pruebas y documentación del repositorio `Datapyme`, se emite el siguiente dictamen pericial:

> **DICTAMEN TÉCNICO:** **DISCREPANCIA CRÍTICA DE ALCANCE ("SCOPE DRIFT / WRONG PRODUCT BUILT")**
> 
> El código desarrollado por su compañero posee una **calidad de ingeniería de software sobresaliente** (patrones limpios, seguridad criptográfica robusta, pruebas automatizadas, exportaciones completas y apego estricto a la Ley 1581 de 2012). Sin embargo, **se construyó el software equivocado para el Objetivo Específico 3**:
> 
> 1. En lugar de desarrollar el **Prototipo Funcional Web (MVP SaaS)** para que las **PyMEs comerciales de Bucaramanga** registren/carguen sus ventas e inventarios, consulten dashboards de KPIs comerciales y visualicen proyecciones predictivas básicas (Objetivo 3, Actividades 3.1 a 3.8 del F-DC-124)...
> 2. Su compañero desarrolló **"Datapyme Research Studio"**, una suite interna para **gestionar el proyecto de grado mismo** (registro de empresas de la muestra, tabulación de encuestas de mercado de la Fase 1, registro de entrevistas, control de versiones del Business Model Canvas de la Fase 2, calculadora de escenarios financieros de la tesis para la Fase 4 y repositorio de evidencias).
> 3. En el repositorio **NO EXISTE** módulo de ventas para PyMEs, ni catálogo de inventario/stock, ni dashboard de KPIs comerciales (ingresos, rotación, ticket promedio), ni algoritmo estadístico de proyección (regresión lineal o promedios móviles). De hecho, el propio compañero dejó documentado en `README.md` y `docs/TRAZABILIDAD.md` la advertencia explícita: *"Research Studio es la herramienta de investigación; el prototipo comercial de ventas, inventarios y analítica es un entregable diferente del objetivo 3... Esta herramienta no afirma que dicho producto ya exista"*.
>
> **Consecuencia Académica Inmediata:** Si el equipo presentara este código ante el comité evaluador de las UTS para la entrega final del F-DC-125, el proyecto sería reprobado o devuelto por **incumplimiento total del Producto Mínimo Viable (Objetivo 3)**.
> 
> **La Solución:** No se debe desechar el código actual; la base arquitectónica es excelente y sirve como plataforma de backend y soporte para las Fases 1, 2 y 4. Se debe activar de inmediato un **Plan de Choque** para desarrollar sobre esta misma base el módulo SaaS real del cliente (Ventas, Inventario, KPIs y Regresión Lineal).

---

## SECCIÓN 1: RADIOGRAFÍA ACTUAL DEL PROYECTO (STACK Y ARQUITECTURA)

### 1.1 Stack Tecnológico Detectado
* **Backend:** Python 3.12+ / 3.14, FastAPI `0.161.1`, Starlette `1.9.0`, Uvicorn `0.54.0` (estándar ASGI).
* **Capa de Persistencia y ORM:** SQLAlchemy `2.1.6`, motor de migraciones Alembic `1.20.1` (con instantánea inmutable en `migrations/schema_v1.py` y revisión `20261022_01`). Base local SQLite (`datapyme_local.db`); soporte dual para PostgreSQL con driver `psycopg[binary]==3.3.6`.
* **Frontend:**
  * Renderizado del lado del servidor (SSR) mediante plantillas Jinja2 `3.1.6` (`templates/*.html`).
  * CSS nativo y modular sin frameworks (`static/style.css`, 33.7 KB), con diseño responsivo móvil/escritorio, modo oscuro/claro y variables semánticas.
  * Biblioteca de gráficos: Chart.js 4.x (`static/vendor/chart.umd.min.js`, 206 KB) alojada 100% localmente.
  * Iconografía: Lucide Icons (`static/vendor/lucide.min.js`, 357 KB) alojada 100% localmente.
  * Lógica cliente: JavaScript vainilla (`static/app.js`, 5.9 KB) para manipulación de DOM, alertas, modales y saltos condicionales en formularios.
* **Seguridad y Criptografía:** `itsdangerous==2.2.0`, `hashlib.pbkdf2_hmac` con 600.000 iteraciones y sal aleatoria de 18 bytes, `secrets`, middleware de sesiones de Starlette con cookies `HttpOnly`, `SameSite=lax` y protección CSRF mediante tokens HMAC.
* **Procesamiento de Documentos y Reportes:** `reportlab==4.5.1` (generación de PDFs vectoriales con fuentes TrueType incrustadas), `xlsxwriter==3.3.0` (generación de libros Excel con sanitización de inyecciones de fórmulas), `pillow==13.0.0` (renderizado rasterizado de imágenes de gráficos).
* **Infraestructura de Despliegue y CI:** Dockerfile multistage (`Dockerfile`), descriptor para Render (`render.yaml`), Procfile y workflow de integración continua (`.github/workflows/ci.yml`).

### 1.2 Estructura de Carpetas y Organización Arquitectónica
El proyecto sigue una arquitectura modular centrada en investigación:
```
Datapyme/
├── app.py                      # Fábrica ASGI, middlewares de seguridad, lifespan y ruteo principal
├── manage.py                   # CLI administrativo (migrate, create-user, reset-password, backup)
├── questions.py                # Diccionarios de preguntas (encuesta mercado M04-M23, entrevista, pruebas)
├── research/                   # Lógica central del sistema actual
│   ├── config.py               # Ajustes Pydantic/dataclass leídos desde variables de entorno (.env)
│   ├── database.py             # Fábrica de sesiones SQLAlchemy y disparador de migraciones Alembic
│   ├── models.py               # Modelos relacionales ORM (17 tablas)
│   ├── security.py             # Hasheo PBKDF2, autenticación, control de sesiones y CSRF
│   ├── auth_routes.py          # Endpoints de login, logout y administración de usuarios
│   ├── research_routes.py      # CRUD de empresas, encuestas, entrevistas y vista de análisis
│   ├── project_routes.py       # Tareas del cronograma, evidencias binarias, Canvas y finanzas
│   ├── analytics.py            # Motor de agregaciones, frecuencias y porcentajes sobre participantes
│   ├── finance.py              # Motor de cálculo financiero del plan de negocios (inversión, punto equilibrio)
│   ├── instruments.py          # Validaciones de formularios, saltos de preguntas y consentimiento
│   ├── file_validation.py      # Inspección de firmas mágicas, tipos MIME y límites de archivos
│   └── exports.py              # Generadores de descargas masivas (CSV, XLSX, PDF, PNG)
├── templates/                  # 20 plantillas Jinja2 divididas entre investigación y gestión
├── static/                     # Archivos estáticos locales (CSS, JS, vendor libs)
├── migrations/                 # Scripts de migración Alembic y esquema versionado
├── docs/                       # Documentación técnica, operacional y de trazabilidad académica
├── scripts/                    # Scripts de arranque PowerShell, empaquetado y túnel de revisión
└── tests/                      # Suite de pruebas unitarias y de integración con pytest
```

### 1.3 Estado de Ejecución, Compilación y Hallazgos de Configuración
Durante la auditoría dinámica se detectaron los siguientes errores técnicos críticos:

1. **ERROR BLOQUEANTE: Entorno Virtual `.venv` Roto y No Portable:**
   * Al intentar ejecutar cualquier script con `.\.venv\Scripts\python.exe` o usar `INICIAR_DATAPYME.cmd`, el sistema falla inmediatamente con:
     `No Python at '"C:\Users\camac\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"'`.
   * **Causa:** El entorno `.venv` fue copiado directamente desde el computador del compañero (usuario `camac`). En Windows, los entornos virtuales contienen rutas absolutas fijas en `pyvenv.cfg` y dentro de cada script en `Scripts/*.exe`. **Nunca debe commitearse ni transferirse la carpeta `.venv` entre desarrolladores.**
2. **Dependencias del Sistema Global:**
   * Al ejecutar pruebas con el intérprete global de Python del sistema, falla por ausencia de `alembic` (`ModuleNotFoundError: No module named 'alembic'`).
3. **Advertencia de Deprecación de Starlette:**
   * La suite de pruebas arroja `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`. Es una advertencia menor de biblioteca de pruebas que no rompe la lógica en tiempo de ejecución.

---

## SECCIÓN 2: MATRIZ DE CUMPLIMIENTO VS. F-DC-124 (SEMÁFORO DE ALINEACIÓN)

A continuación se contrasta cada compromiso técnico aprobado por el comité institucional de las UTS en el formato **F-DC-124** frente a lo que realmente existe en el repositorio:

| Módulo / Capacidad Comprometida (F-DC-124) | Componente Esperado para la PyME | Estado Real en Código | Nivel de Cumplimiento | Diagnóstico Técnico Detallado |
| :--- | :--- | :--- | :---: | :--- |
| **1. Autenticación y Control de Acceso Seguro** *(Consideraciones Éticas)* | Inicio de sesión, roles de usuario de la PyME, sesiones seguras, sin contraseñas en texto plano. | Funcional para investigadores (`admin`, `campo`). No existe para usuarios PyME. | 🟡 **70%** *(Desviado)* | Implementación técnica impecable en `research/security.py` (PBKDF2-SHA256, sesiones revocables en BD, control de fuerza bruta por IP/usuario, CSRF). Sin embargo, está diseñado para el equipo tesista y no para roles comerciales de la PyME (ej. cajero, administrador, bodeguero). |
| **2. Gestión e Integración de Datos de Ventas** *(Actividad 3.3)* | Cargar ventas masivas por CSV/Excel, registrar ventas operativas, fecha, total, cliente. | **Inexistente.** Cero modelos, cero interfaces, cero lógica. | 🔴 **0%** *(No implementado)* | En todo el código no hay una sola tabla para ventas (`sales`), líneas de venta (`sale_items`) o transacciones. Solo existe la pregunta de encuesta `M07` ("¿Qué medios utiliza para registrar ventas?"). |
| **3. Gestión e Integración de Datos de Inventarios** *(Actividad 3.3)* | Registrar productos, categorías, existencias (stock), stock mínimo, entradas/salidas. | **Inexistente.** Cero modelos, cero interfaces, cero lógica. | 🔴 **0%** *(No implementado)* | No existe catálogo de productos, ni control de stock, ni alertas de reorden. Solo existe la pregunta de encuesta `M08` ("¿Cómo controla actualmente el inventario?"). |
| **4. Tablero de Analítica Empresarial / Dashboards** *(Actividad 3.4)* | KPIs comerciales: ingresos totales, ticket promedio, margen bruto, rotación de inventario, gráficos de ventas. | Existe dashboard interactivo en Chart.js, pero grafica **respuestas de la encuesta académica**. | 🔴 **0%** *(Objetivo comercial no cumplido)* | El dashboard en `templates/dashboard.html` y `templates/analytics.html` funciona muy bien con Chart.js, pero calcula métricas de investigación (número de encuestas completadas, % de empresas pequeñas vs medianas, disposición promedio de pago `M20`). **No calcula ningún KPI operativo de la PyME**. |
| **5. Componente Básico de Analítica Predictiva** *(Actividad 3.5)* | Algoritmo estadístico básico (regresión lineal simple / promedios móviles) para pronóstico de ventas con disclaimer ético. | **Inexistente.** No hay ningún algoritmo matemático de pronóstico sobre datos de ventas. | 🔴 **0%** *(No implementado)* | No se encontró regresión lineal simple ($y = mx + b$), ni cálculo de pendiente/intercepto, ni promedios móviles sobre series de tiempo. Lo único que existe es una fórmula de crecimiento exponencial en `research/finance.py:35` para proyectar clientes en la tesis, pero es una simulación teórica de negocio, no analítica de ventas de la PyME. |
| **6. Seguridad, Privacidad y Ley 1581 de 2012** *(Consideraciones Éticas)* | Protección de datos, datos anonimizados/sintéticos, sin APIs de IA que fuguen secretos. | Funcional y rigurosamente implementado para el estudio de campo. | 🟢 **100%** *(Alineado)* | Cumplimiento exhaustivo: registro de consentimiento en BD (`consents`), separación 1:1 de datos de contacto personal (`company_contacts`), neutralización de fórmulas CSV/Excel contra inyección, validación de tipos MIME y binarios en BD. Sin consumo de APIs de IA de terceros. |

---

## SECCIÓN 3: DETECCIÓN DE DESVIACIONES ("SCOPE CREEP" O INCUMPLIMIENTOS)

### 3.1 ¿En qué se está saliendo el proyecto del F-DC-124? ("Scope Creep")
Se detectó un fenómeno de **sobredesarrollo lateral ("Scope Creep Metodológico")**: el compañero dedicó la gran mayoría de las horas de programación a automatizar procesos documentales del trabajo de grado en lugar de programar el software que el trabajo de grado prometió construir:

1. **Módulo de Business Model Canvas (`/canvas`, `CanvasVersion`):** Un sistema completo para versionar los 9 bloques del Canvas de Osterwalder, comparar versiones históricas lado a lado y exportarlas en PDF. *(Esto pertenece al informe escrito F-DC-125, no al software Datapyme)*.
2. **Módulo de Notas de Investigación Académica (`/notas`, `ResearchNote`):** Editor y repositorio interno para registrar citas, estudios de competencia, evaluación ambiental y fuentes de financiación. *(Debe ir en el documento de grado, no dentro del prototipo SaaS)*.
3. **Módulo de Evidencias en Base de Datos (`/evidencias`, `EvidenceBlob`):** Sistema de almacenamiento de archivos binarios en base de datos con verificación de checksums SHA-256 e inspección anti-bomba ZIP.
4. **Calculadora de Escenarios Financieros de la Tesis (`/finanzas`, `FinancialScenario`):** Simulador de viabilidad económica del emprendimiento a 60 meses.
5. **Herramienta de Túnel HTTPS Temporal (`scripts/review_access.py`):** Un script que descarga el binario `cloudflared.exe` directamente desde la API de GitHub para publicar una copia en la nube mediante Quick Tunnels. Aunque ingenioso, no forma parte del alcance aprobado y puede generar alertas en firewalls o antivirus universitarios al descargar ejecutables dinámicamente.

### 3.2 Partes Hardcodeadas o con Datos Falsos en el Código
* **Empresa Sintética Forzada en Revisión:** En `scripts/review_access.py` (líneas 49–51) se inyecta por código una empresa con nombre fijo: `"PRUEBA DE REVISIÓN — NO ES UNA EMPRESA REAL"`.
* **Referencia Mock en Pruebas:** En `tests/conftest.py` (línea 49) se quema `"https://example.org/prototipo-qa"` como la URL del prototipo evaluado.
* **Hitos Quemados:** En `questions.py` (líneas 82–97) están hardcodeados los 14 hitos del cronograma de grado en la variable `MILESTONES`.
* **Gráficos Estáticos:** En `templates/dashboard.html` (línea 8) la lista de preguntas a graficar está quemada en la plantilla (`['company_size','company_activity','M07','M15','M17','M21']`).
* **Base de Datos Operativa:** En `datapyme_local.db` actualmente hay **0 empresas** y **0 respuestas**. Está limpia para iniciar recolección, pero completamente vacía de datos del negocio.

---

## SECCIÓN 4: AUDITORÍA DE MODELO DE DATOS Y SEGURIDAD

### 4.1 Evaluación del Modelo Relacional Actual (17 Tablas)
Las tablas existentes en `migrations/schema_v1.py` y `research/models.py` son:
`users`, `login_sessions`, `login_attempts`, `companies`, `company_contacts`, `consents`, `responses`, `answers`, `instrument_questions`, `tasks`, `evidence`, `evidence_blobs`, `audit_logs`, `canvas_versions`, `financial_scenarios`, `research_notes`, `alembic_version`.

* **Veredicto del Esquema Actual:** Es un esquema normalizado de alta calidad para un sistema de gestión de investigación académica (permite vincular empresas con contactos disociados, almacenar consentimientos informados versionados, respuestas JSON tipificadas y blobs binarios).
* **Ausencia de Entidades Comerciales de la PyME:**
  * No existen tablas para `products` (ID, SKU, nombre, categoría, precio_costo, precio_venta, stock_actual, stock_minimo).
  * No existen tablas para `sales` (ID, fecha_venta, cliente, total_venta, metodo_pago, usuario_id).
  * No existen tablas para `sale_items` (ID, venta_id, producto_id, cantidad, precio_unitario, subtotal).
  * No existen tablas para `inventory_transactions` (ID, producto_id, tipo_movimiento ['entrada','salida','ajuste'], cantidad, motivo, fecha).

### 4.2 Evaluación de Seguridad y Consideraciones Éticas (F-DC-124 / Ley 1581)
* **Gestión de Contraseñas:** Excelente. PBKDF2-SHA256 con 600.000 rondas. Cumple con los estándares más estrictos de OWASP.
* **Protección de Datos Sensibles (Ley 1581 de 2012):** La separación de `company_contacts` respecto a `companies` garantiza que los nombres y teléfonos personales de los empresarios no se mezclen con las respuestas de mercado y no se filtren en las exportaciones masivas.
* **Inyección de Código en Exportaciones:** En `research/exports.py:37` se implementa `excel_safe(value)`, que antepone un apóstrofe si un campo inicia con `=`, `+`, `-` o `@`, neutralizando ataques de ejecución de comandos por CSV/Excel Formula Injection.
* **Privacidad de APIs Externas:** Se cumple al 100% la prohibición de enviar datos a APIs externas de IA. No existe código que transmita información sensible fuera del servidor local.

---

## SECCIÓN 5: QUÉ FALTA EXACTAMENTE POR DESARROLLAR (PLAN DE CHOQUE)

Para completar el 100% de las Actividades 3.1 a 3.8 del documento F-DC-124 y generar los insumos obligatorios para el informe final **F-DC-125**, el equipo debe ejecutar las siguientes tareas técnicas concretas organizadas en **3 Sprints de Scrum**:

### SPRINT 1: Arquitectura y Gestión de Datos de Ventas e Inventarios (Actividades 3.1, 3.2 y 3.3)
1. **Creación de Modelos de Base de Datos Comerciales:**
   * Crear la migración en Alembic (`20261025_02_pyme_mvp.py`) con las tablas `products`, `categories`, `sales`, `sale_items` e `inventory_transactions`.
2. **Módulo de Inventarios (Stock y Productos):**
   * Vista y formulario para registrar, editar y listar productos comerciales con su categoría, stock actual y stock mínimo de seguridad.
   * Carga masiva mediante archivo CSV / Excel (`/inventario/importar`) con plantilla prediseñada para la PyME.
   * Registro de entradas/salidas de mercancía con ajuste automático del stock.
3. **Módulo de Ventas:**
   * Formulario de registro rápido de ventas operativas (selección de productos, cantidad, cálculo de subtotal e IVA, actualización en caliente del stock).
   * Carga masiva de histórico de ventas en CSV / Excel (`/ventas/importar`) para que la PyME pueda cargar sus datos pasados sin tener que digitar factura por factura.

### SPRINT 2: Dashboard de KPIs y Algoritmo Predictivo Básico (Actividades 3.4 y 3.5)
1. **Tablero de Control Comercial (KPIs PyME):**
   * Crear vista `/pyme/dashboard` con tarjetas de indicadores clave (KPIs):
     * *Ventas Totales del Periodo (COP)* y comparativa vs periodo anterior.
     * *Ticket Promedio de Venta (COP)*.
     * *Margen Bruto Estimado (%)*.
     * *Alertas de Stock Crítico* (productos con stock $\le$ stock mínimo).
   * Gráficos interactivos en Chart.js:
     * Tendencia de Ventas Diarias/Mensuales (gráfico de líneas).
     * Top 5 Productos Más Vendidos por Facturación y por Volumen (gráfico de barras).
     * Distribución de Ventas por Categoría (gráfico de dona/pastel).
2. **Componente de Analítica Predictiva Básica (Restricción F-DC-124):**
   * Implementar en Python (`research/pyme_analytics.py`) un algoritmo de **Regresión Lineal Simple por Mínimos Cuadrados Ordinarios (OLS)** sobre la serie de tiempo de ventas históricas mensuales:
     $$\hat{y} = \beta_0 + \beta_1 x$$
     Donde $x$ representa el mes cronológico y $\hat{y}$ el monto de venta proyectado para los próximos 1 a 3 periodos.
   * Opcionalmente, agregar cálculo de **Promedios Móviles Ponderados (PMP)** a 3 meses como alternativa de suavizado.
   * Renderizar en Chart.js la línea de tendencia proyectada en trazo discontinuo (punteado) al final de la línea histórica.
3. **Inclusión Obligatoria del Disclaimer Ético (F-DC-124):**
   * En la vista del gráfico predictivo, incluir una alerta fija:
     > *"Aviso de Apoyo a la Decisión: Esta proyección se basa en un modelo estadístico lineal simple a partir de los datos históricos cargados por la empresa. Constituye exclusivamente una estimación de apoyo orientativo y no garantiza resultados comerciales futuros ni reemplaza el criterio del administrador."*

### SPRINT 3: Pruebas, Validación con PyMEs y Cierre F-DC-125 (Actividades 3.6, 3.7 y 3.8)
1. **Pruebas Funcionales Automatizadas (Actividad 3.6):**
   * Crear pruebas en `tests/test_pyme_mvp.py` verificando: cálculo de totales de venta, decremento atómico del stock al vender, rechazo de importaciones CSV corruptas y precisión matemática del cálculo de la regresión lineal.
2. **Validación Real con PyMEs de Bucaramanga (Actividad 3.7):**
   * Desplegar la aplicación y convocar a las empresas comerciales identificadas.
   * Usar el módulo de pruebas existente en Research Studio (`/instrumentos/prototipo`, tareas `T01-T06` y preguntas `V02-V15`) para evaluar la experiencia de los comerciantes usando el MVP real de ventas e inventario.
3. **Ajustes Finales e Insumo para el Informe F-DC-125 (Actividad 3.8):**
   * Documentar los hallazgos de usabilidad, corregir detalles de interfaz y redactar el Capítulo 3 ("Desarrollo y Resultados del Prototipo") del informe final F-DC-125.

---

## SECCIÓN 6: RECOMENDACIÓN DE DECISIONES PARA EL EQUIPO

### 6.1 Veredicto Franco: ¿Vamos por buen camino?
**SÍ en cuanto a solidez arquitectónica, pero NO en cuanto a alineación con el entregable del Objetivo 3.**
No entren en pánico ni desechen el trabajo realizado: su compañero demostró una gran capacidad técnica para construir un software seguro, modular y bien documentado. El único error fue una **confusión de enfoque conceptual**: construyó una "herramienta para los investigadores" en lugar de la "herramienta para las PyMEs".
Aprovechando que la base de FastAPI, SQLAlchemy, Alembic, Jinja2 y Chart.js ya está totalmente operativa y estilizada, montar los módulos comerciales faltantes tomará una fracción del tiempo que costaría empezar de cero.

### 6.2 Qué Conservar y Qué Refactorizar de Inmediato
* **CONSERVAR AL 100%:**
  * Toda la infraestructura de backend: seguridad (`security.py`), base de datos (`database.py`), configuración (`config.py`) y motor de exportaciones (`exports.py`).
  * Las bibliotecas locales (`Chart.js` y `Lucide`) y los estilos base de CSS (`style.css`).
  * La herramienta de encuestas y Canvas de Research Studio: consérvenla en una sección separada del menú (ej. *"Módulo de Investigación y Tesis"*), ya que les servirá para tabular las encuestas del Objetivo 1 y gestionar los anexos del F-DC-125.
* **REFACTORIZAR DE INMEDIATO:**
  * **Eliminar `.venv` del control de versiones:** Borrar la carpeta `.venv` corrupta y crear un entorno limpio localmente con:
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    ```
  * **Crear la Navegación Principal del Producto Comercial:**
    El menú lateral debe tener dos grandes áreas:
    1. **Datapyme SaaS (Producto PyME):** *Panel de Ventas*, *Catálogo de Inventario*, *Tablero de KPIs*, *Pronóstico de Ventas*.
    2. **Investigación de Grado (Uso Interno):** *Muestra de Empresas*, *Encuestas*, *Canvas*, *Evidencias*, *Finanzas*.

### 6.3 División Estratégica del Trabajo en Pareja

| Integrante | Rol Recomendado | Tareas Concretas a Asignar |
| :--- | :--- | :--- |
| **Compañero (Desarrollador Backend / Arquitecto)** | **Líder Técnico de Backend y Datos** | 1. Diseñar y ejecutar la migración Alembic para `products`, `sales`, `sale_items`, `inventory_transactions`.<br>2. Programar los endpoints de API y lógica de carga masiva CSV/Excel para catálogo e inventario.<br>3. Programar la función matemática de Regresión Lineal Simple y promedios móviles en Python puro.<br>4. Escribir las pruebas unitarias del motor comercial en `tests/test_pyme_mvp.py`. |
| **Usted (Desarrollador Frontend / Product Owner & Campo)** | **Líder de Producto, UI/UX y Validación** | 1. Diseñar y montar las plantillas Jinja2 para el Catálogo de Productos y Registro de Ventas.<br>2. Conectar los gráficos de Chart.js en el nuevo Dashboard comercial (Ventas en el tiempo, Top productos, semáforo de inventario y línea de regresión).<br>3. Diseñar las plantillas CSV de ejemplo con datos sintéticos de tiendas de Bucaramanga para pruebas.<br>4. Coordinar las pruebas de campo con las PyMEs usando el formulario `T01-T06` para el informe F-DC-125. |

---
*Informe generado y firmado digitalmente por el Auditor Técnico de Software Senior.*  
*Archivo preservado en la documentación oficial del repositorio: `docs/AUDITORIA_TECNICA_F-DC-124.md`.*
