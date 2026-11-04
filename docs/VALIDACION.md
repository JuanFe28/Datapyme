# Verificación y estado de entrega

Resultado observado el 23 de octubre de 2026: **54 pruebas aprobadas, 0 fallos, 1 aviso de deprecación de Starlette**, en 73,84 segundos. Comando de la verificación integral: `python -m pytest -q --basetemp=.local/test-team-final`, incluyendo exportaciones financieras y aislamiento de revisión. Registro local: `.local/tests-team-final.log`. Compilación Python y comprobación de sintaxis JavaScript: correctas. `pip check`: sin dependencias rotas. `manage.py check`: conexión correcta y esquema `20261022_01`.

## Comprobaciones realizadas

- Reproducción del fallo original de acceso con las dependencias actuales: llamada obsoleta a TemplateResponse, TypeError en login. Corregido con la API actual.
- Pruebas de empresas, normalización de duplicados y edición sin pérdida de datos.
- Borradores excluidos de resultados; finalización transaccional y protección de encuesta única en base de datos.
- Consentimiento, saltos condicionales, preguntas múltiples, opciones excluyentes y referencia del prototipo.
- Roles leídos desde base, revocación de sesión, desactivación, CSRF y bloqueo de intentos normalizando espacios del usuario.
- Protección de respuestas retiradas: un investigador no puede reactivarlas.
- Filtros, porcentajes por participante, caracterización de candidatas y disposición de pago.
- XLSX, CSV, PDF y PNG, protección de fórmulas y exclusión de contactos.
- Adjuntos privados, falso PNG, expansión excesiva de Office y límite de solicitud.
- Canvas con versiones y evidencia para contrastar; actividades con responsable y evidencia; notas con fuente.
- Fórmulas financieras, contribución no positiva y límite extremo de proyección sin errores de precisión.
- Migración de un esquema histórico con empresa y respuesta relacionadas, conservación de contenido, nuevas claves foráneas y segunda ejecución sin duplicación. Se corrigió la reconstrucción de tablas padre para evitar DROP con referencias activas.
- Persistencia: recreación de la aplicación y recuperación de empresa y archivo binario.
- Respaldo SQLite: integridad, recuperación del binario y rechazo de un destino existente para impedir sobrescritura.
- Navegador auténtico: acceso local, dashboard, gráficos interactivos en QA, formulario a tamaño móvil y saltos M14/M20; progreso de 95 a 100 %, finalización real en QA con respuesta guardada y campos omitidos por salto, y ancho de documento igual al viewport. Sin errores/warnings de consola en las vistas revisadas.
- PDF de QA renderizado con Poppler e inspeccionado visualmente; se agruparon secciones para evitar títulos separados de sus gráficos.
- Revisión HTTPS temporal: inicio de sesión real de administrador desde navegador; 16 pantallas respondieron 200 con aviso de datos de prueba. Inicio de sesión de investigador y cinco comprobaciones de acceso administrativo devolvieron 403. Las rutas privadas sin sesión redirigen a login; cierre de sesión comprobado. Cookie separada, Secure y HttpOnly.
- Exportaciones públicas de la copia de revisión: CSV, XLSX, PDF y PNG descargados y marcados como prueba. PDF renderizado con Poppler e inspeccionado; pie de aviso comprobado en todas sus páginas. XLSX incluye hoja SOLO REVISION. Sin errores/warnings de consola en el panel remoto revisado.
- Base de revisión independiente con dos cuentas y un caso sintético explícito; preparación repetida sin duplicados. Se comprobó que un futuro `.env` local no importe las credenciales reales de bootstrap a la revisión.
- Inicio local desde servidor detenido mediante `scripts/start.ps1 -NoBrowser`, migración y `/ready` correctos; reutilización de un servidor ya iniciado comprobada. Los lanzadores no requieren mantener una terminal abierta.
- TXT privado para los autores en la raíz, fuera de docs, con bloque de acceso actualizado automáticamente. Excluido de Git, Docker y ZIP; `.local` y sus secretos también están excluidos.

Los ejemplos sintéticos de comprobación están identificados como QA y solo existen en bases separadas bajo `.local`. La base de investigación conserva cero empresas y respuestas al terminar la preparación.

## Estado externo

- Carpeta de trabajo sin repositorio Git original; copia del código anterior en `.local/original-source.zip`. Código local actualizado; no se crearon commits, remotos ni PR.
- GitHub conectado: no se identificó repositorio Datapyme entre los disponibles. Falta seleccionar/proporcionar el destino correcto.
- Supabase conectado: el proyecto disponible se llamaba `tienda`; no se modificó. Falta una base persistente específica de Datapyme y su conexión privada.
- Render: sin acceso/configuración específica para publicar. No se creó servicio ni se contrató un plan.
- PostgreSQL remoto, HTTPS del despliegue definitivo, Docker build y GitHub Actions: pendientes de ejecución en el entorno de destino. Se entregan configuraciones e instrucciones, no resultados inventados.
- Existe una URL HTTPS temporal de revisión con autenticación, verificada mediante Quick Tunnel de Cloudflare; el enlace vigente y sus accesos se guardan solo en los archivos privados del equipo. Requiere este computador encendido y conectado. No es un despliegue persistente ni debe recibir datos de investigación reales.
- La base de investigación se mantiene local en http://127.0.0.1:8000, separada del túnel. Para captura definitiva remota falta proporcionar y verificar el destino persistente.

La revisión de código señaló tres fallos materiales (migración SQLite, normalización del bloqueo y reactivación de respuestas retiradas). Los tres se reprodujeron con pruebas y se corrigieron. La dependencia Starlette emite un aviso de deprecación al usar httpx en su TestClient; no es un fallo de la aplicación, pero se registra y no se oculta.


Captura de la instalación real, con base de investigación vacía: `docs/capturas/panel-local.jpg`. Se comprobaron también las exportaciones financieras XLSX/PDF y Canvas PDF en QA, con renderizado visual de sus PDF. Las fuentes y el contenido de prueba no forman parte de la base de investigación ni del ZIP.

Captura de la revisión remota: `docs/capturas/revision-internet.jpg`; muestra la advertencia de prueba y un único caso sintético. Las verificaciones privadas del túnel están en `.local/review/verification.json`, excluido de la entrega junto con las descargas de ensayo.
