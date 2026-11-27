# Estado vigente — demostraciones sin voz

## Fecha, hora y autor/agente

25/11/2026, America/Bogota. Codex para Alvino.
El usuario pidió una alternativa sin voz y luego decidió grabar personalmente
la locución para el recorrido completo.
Rama fix/precios-y-demo-20261124;
correcciones de software publicadas en 3897a79, conservando cambios de Juan Felipe.

## Fase y actividad del F-DC-124

Material de demostración del prototipo para empresas, actividades 3.6–3.8.
No constituye validación de campo ni cierre académico. Research Studio,
F-DC-125 y datos reales sin cambios. Jarvis continúa cancelado.

## Resumen técnico de cambios

Se exportaron dos MP4 sin audio con el mismo video, capítulos y subtítulos
de las versiones anteriores. Se verificó que la imagen es idéntica y que
ambos archivos se decodifican completos. Informe: VERIFICACION_SIN_VOZ.json.
Las grabaciones y pruebas de voz personales permanecen en el equipo.

Guion de locución en doce bloques, con las referencias de tiempo del MP4
y las cifras escritas como se pronuncian. Disponible en
material_demostracion/2026-11-24/GUION_PARA_GRABAR_DATAPYME.txt.

Material de edición compartido por Alvino y Juan Felipe en
material_demostracion/2026-11-24/EDICION. Incluye doce clips del recorrido y
cinco del resumen, sin audio ni subtítulos incrustados, con sus órdenes y
listas de unión. Los clips se decodificaron completos a 1080p y 25 fps.

El 27/11/2026 se añadió PROMPT_EDITAR_VIDEO_DATAPYME.txt. Integra las
recomendaciones del profesor sobre tono casual, voz original y español
cercano al público. Incluye acciones visibles, una escaleta y referencias
a la edición profesional 8946f0a y las fuentes limpias. Se verificaron
las rutas de las dos ramas y los capítulos de referencia. El encargo
no modificó archivos de video ni de aplicación.

Versiones anteriores: MP4 principal de 604,39 s y breve de 81,91 s, 1920×1080 a 25 fps, narración
en español y subtítulos incorporados; SRT, capítulos e informe técnico aparte.
Ubicación versionada: material_demostracion/2026-11-24. Pantallas reales de la
app local corregida, datos sintéticos y voz sintetizada local Microsoft Helena.
Edición mediante cortes y pausas de capturas reales; no se clonó ninguna voz
ni se usaron cuentas ajenas o servicios pagos. Sin nuevos cambios de aplicación.

## Estado de pruebas y evidencia

Ambos MP4 decodificaron completos sin errores de audio/video; se comprobaron
duración, resolución, niveles de audio, orden y límites de subtítulos y hashes.
Revisión visual de escenas finales, incluidos importación, comprobante y móvil.
Informe con hashes: material_demostracion/2026-11-24/VERIFICACION_TECNICA.json.
La ejecución de software anterior registró 112 Python aprobadas, cuatro PG
omitidas y 15 JavaScript aprobadas; no se repitieron al editar solo medios/docs.
No se verificaron versión exacta, persistencia ni recuperación del servidor remoto.

## Arranque y comprobaciones

Los videos se reproducen sin instalar la app. Instrucciones de entrega en
material_demostracion/2026-11-24/LEEME.txt. Fuentes privadas, entorno y base
sintética permanecen fuera de Git; no se copian respaldos, claves ni datos reales.
git diff --cached --check y revisión de lista staged antes de publicar.
Esta rama no se ha integrado en main ni desplegado en el servidor.

## Siguiente paso exacto

Juan Felipe o Alvino entregan el MP4 exacto a corregir al asistente junto
al prompt actualizado. La primera prueba usa una escena de producto o
venta con locución original, movimientos de cursor y confirmación visible.
El video sin voz está disponible mientras se prepara la edición definitiva.
Antes de incorporar
empresas: comprobar PostgreSQL pendiente, revisar/integrar correcciones,
respaldar y actualizar el servidor administrado por Juan Felipe; verificar
acceso, flujo sintético, exportación, persistencia y recuperación remotos.
La evidencia real y comentarios de empresas deben aportarlos los autores.

---

# Estado anterior — correcciones guardadas, pausa solicitada por el usuario

## Fecha, hora y autor/agente

24/11/2026, America/Bogota. Codex para Alvino. Rama fix/precios-y-demo-20261124,
basada en b73bd14 y d7833e7. Hora exacta no registrada. El usuario pidió detener
el trabajo y publicar el avance en GitHub para conservar créditos.

## Fase y actividad del F-DC-124

Correcciones y comprobación de recorridos para demostración a empresas,
actividades 3.6–3.8. No se declara cierre académico, validación de campo ni
preparación comercial absoluta. Research Studio, F-DC-125 y datos reales intactos.

