# Revisión de precios, utilidad e IVA — Colombia

> Actualización posterior: la [condición editable por empresa](IVA_POR_EMPRESA.md)
> ya está implementada y probada. Este informe conserva la revisión inicial;
> sus menciones de esa función como pendiente quedan reemplazadas por la guía nueva.

Fecha de consulta y pruebas: 13/11/2026. Revisión técnica del módulo empresarial
de JuanFe28/Datapyme; continuación de b167ac7 en `fix/revision-iva-20261113`.
Estado: errores concretos corregidos; configuración tributaria integral pendiente.
No constituye certificación fiscal ni autorización para facturar electrónicamente.

## Resultado principal

El caso base 115.000, IVA 21.850 y total 136.850 es coherente **si** el precio
registrado es antes de IVA y corresponde aplicar 19%. No demuestra que esa tarifa
corresponda a todas las empresas o artículos. El equipo confirmó que hay comercios
responsables y no responsables, pero falta verificar la condición de cada uno.
Se conserva la semántica histórica de precios base; no se convierten ventas previas.

## Reglas contrastadas con fuentes oficiales

| Fuente consultada | Regla relevante y consecuencia |
|---|---|
| [Estatuto Tributario, arts. 420, 424, 437, 447, 454, 468, 468-1, 477, 485 y 488](https://normograma.dian.gov.co/dian/compilacion/docs/estatuto_tributario.htm) | El hecho gravado, responsable, base y tarifa deben determinarse para la operación. El 19% es general, con excepciones. El IVA descontable requiere condiciones; no basta haberlo pagado. Un porcentaje cero no identifica por sí solo exención o exclusión. |
| [DIAN, Concepto 14527 de 2025](https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_14527_2025.htm) | Mientras se tenga condición de no responsable no se adiciona IVA al precio por ese concepto. No inferir condición por tamaño, nombre comercial o subsector. |
| [DIAN, Oficio 26025 de 2019](https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_26025_2019.htm) | Se distinguen operaciones gravadas con diferentes tarifas, exentas y excluidas; una canasta no justifica imponer una tarifa uniforme. |
| [DIAN, Oficio 5737 de 2019](https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_5737_2019.htm) | El descuento efectivo, normal y no condicionado que consta en el documento puede reducir base; los descuentos condicionados requieren otro tratamiento. La app solo maneja reducción inmediata por línea. |
| [SIC, información de precios; art. 26 Ley 1480](https://sedeelectronica.sic.gov.co/temas/proteccion-al-consumidor/derechos-y-deberes/inconvenientes-precio) | El precio informado al consumidor debe incluir impuestos y cargos aplicables. Una base interna sin IVA debe identificarse y diferenciarse del precio final informado al público. |
| [CTCP, NIIF para Pymes, sección 13, párr. 13.6](https://www.ctcp.gov.co/ctcp_files/CTCP/78/7827901a-191a-41ee-adb8-1354ecb0d712.pdf) | El costo incluye impuestos no recuperables y costos atribuibles; excluye impuestos recuperables. El importe de la factura de compra no siempre es el costo del inventario. Confirmar marco contable aplicable. |
| [DIAN, Concepto 5716 de 2026](https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_5716_2026.htm) | Remite al sistema de facturación y Resolución 227 de 2025. Un comprobante interno con IVA no acredita habilitación, generación, transmisión ni validación electrónica. |

Exento y excluido tienen efectos distintos: la tarifa cero de ciertas operaciones
exentas y los derechos relacionados dependen de los requisitos legales y del sujeto;
no son categorías intercambiables. Tampoco se equipara un no responsable con un bien
excluido. Esta distinción aún no existe como configuración diferenciada en el modelo.

## Ejemplos ficticios para el equipo

Las fórmulas siguientes explican un caso simple, sin descuentos condicionados,
retenciones, gastos adicionales ni impuestos especiales. Redondeo a dos decimales.

| Supuesto | Base / ingreso sin IVA | IVA cobrado | Precio final | Utilidad bruta con costo 78.000 |
|---|---:|---:|---:|---:|
| 115.000 es base; aplica 19% | 115.000,00 | 21.850,00 | 136.850,00 | 37.000,00 |
| 115.000 es precio final; incluye 19% | 96.638,66 | 18.361,34 | 115.000,00 | 18.638,66 |
| Vendedor confirmado no responsable; precio 115.000 | 115.000,00 | No adiciona IVA | 115.000,00 | 37.000,00 |

Para extraer IVA incluido: base = precio final / (1 + tarifa/100); IVA = final - base.
La app no admite todavía un modo separado de captura con IVA incluido. Registrar
115.000 finales como si fueran base genera un cobro superior al esperado.

Utilidad bruta = ingreso después de descuentos, sin IVA generado, menos costo de
ventas. Margen sobre ventas = utilidad / ingreso neto; recargo sobre costo =
utilidad / costo. En el primer ejemplo: margen 32,17%; recargo 47,44%. No son
porcentajes equivalentes. La utilidad neta exige además gastos y demás conceptos;
el saldo de caja tampoco equivale automáticamente a utilidad.

Si los 78.000 de compra incluyen 19% y ese IVA es recuperable bajo las condiciones
aplicables: base 65.546,22 e IVA 12.453,78; el costo no sería automáticamente 78.000.
Si no es recuperable, integra el costo según corresponda. Datapyme no determina
el derecho al descuento tributario ni calcula declaraciones o IVA a pagar.

Canasta sintética probada: tres artículos a base 100, cantidades 1,5 y descuento
inmediato 10 por línea; tarifas 19%, 5%, 0%. Subtotal 450, descuento 30, bases
netas 420, IVA 33,60, total 453,60, costo 225 y utilidad bruta 195. El cero en
esta prueba es un supuesto matemático, no una clasificación legal de un producto.

## Trazabilidad y correcciones

| Componente | Antes | Resultado corregido / límite |
|---|---|---|
| `static/js/app.js`, `calculateCartTotals` | Estimaba 19% para toda la venta | IVA por tarifa del producto y redondeo de línea a centavos; servidor conserva autoridad |
| `schemas.py`, `routes/products.py` | Editar IVA se ignoraba | Edición y validación de rango 0–100; no certifica que una tarifa específica sea legal |
| `smart_excel_mapper.py` y mapeo JS | Importación mapeada sustituía tarifa por 19 | Reconoce y conserva `vat_rate`; si se omite sigue 19 por compatibilidad y UI advierte el supuesto |
| `commercial_service.py` | Permitía precio/descuento negativo por API; truncaba descuentos excesivos | Rechaza negativos y descuento superior al importe; alta rechaza importes negativos/no finitos |
| `app.js`, `openSaleDetailDrawer` | Ganancia y margen ignoraban descuentos | Utilidad sobre ingreso después del descuento, sin IVA |
| `templates/dashboard.html` | Precio ambiguo, IVA 19 fijo y subtotal de artículo con IVA | Formularios indican base SIN IVA y costo contable; tarifa explícita en alta; rótulos de IVA y total de línea corregidos |
| `analytics/kpis.py`, `compute_pure_kpis` | Ya excluía IVA y ventas anuladas | Se conserva; no implica que todos los periodos y rótulos del tablero estén validados |

La tasa almacenada en una venta histórica permanece aunque cambie el producto.
La anulación de la prueba mixta restituyó existencias. No se aplicaron cambios a
bases de comerciantes, declaraciones ni servicios de facturación reales.

## Pruebas ejecutadas

Las regresiones detectaron antes de corregir: actualización de tarifa ignorada,
tarifa perdida en mapeo, precio negativo aceptado y estimación visual 57 en vez de
24 para tres artículos base 100 con tasas 19/5/0. Tras corregir:

```text
python -m pytest tests/unit tests/integration tests/security
node --test tests/frontend/vat.test.cjs
```

41 pruebas Python y dos pruebas JavaScript aprobadas. Python emite una advertencia
de deprecación Starlette/httpx. Se excluye la suite E2E externa; el recorrido visual
se hizo en el navegador del chat y base sintética local, puerto 8020.

Prueba visual: artículo QA-ROL-IMPORT-01, costo 2.000, base 4.000, tasa de prueba 5%:
formulario estimó IVA 200 y total 4.200; venta #18 e historial conservaron esos
valores; comprobante mostró utilidad bruta 2.000 y margen 50%. La tasa 5% fue un
supuesto sintético para probar el software, no una clasificación del artículo.

## Información que se debe recopilar y validar

Para cada empresa: condición de IVA confirmada y fecha, actividad y operaciones,
política de precios (finales o bases), obligación y sistema de facturación,
persona encargada de validar y evidencia bajo acceso privado. Para cada artículo:
tratamiento, tarifa y soporte de clasificación; costos y tratamiento de impuestos
de compra; descuentos y devoluciones. No guardar RUT ni datos sensibles en GitHub.

Las condiciones son mixtas y parcialmente desconocidas según el equipo. Cada caso
desconocido debe permanecer pendiente de validación. Un contador debe confirmar
la condición, clasificación y recuperabilidad antes de parametrizar cobros reales.

## Pendientes que impiden declarar cumplimiento integral

- Configuración por empresa: responsable/no responsable/pendiente, con validación
  y aplicación transversal. Actualmente se calcula a partir de tasas de producto.
- Diferenciar categorías exento, excluido, gravado y no sujeto; no usar simplemente
  tasa cero como sustituto jurídico. Configuración confirmada antes del piloto real.
- Captura explícita de precios IVA incluido, precio final unitario en catálogo y
  coherencia en todos los puntos de presentación al consumidor.
- Documentar y unificar política de redondeo, decimales visuales (hoy se muestran
  pesos enteros), valores límite y formatos colombianos. El cálculo del servidor
  usa Decimal, mientras la previsualización JS usa Number y no reemplaza al servidor.
- Control de descuentos condicionados, devoluciones parciales, impuestos especiales,
  retenciones y múltiples escenarios de compras; quedan fuera de lo demostrado.
- Seguridad y concurrencia monetaria, actualización de valores negativos en todos
  los caminos, tarifas explícitas en todas las plantillas y exportaciones completas.
- Facturación DIAN: no implementada ni certificada. Anular internamente no sustituye
  una nota crédito o procedimiento fiscal cuando corresponda.

Para el profesor: «Corregimos diferencias entre pantalla y servidor al calcular
IVA, preservamos tarifas por producto y descontamos correctamente al calcular
utilidad bruta. La configuración tributaria de cada comercio y la facturación
electrónica requieren trabajo y validación adicionales; todo lo mostrado es sintético».
