# Datapyme: presentación para profesionales

Edición del 25 de noviembre de 2026, preparada con las capturas reales y los datos sintéticos de la carpeta anterior. Los originales se conservan.

| Uso | Archivo |
| --- | --- |
| Presentación principal, 6:10 | [MP4 en 1080p](DATAPYME_PRESENTACION_PROFESIONAL_1080P.mp4) |
| Primer contacto, 1:35 | [Resumen en 1080p](DATAPYME_RESUMEN_PROFESIONAL_1080P.mp4) |
| Texto de la presentación | [Subtítulos SRT](DATAPYME_PRESENTACION_PROFESIONAL.srt) |
| Texto del resumen | [Subtítulos SRT](DATAPYME_RESUMEN_PROFESIONAL.srt) |
| Navegación y tiempos | [Capítulos completos](CAPITULOS.txt) · [Resumen](CAPITULOS_RESUMEN.txt) |
| Comprobaciones y huellas de los archivos | [Verificación técnica](VERIFICACION_TECNICA.json) |
| Cambios revisados en la aplicación | [Revisión](REVISION_CAMBIOS.md) |

Los MP4 no tienen audio. Incluyen los textos visibles y capítulos de navegación; los SRT son una copia opcional de esos textos. Al reproducirlos, desactive los subtítulos externos para evitar mostrarlos dos veces. Para una reunión, descargue el MP4 y compruebe su reproducción antes de compartir pantalla.

## Cambios de montaje

- Se condensó el recorrido de 10:04 a 6:10 manteniendo las doce secciones. Se aceleraron las capturas; se conservó su orden.
- Se añadieron apertura y cierre dirigidos a la revisión con profesionales, una jerarquía de títulos consistente y un indicador de avance.
- Se reemplazaron los subtítulos antiguos por frases completas, con tiempos proporcionales a su longitud y un límite de 17,5 caracteres por segundo.
- Se explican por separado precio base, IVA, total y utilidad bruta. Se aclaran las limitaciones del comprobante interno y de la proyección.
- El resumen pasa de 1:22 a 1:35 para dar más tiempo a la lectura.

El material presenta un prototipo con datos de práctica. No acredita validación con empresas, despliegue del servidor ni certificación de funciones. Las capturas corresponden a la revisión fuente `a95aac66825bfab5334c5843eb57ce07b1758fab`; esta edición no modifica la aplicación.

## Reproducir la edición

Requiere Python, Pillow, OpenCV, FFmpeg con libass y libx264, y las fuentes Segoe UI de Windows. Desde cualquier carpeta:

```powershell
python editar_video.py --ffmpeg 'C:\ruta\ffmpeg.exe'
python editar_video.py --ffmpeg 'C:\ruta\ffmpeg.exe' --resumen
python verificar_video.py --ffmpeg 'C:\ruta\ffmpeg.exe'
```

Ejecute los comandos indicando la ruta completa de los scripts si no está en esta carpeta. El generador conserva las fuentes y crea los intermedios en carpetas ignoradas por Git. Los manifiestos MONTAJE registran fuentes, huellas, duración y texto de cada capítulo. El informe técnico se actualiza después de comprobar ambos MP4.

Para incorporar la voz de Alvino, grabe y ajuste la locución en un montaje local a partir de estos tiempos. El guion anterior tiene tiempos del recorrido de diez minutos y requiere resincronización. Las grabaciones personales y exportaciones que las incluyan se mantienen fuera de GitHub, según las instrucciones del material original.
