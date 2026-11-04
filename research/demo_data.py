"""Módulo para sembrar y limpiar datos de demostración simulados para el informe F-DC-125."""
import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .models import (
    Company, CompanyContact, Consent, Response, Answer,
    CanvasVersion, FinancialScenario, ResearchNote, AuditLog, normalized, utcnow
)
from .instruments import VERSION, CONSENT_STATEMENT

DEMO_MARKER = " [DEMO-FDC125]"

DEMO_COMPANIES = [
    {
        "name": "Calzados y Cueros San Francisco",
        "barrio": "San Francisco",
        "city": "Bucaramanga",
        "activity": "Comercio minorista",
        "ciiu": "4772",
        "size": "Pequeña",
        "source": "Cámara de Comercio de Bucaramanga",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Gerente o administrador",
        "willing": "Sí",
        "contact_name": "Carlos Mauricio Gómez",
        "contact_detail": "3154829102 · admon@cuerossanfrancisco.com",
        "survey": {
            "M04": "Gerente o administrador",
            "M05": "Ropa, calzado y accesorios",
            "M06": "2 a 3",
            "M07": ["Hojas de cálculo", "Facturación / punto de venta"],
            "M08": ["Hojas de cálculo"],
            "M09": "Semanalmente",
            "M10": ["Diferencias en inventario", "Demora preparando informes", "Datos dispersos"],
            "M11": 5,
            "M12": ["Productos más y menos vendidos", "Rotación de productos", "Tendencias o estimaciones"],
            "M13": "Sí",
            "M14": "Usamos Excel; es tedioso conciliar ventas con existencias los fines de mes.",
            "M15": ["Precio", "Tiempo de implementación", "Falta de soporte / capacitación"],
            "M16": 5,
            "M17": "Rotación de productos",
            "M18": ["Precio accesible", "Facilidad de uso", "Demostración / prueba"],
            "M19": "Suscripción mensual",
            "M20": 110000,
            "M21": "Sí",
            "M22": "Requerimos que la curva de aprendizaje sea rápida para los empleados.",
            "M23": "Entrevistador presencial"
        }
    },
    {
        "name": "Distribuidora Mayorista del Oriente",
        "barrio": "Centro",
        "city": "Bucaramanga",
        "activity": "Comercio mayorista",
        "ciiu": "4690",
        "size": "Mediana",
        "source": "Directorio empresarial Fenalco Santander",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Propietario o socio",
        "willing": "Sí",
        "contact_name": "Héctor Fabio Duarte",
        "contact_detail": "3209142388 · hduarte@distorientebuc.com",
        "survey": {
            "M04": "Propietario o socio",
            "M05": "Comercio mayorista no especializado",
            "M06": "4 o más",
            "M07": ["Software administrativo / ERP", "Facturación / punto de venta"],
            "M08": ["Software de inventarios"],
            "M09": "Diariamente",
            "M10": ["No identifica fácilmente la rotación", "Herramientas costosas o complejas"],
            "M11": 5,
            "M12": ["Tablero resumen de indicadores", "Comparación entre periodos", "Tendencias o estimaciones"],
            "M13": "Sí",
            "M14": "El ERP actual es muy rígido y no genera visualizaciones gerenciales claras.",
            "M15": ["Precio", "Integración de datos"],
            "M16": 4,
            "M17": "Gráficos y tablero",
            "M18": ["Importación de datos", "Protección de información", "Facilidad de uso"],
            "M19": "Suscripción mensual",
            "M20": 150000,
            "M21": "Sí",
            "M22": "Nos interesa mucho poder proyectar compras trimestrales.",
            "M23": "Entrevistador presencial"
        }
    },
    {
        "name": "Boutique Elegance Provenza",
        "barrio": "Provenza",
        "city": "Bucaramanga",
        "activity": "Comercio minorista",
        "ciiu": "4771",
        "size": "Pequeña",
        "source": "Censo comercial Provenza",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Responsable de ventas",
        "willing": "Sí",
        "contact_name": "Marcela Rueda",
        "contact_detail": "3187219904 · marcela.rueda@boutiqueelegance.co",
        "survey": {
            "M04": "Responsable de ventas",
            "M05": "Ropa, calzado y accesorios",
            "M06": "1",
            "M07": ["Hojas de cálculo", "Comercio electrónico"],
            "M08": ["Hojas de cálculo"],
            "M09": "Semanalmente",
            "M10": ["Información desactualizada", "Diferencias en inventario"],
            "M11": 4,
            "M12": ["Productos más y menos vendidos", "Existencias y alertas"],
            "M13": "No",
            "M14": "",
            "M15": ["Falta de conocimientos tecnológicos", "Precio"],
            "M16": 4,
            "M17": "Consulta de ventas e indicadores",
            "M18": ["Facilidad de uso", "Capacitación", "Precio accesible"],
            "M19": "Suscripción mensual",
            "M20": 85000,
            "M21": "Sí",
            "M22": "Necesitamos interfaz limpia que funcione desde tablet o celular.",
            "M23": "Respondida directamente por la empresa"
        }
    },
    {
        "name": "Ferretería y Eléctricos Cabecera",
        "barrio": "Cabecera del Llano",
        "city": "Bucaramanga",
        "activity": "Comercio minorista",
        "ciiu": "4752",
        "size": "Pequeña",
        "source": "Registro Mercantil CCB",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Responsable de inventarios",
        "willing": "Sí",
        "contact_name": "Javier Mantilla",
        "contact_detail": "3114523881 · javier@ferrecabecera.com",
        "survey": {
            "M04": "Responsable de inventarios",
            "M05": "Ferretería y hogar",
            "M06": "1",
            "M07": ["Facturación / punto de venta", "Registros manuales"],
            "M08": ["Software de inventarios"],
            "M09": "Mensualmente",
            "M10": ["No identifica fácilmente la rotación", "Datos dispersos"],
            "M11": 5,
            "M12": ["Rotación de productos", "Existencias y alertas", "Tendencias o estimaciones"],
            "M13": "No",
            "M14": "",
            "M15": ["Tiempo de implementación", "Falta de conocimientos tecnológicos"],
            "M16": 5,
            "M17": "Inventarios y existencias",
            "M18": ["Facilidad de uso", "Demostración / prueba", "Soporte técnico"],
            "M19": "Suscripción mensual",
            "M20": 95000,
            "M21": "Sí",
            "M22": "Manejamos más de 1200 referencias, el control de stock es vital.",
            "M23": "Entrevistador presencial"
        }
    },
    {
        "name": "Supermercado Mercamás Real de Minas",
        "barrio": "Real de Minas",
        "city": "Bucaramanga",
        "activity": "Comercio minorista",
        "ciiu": "4711",
        "size": "Mediana",
        "source": "Directorio Fenalco",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Gerente o administrador",
        "willing": "Sí",
        "contact_name": "Esperanza Villamizar",
        "contact_detail": "3165218765 · evillamizar@mercamasrdm.com",
        "survey": {
            "M04": "Gerente o administrador",
            "M05": "Alimentos y bebidas",
            "M06": "2 a 3",
            "M07": ["Software administrativo / ERP"],
            "M08": ["Software administrativo integrado"],
            "M09": "Diariamente",
            "M10": ["Demora preparando informes", "Dificultad para analizar ventas"],
            "M11": 5,
            "M12": ["Ventas por periodo", "Comparación entre periodos", "Tablero resumen de indicadores"],
            "M13": "Sí",
            "M14": "El software POS saca reportes planos en texto que toca pasar a mano a Excel.",
            "M15": ["Integración de datos", "Tiempo de implementación"],
            "M16": 5,
            "M17": "Consulta de ventas e indicadores",
            "M18": ["Importación de datos", "Precio accesible", "Soporte técnico"],
            "M19": "Suscripción mensual",
            "M20": 130000,
            "M21": "Sí",
            "M22": "Requerimos visualización ágil de productos de alta rotación.",
            "M23": "Entrevistador presencial"
        }
    },
    {
        "name": "Cosméticos y Belleza Chic Centro",
        "barrio": "Centro",
        "city": "Bucaramanga",
        "activity": "Comercio minorista",
        "ciiu": "4773",
        "size": "Pequeña",
        "source": "Registro Mercantil CCB",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Propietario o socio",
        "willing": "Sí",
        "contact_name": "Claudia Patricia Jaimes",
        "contact_detail": "3103429811 · chicbellezacentro@gmail.com",
        "survey": {
            "M04": "Propietario o socio",
            "M05": "Belleza y cuidado personal",
            "M06": "1",
            "M07": ["Registros manuales", "Hojas de cálculo"],
            "M08": ["Registros manuales"],
            "M09": "Cuando surge una necesidad",
            "M10": ["Datos dispersos", "Información desactualizada", "Diferencias en inventario"],
            "M11": 4,
            "M12": ["Productos más y menos vendidos", "Existencias y alertas"],
            "M13": "No",
            "M14": "",
            "M15": ["Precio", "Falta de conocimientos tecnológicos", "Falta de soporte / capacitación"],
            "M16": 4,
            "M17": "Inventarios y existencias",
            "M18": ["Precio accesible", "Capacitación", "Facilidad de uso"],
            "M19": "Suscripción mensual",
            "M20": 75000,
            "M21": "Sí",
            "M22": "Un sistema sencillo que avise cuándo se agota el stock.",
            "M23": "Respondida directamente por la empresa"
        }
    },
    {
        "name": "Tecnología y Electrónica del Santander",
        "barrio": "García Rovira",
        "city": "Bucaramanga",
        "activity": "Comercio minorista",
        "ciiu": "4741",
        "size": "Pequeña",
        "source": "Censo comercial UIS/UTS",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Administrador",
        "willing": "Sí",
        "contact_name": "Andrés Felipe Serrano",
        "contact_detail": "3178904561 · aserrano@tecnosantander.com.co",
        "survey": {
            "M04": "Gerente o administrador",
            "M05": "Tecnología y electrónicos",
            "M06": "1",
            "M07": ["Facturación / punto de venta", "Comercio electrónico"],
            "M08": ["Software de inventarios"],
            "M09": "Semanalmente",
            "M10": ["No identifica fácilmente la rotación", "Dificultad para analizar ventas"],
            "M11": 5,
            "M12": ["Ventas por periodo", "Tendencias o estimaciones", "Tablero resumen de indicadores"],
            "M13": "Sí",
            "M14": "Usamos Google Sheets conectado por scripts pero se desconfigura a menudo.",
            "M15": ["Precio", "Integración de datos"],
            "M16": 5,
            "M17": "Tendencias o estimaciones",
            "M18": ["Facilidad de uso", "Precio accesible", "Protección de información"],
            "M19": "Suscripción mensual",
            "M20": 120000,
            "M21": "Sí",
            "M22": "Visualizar tendencias con regresión lineal nos permitiría planificar pedidos a importadores.",
            "M23": "Entrevistador presencial"
        }
    },
    {
        "name": "Dotaciones Industriales Comuneros",
        "barrio": "Comuneros",
        "city": "Bucaramanga",
        "activity": "Comercio mayorista",
        "ciiu": "4669",
        "size": "Mediana",
        "source": "Cámara de Comercio de Bucaramanga",
        "verification_status": "verificada",
        "operating_status": "activa",
        "has_records": "Sí, ambos",
        "respondent_role": "Gerente o administrador",
        "willing": "Sí",
        "contact_name": "Liliana Pinzón",
        "contact_detail": "3146781290 · gerencia@dotacionescomuneros.com",
        "survey": {
            "M04": "Gerente o administrador",
            "M05": "Comercio mayorista no especializado",
            "M06": "1",
            "M07": ["Software administrativo / ERP"],
            "M08": ["Software administrativo integrado"],
            "M09": "Semanalmente",
            "M10": ["Demora preparando informes", "Herramientas costosas o complejas"],
            "M11": 4,
            "M12": ["Comparación entre periodos", "Rotación de productos", "Tablero resumen de indicadores"],
            "M13": "No",
            "M14": "",
            "M15": ["Precio", "Tiempo de implementación"],
            "M16": 4,
            "M17": "Gráficos y tablero",
            "M18": ["Demostración / prueba", "Importación de datos", "Precio accesible"],
            "M19": "Suscripción mensual",
            "M20": 100000,
            "M21": "Tal vez",
            "M22": "Nos gustaría ver un piloto antes de contratar.",
            "M23": "Entrevista remota"
        }
    }
]

