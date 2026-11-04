# Operación de Datapyme Research Studio

## Configuración

| Variable | Uso |
|---|---|
| APP_ENV | `local` en desarrollo, `review` solo para la copia sintética temporal, `production` al publicar. |
| DATABASE_URL | SQLite local o PostgreSQL con driver psycopg. PostgreSQL es obligatorio en producción. |
| SESSION_SECRET | Aleatorio, mínimo 32 caracteres en producción; debe conservarse entre despliegues. |
| ALLOWED_HOSTS | Dominios exactos separados por comas, sin protocolo ni ruta; no usar `*`. |
| ADMIN_USER / ADMIN_PASSWORD | Bootstrap opcional de la primera cuenta. Contraseña de 12–512 caracteres; nunca se reemplaza una cuenta existente automáticamente. |
| FIELD_USER / FIELD_PASSWORD | Bootstrap opcional por compatibilidad; preferir cuentas individuales creadas por el administrador. |

Las contraseñas de bootstrap solo se usan para crear cuentas faltantes y se convierten en hash. Retirar estas variables de contraseña del proveedor después de crear las cuentas. Los secretos nunca deben viajar en argumentos de consola, commits, capturas ni archivos de entrega.

## Revisión temporal separada

Ejecutar `REVISAR_POR_INTERNET.cmd` desde la raíz preparada. El ayudante `scripts/review_access.py` crea usuarios propios y la base `.local/review/revision.db`; nunca publica `datapyme_local.db`. Usa el puerto local 8002 y un Quick Tunnel HTTPS con cabecera de origen fija. La cookie `datapyme_revision_session` es Secure/HttpOnly y está separada de la cookie local. Las páginas y los archivos generados identifican la revisión como datos de prueba.

El acceso privado se encuentra en `.local/review/ACCESO_REVISION.txt`; la guía interna `USO_PRIVADO_EQUIPO.txt`, si existe, actualiza su bloque de acceso al iniciar/detener. No incluir ninguno en repositorios, contenedores ni entregas académicas. La descarga oficial de cloudflared se verifica contra el SHA-256 publicado en su release; queda en `.local/tools`.

`python scripts/review_access.py status` comprueba los procesos y `/ready` público. `DETENER_REVISION.cmd` detiene únicamente procesos cuyo ejecutable y comando coinciden con esta revisión, conservando los registros. El computador debe permanecer encendido, conectado y sin suspensión. La URL cambia entre túneles y el proveedor no ofrece SLA para este mecanismo; consultar [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). No usar esta copia para levantamiento real. Si cambia una contraseña reservada de revisión en la app, actualizar también su archivo privado; el inicio no reemplaza contraseñas existentes.

## Render y PostgreSQL

