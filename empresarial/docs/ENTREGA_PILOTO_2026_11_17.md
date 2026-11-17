# Entrega técnica para el piloto — 17/11/2026

Versión candidata con 76 pruebas Python y cuatro JavaScript aprobadas. El acceso
al servidor lo conserva Juan Felipe. Esta guía no es evidencia de despliegue.
No se contrataron servicios ni se tocaron las bases reales.

## Actualización en el servidor (Juan Felipe)

1. Coordinar una ventana sin uso. Ubicarse en el clon real y comprobar `git status
   --short`: si hay cambios locales, conservarlos y revisarlos antes de continuar.
   Descargar los cambios con `git fetch origin`; actualizar por avance directo,
   sin `reset --hard` ni sobrescritura de archivos locales. Revisar el commit
   indicado en GitHub para esta entrega.
2. Conservar la versión anterior (`git rev-parse HEAD` antes de actualizar) y el
   archivo de variables privado. Nunca imprimir o subir las variables.
3. Antes de arrancar la versión nueva, respaldar PostgreSQL. Desde
   `empresarial/deploy`, usando el mismo archivo `.env` privado del despliegue:

   ```bash
   umask 077
   mkdir -p "$HOME/datapyme-backups"
   backup="$HOME/datapyme-backups/empresarial-$(date +%Y%m%d-%H%M%S).dump"
   docker compose -f docker-compose.prod.yml exec -T empresarial_db pg_dump -U datapyme_emp -d datapyme_empresarial -Fc > "$backup"
   test -s "$backup"
   ```

   Detenerse si cualquier comando falla. El archivo queda fuera del repositorio.
   No usar `down -v`, no borrar volúmenes ni restaurar sobre producción.
4. Comprobar el respaldo en una base auxiliar de nombre único del mismo servidor:

   ```bash
   restore_db="dp_restore_$(date +%Y%m%d_%H%M%S)"
   docker compose -f docker-compose.prod.yml exec -T empresarial_db createdb -U datapyme_emp "$restore_db"
   docker compose -f docker-compose.prod.yml exec -T empresarial_db pg_restore -U datapyme_emp -d "$restore_db" --exit-on-error < "$backup"
   docker compose -f docker-compose.prod.yml exec -T empresarial_db psql -U datapyme_emp -d "$restore_db" -v ON_ERROR_STOP=1 -c 'SELECT COUNT(*) AS sales_count FROM sales; SELECT COUNT(*) AS products_count FROM products;'
   ```

   Registrar resultados privados y revisar una venta, sus líneas y el stock
   restaurado. La creación de un archivo por sí sola no demuestra recuperación.
   La base auxiliar contiene datos privados y debe conservarse con acceso restringido.
5. Con el código nuevo ya descargado, construir e iniciar únicamente la aplicación:

   ```bash
   export DATAPYME_RELEASE="$(git rev-parse HEAD)"
   docker compose -f docker-compose.prod.yml build empresarial_app
   docker compose -f docker-compose.prod.yml up -d --no-deps empresarial_app
   curl --fail http://127.0.0.1:8210/ready
   ```

   `/ready` debe indicar `database=ok` y la revisión instalada. Un esquema que no
   pueda actualizarse cancela el arranque. Stock negativo preexistente provoca
   respuesta 503: investigar su conciliación, nunca cambiarlo a cero sin evidencia.
6. Las cuentas demo públicas ya no ingresan en producción. Si solo existía el
   auditor demo, crear una cuenta privada desde la consola del servidor:

   ```bash
   docker compose -f docker-compose.prod.yml exec empresarial_app python -m app.core.admin_cli
   ```

   Ingresar correo propio y contraseña exclusiva cuando la consola lo solicite;
   no ponerla como argumento, en GitHub ni en el chat. No modifica cuentas
   existentes. El propietario de cada negocio conserva una cuenta independiente.
7. En el panel administrativo, usar **Renovar clave inicial** para propietarios
   pendientes de activación que recibieron claves antiguas. La fórmula anterior
   queda bloqueada. La nueva clave se muestra una sola vez; el reporte posterior
   no puede recuperarla. Verificar destinatario antes de entregarla privadamente.
   Cuentas ya activadas no se restablecen mediante este control.
