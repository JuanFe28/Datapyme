# Cambios revisados para preparar la demostración

Comparación de archivos entre `origin/main` y la revisión fuente `a95aac66825bfab5334c5843eb57ce07b1758fab` de `fix/precios-y-demo-20261124`. Es una revisión del código disponible, sin ejecutar de nuevo las pruebas funcionales ni comprobar el servidor remoto.

| Área | Cambio observado | Implicación para el video |
| --- | --- | --- |
| Precios | Formulario con precio base sin IVA y vista previa del importe final; ajustes en `empresarial/static/js/app.js` y `empresarial/templates/dashboard.html`. | Mostrar base, impuesto y total como valores distintos. |
| Excel | `smart_excel_mapper.py` rechaza importes inválidos, negativos o no finitos con error 422 y contexto de fila/campo; evita confundir el total de una línea con un precio unitario. | Pedir revisar el archivo y corregir errores antes de importarlo. |
| IVA importado | El importador distingue valores que incluyen IVA y convierte a base del catálogo cuando corresponde. Exige nueva revisión si cambia la condición tributaria durante el proceso. | Pedir confirmar la condición de IVA y revisar la vista previa. |
| Confirmación de importación | La ruta y la interfaz incorporan revisión previa y controles antes de guardar. | Mostrar la importación como un flujo de revisión y confirmación. |
| Indicadores | Los textos distinguen utilidad bruta de ganancia neta y moderan las promesas sobre importación y proyección. | Explicar gastos no incluidos y límites de la estimación. |

El estado heredado del proyecto registra 112 pruebas Python aprobadas, cuatro de PostgreSQL omitidas y 15 JavaScript aprobadas. Son resultados anteriores, no resultados obtenidos en esta edición. El despliegue, persistencia y recuperación del servidor permanecen sin verificar aquí.

Esta entrega cambia exclusivamente el material audiovisual y su documentación. Los ejemplos conservan las cifras de las capturas: $10.000 + $1.900 = $11.900; $115.000 + $21.850 = $136.850; $115.000 − $78.000 = $37.000 de utilidad bruta. Antes de usar información de empresas se mantienen las comprobaciones remotas indicadas en ESTADO_PROYECTO.md.
