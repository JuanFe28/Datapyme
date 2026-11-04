Actúa como un Ingeniero de QA Senior, Especialista en Datos y Asesor Técnico del Informe Final **F-DC-125** (Modalidad Emprendimiento / Plan de Negocios de las UTS), manteniendo estricto apego a lo aprobado en el formato **F-DC-124**.

Acabo de confirmar con mi compañero de trabajo de grado el propósito real de este repositorio (`Datapyme Research Studio`): **es nuestra plataforma tecnológica para recolectar los datos de campo (encuestas, entrevistas y validaciones), procesarlos estadísticamente, generar las gráficas y tablas, controlar la evolución del Business Model Canvas (Inicial vs. Validado), calcular los escenarios financieros y consolidar todos los insumos obligatorios del informe final F-DC-125.**

Por lo tanto, **NO** vamos a cambiar la naturaleza de esta aplicación, sino que necesito que la dejes **100% funcional en mi máquina, auditada, probada de extremo a extremo y verificada frente a todos los requisitos del documento F-DC-125 y las exigencias del evaluador.**

Por favor, ejecuta las siguientes 5 tareas en orden:

---

### TAREA 1: Reparación del Entorno Local y Puesta en Marcha
En la auditoría anterior detectaste que la carpeta `.venv` tiene rutas fijas del computador de mi compañero (`C:\Users\camac\...`) y por eso no puedo ejecutar la aplicación.
1. Reconstruye un entorno virtual limpio en mi equipo (`.venv`), instala todas las dependencias de `requirements.txt` (incluyendo `alembic`, `pytest`, `httpx`, etc.) y verifica que la base de datos SQLite (`datapyme_local.db`) tenga todas sus migraciones al día.
2. Verifica o crea un usuario administrador de prueba para que yo pueda iniciar sesión inmediatamente en mi navegador local y revisar toda la aplicación.

---

### TAREA 2: Ejecución de Pruebas Exhaustivas (QA Funcional y de Datos)
Ejecuta toda la suite de pruebas (`pytest`) y realiza pruebas adicionales de extremo a extremo sobre cada módulo de la aplicación verificando que todo funcione perfectamente:
1. **Autenticación, Seguridad y Ley 1581 de 2012:** Login, sesiones, registro de consentimientos informados (`consents`) y separación de datos sensibles (`company_contacts`).
2. **Recolección de Datos e Instrumentos (`/empresas`, `/instrumentos`):**
   * Registro de PyMEs comerciales de Bucaramanga.
   * Aplicación y guardado de la **Encuesta de Estudio de Mercado (`M04-M23`)** (validando saltos condicionales, tipos de datos y campos obligatorios).
   * Aplicación de la **Entrevista Semiestructurada** y del **Instrumento de Validación del Prototipo (`T01-T06`, `V02-V15`)**.
3. **Motor de Analítica y Gráficas (`/analisis`, `/dashboard`):**
   * Verifica que los cálculos de frecuencias, porcentajes, promedios (como la disposición de pago `M20`) y tabulaciones cruzadas sean matemáticamente exactos.
   * Verifica que todas las gráficas de `Chart.js` se rendericen bien y que las exportaciones a **CSV, Excel (`.xlsx`), PDF y PNG** funcionen sin errores.
4. **Business Model Canvas (`/canvas`) y Finanzas (`/finanzas`):**
   * Verifica que funcione la creación y comparación entre **Canvas Inicial (Hipótesis)** y **Canvas Validado (Post-estudio)** (exigencia directa del evaluador para el F-DC-125).
   * Verifica que el módulo financiero calcule correctamente inversión inicial, costos fijos/variables, punto de equilibrio y flujo de caja alimentándose de la tasa de adopción y disposición de pago real recolectada en las encuestas (exigencia del evaluador de no inventar ingresos de la nada).

---

### TAREA 3: Auditoría de Cobertura para Solucionar el Documento F-DC-125
El formato oficial **F-DC-125** de las UTS exige para nuestra modalidad los siguientes apartados dentro del **Capítulo 4 (Desarrollo del Trabajo de Grado)** y **Capítulo 5 (Resultados)**:
1. **Estudio de Mercado** (caracterización de PyMEs en Bucaramanga, necesidades analíticas, gestión actual de ventas/inventarios, barreras de adopción, competencia y disposición de pago).
2. **Evaluación Técnica** (arquitectura, diseño de software, requerimientos, modelo de datos, alcance del algoritmo estadístico básico de regresión lineal/promedios móviles y validación).
3. **Evaluación Administrativa y Organizacional** (recursos humanos, procesos operativos, estructura y evolución del Business Model Canvas Inicial vs. Validado).
4. **Evaluación Económica-Financiera** (inversión, costos, ingresos basados en encuestas, punto de equilibrio, flujo de caja e indicadores).
5. **Evaluación Ambiental y Posibles Fuentes de Financiación** (impacto ambiental según normatividad vigente y convocatorias como Fondo Emprender).
6. **Resultados, Tablas y Figuras bajo Norma APA.**

Revisa qué partes de la aplicación (`questions.py`, `research_routes.py`, `project_routes.py`, `analytics.py`, `finance.py`, `exports.py`, `notas`) ya cubren estos 6 puntos del F-DC-125 y **dime si hace falta agregar alguna pregunta, algún gráfico, alguna tabla exportable o algún cálculo** para que la aplicación nos entregue absolutamente todo lo necesario para llenar el F-DC-125 sin salirnos jamás del F-DC-124 aprobado. Si detectas alguna mejora menor o corrección de bugs para que los reportes/gráficas salgan listos para el F-DC-125, impleméntala.

---

### TAREA 4: Simulación de Prueba (Datos de Demostración Reversibles) o Guía de Uso
Para que yo pueda ver ahora mismo cómo se ven las gráficas llenas, las tablas tabuladas, el Canvas comparado y las proyecciones financieras funcionando:
* Verifícame si existe un comando o script para cargar datos de prueba simulados (y otro para limpiar la base de datos y dejarla en cero cuando empecemos a meter las encuestas reales), o créame un comando seguro en `manage.py` (por ejemplo `seed-demo` y `clear-demo`) que me permita inspeccionar la aplicación con gráficas llenas hoy mismo y luego dejarla limpia para el trabajo de campo real.

---

### TAREA 5: Entrégame el Reporte Operativo y Guía para Revisar la Aplicación
Al finalizar, entrégame un resumen claro con:
1. Estado de todas las pruebas (`pytest`) y confirmación de que todo funciona al 100%.
2. **Cómo abrir la aplicación paso a paso** (URL local, usuario y contraseña de acceso).
3. **Recorrido guiado pantalla por pantalla:** qué debo revisar en cada menú para familiarizarme con lo que programó mi compañero y cómo vamos a usar cada módulo para recolectar los datos y redactar el F-DC-125.
4. Qué nos falta hacer a nivel de recolección de datos o ajustes para completar el documento F-DC-125.