DEMO_CANVAS_VERSIONS = [
    {
        "title": "Versión 1 · Canvas Inicial (Hipótesis F-DC-124)",
        "hypothesis_status": "pendiente",
        "conclusion": "Hipótesis iniciales formuladas en la propuesta de grado aprobada F-DC-124.",
        "blocks": {
            "segments": "Pequeñas y medianas empresas (PyMEs) comerciales de Bucaramanga (alimentos, calzado, confección, ferretería) que registran ventas e inventarios en hojas de cálculo o sistemas contables básicos.",
            "value": "Plataforma web SaaS de analítica empresarial accesible, que integra información de ventas e inventarios para generar dashboards visuales automáticos y estimaciones estadísticas preliminares de tendencias sin complejidad técnica.",
            "channels": "Canal digital directo (web), demostraciones presenciales en zonas comerciales de Bucaramanga (Centro, Cabecera, San Francisco), convenios gremiales (Fenalco Santander) y redes profesionales.",
            "relationships": "Asistencia técnica personalizada en onboarding, autoservicio intuitivo en la plataforma, soporte técnico local por WhatsApp y canales digitales.",
            "revenue": "Suscripción recurrente mensual (SaaS) estimada en $90.000 a $120.000 COP por empresa, con prueba gratuita de 14 días y planes anuales con descuento.",
            "resources": "Equipo de desarrollo de software, infraestructura en la nube (servidores de aplicación y base de datos), algoritmos estadísticos básicos y metodologías ágiles Scrum.",
            "activities": "Desarrollo iterativo de software (FastAPI/SQLAlchemy), mantenimiento de servidores, seguridad y soporte al cliente, marketing B2B local y capacitación a PyMEs.",
            "partners": "Gremios comerciales locales (Fenalco Santander, Cámara de Comercio de Bucaramanga), proveedores de servicios en la nube (Render, Supabase/PostgreSQL) e instituciones académicas (UTS).",
            "costs": "Costos de servidores y bases de datos en la nube, licencias de software, soporte técnico, conectividad, comercialización y costos administrativos y contables."
        }
    },
    {
        "title": "Versión 2 · Canvas Validado (Resultados F-DC-125)",
        "hypothesis_status": "validada",
        "conclusion": "Hipótesis validadas y ajustadas tras el estudio de mercado con 8 PyMEs de Bucaramanga y pruebas de usabilidad del prototipo. Se confirma disposición de pago promedio de $108.125 COP/mes y alta prioridad en rotación de inventarios y dashboards visuales sencillos.",
        "blocks": {
            "segments": "PyMEs comerciales activas de Bucaramanga con 1 a 3 puntos de venta que manejan inventario multirreferencia y requieren optimizar su rotación de stock y flujo de caja.",
            "value": "Solución analítica visual que transforma registros de ventas e inventarios en decisiones claras: identificación inmediata de productos de baja rotación, alertas de stock mínimo y proyección estadística de ventas.",
            "channels": "Demostraciones comerciales interactivas en sitio, canal web con registro guiado y referidos de comerciantes verificados en Bucaramanga.",
            "relationships": "Acompañamiento en la primera carga de datos (plantilla Excel), soporte ágil vía WhatsApp Business y diseño enfocado en usabilidad con cero fricción.",
            "revenue": "Planes de suscripción mensual de $95.000 COP (plan estándar) y $130.000 COP (plan multisede con proyecciones avanzadas), validados frente a la disposición de pago real.",
            "resources": "Arquitectura modular ligera (FastAPI/Chart.js), base de datos relacional, repositorio privado de datos y protocolos de seguridad acordes a la Ley 1581 de 2012.",
            "activities": "Optimización continua de usabilidad, soporte al cliente, validación periódica con usuarios y marketing directo en corredores comerciales de Bucaramanga.",
            "partners": "Fenalco Santander, asociaciones de comerciantes locales y asesores contables independientes de PyMEs.",
            "costs": "Infraestructura SaaS elástica de bajo costo, costos de pasarela de pagos local, marketing digital geolocalizado en Bucaramanga y atención técnica."
        }
    }
]

