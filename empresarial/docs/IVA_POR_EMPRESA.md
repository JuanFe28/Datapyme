# Condición de IVA editable por empresa

Implementado el 13/11/2026, rama `feat/iva-por-empresa-20261113`.
Continúa la revisión de precios e IVA; aplica a las operaciones del prototipo.

## Uso y reglas

Entrar como administrador de la empresa (`owner`) y pulsar **Editar condición de IVA**
o entrar a **Mis Datos**. Seleccionar la condición vigente, indicar el motivo de
cambio o corrección y guardar. El tablero se recarga con la nueva revisión.

| Condición | Operaciones nuevas |
|---|---|
| Pendiente de confirmar | No permite guardar ventas manuales ni confirmar importaciones de ventas. El formulario no presenta un total definitivo. |
| No responsable de IVA | Aplica IVA cero en la venta; conserva las tarifas configuradas de los artículos para futuras transiciones. |
| Responsable de IVA | Aplica la tarifa configurada de cada artículo, incluidos los de tasa cero. No asigna automáticamente 19% a todos. |

RN-01. Cada empresa configura exclusivamente su propia condición; solo su `owner`
puede modificarla. Otros operarios pueden consultarla; el SuperAdmin no obtiene
acceso operativo mediante este endpoint. Los comercios nuevos y existentes sin
registro parten en pendiente. Los seeds nuevos declaran responsable como supuesto
sintético de sus ejemplos; no se infiere condición de comercios reales ni existentes.

RN-02. Guardar aplica inmediatamente a las operaciones registradas después del
cambio; no programa fechas futuras ni permite retroactividad. Registrar el cambio
cuando la condición sea efectivamente vigente y confirmada. Una transición legal
no se determina automáticamente por alcanzar un tamaño o monto de ventas.

RN-03. Se recalculan previsualización, precio final del catálogo, IVA, total y las
ventas manuales/importadas. Precios base y costos contables se conservan. Ingresos
y utilidad excluyen IVA; las operaciones nuevas alimentan los indicadores según
sus importes efectivos. Un cambio tributario no supone cambiar el precio base.

RN-04. Cada venta nueva conserva condición, revisión y tarifa efectiva por línea.
Cambiar la condición no reescribe ventas, ingresos ni impuestos anteriores. Las
ventas previas a esta función muestran condición histórica no registrada; no se
inventa una condición a partir de su porcentaje. Para corregir una venta errónea
en el prototipo: revisar, anular si corresponde y volver a registrar correctamente.
Eso no sustituye notas crédito ni obligaciones fiscales de un sistema de facturación.

RN-05. El historial guarda revisión, motivo, usuario y fecha de registro UTC.
Se rechazan cambios basados en una revisión obsoleta; la interfaz envía también la
revisión con la venta, para exigir recarga si cambió la condición. En PostgreSQL
se toma bloqueo de la empresa durante la operación/cambio. No se afirma aquí
haber probado cargas concurrentes PostgreSQL; SQLite tiene sus propios límites.

RN-06. No se modifican automáticamente los costos por IVA de compras: su
recuperabilidad exige soporte y análisis del caso. Exento y excluido requieren
clasificación diferenciada pendiente en el catálogo; tasa cero no la certifica.

## Implementación y actualización de base existente

- `app/core/models.py`: tablas nuevas `company_tax_changes`, `sale_tax_snapshots`.
- `app/core/company_tax.py`: política y bloqueo central de operaciones pendientes.
- `app/routes/company_tax.py`: GET/PUT `/api/company/tax`, aislado por sesión.
- `app/core/commercial_service.py`: liquidación central utilizada por ventas e importaciones.
- `app/routes/dashboard.py`, `static/js/app.js`, `templates/company_tax_settings.html`:
  formulario, mensajes, revisión y cálculo visual por estado.
- Exportación JSON incluye historial y metadatos de las ventas nuevas.

La creación es aditiva mediante `Base.metadata.create_all` en el arranque ya
existente. Antes de actualizar una base real, respaldar y probar en copia. Esta
revisión se ejecutó exclusivamente con SQLite sintético: no migró Supabase ni la
base del compañero ni publicó el cambio en producción. No se alteran columnas ni
se convierten importes anteriores. Conservar respaldo; volver al código anterior
no requiere eliminar las tablas nuevas y no se debe purgar su historial.

## Evidencia

Suite aislada: **46 pruebas Python aprobadas** y **dos pruebas JavaScript aprobadas**.
Una advertencia de deprecación Starlette/httpx. Pruebas de la nueva función cubren
pendiente, transiciones, conservación histórica, revisión obsoleta, permisos,
aislamiento, importación y motivo que contiene caracteres de script.
Los fixtures anteriores de ventas ahora declaran expresamente su supuesto
`tax_status=responsible`, sin cambiar sus expectativas monetarias.

Recorrido visible sobre base anterior con 46 ventas:

1. Arranque crea las tablas nuevas; empresa existente aparece pendiente.
2. Venta pendiente bloqueada con mensaje para confirmar condición.
3. Seleccionar no responsable y guardar motivo sintético: base 4.000,
   IVA 0 y total 4.000; venta #19 guardada.
4. Cambiar a responsable: el artículo conserva su tarifa nominal sintética de 5%;
   base 4.000, IVA 200 y total 4.200; venta #20 guardada.
5. Historial conserva venta #19 con IVA cero y #20 con IVA 200.
6. Comparación con respaldo previo: las 46 ventas originales conservan subtotal,
   descuento, IVA, total, costo y estado; integridad SQLite correcta.

La condición configurada no acredita verificación del RUT. El administrador debe
confirmarla para cada empresa antes de cobros reales.

## Fuentes y límites

[DIAN, Concepto 14527 de 2025](https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_14527_2025.htm),
consultado 13/11/2026: el no responsable no adiciona IVA; la transición y el
tratamiento de compras requieren condiciones y soportes. La configuración registra
lo declarado por el usuario, no determina automáticamente su situación fiscal.
Se mantiene el [informe de revisión previo](REVISION_IVA_COLOMBIA_2026_11_13.md)
como evidencia histórica; este documento reemplaza su pendiente de configuración
por empresa. Permanecen pendientes de aquel informe los asuntos no implementados,
incluida facturación DIAN, clasificación completa y modo de precio IVA incluido.
