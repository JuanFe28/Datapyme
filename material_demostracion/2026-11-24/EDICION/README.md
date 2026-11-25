# Cómo continuar la edición

Los clips de esta carpeta abren en un editor de video sin iniciar Datapyme. Están a 1920 × 1080 y 25 cuadros por segundo. Cada clip conserva la cabecera y el encuadre de su capítulo. La pista de audio y los subtítulos se añaden durante la edición.

1. Descarga la rama `fix/precios-y-demo-20261124` como ZIP o clónala. Abre `material_demostracion/2026-11-24/EDICION`.
2. Para el video largo, importa los doce MP4 de [completo](completo) en orden desde `01.mp4`. Para el corto, usa los cinco de [breve](breve). Las listas [del recorrido completo](orden_completo.txt) y [del resumen](orden_breve.txt) indican en qué segundo empieza cada capítulo.
3. Ajusta los cortes y los tiempos sobre esa pista. Los [subtítulos del recorrido anterior](../DATAPYME_RECORRIDO_COMPLETO.srt) y los [del resumen anterior](../DATAPYME_RESUMEN_CORTO.srt) se pueden importar y editar. El [guion de Alvino](../GUION_PARA_GRABAR_DATAPYME.txt) es el texto de referencia para subtitular la nueva narración.
4. Si Alvino graba, coloca sus audios del 01 al 12 debajo de cada capítulo en tu editor local. Edita las repeticiones, nivela el volumen y ajusta la imagen y los subtítulos a su ritmo.
5. Exporta un MP4 en 1080p. Si incorpora la voz de Alvino, guárdalo localmente junto a las tomas de voz y las pruebas de imitación. A GitHub se suben únicamente las versiones sin su voz. Revisa las cifras de la venta y del IVA, así como la lectura de los subtítulos en el celular.

Para evitar pisarse, Juan Felipe puede crear una rama de edición desde esta revisión y abrir una solicitud de cambios en GitHub para que Alvino la revise. Los MP4 terminados de la carpeta superior sirven para comparar la edición y presentar el prototipo mientras llega la voz original.

Si solo necesitas unir los clips limpios, ejecuta desde esta carpeta, con FFmpeg disponible en la terminal:

```text
ffmpeg -f concat -i completo.ffconcat -c copy -movflags +faststart Datapyme_base_completa.mp4
ffmpeg -f concat -i breve.ffconcat -c copy -movflags +faststart Datapyme_base_breve.mp4
```

[Inventario técnico de los clips](fuentes.json) con tiempos, tamaños y huellas SHA-256.
