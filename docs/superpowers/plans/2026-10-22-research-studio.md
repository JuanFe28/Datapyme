# Datapyme Research Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para implementar en esta sesión. El usuario pidió ejecución autónoma y no detenerse tras el diagnóstico.

**Goal:** Entregar la plataforma local probada y preparada para publicación persistente.

**Architecture:** FastAPI/Jinja modular, SQLAlchemy y Alembic. Un servicio de filtros y análisis alimenta dashboard, tablas y exportaciones. Sesiones y archivos privados en base de datos.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL/SQLite, Chart.js, ReportLab, XlsxWriter.

**Spec:** docs/superpowers/specs/2026-10-22-research-studio-design.md

## Global Constraints

- Español, datos auténticos en operación y fixtures aislados en pruebas.
- No borrar registros existentes ni alterar objetivos académicos.
- Conservar rutas funcionales y copia de fuentes originales.
- No publicar secretos ni usar proyectos externos no identificados como Datapyme.
- Sin Git disponible en el proyecto: registrar progreso local; no inventar commits ni ejecutar scripts que presupongan un repositorio.

## Review Focus

- Edición concurrente y normalización de duplicados: conflicto manejado sin perder datos.
- Datos históricos sin consentimiento/criterios nuevos: fuera de resultados válidos hasta revisión explícita.
- Selección múltiple, saltos y formularios parciales: denominadores y validación consistentes.
- Archivo renombrado o ZIP de expansión excesiva: rechazo y cero archivos huérfanos.
- Revocación de usuario/sesión: los permisos cambian inmediatamente en servidor.

### Task 1: Base, acceso y migración

**Files:** research/config.py, database.py, models.py, security.py; migrations/; manage.py; tests/conftest.py, test_security.py, test_migrations.py.

**Interfaces:** `SessionLocal`, `Base`, `engine`; `auth(request)`, `admin(request)`, `csrf(request, token)`; `upgrade_database()`.

- [x] Escribir y ejecutar pruebas de cookie, contraseña, rol, revocación, CSRF, readiness y esquema heredado; observar fallos.
- [x] Implementar modelos y migraciones aditivas, usuarios hash y sesiones en base, bootstrap seguro y errores genéricos.
- [x] Ejecutar `python -m pytest tests/test_security.py tests/test_migrations.py -q`; esperado: todas pasan.

### Task 2: Empresas e instrumentos

**Files:** research/research_routes.py, instruments.py; questions.py; templates/company_form.html, companies.html, instrument.html, response_detail.html; tests/test_research.py.

**Interfaces:** `Company.eligible`, `Company.eligibility_status`; `validate_answers(category, form, complete)`; respuestas con estado y consentimiento.

- [x] Pruebas fallidas de clasificación verificada, duplicado en edición, consentimiento, encuesta única, borradores y saltos.
- [x] Implementar fichas, contacto separado, auditoría, borradores y finalización transaccional.
- [x] Ejecutar `python -m pytest tests/test_research.py -q`; esperado: todas pasan.

### Task 3: Análisis y exportaciones

**Files:** research/analytics.py, exports.py; templates/dashboard.html, analytics.html, reports.html; static/app.js; tests/test_analytics.py, test_exports.py.

**Interfaces:** `filtered_records(db, params)`, `build_analysis(companies, responses)`, `export_dataset(kind, selection)`.

- [x] Pruebas fallidas de denominadores, filtros comunes, hojas con todas las columnas, neutralización de fórmulas, PDF válido y PNG con contexto.
- [x] Implementar dashboard y análisis con n, estados vacíos y filtros compartidos; exportaciones sin datos de contacto.
- [x] Ejecutar `python -m pytest tests/test_analytics.py tests/test_exports.py -q`; esperado: todas pasan.

### Task 4: Evidencias, actividades, Canvas y viabilidad

**Files:** research/project_routes.py, file_validation.py, finance.py; templates/evidence.html, tasks.html, canvas.html, finance.html; tests/test_project.py.

**Interfaces:** `Evidence`, `EvidenceBlob`, `Task`, `CanvasVersion`, `FinancialScenario`; `calculate_scenario(inputs)`.

- [x] Pruebas fallidas de adjuntos privados, formato/tamaño, estados/fechas, evidencia requerida, versiones de Canvas y fórmulas financieras.
- [x] Implementar flujos con auditoría, persistencia y fuentes documentadas.
- [x] Ejecutar `python -m pytest tests/test_project.py -q`; esperado: todas pasan.

### Task 5: Interfaz, entrega y despliegue

**Files:** templates/base.html, static/style.css, static/vendor/; README.md, docs/; render.yaml, Dockerfile, .github/workflows/ci.yml, requirements*.txt; scripts/.

- [x] Verificar aplicación original y capturar errores antes de cambios.
- [x] Navegar todos los módulos, comprobar formularios y capturas reales, resolver fallos observados.
- [x] Ejecutar suite completa, migración repetida, persistencia tras reinicio y revisión independiente de código.
- [x] Documentar resultados exactos y accesos externos faltantes; producir ZIP limpio sin bases, adjuntos ni secretos.


Verificación real: ver docs/VALIDACION.md. Los archivos de prueba se consolidaron inicialmente en tres módulos; se preserva el alcance. El 23 de octubre se añadió tests/test_review_access.py para la revisión temporal remota. Esa copia HTTPS fue verificada; la publicación definitiva persistente sigue pendiente de destinos y accesos específicos.
