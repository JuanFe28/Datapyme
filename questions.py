"""Instrumentos Datapyme, basados en objetivos del F-DC-124 aprobado."""

def q(code, label, kind='select', choices=None, required=True, help='', maximum=None):
    return dict(code=code, label=label, kind=kind, choices=choices or [], required=required, help=help, maximum=maximum)

SURVEY_SECTIONS = [
    ('A · Caracterización de la empresa', [
      q('M04','Cargo o función de quien responde',choices=['Propietario o socio','Gerente o administrador','Responsable de ventas','Responsable de inventarios','Otro']),
      q('M05','Actividad comercial predominante',choices=['Alimentos y bebidas','Ropa, calzado y accesorios','Belleza y cuidado personal','Tecnología y electrónicos','Ferretería y hogar','Comercio mayorista no especializado','Otra actividad comercial']),
      q('M06','Número de puntos de venta',choices=['1','2 a 3','4 o más','No sabe / no aplica']),
    ]),
    ('B · Gestión de ventas e inventarios', [
      q('M07','¿Qué medios utiliza para registrar o consultar las ventas?','multi',['Registros manuales','Hojas de cálculo','Facturación / punto de venta','Software administrativo / ERP','Comercio electrónico','No hay registro organizado']),
      q('M08','¿Cómo controla actualmente el inventario?','multi',['Registros manuales','Hojas de cálculo','Software de inventarios','Software administrativo integrado','No lleva control sistemático']),
      q('M09','¿Con qué frecuencia consulta informes o indicadores?',choices=['Diariamente','Semanalmente','Mensualmente','Cuando surge una necesidad','Nunca']),
      q('M10','¿Qué dificultades identifica actualmente?','multi',['Datos dispersos','No identifica fácilmente la rotación','Diferencias en inventario','Información desactualizada','Dificultad para analizar ventas','Demora preparando informes','Herramientas costosas o complejas','No enfrenta dificultades relevantes'], maximum=3,help='Seleccione máximo tres opciones.'),
      q('M11','Importancia de mejorar el análisis de ventas e inventarios','scale',help='1 = Nada importante · 5 = Muy importante'),
      q('M12','¿Qué información sería más útil?','multi',['Ventas por periodo','Productos más y menos vendidos','Existencias y alertas','Rotación de productos','Comparación entre periodos','Tendencias o estimaciones','Tablero resumen de indicadores'],maximum=3,help='Seleccione máximo tres opciones.'),
    ]),
    ('C · Tecnología y barreras', [
      q('M13','¿Usa tableros, gráficos o reportes digitales para analizar ventas e inventarios?',choices=['Sí','No','No está seguro']),
      q('M14','Si utiliza herramientas, ¿cuáles y qué limitaciones encuentra?','textarea',required=False),
      q('M15','¿Qué factores dificultarían adoptar otra herramienta?','multi',['Precio','Falta de conocimientos tecnológicos','Tiempo de implementación','Integración de datos','Confidencialidad y seguridad','Falta de soporte / capacitación','El sistema actual es suficiente','Ninguno'],maximum=3,help='Seleccione máximo tres opciones.'),
    ]),
    ('D · Evaluación neutral de Datapyme', [
      q('M16','¿Qué tan útil podría ser una plataforma como Datapyme?','scale',help='1 = Nada útil · 5 = Muy útil'),
      q('M17','¿Qué capacidad priorizaría?',choices=['Consulta de ventas e indicadores','Inventarios y existencias','Rotación de productos','Gráficos y tablero','Tendencias o estimaciones','Ninguna de las anteriores']),
      q('M18','¿Qué condiciones necesitaría para considerar usarla?','multi',['Precio accesible','Facilidad de uso','Importación de datos','Protección de información','Capacitación','Demostración / prueba','Soporte técnico'],maximum=3,help='Seleccione máximo tres opciones.'),
      q('M19','¿Qué modalidad de pago preferiría?',choices=['Suscripción mensual','Suscripción anual','Pago único','Solo una opción gratuita','No tendría interés','Necesita más información']),
      q('M20','Si considerara una suscripción, ¿cuál es el valor mensual MÁXIMO dispuesto a pagar (COP)?','number',required=False,help='Opcional. Por empresa/mes. Sin puntos ni comas; si no sabe, dejar vacío.'),
      q('M21','¿Estaría dispuesto a probar una demostración del prototipo?',choices=['Sí','Tal vez','No']),
      q('M22','¿Qué otra necesidad u observación considera importante?','textarea',required=False),
      q('M23','Modo de aplicación',choices=['Entrevistador presencial','Respondida directamente por la empresa','Entrevista remota']),
    ])
]

