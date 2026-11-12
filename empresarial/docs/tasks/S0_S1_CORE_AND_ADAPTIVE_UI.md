# Paquete Técnico Atómico S0-S1: Fundaciones, Seguridad Multi-Tenant, Inmutabilidad Legal y Motor Adaptativo `ui_personalization_service.py`

## CONTEXTO
Proyecto `Datapyme Empresarial` (`empresarial/`), alineado al Objetivo Específico 3 del formato F-DC-124 (UTS).
Los tests de aceptación ya están escritos por Antigravity en:
- `tests/unit/test_sprint0_foundations.py`
- `tests/unit/test_ui_personalization.py`
- `tests/security/test_sprint1_security_and_legal.py`

## OBJETIVO
Implementar los módulos de `app/`, `static/css/tokens.css` y `templates/` para que el 100% de la suite `pytest` pase sin errores y cumpla `ruff check`.

## ARCHIVOS A CREAR / COMPLETAR
1. `app/core/config.py`
2. `app/core/models.py` (`Tenant`, `User`, `SessionModel`, `LegalConsent` con triggers SQLite de inmutabilidad `BEFORE UPDATE`/`BEFORE DELETE` y cadena SHA-256 `prev_hash`/`row_hash`, `CompanyUIPreference`, `UserViewSetting`)
3. `app/core/security.py` (`hash_password` y `verify_password` con `argon2-cffi`, tokens de sesión firmados/hasheados)
4. `app/ui/ui_personalization_service.py` (`DiagnosisInput`, `PriorityProfile`, `ALL_KPIS`, `ALL_WIDGETS`, `compute_priority_weights` con Laplace $\alpha = 0.5$ bajo `map-v1`, `build_layout_config` bajo `layout-v1`)
5. `app/main.py` (`create_app(database_url=None, testing=False)` con cabeceras CSP/X-Frame-Options/X-Content-Type-Options/Referrer-Policy, `GET /health`, `POST /api/auth/register`, `GET /api/ui/layout`, `PUT /api/ui/view-mode`, `GET /api/tenants/{tenant_id}/preferences` con aislamiento multi-tenant estricto)
6. `static/css/tokens.css` y `templates/base.html` (con `.bento-grid`, `tabular-nums`, `rgba(15, 23, 42, 0.06)` y cero emojis).