8. Revisar empresas creadas con catálogo de ejemplo en versiones anteriores:
   podrían tener datos ficticios marcados como reales. No convertir ni borrar
   automáticamente registros mezclados. Conciliar con el propietario antes del uso.

Si falla el arranque: conservar respaldo y logs privados, detener el inicio del
piloto y evaluar la versión anterior. No ejecutar una restauración destructiva
por intuición. Las pruebas de esta sesión usaron Python 3.12/SQLite; Docker usa
Python 3.14 según el archivo del compañero y requiere comprobación en el servidor.

## Comprobación remota obligatoria antes de invitar empresas

Usar una cuenta y registros sintéticos separados de los negocios participantes.

| Flujo | Resultado que se debe observar y registrar |
|---|---|
| HTTPS y `/ready` | Login abre; base responde y revisión coincide con GitHub. |
| Activación | Clave inicial obliga a crear otra; antes de activar no se opera. |
| Roles | Propietario no accede al panel administrativo; administrador no opera ventas de un negocio. |
| Aislamiento | Una segunda empresa no consulta ni modifica productos/ventas de la primera. |
| IVA | Pendiente bloquea venta real; no responsable cobra 0; responsable usa tarifa del artículo; cambio conserva ventas anteriores. |
| Venta | Dos líneas del mismo producto no venden más stock del disponible. Totales coinciden con el comprobante. |
| Anulación | Reingresa la cantidad una sola vez y conserva el historial. |
| Importación | Previsualización no cambia stock; confirmación válida lo actualiza y muestra errores de fila. |
| Descargas | JSON incluye líneas; CSV abre como CSV y contiene únicamente la empresa autenticada. |
| MFA | Activación, login con código y recuperación de un solo uso; códigos incorrectos limitados. |
| Persistencia | Un reinicio de solo la app conserva producto, venta, IVA y stock de prueba. |
| Respaldo | Restauración auxiliar correcta, con conciliación de venta e inventario. |
| Escritorio/móvil | Navegación, formularios, botones, gráficos y mensajes visibles sin quedar ocultos. |

No marcar esta tabla como aprobada sin hacerla en el servidor. Cloudflare Quick
Tunnel puede cambiar de dirección al reiniciarse: confirmar el enlace vigente,
su continuidad y la persona de soporte antes de compartirlo.

## Inicio del piloto acompañado

- Empezar con una empresa elegible y su consentimiento; no afirmar dos semanas
  de uso si el periodo real empieza hoy. Coordinar el alcance con el director.
- Alta en cero; catálogo de entrenamiento solo si se pide y claramente identificado.
  Eliminar la práctica al terminar; conservarla mantiene su carácter sintético.
- Confirmar condición tributaria con el negocio. No inferirla del tamaño ni activar
  automáticamente responsabilidad de IVA. No es facturación electrónica DIAN.
- Cargar un inventario pequeño y comprobar cinco artículos antes de importar todo.
  Precios de entrada son base sin IVA; revisar costo e impuestos recuperables con
  su asesor. Las ganancias mostradas no incluyen todos los gastos del negocio.
- Acompañar la primera venta, comprobante, anulación de prueba y descarga.
  Registrar versión, fecha, tarea, ayuda requerida e incidencias reales.
- Las proyecciones necesitan tres meses calendario completos y consecutivos
  con ventas; una cuenta nueva puede mostrar “datos insuficientes”.

## Límites y pendientes

No se verificó visualmente esta revisión por fallo de la herramienta del
navegador. No se probó PostgreSQL, concurrencia con varios trabajadores,
compatibilidad del contenedor ni recuperación remota en esta sesión. La prueba
de restauración local sí recuperó ventas, líneas y stock en una base sintética.
Las pruebas E2E de navegador del repositorio no se ejecutaron: usan otro puerto
y no deben dirigirse accidentalmente a la operación real. No se ha hecho una
prueba de carga que permita prometer manejo masivo sin límites.

Los datos de participantes retirados de la fuente permanecen en commits previos:
el equipo debe revisar las copias históricas y mantener privado el repositorio.
No se reescribió el historial compartido ni se enviaron mensajes a terceros.
