Actúa como un Auditor Técnico de Software Senior y Arquitecto de Soluciones. Tu objetivo es realizar una auditoría completa y exhaustiva de todo el código fuente, estructura de carpetas, base de datos y configuración de este proyecto llamado **"Datapyme"**.

Este proyecto corresponde al componente técnico (Prototipo Funcional Web / MVP) de un Trabajo de Grado aprobado bajo el formato institucional **F-DC-124** (Modalidad Emprendimiento: Plan de Negocios) y documentado hacia el informe final **F-DC-125**. 

Es un trabajo en pareja y acabo de recibir los avances de código de mi compañero. **ESTÁ ESTRICTA Y ROTUNDAMENTE PROHIBIDO salirse de los lineamientos aprobados en el documento F-DC-124.** No podemos omitir nada de lo prometido ni agregar arquitecturas o algoritmos que contradigan el alcance aprobado por el comité evaluador.

A continuación, te presento la **Especificación Oficial Aprobada (F-DC-124)** contra la cual debes auditar cada archivo del repositorio:

### 1. ALCANCE TÉCNICO Y FUNCIONAL OBLIGATORIO (F-DC-124)
* **Tipo de aplicación:** Prototipo funcional web (Producto Mínimo Viable - MVP) bajo concepto SaaS (Software como Servicio).
* **Objetivo Específico 3:** Desarrollar un prototipo web funcional de Datapyme que integre **ventas, inventarios, indicadores, visualizaciones y analítica básica**, empleando la metodología ágil Scrum para organizar el desarrollo del software.
* **Módulos y Capacidades comprometidas (Actividades Fase 3 y Resultados Esperados):**
  1. **Gestión e integración de datos (Actividad 3.3):** Funcionalidades para cargar, registrar o integrar información operativa de **ventas** e **inventarios**.
  2. **Tablero de Analítica Empresarial / Dashboards (Actividad 3.4):** Generación de indicadores empresariales (KPIs) y visualizaciones interactivas (gráficos, tendencias y comportamientos de ventas e inventarios) comprensibles para PyMEs comerciales.
  3. **Componente básico de analítica predictiva (Actividad 3.5):** Orientado a procesar información histórica disponible y generar estimaciones preliminares relacionadas con el comportamiento/tendencia de ventas u otras variables definidas.
     * *RESTRICCIÓN CRÍTICA DEL EVALUADOR:* Debe ser un **algoritmo estadístico/predictivo básico** (como regresión lineal simple o promedios móviles). **NO** debe aparentar ni implementar modelos complejos de IA avanzada o Deep Learning desproporcionados, y en la interfaz/documentación debe quedar claro que son estimaciones sujetas a la cantidad y calidad de los datos (apoyo a la decisión, NO decisiones automáticas ni certezas absolutas).
  4. **Seguridad, Privacidad y Consideraciones Éticas (Obligatorio en F-DC-124):**
     * Control de acceso básico (autenticación/autorización).
     * Gestión adecuada de archivos y restricción de datos en ambiente de pruebas.
     * **PROHIBIDO** solicitar o almacenar en base de datos contraseñas en texto plano, credenciales bancarias, secretos comerciales o datos sensibles no indispensables.
     * Cumplimiento de privacidad (Ley 1581 de 2012): manejo de datos anonimizados, seudonimizados o sintéticos para pruebas, y verificación de que no se envíen datos empresariales/personales identificables a servicios externos o APIs de IA de terceros sin control.

---

### 2. INSTRUCCIONES DE AUDITORÍA (LO QUE DEBES HACER AHORA)
Explora absolutamente todas las carpetas, archivos de configuración, paquetes, esquemas de base de datos, backend y frontend del espacio de trabajo actual y entrégame un **Informe de Auditoría Técnica y de Alineación F-DC-124** dividido en las siguientes 6 secciones:

#### SECCIÓN 1: Radiografía Actual del Proyecto (Stack y Arquitectura)
* ¿Qué tecnologías, lenguajes, frameworks y librerías se están utilizando en Frontend, Backend y Base de Datos?
* ¿Cuál es la estructura de carpetas actual y cómo está organizada la arquitectura (Act. 3.2: modelo de datos, flujos de interacción e interfaces)?
* ¿El proyecto compila/ejecuta actualmente o tiene errores de dependencias, configuración o sintaxis rotos?

#### SECCIÓN 2: Matriz de Cumplimiento vs. F-DC-124 (Semáforo de Alineación)
Evalúa módulo por módulo qué existe realmente en el código (funcional vs. maqueta/mock vs. inexistente):
1. **Autenticación y Control de Acceso (Consideraciones Éticas):** ¿Existe login/control de acceso seguro?
2. **Módulo de Ventas (Act. 3.3):** ¿Permite registrar, importar (ej. CSV/Excel) o gestionar datos de ventas?
3. **Módulo de Inventarios (Act. 3.3):** ¿Permite registrar, importar o gestionar stock/inventarios?
4. **Indicadores y Dashboards Interactivos (Act. 3.4):** ¿Qué KPIs se calculan realmente con datos reales del backend y qué gráficas interactivas están implementadas?
5. **Componente Básico de Analítica Predictiva (Act. 3.5):** ¿Está implementado? ¿Qué fórmula o algoritmo exacto está usando en el código? ¿Cumple con ser analítica predictiva básica sin salirse del F-DC-124? ¿Incluye las advertencias de alcance/limitación de datos para el usuario?

#### SECCIÓN 3: Detección de Desviaciones ("Scope Creep" o Incumplimientos)
* **¿En qué nos estamos saliendo del F-DC-124?** Identifica si mi compañero agregó módulos, librerías, integraciones externas (ej. APIs de IA de terceros no permitidas, pasarelas de pago reales, módulos contables complejos) que NO están en el F-DC-124 o que violan las Consideraciones Éticas.
* **¿Qué partes están "Hardcodeadas" (datos falsos fijos en el código)?** Identifica dónde hay gráficas o tablas con números estáticos que aún no se conectan a la lógica real o base de datos.

#### SECCIÓN 4: Auditoría de Modelo de Datos y Seguridad
* Revisa los modelos/esquemas de base de datos. ¿Cubren las entidades necesarias para Ventas, Inventarios y Usuarios de una PyME comercial?
* Verifica que no haya vulnerabilidades obvias ni almacenamiento de datos prohibidos según el apartado de Consideraciones Éticas del F-DC-124.

#### SECCIÓN 5: Qué Falta Exactamente por Desarrollar (Plan de Choque)
Lista de tareas técnicas concretas (Backlog pendiente) para completar el 100% de las actividades 3.1 a 3.8 del F-DC-124 y dejar el prototipo listo para las pruebas funcionales y la validación con usuarios (PyMEs de Bucaramanga), lo cual es el insumo obligatorio para redactar el informe final **F-DC-125**.

#### SECCIÓN 6: Recomendación de Decisiones para el Equipo
Dime con total franqueza técnica: ¿Vamos por buen camino con esta base de código? ¿Qué debemos conservar, qué debemos refactorizar/corregir de inmediato y cómo debemos dividirnos el trabajo restante mi compañero y yo para cumplir estrictamente con el F-DC-124?

Por favor, inicia la inspección de todos los archivos del proyecto antes de responder y sé sumamente detallado y crítico en tu reporte.