DEMO_FINANCIAL_SCENARIOS = [
    {
        "name": "Escenario Base · Fondo Emprender / Conservador",
        "inputs": {
            "initial_investment": "24500000",
            "monthly_fixed": "3200000",
            "unit_price": "100000",
            "unit_variable": "8000",
            "initial_customers": "6",
            "monthly_growth": "8",
            "months": "24"
        },
        "source": "Cotizaciones de hosting en la nube (Render/PostgreSQL), servicios de dominio, conectividad y presupuesto de referencia SENA Fondo Emprender 2026.",
        "assumptions": "Precio mensual de $100.000 COP coherente con la disposición de pago promedio obtenida en las encuestas de mercado ($108.125 COP). Margen de contribución unitario de $92.000 COP por cliente/mes. Punto de equilibrio estimado en 35 clientes activos."
    },
    {
        "name": "Escenario Optimista · Expansión Comercial Santander",
        "inputs": {
            "initial_investment": "28000000",
            "monthly_fixed": "4100000",
            "unit_price": "115000",
            "unit_variable": "7500",
            "initial_customers": "10",
            "monthly_growth": "12",
            "months": "36"
        },
        "source": "Proyección de escalamiento comercial en el área metropolitana de Bucaramanga (Floridablanca y Girón) con alianzas gremiales.",
        "assumptions": "Precio promedio ponderado de $115.000 COP considerando ventas de planes estándar y planes avanzados. Crecimiento mensual del 12% impulsado por referidos y alianzas con distribuidores."
    }
]