## Resumen técnico de cambios

Precio base sin IVA explícito y vista previa del total en alta/edición; revisión
sin guardar por defecto al importar; botón coherente con la acción elegida.
El importador unificado rechaza importes inválidos, bloquea archivos repetidos,
exige IVA confirmado para ventas y distingue precios inferidos de totales brutos
de precios base del catálogo. Se retiraron promesas de ganancia neta y de aceptar
cualquier hoja de cálculo. No se reescribieron datos históricos.

## Estado de pruebas y evidencia

112 pruebas Python aprobadas; cuatro PostgreSQL omitidas; un aviso Starlette/httpx.
Quince pruebas JavaScript aprobadas. Ruff correcto en archivos modificados.
Revisión independiente y pruebas de regresión para los problemas de importación.
Recorridos sintéticos y tomas reales de productos/ajuste, IVA, ventas/anulación,
archivo inválido, importación válida, filtros, proyección y falta de historial,
activación sin cambiar contraseña, tutorial y móvil. No se probó cada línea.

Hay fotogramas con tiempos y narración WAV local; **no hay MP4 final**. Falta
montaje, sincronización, exportación y revisión. PostgreSQL de QA se inició,
pero sus pruebas no se ejecutaron de nuevo antes de parar. Login y /ready remotos
respondieron HTTP 200; no se verificó persistencia ni versión exacta del servidor.

## Arranque y comprobaciones

Los servidores sintéticos se detienen al cerrar este avance. El material local
se conserva en C:\Datapyme\03_DEMOSTRACION_EMPRESAS\2026-11-24\privado.
El código de aplicación solo cambia en la rama indicada, no en main ni servidor.
Detalles de arranque, material, pruebas y límites en
empresarial/docs/video_empresas/2026-11-24/CONTINUAR_DESDE_AQUI.txt.

## Siguiente paso exacto

Esperar a que el usuario pida retomar. Entonces leer el punto de reanudación,
comprobar el estado Git, completar la comprobación PostgreSQL pendiente y montar
el MP4 desde las tomas y audio conservados. Sin cuentas ajenas ni servicios pagos.
No repetir trabajo ya comprobado sin motivo. Jarvis sigue cancelado.

---

# Estado anterior — revisión para demostración a empresas

## Fecha, hora y autor/agente

24/11/2026, America/Bogota. Codex para Alvino. Hora exacta no registrada.
Base de producto d7833e7, coincidente con origin/main al consultar GitHub.
Esta actualización solo incorpora documentación de producción audiovisual.

## Fase y actividad del F-DC-124

Revisión de uso y material explicativo para empresas, actividades 3.6–3.8.
No se declara lista la operación comercial ni validación de campo. Jarvis fue
cancelado y retirado; esta entrega no lo incorpora. Research Studio y F-DC-125
se conservan sin cambios.

## Resumen técnico de cambios

Guion de diez minutos, versión breve de 75 segundos, índice, plan de grabación
y subtítulos provisionales en empresarial/docs/video_empresas/2026-11-24.
No se produjo MP4 ni audio: no se dispuso de grabación continua/exportación
verificada y el editor conectado correspondía a otra cuenta no autorizada.
El cierre omite contactos, costos, condiciones y duración del piloto según
instrucción del usuario. No se modificó código ni información comercial real.

## Estado de pruebas y evidencia

Se ejecutaron 104 pruebas Python aprobadas, cuatro PostgreSQL omitidas por no
estar habilitada su instancia sintética y un aviso Starlette/httpx; 12 pruebas
JavaScript aprobadas. Recorrido visible con una base nueva sintética: login de
propietario y administrador, catálogo y alta, condición de IVA, stock insuficiente,
venta y comprobante, inventario 12 -> 11, proyección y navegación móvil 390×844.
No hubo uso con participantes reales ni prueba de cada botón o línea.

**Bloqueo detectado:** alta/edición dicen precio de venta al público, pero envían
el importe como base sin IVA. Introducir 11.900 al 19 % mostró base 11.900 y final
14.161. Resolver coherencia del formulario/API/catálogo antes de incorporar
empresas y de grabar esa escena como correcta. La suite actual no cubre este
desajuste semántico. No se corrigió dentro del encargo audiovisual.

Login y /ready de la URL Cloudflare confirmada respondieron HTTP 200, status ok.
No se verificaron versión exacta ni persistencia/recuperación del servidor.
Activación, anulación, importación y exportación no completaron un recorrido
visual nuevo en esta sesión; no atribuirles evidencia inexistente.

## Arranque y comprobaciones

