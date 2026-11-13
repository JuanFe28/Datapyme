# IVA editable por empresa

Requisito autorizado: cambiar la condición cuando se corrija un registro o cambie
la situación del comercio, aplicando automáticamente el cálculo correspondiente.
Ejecución directa conforme a la autonomía solicitada por el usuario.

Diseño: historial separado por empresa, con estado responsable/no responsable/
pendiente, motivo, usuario, fecha de registro y revisión. Guardar tiene efecto
inmediato para ventas nuevas; no backdating ni programación futura en esta entrega.
No responsable genera IVA cero; responsable usa la tarifa de cada artículo;
pendiente bloquea venta e importación de ventas. Precios base y costos no cambian.
Las tasas y totales de ventas guardadas se conservan. Correcciones de ventas
previas requieren anulación y registro nuevo en el prototipo, sin sustituir
procedimientos fiscales. Tabla nueva evita reescribir columnas de bases existentes.

Alternativas: sobrescribir tasas de productos perdería su clasificación al volver
a responsable; recalcular todo el histórico alteraría operaciones ya registradas.
Se usa política de empresa y snapshot por venta, con trazabilidad.

1. Agregar pruebas rojas: pendiente, transiciones, histórico, importación,
   aislamiento, permisos y revisión obsoleta.
2. Implementar modelos de historial/snapshot, servicio y API; migración aditiva.
3. Integrar liquidación central, registro y seeds sintéticos; actualizar fixtures
   para declarar explícitamente el supuesto tributario que ya estaban probando.
4. Integrar pantalla editable, previsualización por estado y control de revisión.
5. Probar API, JavaScript, base existente y recorrido visible; documentar y subir
   rama de revisión sin bases ni secretos.

Revisión de riesgos: no inferir régimen de empresas existentes; conservar costo
contable; rechazar sesiones ajenas y cambios del auditor; pedir recarga si cambió
la revisión desde que se abrió la pantalla. No garantiza concurrencia total de
ventas ni determina clasificación fiscal de cada artículo.
