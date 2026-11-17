# Estado vigente de Datapyme — piloto empresarial

## Fecha, hora y autor/agente

17 de noviembre de 2026, America/Bogota. Codex para Alvino. Hora exacta no registrada.
Repositorio de trabajo: JuanFe28/Datapyme. Base revisada: 2e3a9a8.
Se preservaron los cambios de Juan Felipe y las correcciones anteriores de IVA.

## Fase y actividad del F-DC-124

Preparación técnica del piloto, actividades 3.6–3.8. No se declara validación con
empresarios, finalización académica ni conformidad tributaria. Research Studio
no se modificó en esta revisión. No se alteró la plantilla F-DC-125.

## Resumen de cambios

- Ventas: validación acumulada de artículos repetidos, bloqueo de productos
  inactivos y separación entre inventario real y práctica. Bloqueos transaccionales
  por empresa para ventas, movimientos y anulaciones en PostgreSQL.
- Precios: rechazo de importes negativos y texto inválido; presentación de
  centavos; ingresos por producto sin IVA y KPIs limitados al periodo solicitado.
- Proyección: meses calendario completos de Colombia; no usar transacciones como
  si fueran meses ni comprimir huecos en la serie. Semilla sintética consecutiva.
- Cuentas: claves iniciales aleatorias, entrega una vez, renovación administrativa
  con revocación de sesiones y bloqueo de la fórmula antigua. Credenciales demo
  públicas deshabilitadas en producción. Alta privada de administrador por consola.
- MFA: bloqueo tras intentos fallidos; configurar de nuevo no desactiva MFA vigente.
- Práctica: catálogo inicial identificado; sus cifras no se contabilizan como
  operación; limpieza rechazada si afectaría relaciones reales. Conservar una
  práctica no transforma sus cifras en información real.
- Exportación CSV real y JSON con líneas de venta; solicitud de supresión con
  autorización Bearer desde el formulario. Control de disponibilidad `/ready`.
- Retirados del código datos de participantes y fallback de empresas reales.
  No se reescribió el historial Git: los administradores deben revisar las copias
  históricas y renovar las claves iniciales previamente entregadas.

## Estado de pruebas

76 pruebas Python de unidad, integración y seguridad aprobadas el 17/11/2026;
1 advertencia Starlette/httpx. Cuatro pruebas JavaScript aprobadas.
Incluye registro/activación, IVA editable y conservación histórica, aislamiento,
importaciones, ventas/anulación, MFA, exportación y restauración SQLite sintética.
No equivale a probar cada botón, navegador o línea del código.

El navegador del chat falló al inicializar su entorno. No hubo revisión visual
nueva. Docker local está instalado pero su motor no está disponible: no se
ejecutó el contenedor ni se probó PostgreSQL en esta sesión. La URL Cloudflare
documentada respondió HTTP 200 en login; eso no acredita la versión ni la
persistencia remota. No se ingresó a cuentas reales ni se envió ningún mensaje.

## Arranque y comprobaciones

Desde `empresarial`, con un entorno Python independiente:

```text
python -m pip install -r requirements.txt
python -m pytest tests/unit tests/integration tests/security -o addopts=-ra -q
node --test tests/frontend/*.test.cjs
python -m uvicorn app.main:app --host 127.0.0.1 --port 8021
```

La ejecución debe usar una DATABASE_URL sintética para pruebas. No apuntar estos
recorridos a la base de participantes. En producción, usar PostgreSQL,
APP_ENV=production y SESSION_SECRET exclusiva, conforme al Compose existente.
Guía del servidor: `empresarial/docs/ENTREGA_PILOTO_2026_11_17.md`.

## Siguiente paso exacto

Juan Felipe, quien tiene acceso al servidor, debe respaldar, comprobar la
restauración en una base auxiliar y aplicar esta revisión. Crear/confirmar un
administrador privado y renovar claves iniciales antiguas; revisar coherencia de
stock preexistente y catálogos de ejemplo creados antes de esta corrección.
Luego verificar `/ready`, activación de una cuenta sintética, flujo de ventas,
exportaciones y persistencia tras reinicio en PostgreSQL. Solo después confirmar
el enlace y habilitar un piloto acompañado, empezando con una empresa.
Datos de campo, consentimiento, elegibilidad y revisión del director corresponden
a los autores; nunca sustituirlos por la demostración sintética.
