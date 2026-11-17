# Piloto acompañado de cinco días

Guía operativa para el equipo y los comercios autorizados. No reemplaza el
instrumento académico aprobado, no demuestra validación empresarial y no promete
ausencia absoluta de errores. Los cinco días empiezan cuando cada negocio accede
a la versión instalada y comprobada, no cuando se publica código en GitHub.

## Antes del primer negocio

1. Instalar la revisión de esta entrega; confirmar `/ready`, acceso HTTPS y un
   registro sintético conservado tras reiniciar solo la aplicación.
2. Mantener administrador privado del equipo; cada empresa recibe su propio
   propietario. Los perfiles de inventario, ventas y proyección son prioridades
   de interfaz del mismo rol propietario, no tres permisos distintos.
3. Confirmar participación y autorización del comercio, y elegibilidad conforme
   al estudio aprobado. No inferir tamaño o responsabilidad de IVA del nombre,
   sector o crecimiento. No ampliar automáticamente la población académica.
4. Crear la cuenta en cero. Si usan práctica, finalizar el recorrido con limpieza
   antes de registrar existencias reales. Si ya se mezclaron relaciones reales,
   la aplicación bloqueará la eliminación: solicitar revisión y conservar datos.
5. Entregar por un canal privado la dirección y clave inicial de una sola vez.
   El propietario crea su clave definitiva; el equipo no debe pedirla ni guardarla.
6. Confirmar IVA, cinco productos, existencias, costo contable y precio base sin
   IVA con el propietario. Comparar el total final de un ejemplo con sus soportes.
   Estos comprobantes internos no son facturación electrónica DIAN.

## Actividades de uso

| Día | Actividad del comercio | Evidencia privada del equipo |
|---|---|---|
| 1 | Acceso, cambio de clave, recorrido, IVA e ingreso/revisión de cinco artículos. | Fecha real de inicio, revisión instalada, tareas completadas y ayuda requerida. |
| 2 | Registrar ventas de prueba controlada; comprobar total, IVA y existencias. | Resultado observado, diferencias y tiempo aproximado si se midió realmente. |
| 3 | Movimientos de entrada/ajuste e importación pequeña con revisión previa. | Archivo de ejemplo autorizado, filas válidas/rechazadas y conciliación con el negocio. |
| 4 | Consultar ventas, rankings, gráficos y descargar una copia JSON/CSV. | Qué información entendió, qué decisión consideró y qué dudas aparecieron. |
| 5 | Completar la revisión de tareas y recoger comentarios de cierre. | Respuestas auténticas, incidencias, mejoras solicitadas y periodo real de uso. |

No obligar a registrar transacciones ficticias dentro de la operación real para
cumplir esta tabla. Las pruebas que requieran anular o borrar se realizan en una
cuenta sintética separada. El comercio decide si su operación real puede
acompañarse; no sustituir sus controles habituales durante la evaluación.

## Importaciones sin distorsionar las cifras

- **Productos:** previsualizar primero, comprobar columnas/precios/IVA/unidades
  y guardar después. Los SKU repetidos se informan y no sobrescriben artículos.
  El archivo de productos puede guardar filas válidas y rechazar otras: revisar
  el resumen antes de seguir. Límites de 5 MiB y 20.000 filas.
- **Ventas operativas actuales:** registran ventas ahora y descuentan stock.
  No enviar un archivo histórico a esa opción. Una copia idéntica del archivo
  ya aplicado se bloquea; no se garantiza detectar todas las duplicaciones de
  registros manuales o archivos reescritos.
- **Historial:** conserva fecha y referencia de origen; agrupa las líneas de una
  misma venta; exige costo histórico e IVA efectivo por artículo, sin inferirlos
  del catálogo actual. No modifica las existencias actuales. Una referencia ya
  importada se rechaza incluso si cambia el archivo. Un error rechaza todo el
  archivo histórico para evitar comprobantes parciales. No volver a importar
  ventas ya registradas manualmente.
- En el historial, `sale_number` es la referencia externa; el sistema conserva
  también su consecutivo interno. `occurred_at` acepta fecha ISO con zona; sin
  zona se interpreta en Colombia. `unit_price` es base sin IVA; `unit_cost` y
  `vat_rate` deben corresponder al documento original. No usar el IVA actual para
  reconstruir a ciegas ventas pasadas. Cero no distingue exento de excluido.

Una empresa nueva puede no tener proyección: se requieren tres meses calendario
completos consecutivos con registros. La aplicación no reemplaza meses ausentes
por cifras inventadas. R² describe el ajuste histórico, no certeza futura.
La ganancia comercial presentada no incluye todos los gastos generales del negocio.

## Comentarios de cierre

Usar primero el instrumento aprobado con el director. Como registro operativo
complementario pueden pedir, sin sugerir respuestas:

1. ¿Qué tareas pudo completar y en cuáles necesitó ayuda?
2. ¿Qué pantalla o mensaje le resultó confuso? Dé un ejemplo.
3. ¿Los precios, IVA, totales y existencias coincidieron con sus registros?
4. ¿Qué información o gráfico le fue útil y para qué lo usaría?
5. ¿Encontró errores, lentitud o pérdida de información? ¿Qué ocurrió antes?
6. ¿Qué cambiaría primero y volvería a usar la herramienta? ¿Por qué?

Registrar también versión, fechas reales, tareas no realizadas y motivo. No
presentar estas preguntas como escala validada ni calcular satisfacción o éxito
si no se recolectaron los datos correspondientes. No pedir contraseñas, RUT,
contactos de clientes ni cifras comerciales innecesarias para el comentario.

## Incidencias durante los cinco días

Si falla el acceso, cambian totales/stock incorrectamente, desaparecen registros
o aparecen datos de otra empresa: detener la función afectada, conservar hora,
versión y pasos, y avisar al equipo por el canal acordado. No repetir una venta
o importación cuando no se sabe si se guardó; consultar el historial primero.
Respaldar antes de corregir datos. Un problema de presentación puede registrarse
sin detener tareas independientes que sí funcionen.

Conservar una copia privada diaria y comprobar la recuperación conforme a la guía
de despliegue. Si cambia la versión por una corrección, registrar cuándo y qué
empresas la usaron. No borrar evidencia de errores para mejorar el resultado del
estudio. El informe debe indicar el periodo efectivo; cinco días no equivalen a
dos semanas ni a una validación comercial definitiva.
