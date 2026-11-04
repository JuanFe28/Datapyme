# Datapyme Research Studio

## Propósito y alcance autorizado

Herramienta privada de investigación para los autores del Plan de Negocios UTS, propuesta 65-2026-147. Conservar los cuatro objetivos específicos del F-DC-124. Research Studio no acredita que el producto comercial ni su analítica predictiva estén desarrollados. Fuentes contrastadas: solicitud del usuario, F-DC-124 DOCX y PDF, plantilla F-DC-125. No modificar los documentos originales ni crear resultados de investigación.

## Decisiones

Ampliar FastAPI/Jinja y conservar las rutas existentes. Separar configuración, modelos, seguridad, investigación, análisis y exportación en módulos Python. PostgreSQL en producción; SQLite en desarrollo y pruebas. Migraciones Alembic aditivas, sin borrar registros previos. Las respuestas antiguas quedan pendientes de revisión de calidad hasta documentar su validez. No hay repositorio Git en la carpeta, por lo que se conserva una copia ZIP del código original y se entrega código local sin inventar commits.

Los archivos autorizados (máximo 10 MiB) se guardan con metadatos y contenido binario en tablas separadas de la base persistente; esto evita depender del disco efímero del alojamiento. Formatos permitidos: PDF, PNG, JPEG, TXT, CSV, DOCX y XLSX con verificación de contenido. Acceso del administrador o del investigador que adjuntó el archivo; sin enlaces públicos.

## Flujos

1. Usuarios individuales administrador e investigador, contraseña PBKDF2 con sal aleatoria, sesiones revocables, CSRF y limitación de intentos. Bootstrap por CLI o variables iniciales; sin claves predeterminadas.
2. Empresa con estado de verificación, fuente, tamaño, municipio, actividad, registros operativos, aptitud del informante y participación. Solo pequeñas/medianas comerciales activas de Bucaramanga verificadas y dispuestas son elegibles. Normalizar nombre/barrio para evitar duplicados también en edición y concurrencia. Contacto personal separado y visible al administrador. Historial de cambios.
3. Instrumentos por secciones con consentimiento versionado y participante codificado. Guardar borradores sin incluirlos en estadísticas; finalizar con validación completa en servidor. Una encuesta final por empresa, garantizada en base. Saltos M14/M20/V11, límites, exclusiones de opciones y revisión de datos heredados. Entrevistas distinguen palabras del participante de interpretación del investigador. Pruebas requieren versión y referencia verificable del prototipo, sin proclamar su validación.
4. Dashboard y análisis con filtros de empresa, actividad, tamaño y fechas compartidos con exportaciones. Contadores separados de encuestas finales válidas, borradores y registros históricos pendientes. Selección múltiple: porcentaje = empresas que mencionan la opción / personas con respuesta válida a esa pregunta. Mostrar n y limitaciones. Sin agregaciones de contactos.
5. Evidencias asociadas a empresa, respuesta o actividad; consentimiento explícito de carga, restricciones y descargas privadas. Actividades de los cuatro objetivos con responsable, estado, plazo y evidencia.
6. Canvas con nueve componentes, versiones y vínculos a evidencias. La validación de hipótesis requiere evidencia y conclusión explícitas. Escenarios financieros con supuestos y fuentes: inversión separada del presupuesto académico; precio, costos variables/fijos, clientes y crecimiento. Cálculos transparentes de contribución, equilibrio y flujo de caja, sin supuestos predeterminados presentados como hallazgos. Registro organizacional, ambiental, competidores y financiación como notas sustentadas.
7. Excel, CSV, PDF y PNG con el mismo subconjunto filtrado, encabezados legibles, denominadores, fecha de corte, protección de fórmulas y sin contactos. PDF con tablas y gráficos; PNG con título, n, leyenda y contexto.

## Operación

Health/readiness verifica conexión y revisión de esquema. Producción rechaza SQLite y secretos débiles, exige HTTPS/cookies seguras, PostgreSQL y hosts permitidos. Configuración Render, Docker, CI, dependencias bloqueadas, CLI de migración, respaldo y restauración documentados. No crear servicios de pago ni modificar proyectos ajenos. Conexiones observadas: Supabase solo muestra `tienda`; GitHub no muestra un repositorio Datapyme. Falta seleccionar/proveer destino específico y acceso a Render.

## Validación

Pruebas con bases temporales y fixtures explícitamente sintéticos, nunca en la base de investigación. Verificar rutas, roles, consentimiento, edición, duplicados, borradores, saltos, denominadores, filtros, exportaciones, archivos, auditoría, migración de esquema antiguo y persistencia tras recrear el proceso. Navegación visual auténtica en navegador disponible, con comprobación responsive si la herramienta lo permite. Reportar por separado PostgreSQL remoto y despliegue no ejecutados.