El archivo `render.yaml` declara un servicio Python con `pip install -r requirements.txt`, arranque `uvicorn app:app --host 0.0.0.0 --port $PORT` y comprobación `/ready`. La [guía oficial de FastAPI en Render](https://render.com/docs/deploy-fastapi) documenta este modelo de arranque. No se crearon servicios ni se asumió ningún gasto.

1. Crear o seleccionar un repositorio privado de Datapyme y subir exclusivamente el código de la entrega. No usar `.local`, `.env`, bases ni los documentos privados de investigación.
2. Proporcionar una base PostgreSQL persistente destinada a Datapyme. En Supabase, usar la conexión directa si la red lo permite o el pooler de sesión para un backend persistente en IPv4; copiar host y usuario desde **Connect**, sin deducirlos. Consultar [conexiones PostgreSQL de Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).
3. Configurar los secretos en Render: URL de base, clave de sesión, dominio exacto y contraseña inicial de administrador. Codificar los caracteres reservados de la contraseña en la URL. TLS se solicita con `sslmode=require` si no se especifica otra configuración.
4. El backend debe conectarse con un rol propietario de estas tablas o un rol privado correctamente autorizado. La migración habilita RLS en PostgreSQL y retira acceso de `anon` y `authenticated` cuando existen; no se crean políticas públicas. La aplicación accede mediante el servidor, no mediante claves en JavaScript. No mezclar estas tablas con un proyecto ajeno.
5. Hacer una copia previa y ejecutar `python manage.py migrate`. El inicio también verifica/aplica migraciones. Usar una sola instancia/worker durante la migración; no hacer actualizaciones de esquema simultáneas.
6. Comprobar `/health` y `/ready`, acceso por HTTPS, inicio/cierre de sesión, permiso de investigador y exportaciones. No dar por exitoso un despliegue solo porque terminó el build.
7. Probar persistencia en una base de staging: registrar fixtures identificados como QA, adjuntar un archivo, reiniciar o volver a desplegar y consultar los mismos IDs y SHA-256. No mezclar estos registros con el levantamiento definitivo.
8. Confirmar respaldo/recuperación y retirar las contraseñas de bootstrap. Crear las dos cuentas individuales del equipo.

`/health` solo confirma que el proceso responde. `/ready` ejecuta una consulta y verifica la revisión Alembic esperada; devuelve 503 si falla. Ninguno muestra cadenas de conexión ni datos personales. Cookies HttpOnly/Secure y HSTS se activan en producción. El HTTPS público depende del proveedor y debe probarse después de desplegar.

La declaración `plan: free` no garantiza condiciones permanentes ni capacidad suficiente. Verificar condiciones del proveedor antes de aceptar un servicio. La aplicación no debe usar SQLite en un disco efímero remoto; los binarios de evidencia también residen en PostgreSQL.

## Copias completas

Un XLSX no contiene todos los consentimientos, hashes, sesiones ni binarios: no sustituye el respaldo de base de datos.

SQLite local:

```powershell
.\.venv\Scripts\python.exe manage.py backup --output .local\respaldos\datapyme-AAAA-MM-DD.sqlite
```

La copia utiliza la API de backup de SQLite, comprueba integridad y crea un manifiesto SHA-256. Un destino existente se rechaza para evitar sobrescribir copias. Incluye metadatos y contenido de los adjuntos. Guardar una copia cifrada fuera de este equipo en una ubicación autorizada.

PostgreSQL:

```text
python manage.py backup --output /ruta/privada/datapyme-AAAA-MM-DD.dump
```

Requiere `pg_dump` compatible con el servidor. Se usa formato custom, sin propietario ni ACL; la contraseña se suministra al proceso mediante el entorno y no aparece en sus argumentos. Una salida fallida no confirma un respaldo correcto. Usar una conexión adecuada para operaciones nativas de PostgreSQL y verificar con `pg_restore --list`.

Conservar varias generaciones de copia según el acuerdo de retención y los permisos del proyecto. La programación de respaldos externos está pendiente de elegir el alojamiento; no se creó una automatización que no pueda ejecutarse.

## Recuperación sin sobrescribir la base activa

1. Detener las escrituras y preservar la base actual y sus respaldos.
2. Verificar el SHA-256 contra el manifiesto.
3. **SQLite:** copiar el archivo de respaldo a un archivo NUEVO y configurar temporalmente DATABASE_URL para ese archivo; no reemplazar el original. Ejecutar `manage.py check` y verificar `PRAGMA integrity_check`.
4. **PostgreSQL:** crear una base NUEVA vacía, revisar `pg_restore --list` y restaurar sin `--clean` ni opciones que eliminen objetos existentes. Usar credenciales en el entorno, no en comandos compartidos. Ejecutar migraciones y revisar RLS/permisos del rol privado restaurado.
5. En la base restaurada, comprobar conteos de empresas, respuestas, consentimientos, usuarios y archivos; descargar al menos un adjunto y verificar su SHA-256. Probar acceso y un informe.
6. Cambiar el servicio a la base verificada. Conservar la copia anterior hasta terminar la comprobación y documentar quién realizó el cambio.

La recuperación remota está documentada; no se ejecutó sin una base PostgreSQL específica. Los ensayos locales de persistencia y copia se documentan en VALIDACION.md.

## Diagnóstico

- 303 hacia `/login`: sesión ausente, vencida o revocada.
- 403: rol insuficiente, archivo privado o token CSRF vencido. Recargar el formulario.
- 409: duplicado, conflicto entre respuestas finales o intento de cambiar un registro protegido.
- 422: datos incompletos, criterio de selección, formato o fecha inválida. El instrumento conserva las respuestas para su corrección.
- 413: solicitud/archivo mayor al límite.
- 429: esperar el periodo de bloqueo por intentos fallidos.
- 503 en `/ready`: revisar conectividad, secretos y migración en los logs del proveedor. No copiar secretos al chat.

No hay analítica ni telemetría externa configurada por el proyecto. Evitar registrar contenido de formularios en logs del alojamiento. `hide_parameters=True` limita la exposición de datos en errores SQLAlchemy.