Producto desde empresarial, con DATABASE_URL sintética explícita y entorno
independiente: python -m uvicorn app.main:app --host 127.0.0.1 --port 8024.
Pruebas: python -m pytest tests/unit tests/integration tests/security -o addopts=-ra -q;
node --test tests/frontend/*.test.cjs. No apuntar pruebas a la base real.
El paquete local completo está fuera de Git en
C:\Datapyme\03_DEMOSTRACION_EMPRESAS\2026-11-24; sus bases y notas privadas no se publican.

## Siguiente paso exacto

Corregir la referencia de precios en alta/edición y probar IVA 0/5/19,
responsable/no responsable y redondeo sin reescribir registros históricos.
Comprobar el despliegue autenticado, persistencia y recuperación con cuenta
sintética. Completar las tomas pendientes, grabar voz/pantalla real y ajustar
subtítulos antes de compartir el video como demostración final aprobada.

---

# Estado anterior — cierre del piloto acompañado

## Fecha, hora y autor/agente

17/11/2026, America/Bogota. Codex para Alvino; hora exacta no registrada.
Repositorio JuanFe28/Datapyme, revisión sobre c7d3731. Cambios de Juan Felipe
preservados. Carpeta local: `02_APLICATIVO_PYMES/.local/juanfe-demo-20261113`.

## Fase y actividad del F-DC-124

Preparación para uso y comentarios de empresas durante cinco días, actividades
3.6–3.8 y correcciones del núcleo comercial. No se declara terminada la
investigación ni su validación humana. Research Studio y F-DC-125 no se modificaron.

## Resumen técnico de cambios

Se corrigieron importación CSV/Excel, duplicados y previsualización, cantidades
por peso y redondeo, accesibilidad, texto/atributos importados interpretables como
HTML y cierre de práctica rechazado por el servidor. El historial conserva fecha,
referencia única por empresa, costo e IVA de origen; no modifica stock ni al
importarlo ni al anularlo. Tabla nueva aditiva `historical_sale_references`.

Se retiraron métricas/gráficos de ejemplo para cuentas sin historia. La proyección
requiere meses calendario completos consecutivos, conserva cero y describe R²
como ajuste histórico. No se reescriben registros antiguos automáticamente.

## Estado de pruebas y evidencia

**96 pruebas Python aprobadas**, incluidas cuatro PostgreSQL 17 local, y **once
JavaScript aprobadas**. Un aviso Starlette/httpx. PostgreSQL comprobó ventas y
anulaciones simultáneas, recuperación `pg_dump`/`pg_restore`, práctica e históricos.

Recorrido visible de los cuatro perfiles demo: propietario en tres prioridades
de interfaz y superadmin. Alta/edición, venta/comprobante/anulación, falta de stock,
IVA, importación y descarga CSV, histórico y venta de 0,25 kg, proyección y móvil
390×844. Reinicios locales conservaron datos. No afirmar cada botón o línea probada.
Detalle: `empresarial/docs/QA_PILOTO_2026_11_17.md`. Evidencias y bases privadas fuera
de Git. No hubo operación con participantes reales.

## Arranque y comprobaciones

Desde `empresarial`, con base sintética explícita y entorno independiente:

```text
python -m pip install -r requirements.txt
python -m pytest tests/unit tests/integration tests/security -o addopts=-ra -q
node --test tests/frontend/*.test.cjs
python -m uvicorn app.main:app --host 127.0.0.1 --port 8022
```

El comando normal omite cuatro pruebas PG si no se habilita expresamente su
instancia sintética dedicada. Nunca usar una base real para ejecutarlas.
Recorrido actual: aplicación 127.0.0.1:8022 y PostgreSQL 127.0.0.1:55439, solo demo.
No es el enlace de las empresas. Producción: Compose existente, APP_ENV=production,
SESSION_SECRET exclusiva y administrador privado; guía en
`empresarial/docs/ENTREGA_PILOTO_2026_11_17.md`.

## Siguiente paso exacto

Juan Felipe tiene acceso al servidor: descargar esta revisión, respaldar, arrancar
y confirmar `/ready`, HTTPS y conservación de un registro sintético tras reinicio.
El servidor y su contenedor no se actualizaron desde este equipo. No reutilizar
claves iniciales antiguas o cuentas demo públicas en producción. Revisar y conciliar
registros de importaciones antiguas sin borrar/recalcular información real a ciegas.

Con esa instalación comprobada, iniciar `empresarial/docs/PILOTO_CINCO_DIAS.md`:
registrar fechas reales, versión, tareas, incidencias y comentarios auténticos.
No se comprobó carga masiva sin límites, DIAN ni certificación contable. El cierre
académico depende del campo y del director.

---

# Registro anterior de la misma fecha — histórico

El corte siguiente se conserva como antecedente; el estado vigente es el anterior.

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