INTERVIEW_SECTIONS=[('Entrevista semiestructurada',[
  q('E04','Cargo del participante',choices=['Propietario o socio','Gerente o administrador','Responsable de ventas','Responsable de inventarios','Otro']),
  q('E05','¿Se autorizó expresamente una grabación?',choices=['Sí','No; solo tomar notas']),
  q('E06','¿Cómo administra la información de ventas e inventarios?','textarea'),
  q('E07','¿Qué dificultades encuentra al consultarla o interpretarla?','textarea'),
  q('E08','Describa una situación en que faltó información para decidir (sin datos sensibles)','textarea',required=False),
  q('E09','¿Qué herramientas ha usado y qué ventajas o limitaciones observa?','textarea'),
  q('E10','¿Qué indicadores le gustaría consultar fácilmente?','textarea'),
  q('E11','¿Qué preocupaciones tendría al adoptar una plataforma web?','textarea'),
  q('E12','¿Qué condiciones justificarían pagar por ella?','textarea',required=False),
  q('E13','¿Qué tendría que demostrar Datapyme para considerar probarlo?','textarea'),
  q('E14','Otras observaciones expresadas por el participante','textarea',required=False),
  q('E15','Síntesis del investigador (no son citas textuales)','textarea',required=False),
])]

TASK_CHOICES=['Completada sin ayuda','Completada con ayuda','Parcial','No completada','No implementada / no aplica']
TEST_SECTIONS=[
 ('Registro técnico y tareas observadas',[
  q('V02','Versión del prototipo probada','text',help='Ejemplo: v0.2 o commit de Git.'),
  q('V03','Cargo del participante',choices=['Propietario o gerente','Administrador','Responsable de ventas','Responsable de inventarios','Otro']),
  q('T01','Localizar el tablero principal',choices=TASK_CHOICES),
  q('T02','Consultar ventas de un periodo',choices=TASK_CHOICES),
  q('T03','Interpretar existencias o estado de inventario',choices=TASK_CHOICES),
  q('T04','Interpretar gráfico de ventas',choices=TASK_CHOICES),
  q('T05','Consultar tendencias o estimaciones',choices=TASK_CHOICES),
  q('T06','Errores, ayudas requeridas o incidencias observadas','textarea',required=False),
 ]),
 ('Valoración del participante',[
  q('V04','¿Qué tan fácil fue usar el prototipo?','scale'),
  q('V05','¿Qué tan clara fue la organización de pantallas?','scale'),
  q('V06','¿Qué tan comprensibles fueron indicadores y gráficos?','scale'),
  q('V07','¿Pudo encontrar la información solicitada?',choices=['Sí, sin dificultad','Sí, con dificultades','Solo parcialmente','No']),
  q('V08','¿Qué funcionalidad probada resultó más útil?',choices=['Indicadores de ventas','Información de inventario','Gráficos','Tendencias o estimaciones','Ninguna','No sabe']),
  q('V09','¿Qué tan útil considera el prototipo?','scale'),
  q('V10','¿Encontró fallas o errores?',choices=['Sí','No','No sabe']),
  q('V11','Si hubo errores, descríbalos','textarea',required=False),
  q('V12','¿Qué mejoraría primero?','textarea',required=False),
  q('V13','¿Consideraría utilizar una solución similar?',choices=['Sí','Tal vez','No']),
  q('V14','¿Qué condiciones necesitaría para considerarla?','multi',['Capacitación','Mejor funcionamiento','Integración con herramientas actuales','Seguridad y confidencialidad','Precio adecuado','Soporte técnico']),
  q('V15','Recomendaciones adicionales','textarea',required=False),
 ])]

QUESTION_SETS={'mercado':SURVEY_SECTIONS,'entrevista':INTERVIEW_SECTIONS,'prototipo':TEST_SECTIONS}
Q_MAP={typ:{q['code']:q for _,section in groups for q in section} for typ,groups in QUESTION_SETS.items()}

MILESTONES=[
 ('01','Definir criterios y muestra del estudio de mercado'),
 ('01','Pilotear y revisar el cuestionario con el director'),
 ('01','Aplicar encuestas a PyMEs comerciales elegibles'),
 ('01','Analizar respuestas y competidores'),
 ('02','Construir Business Model Canvas inicial'),
 ('02','Contrastar hipótesis y ajustar Canvas'),
 ('03','Definir requisitos y arquitectura del prototipo'),
 ('03','Desarrollar funcionalidades priorizadas'),
 ('03','Realizar pruebas técnicas y con usuarios'),
 ('04','Estimar inversiones y costos comerciales'),
 ('04','Proyectar ingresos y escenarios financieros'),
 ('04','Evaluar aspectos organizacionales y ambientales'),
 ('04','Identificar fuentes potenciales de financiación'),
 ('04','Consolidar resultados, conclusiones y F-DC-125'),
]
