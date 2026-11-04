# Arquitectura y datos

## Componentes

- `app.py`: fábrica ASGI, ciclo de vida, middleware, límites y comprobaciones de estado.
- `research/config.py`: entorno, secretos, hosts y conexión.
- `research/database.py`, `models.py`, `migrations/`: SQLAlchemy, Alembic y esquema. La migración conserva una instantánea inmutable en `migrations/schema_v1.py`.
- `research/security.py`, `auth_routes.py`: contraseñas, sesiones, autorización, cuentas y auditoría.
- `research/research_routes.py`, `instruments.py`, `questions.py`: empresas, consentimiento, instrumentos y calidad de datos.
- `research/analytics.py`: selección filtrada, fechas Colombia, elegibilidad actual y denominadores.
- `research/project_routes.py`, `finance.py`, `file_validation.py`: gestión del proyecto, cálculos y archivos privados.
- `research/exports.py`: exportaciones desde la misma selección y cálculo compartidos.
- `templates/`, `static/`: Jinja, CSS responsive, JavaScript y bibliotecas locales.
- `manage.py`, `scripts/`: administración, respaldos, arranque y empaquetado.

No se utilizan Supabase Auth ni Storage: PostgreSQL puede alojarse en Supabase u otro proveedor. Los usuarios, sesiones y archivos son privados del backend. RLS sin políticas públicas impide el uso de estas tablas desde los roles públicos de Supabase; la conexión del backend necesita sus permisos propios.

## Entidades

| Grupo | Tablas | Relación y propósito |
|---|---|---|
| Acceso | users, login_sessions, login_attempts | Identidades individuales, hash de contraseña y hash del token de sesión. Permisos leídos desde base en cada petición. |
| Empresas | companies, company_contacts | Criterios de selección y contacto personal separado 1:1. Clave normalizada única para nuevos registros. |
| Investigación | responses, consents, answers, instrument_questions | Respuesta y estado, consentimiento versionado, respuestas por código y diccionario de instrumentos. Se conserva también el payload JSON del formulario. |
| Proyecto | tasks, canvas_versions, financial_scenarios, research_notes | Actividades, versiones inmutables del Canvas, escenarios con fuentes y estudios complementarios. |
| Archivos | evidence, evidence_blobs | Metadatos, asociaciones opcionales, checksum y contenido binario privado 1:1. |
| Trazabilidad | audit_logs, alembic_version | Cambios administrativos y revisión del esquema. |

Las preguntas se identifican con códigos estables; cambiar un instrumento requiere una versión nueva. La definición actual es un instrumento de trabajo para revisión del director, no una validación metodológica concedida por el software.

## Calidad y análisis

Una encuesta cuenta como válida si su estado es `complete`, tiene un consentimiento asociado y la empresa cumple los criterios actuales de elegibilidad. Si la clasificación cambia, el formulario se conserva y deja de alimentar las distribuciones válidas. Los gráficos de candidatas incluyen por separado todas las empresas seleccionadas; los gráficos de encuestas usan solo finales válidas.

Para una pregunta de selección múltiple con n participantes que contestaron válidamente, cada opción usa frecuencia de personas / n × 100. No se divide entre el total de menciones. Las opciones son únicas y se verifican en servidor; opciones de ausencia no se combinan con otras. Los saltos condicionales se aplican tanto en navegador como en servidor. La disposición de pago excluye respuestas no aplicables y conserva ceros declarados.

Las fechas se almacenan en UTC. Los filtros de campo interpretan el día de America/Bogota. En conjuntos con empresas y respuestas, cada registro usa su propia fecha de creación; filtrar respuestas no elimina una encuesta solo porque la empresa fue registrada antes del periodo. El informe muestra filtros y denominadores por tabla/gráfico.

Una respuesta final tiene clave única de encuesta por empresa. Un borrador no ocupa esta clave; al finalizar se actualiza el mismo registro transaccionalmente. Retirar una respuesta libera su clave sin eliminar el historial. La reactivación queda reservada al administrador.

## Límites explícitos

- Investigación por formularios autenticados; no hay enlace público de encuesta ni edición offline.
- Estado de validación del Canvas global por versión, con conclusión y evidencia; no existe un sistema independiente de hipótesis por cada tarjeta.
- Finanzas: proyección mensual básica, sin contabilidad, impuestos, deuda, VAN ni TIR automáticos.
- La retención, la información a participantes y los canales de ejercicio de derechos deben acordarse y comunicarse antes de recolectar. El texto de consentimiento del formulario no sustituye el procedimiento académico ni la revisión institucional.
- Los archivos se validan por tipo y tamaño, pero no se incorpora un antivirus externo. Se descargan como adjuntos y no se ejecutan ni se publican enlaces abiertos.
- No hay despliegue remoto ni ensayo con PostgreSQL confirmado en esta entrega. Docker y CI están preparados, no ejecutados en un proveedor.