DEMO_NOTES = [
    {
        "kind": "competencia",
        "title": "Análisis comparativo de soluciones analíticas para PyMEs",
        "source": "Estudio de mercado y benchmarking de software administrativo en Colombia (Siigo, Alegra, Loggro, Excel)",
        "content": "Las PyMEs de Bucaramanga emplean principalmente hojas de cálculo (Excel) y módulos de facturación tradicionales. Software como Siigo o Alegra se enfocan en cumplimiento contable y tributario (facturación electrónica, nómina), pero presentan tableros de analítica avanzados solo en planes de alto costo, con visualizaciones poco intuitivas para el comerciante no financiero. Datapyme se posiciona como una capa analítica complementaria, visual, ágil y de costo accesible."
    },
    {
        "kind": "organizacion",
        "title": "Estructura administrativa y roles operativos del emprendimiento",
        "source": "Formato F-DC-125 Capítulo 4.3 (Evaluación Administrativa y Organizacional) y metodología Lean Startup",
        "content": "Estructura organizacional inicial para fase de puesta en marcha:\n- Dirección General y Comercial: Lidera alianzas gremiales, ventas B2B y validación de clientes.\n- Dirección Técnica y de Operaciones: Mantenimiento de software, arquitectura de datos, soporte técnico e infraestructura en la nube.\n- Asesoría Externa Contable y Legal: Soporte en cumplimiento tributario y protección de datos (Ley 1581 de 2012)."
    },
    {
        "kind": "ambiental",
        "title": "Evaluación de impacto ambiental y digitalización ecológica",
        "source": "Decreto 1076 de 2015 (Sector Ambiente) y política de compras verdes sostenibles MinAmbiente",
        "content": "Datapyme genera un impacto ambiental positivo directo al promover la transición digital y reducir el consumo de papel (facturación, reportes manuales, carpetas físicas de inventario). Al alojarse en centros de datos en la nube con compromisos de energía 100% renovable (PUE < 1.2), la huella de carbono por transacción es marginal comparada con servidores locales tradicionales. No genera residuos peligrosos ni vertimientos."
    },
    {
        "kind": "financiacion",
        "title": "Convocatorias y fuentes de financiación potenciales",
        "source": "Términos de referencia Fondo Emprender SENA 2026, convocatorias MinCiencias y programas de la Cámara de Comercio de Bucaramanga",
        "content": "Fuentes identificadas para capital semilla:\n1. Fondo Emprender del SENA: Financiación no reembolsable de hasta 80-100 SMMLV para proyectos tecnológicos y de servicios innovadores.\n2. Convocatorias de Innovación Abierta CCB (Cámara de Comercio de Bucaramanga) y programas ALDEA de iNNpulsa Colombia.\n3. Recursos propios de los fundadores valorados en aportes en especie de hardware y horas de investigación técnica ($9.559.000 COP según presupuesto F-DC-124)."
    }
]


