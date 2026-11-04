# Datapyme Research Studio

Plataforma privada para recopilar, organizar y analizar las evidencias del Plan de Negocios de Datapyme, propuesta UTS 65-2026-147. Research Studio es la herramienta de investigación; el prototipo comercial de ventas, inventarios y analítica es un entregable diferente del objetivo 3.

El código actualizado está en esta carpeta. La base local se conserva en `datapyme_local.db`; no se incluyeron empresas ni respuestas de muestra en ella. Los fixtures de QA están separados en `.local/` y nunca se incluyen en la entrega.

## Abrir la instalación preparada en este equipo

1. Abrir [http://127.0.0.1:8000](http://127.0.0.1:8000).
2. Consultar las credenciales iniciales en `.local/acceso-local.txt`, únicamente en este equipo. No copiar ese archivo al repositorio ni compartirlo públicamente.
3. Crear las cuentas individuales del equipo en **Usuarios y acceso** y actualizar la contraseña inicial. Cambiar el acceso revoca las sesiones anteriores.
4. Para abrir o iniciar la aplicación, hacer doble clic en `INICIAR_DATAPYME.cmd`. También se puede ejecutar desde PowerShell en esta carpeta:

```powershell
.\scripts\start.ps1
```

También funciona directamente:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

La base de investigación está limitada al equipo local. La revisión remota tiene una copia separada.

## Revisión temporal por Internet

`REVISAR_POR_INTERNET.cmd` inicia una copia de revisión con base propia en `.local/review/revision.db`, cuentas independientes y un enlace HTTPS temporal. Incluye un caso sintético explícitamente identificado; **no registrar datos reales en esa copia**. Las páginas y exportaciones llevan la advertencia de prueba. El acceso y sus contraseñas se guardan en `.local/review/ACCESO_REVISION.txt` y, en este equipo, en `USO_PRIVADO_EQUIPO.txt`. Ambos archivos privados se excluyen de la entrega.

Mantener este computador encendido, conectado y sin suspensión durante la revisión. Al reiniciar puede cambiar el enlace; consultar el archivo de acceso actualizado. `DETENER_REVISION.cmd` cierra únicamente la revisión y conserva su base. El ayudante verifica el SHA-256 de la descarga oficial de cloudflared y no detiene procesos ajenos. Los [Quick Tunnels de Cloudflare](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) se destinan a pruebas y no ofrecen un alojamiento permanente.

La revisión HTTPS se verificó con inicio de sesión real desde el navegador. El despliegue definitivo con PostgreSQL persistente sigue pendiente del destino y las cuentas del equipo; antes de recopilar datos reales remotamente deben verificarse persistencia y recuperación en ese entorno.

## Instalación reproducible en otro equipo

Requiere Python 3.12 y un entorno virtual. Las versiones directas están fijadas en `requirements.txt`; `constraints.txt` fija las dependencias transitivas comprobadas.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py create-user --username admin --role admin
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

La creación de cuentas solicita la contraseña sin mostrarla. Si no se define `SESSION_SECRET` en desarrollo, se genera una clave local persistente en `.local/session-secret`. En producción se exige una clave explícita de al menos 32 caracteres, PostgreSQL y dominios permitidos. `.env` se carga automáticamente; no se sube a GitHub.

En Linux/macOS, sustituir `.venv\Scripts\python.exe` por `.venv/bin/python`.

## Funciones implementadas

- Acceso con cuentas individuales, hash PBKDF2-SHA256 con sal y 600.000 iteraciones, sesiones revocables de 12 horas, CSRF y bloqueo temporal tras cinco fallos. Roles administrador e investigador.
- Empresas: identificación interna, municipio, actividad, CIIU, tamaño, fuente, verificación, actividad vigente, informante y participación. Duplicados normalizados por nombre/barrio, también al editar. Historial de cambios. Contactos personales en tabla separada, accesible solo a administradores y excluida de exportaciones.
- Encuestas, entrevistas y pruebas: consentimiento versionado, participantes codificados, borradores, validaciones completas en servidor, saltos M14/M20/V11, opciones excluyentes, máximos de selección y una encuesta final por empresa garantizada en base de datos.
- Las pruebas del prototipo requieren versión y referencia de lo efectivamente evaluado. Una sesión registrada no significa que el producto comercial esté aprobado.
- Dashboard y análisis: filtros de búsqueda, tamaño, actividad, elegibilidad y fechas de Colombia; candidatas separadas de encuestas válidas. Porcentajes de preguntas múltiples usan participantes con respuesta válida, no cantidad de menciones. Se muestra el denominador por variable.
- Archivos autorizados: PDF, PNG, JPEG, TXT, CSV, DOCX y XLSX, hasta 10 MiB. Validación del contenido, ZIP de Office limitado, SHA-256 y descarga privada. Metadatos y binarios se guardan en tablas separadas de la base persistente, sin depender del disco temporal del alojamiento.
- Actividades de los cuatro objetivos con responsable, estado, fecha y evidencia requerida para completar.
- Business Model Canvas: nueve componentes, versiones conservadas, comparación y exportación PDF. El estado global de las hipótesis solo cambia a contrastada/validada/descartada si hay evidencia adjunta y conclusión explícita.
- Escenarios financieros con fuentes y supuestos: inversión inicial, costos, precio, clientes, crecimiento, contribución, equilibrio y flujo de caja. Comparación, fórmulas visibles y exportaciones Excel/PDF. Proyección básica sin impuestos, financiación, inflación ni descuento.
- Notas con fuentes para competencia, organización, ambiente, financiación, método y cotizaciones.
- Excel, CSV, PDF y PNG. Los datos de investigación respetan los filtros; las hojas de gestión del proyecto se incluyen completas y se identifican por separado. Excel y CSV neutralizan fórmulas introducidas en respuestas. PDF y PNG incluyen contexto y denominadores.
- Interfaz en español, menú móvil, progreso y estados vacíos. Chart.js y Lucide se sirven desde `static/vendor/`, sin recursos de terceros durante el uso.

## Flujo recomendado de operación

1. Revisar con el director el instrumento, consentimiento, clasificación, muestra y procedimiento. El software no sustituye esta revisión.
2. Registrar candidatas; las microempresas y grandes empresas quedan fuera de la población objetivo. Una pequeña/mediana sin verificación y fuente no es elegible. Se requiere actividad comercial vigente en Bucaramanga, registros de ventas e inventarios, informante idóneo y disposición voluntaria.
3. Obtener el consentimiento informado y aplicar los instrumentos. Los borradores e históricos pendientes no se convierten en resultados válidos automáticamente.
4. Adjuntar evidencia autorizada, actualizar actividades y contrastar Canvas y supuestos financieros.
5. Filtrar, revisar denominadores, exportar y redactar las interpretaciones en el F-DC-125. Una muestra por conveniencia no representa automáticamente toda Bucaramanga.

## Migraciones y conservación

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

Alembic incorpora campos y tablas sin borrar las empresas, respuestas o actividades del MVP anterior. Las respuestas antiguas quedan como `legacy_pending`; necesitan revisión explícita y consentimiento antes de contar como finales válidas. Las empresas antiguas requieren verificar los nuevos criterios. No hay downgrade destructivo automático.

La corrección de una respuesta final está reservada al administrador y queda auditada. **Retirar del análisis** conserva el registro y su historial. Un investigador no puede reactivarlo. La eliminación física de datos por solicitud del titular requiere un procedimiento administrativo específico, revisión de dependencias y copias; no se implementó un botón de borrado irreversible.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Se usan bases temporales bajo `.local/test-runs`, nunca la base de investigación. No ejecutar dos suites a la vez con el mismo `--basetemp`; puede indicarse una carpeta diferente. El registro exacto de comprobaciones está en `docs/VALIDACION.md`.

## Publicación, respaldos y arquitectura

- `docs/OPERACION.md`: Render/PostgreSQL, secretos, respaldo y recuperación.
- `docs/ARQUITECTURA.md`: componentes, datos y criterios de análisis.
- `docs/TRAZABILIDAD.md`: objetivos aprobados, módulos y evidencia esperada.
- `docs/VALIDACION.md`: pruebas realizadas, limitaciones y estado de publicación.

Hay configuración para Render, Docker y GitHub Actions. La publicación definitiva y las pruebas contra un PostgreSQL remoto no se realizaron: falta identificar el repositorio Datapyme, proporcionar su base y dar acceso al servicio Render. La copia temporal de revisión HTTPS se verificó por separado. La conexión Supabase disponible correspondía a otro proyecto y no fue modificada. Esta carpeta no era un repositorio Git; no se inventaron commits ni remotos.

Para empaquetar sin datos ni secretos:

```powershell
.\.venv\Scripts\python.exe scripts\package_release.py
```

La entrega queda en `dist/datapyme-research-studio.zip` con su SHA-256. La copia del código original de esta sesión se conserva en `.local/original-source.zip`.