def seed_demo_data(db: Session, author: str = "admin") -> dict:
    """Inserta datos de demostración coherentes con F-DC-124 para inspección y redacción del F-DC-125."""
    stats = {"companies": 0, "surveys": 0, "canvas": 0, "finance": 0, "notes": 0}

    # 1. Empresas y encuestas
    for item in DEMO_COMPANIES:
        name = item["name"] + DEMO_MARKER
        barrio = item["barrio"]
        dup_key = hashlib.sha256((normalized(name) + "|" + normalized(barrio)).encode()).hexdigest()

        company = db.query(Company).filter_by(duplicate_key=dup_key).first()
        if not company:
            company = Company(
                name=name,
                duplicate_key=dup_key,
                barrio=barrio,
                city=item["city"],
                activity=item["activity"],
                ciiu=item["ciiu"],
                size=item["size"],
                source=item["source"],
                verification_status=item["verification_status"],
                operating_status=item["operating_status"],
                has_records=item["has_records"],
                respondent_role=item["respondent_role"],
                willing=item["willing"],
                notes="Empresa de prueba sintética para demostración institucional del informe final F-DC-125.",
                owner=author
            )
            db.add(company)
            db.flush()
            stats["companies"] += 1

            # Contacto
            contact = CompanyContact(
                company_id=company.id,
                name=item["contact_name"],
                detail=item["contact_detail"]
            )
            db.add(contact)

        # Consentimiento
        part_code = f"PART-{company.id:04d}"
        consent = db.query(Consent).filter_by(company_id=company.id, instrument="mercado").first()
        if not consent:
            consent = Consent(
                company_id=company.id,
                participant_code=part_code,
                instrument="mercado",
                version=VERSION,
                statement=CONSENT_STATEMENT,
                recorded_by=author
            )
            db.add(consent)
            db.flush()

        # Respuesta de encuesta
        survey_key = f"mercado:{company.id}"
        resp = db.query(Response).filter_by(survey_key=survey_key).first()
        if not resp:
            survey_data = item["survey"]
            resp = Response(
                company_id=company.id,
                category="mercado",
                data=survey_data,
                author=author,
                status="complete",
                participant_code=part_code,
                consent_id=consent.id,
                survey_key=survey_key,
                instrument_version=VERSION,
                prototype_reference="Prototipo Datapyme MVP v0.9 (Validación F-DC-125)"
            )
            db.add(resp)
            db.flush()
            stats["surveys"] += 1

            for q_code, q_val in survey_data.items():
                db.add(Answer(response_id=resp.id, question_code=q_code, value=q_val))

    # 2. Canvas Versions
    for cv in DEMO_CANVAS_VERSIONS:
        existing = db.query(CanvasVersion).filter_by(title=cv["title"]).first()
        if not existing:
            db.add(CanvasVersion(
                title=cv["title"],
                blocks=cv["blocks"],
                hypothesis_status=cv["hypothesis_status"],
                conclusion=cv["conclusion"],
                author=author
            ))
            stats["canvas"] += 1

    # 3. Escenarios Financieros
    for fs in DEMO_FINANCIAL_SCENARIOS:
        existing = db.query(FinancialScenario).filter_by(name=fs["name"]).first()
        if not existing:
            db.add(FinancialScenario(
                name=fs["name"],
                inputs=fs["inputs"],
                source=fs["source"],
                assumptions=fs["assumptions"],
                author=author
            ))
            stats["finance"] += 1

    # 4. Notas de investigación
    for rn in DEMO_NOTES:
        existing = db.query(ResearchNote).filter_by(title=rn["title"]).first()
        if not existing:
            db.add(ResearchNote(
                kind=rn["kind"],
                title=rn["title"],
                content=rn["content"],
                source=rn["source"],
                author=author
            ))
            stats["notes"] += 1

    db.add(AuditLog(
        actor=author,
        action="seed_demo",
        entity_type="demo",
        changes={"stats": stats, "timestamp": utcnow().isoformat()}
    ))
    db.commit()
    return stats


def clear_demo_data(db: Session, author: str = "admin") -> dict:
    """Elimina únicamente los datos de demostración creados o limpia las tablas conservando usuarios y tareas."""
    # Eliminar respuestas y respuestas asociadas a empresas demo
    demo_companies = db.query(Company).filter(Company.name.like(f"%{DEMO_MARKER}%")).all()
    demo_comp_ids = [c.id for c in demo_companies]

    deleted_counts = {
        "answers": 0,
        "responses": 0,
        "consents": 0,
        "contacts": 0,
        "companies": 0,
        "canvas": 0,
        "finance": 0,
        "notes": 0
    }

    if demo_comp_ids:
        responses = db.query(Response).filter(Response.company_id.in_(demo_comp_ids)).all()
        resp_ids = [r.id for r in responses]
        if resp_ids:
            deleted_counts["answers"] = db.query(Answer).filter(Answer.response_id.in_(resp_ids)).delete(synchronize_session=False)
            deleted_counts["responses"] = db.query(Response).filter(Response.id.in_(resp_ids)).delete(synchronize_session=False)

        deleted_counts["consents"] = db.query(Consent).filter(Consent.company_id.in_(demo_comp_ids)).delete(synchronize_session=False)
        deleted_counts["contacts"] = db.query(CompanyContact).filter(CompanyContact.company_id.in_(demo_comp_ids)).delete(synchronize_session=False)
        deleted_counts["companies"] = db.query(Company).filter(Company.id.in_(demo_comp_ids)).delete(synchronize_session=False)

    # Eliminar canvas demo
    deleted_counts["canvas"] = db.query(CanvasVersion).filter(CanvasVersion.title.like("%F-DC-12%")).delete(synchronize_session=False)
    # Eliminar finanzas demo
    deleted_counts["finance"] = db.query(FinancialScenario).filter(FinancialScenario.name.like("%Escenario%")).delete(synchronize_session=False)
    # Eliminar notas demo
    deleted_counts["notes"] = db.query(ResearchNote).filter(ResearchNote.title.in_([n["title"] for n in DEMO_NOTES])).delete(synchronize_session=False)

    db.add(AuditLog(
        actor=author,
        action="clear_demo",
        entity_type="demo",
        changes={"deleted": deleted_counts, "timestamp": utcnow().isoformat()}
    ))
    db.commit()
    return deleted_counts


def clear_all_research_data(db: Session, author: str = "admin") -> dict:
    """Limpia completamente todas las empresas, encuestas, notas y finanzas para iniciar el trabajo de campo en limpio."""
    deleted_counts = {
        "answers": db.query(Answer).delete(synchronize_session=False),
        "responses": db.query(Response).delete(synchronize_session=False),
        "consents": db.query(Consent).delete(synchronize_session=False),
        "contacts": db.query(CompanyContact).delete(synchronize_session=False),
        "companies": db.query(Company).delete(synchronize_session=False),
        "canvas": db.query(CanvasVersion).delete(synchronize_session=False),
        "finance": db.query(FinancialScenario).delete(synchronize_session=False),
        "notes": db.query(ResearchNote).delete(synchronize_session=False)
    }
    db.add(AuditLog(
        actor=author,
        action="clear_all_research",
        entity_type="research",
        changes={"deleted": deleted_counts, "timestamp": utcnow().isoformat()}
    ))
    db.commit()
    return deleted_counts
