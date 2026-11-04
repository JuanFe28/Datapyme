import hashlib
import secrets
import time
from collections import defaultdict
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.exc import IntegrityError
from .models import Company, CompanyContact, Response, Consent, Answer, AuditLog, utcnow, normalized
from .security import audit
from .web import render, redirect
from .tokens import generate_survey_token, verify_survey_token
from .instruments import VERSION, validate_answers
from questions import QUESTION_SETS

router = APIRouter()
_SURVEY_RATE_LIMITS = defaultdict(list)
_REG_RATE_LIMITS = defaultdict(list)

CONSENT_STATEMENT_PUBLIC = (
    "Autorizo de manera voluntaria el tratamiento de esta información con fines exclusivamente académicos "
    "para el proyecto de grado Datapyme de las Unidades Tecnológicas de Santander (UTS), conforme a la Ley 1581 de 2012. "
    "Comprendo que mis respuestas son confidenciales, se analizarán de forma anónima/agregada, no se solicitan datos sensibles "
    "y puedo retirarme o abstenerme de responder en cualquier momento."
)

PUBLIC_QUESTION_HELP = {
    'M04': 'Seleccione su cargo o rol principal dentro del negocio.',
    'M05': 'Seleccione la categoría que mejor describa los productos que vende su comercio.',
    'M06': 'Indique el número de locales, tiendas físicas o puntos de venta que opera actualmente.',
    'M07': 'Puede marcar varias opciones: ¿cómo registra o consulta habitualmente las ventas del día?',
    'M08': 'Puede marcar varias opciones: ¿cómo controla sus existencias físicas y stock de productos?',
    'M09': '¿Con qué frecuencia consulta cifras o indicadores para saber cómo va el negocio?',
    'M10': 'Seleccione hasta 3 dificultades que experimente con mayor frecuencia en su operación comercial.',
    'M11': 'Califique del 1 al 5 qué tan prioritario es mejorar la gestión de ventas e inventarios.',
    'M12': 'Seleccione hasta 3 datos o reportes que más le ayudarían a tomar mejores decisiones comerciales.',
    'M13': '¿Cuenta con algún sistema, aplicación o software que genere gráficos o reportes automáticos?',
    'M14': 'Opcional: Si utiliza alguna herramienta digital, cuéntenos brevemente qué limitaciones o molestias encuentra.',
    'M15': 'Seleccione hasta 3 factores que le harían dudar o frenarían el cambio a otra herramienta.',
    'M16': 'Califique del 1 al 5 qué tan útil le resultaría una plataforma web sencilla para centralizar ventas e inventarios.',
    'M17': 'Si tuviera que priorizar solo una función principal para su negocio, ¿cuál elegiría?',
    'M18': 'Seleccione hasta 3 condiciones indispensables para que considere implementar una herramienta como Datapyme.',
    'M19': '¿Qué modalidad de pago le resultaría más atractiva y conveniente para su negocio?',
    'M20': 'Opcional: Si considerara una suscripción, ¿cuál es el valor mensual máximo que pagaría en pesos colombianos (COP)? Escriba solo números (ej. 50000).',
    'M21': '¿Le gustaría recibir una invitación sin costo para probar la versión preliminar del software?',
    'M22': 'Opcional: Cuéntenos cualquier otra necesidad, comentario o sugerencia que considere valiosa para su sector.'
}

PUBLIC_REG_CHOICES = {
    'city': ['Bucaramanga', 'Otro / por verificar'],
    'activity': [
        'Comercio minorista',
        'Comercio mayorista',
        'Servicios',
        'Manufactura',
        'Otra / verificar'
    ],
    'size': [
        'Pequeña',
        'Mediana',
        'Microempresa'
    ],
    'size_options': [
        {'value': 'Pequeña', 'label': 'Pequeña empresa (incluye micro y pequeño comercio)'},
        {'value': 'Mediana', 'label': 'Mediana empresa'}
    ],
    'has_records': [
        'Sí, ambos',
        'Solo ventas',
        'Solo inventarios',
        'No / no sabe'
    ],
    'respondent_role': [
        'Propietario o socio',
        'Gerente o administrador',
        'Administrador',
        'Responsable de ventas',
        'Responsable de inventarios',
        'Otro'
    ]
}

def check_survey_rate_limit(request: Request, max_requests: int = 20, window_seconds: int = 60):
    client_ip = request.client.host if request.client else 'unknown'
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        client_ip = forwarded.split(',')[0].strip()
    now = time.time()
    history = [t for t in _SURVEY_RATE_LIMITS[client_ip] if now - t < window_seconds]
    if len(history) >= max_requests:
        raise HTTPException(429, 'Demasiadas solicitudes. Por favor, espere un minuto antes de reintentar.', headers={'Retry-After': str(window_seconds)})
    history.append(now)
    _SURVEY_RATE_LIMITS[client_ip] = history

def check_registration_rate_limit(request: Request, max_requests: int = 10, window_seconds: int = 60):
    client_ip = request.client.host if request.client else 'unknown'
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        client_ip = forwarded.split(',')[0].strip()
    now = time.time()
    history = [t for t in _REG_RATE_LIMITS[client_ip] if now - t < window_seconds]
    if len(history) >= max_requests:
        raise HTTPException(429, 'Demasiadas solicitudes de registro. Por favor, espere un minuto antes de reintentar.', headers={'Retry-After': str(window_seconds)})
    history.append(now)
    _REG_RATE_LIMITS[client_ip] = history

def filter_public_sections(sections):
    filtered = []
    for title, q_list in sections:
        visible_qs = [q for q in q_list if q['code'] != 'M23']
        if visible_qs:
            filtered.append((title, visible_qs))
    return filtered

def find_company_duplicate(db, name: str, barrio: str, exclude_id: int | None = None):
    norm_name = normalized(name)
    norm_barrio = normalized(barrio)
    dup_key = hashlib.sha256(f"{norm_name}|{norm_barrio}".encode('utf-8')).hexdigest()
    existing = db.query(Company).filter(Company.duplicate_key == dup_key).first()
    if existing and (exclude_id is None or existing.id != exclude_id):
        return existing
    return next((c for c in db.query(Company).all() if (exclude_id is None or c.id != exclude_id) and normalized(c.name) == norm_name and normalized(c.barrio) == norm_barrio), None)

@router.get('/registro')
def public_company_register_alias():
    return redirect('/registro-empresa')

@router.get('/registro-empresa')
def public_company_register_get(request: Request):
    check_registration_rate_limit(request)
    return render(
        request,
        'public_company_register.html',
        title='Paso 1: Registro de Empresa · Datapyme UTS',
        choices=PUBLIC_REG_CHOICES,
        consent_statement=CONSENT_STATEMENT_PUBLIC,
        values={
            'city': 'Bucaramanga',
            'activity': 'Comercio mayorista',
            'size': 'Pequeña',
            'has_records': 'Sí, ambos',
            'respondent_role': 'Propietario o socio'
        },
        errors={},
        user=None
    )

@router.post('/registro-empresa')
async def public_company_register_post(request: Request):
    check_registration_rate_limit(request)
    form = await request.form()
    
    # Trampa oculta para bots (Honeypot)
    if form.get('website_url'):
        raise HTTPException(400, 'Solicitud no permitida.')
    
    name = str(form.get('name', '')).strip()
    barrio = str(form.get('barrio', '')).strip()
    city = str(form.get('city', 'Bucaramanga')).strip()
    activity = str(form.get('activity', 'Comercio minorista')).strip()
    raw_size = str(form.get('size', 'Pequeña')).strip()
    # Mapeo al segmento objetivo del F-DC-124 (Mipymes comerciales):
    # La autocalificación como 'Microempresa' se homologa a 'Pequeña'
    size = 'Pequeña' if raw_size == 'Microempresa' else raw_size
    has_records = str(form.get('has_records', 'Sí, ambos')).strip()
    respondent_role = str(form.get('respondent_role', 'Propietario o socio')).strip()
    contact_name = str(form.get('contact_name', '')).strip()
    contact_detail = str(form.get('contact_detail', '')).strip()
    notes = str(form.get('notes', '')).strip()
    consent = form.get('consent')
    
    errors = {}
    if len(name) < 2:
        errors['name'] = 'Ingrese el nombre comercial de la empresa (mínimo 2 caracteres).'
    elif len(name) > 180:
        errors['name'] = 'El nombre comercial no puede exceder los 180 caracteres.'
        
    if not barrio or len(barrio) < 2:
        errors['barrio'] = 'Indique el barrio o sector de ubicación (mínimo 2 caracteres).'
    elif len(barrio) > 120:
        errors['barrio'] = 'El barrio no puede exceder los 120 caracteres.'
        
    if city not in PUBLIC_REG_CHOICES['city']:
        errors['city'] = 'Seleccione una ciudad válida.'
    if activity not in PUBLIC_REG_CHOICES['activity']:
        errors['activity'] = 'Seleccione una actividad económica válida.'
    if size not in PUBLIC_REG_CHOICES['size']:
        errors['size'] = 'Seleccione un tamaño de empresa válido.'
    if has_records not in PUBLIC_REG_CHOICES['has_records']:
        errors['has_records'] = 'Seleccione una opción válida para registros de ventas e inventarios.'
    if respondent_role not in PUBLIC_REG_CHOICES['respondent_role']:
        errors['respondent_role'] = 'Seleccione un cargo válido.'
        
    if not contact_detail:
        errors['contact_detail'] = 'Indique un teléfono, WhatsApp o correo de contacto.'
    elif len(contact_detail) > 250:
        errors['contact_detail'] = 'Los datos de contacto no deben exceder los 250 caracteres.'
        
    if len(contact_name) > 120:
        errors['contact_name'] = 'El nombre de contacto no debe exceder los 120 caracteres.'
    if len(notes) > 1000:
        errors['notes'] = 'Las observaciones no deben exceder los 1000 caracteres.'
        
    if consent != 'yes':
        errors['consent'] = 'Debe aceptar el consentimiento informado conforme a la Ley 1581 de 2012 para participar.'
        
    values = {
        'name': name,
        'barrio': barrio,
        'city': city,
        'activity': activity,
        'size': size,
        'has_records': has_records,
        'respondent_role': respondent_role,
        'contact_name': contact_name,
        'contact_detail': contact_detail,
        'notes': notes,
        'consent': consent
    }
    
    if errors:
        return render(
            request,
            'public_company_register.html',
            status_code=422,
            title='Paso 1: Registro de Empresa · Datapyme UTS',
            choices=PUBLIC_REG_CHOICES,
            consent_statement=CONSENT_STATEMENT_PUBLIC,
            values=values,
            errors=errors,
            user=None
        )
    
    secret = request.app.state.settings.secret
    norm_name = normalized(name)
    norm_barrio = normalized(barrio)
    dup_key = hashlib.sha256(f"{norm_name}|{norm_barrio}".encode('utf-8')).hexdigest()
    
    with request.app.state.Session() as db:
        # Detección de duplicados
        existing = find_company_duplicate(db, name, barrio)
        if existing:
            existing_response = db.query(Response).filter_by(company_id=existing.id, category='mercado', status='complete').first()
            if existing_response:
                return render(
                    request,
                    'public_company_already_done.html',
                    title='Empresa ya registrada · Datapyme',
                    company=existing,
                    response=existing_response,
                    user=None
                )
            
            token = generate_survey_token(secret, existing.id)
            base_url = str(request.base_url).rstrip('/')
            survey_url = f"{base_url}/encuesta/{token}"
            whatsapp_message = (
                f"Estimado(a) representante de {existing.name},\n\n"
                f"Le compartimos el enlace seguro para responder el Estudio de Mercado Datapyme (UTS):\n\n"
                f"{survey_url}\n\n"
                f"Toma de 3 a 5 minutos. ¡Muchas gracias por su valiosa colaboración!"
            )
            return render(
                request,
                'public_company_success.html',
                title='Empresa ya registrada · Datapyme',
                company=existing,
                token=token,
                survey_url=survey_url,
                whatsapp_message=whatsapp_message,
                is_already_registered=True,
                user=None
            )
        
        # Nueva empresa
        company = Company(
            name=name,
            duplicate_key=dup_key,
            barrio=barrio,
            city=city,
            activity=activity,
            ciiu='',
            size=size,
            source='Autoregistro web empresarial',
            verification_status='pendiente',
            operating_status='activa',
            has_records=has_records,
            respondent_role=respondent_role,
            willing='Sí',
            notes=notes,
            owner='Autoregistro web'
        )
        db.add(company)
        
        try:
            db.flush()
            if contact_name or contact_detail:
                contact = CompanyContact(
                    company_id=company.id,
                    name=contact_name,
                    detail=contact_detail
                )
                db.add(contact)
            
            audit(db, 'Autoregistro web', 'crear_publico', 'company', company.id, {'code': company.code, 'name': company.name})
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = find_company_duplicate(db, name, barrio)
            if existing:
                token = generate_survey_token(secret, existing.id)
                base_url = str(request.base_url).rstrip('/')
                survey_url = f"{base_url}/encuesta/{token}"
                whatsapp_message = (
                    f"Estimado(a) representante de {existing.name},\n\n"
                    f"Le compartimos el enlace seguro para responder el Estudio de Mercado Datapyme (UTS):\n\n"
                    f"{survey_url}\n\n"
                    f"¡Muchas gracias por su colaboración!"
                )
                return render(
                    request,
                    'public_company_success.html',
                    title='Empresa ya registrada · Datapyme',
                    company=existing,
                    token=token,
                    survey_url=survey_url,
                    whatsapp_message=whatsapp_message,
                    is_already_registered=True,
                    user=None
                )
            raise HTTPException(409, 'Error al procesar el registro de la empresa.')
        
        token = generate_survey_token(secret, company.id)
        base_url = str(request.base_url).rstrip('/')
        survey_url = f"{base_url}/encuesta/{token}"
        whatsapp_message = (
            f"Estimado(a) representante de {company.name},\n\n"
            f"Un cordial saludo del equipo de investigación de las Unidades Tecnológicas de Santander (UTS) para el proyecto Datapyme.\n\n"
            f"Le compartimos su enlace seguro para responder la breve encuesta académica de ventas e inventarios (toma de 3 a 5 minutos):\n\n"
            f"{survey_url}\n\n"
            f"¡Agradecemos mucho su valiosa colaboración!"
        )
        return render(
            request,
            'public_company_success.html',
            title='¡Bienvenido al Proyecto Datapyme! · Paso 1 completado',
            company=company,
            token=token,
            survey_url=survey_url,
            whatsapp_message=whatsapp_message,
            is_already_registered=False,
            user=None
        )

@router.get('/encuesta/{token}')
def public_survey_get(request: Request, token: str):
    check_survey_rate_limit(request)
    secret = request.app.state.settings.secret
    company_id = verify_survey_token(secret, token)
    if not company_id:
        return render(request, 'public_survey_invalid.html', status_code=400, title='Enlace no válido o expirado', user=None)
    
    with request.app.state.Session() as db:
        company = db.get(Company, company_id)
        if not company:
            return render(request, 'public_survey_invalid.html', status_code=404, title='Empresa no encontrada', user=None)
        
        existing = db.query(Response).filter_by(company_id=company_id, category='mercado', status='complete').first()
        if existing:
            return render(request, 'public_survey_done.html', title='Encuesta ya respondida', company=company, response=existing, user=None)
        
        sections = filter_public_sections(QUESTION_SETS['mercado'])
        return render(
            request,
            'public_survey.html',
            title=f'Paso 2: Encuesta de Mercado · {company.name}',
            company=company,
            token=token,
            sections=sections,
            consent_statement=CONSENT_STATEMENT_PUBLIC,
            q_help=PUBLIC_QUESTION_HELP,
            values={'consent': 'yes', 'M04': company.respondent_role or ''},
            errors={},
            user=None
        )

@router.post('/encuesta/{token}')
async def public_survey_post(request: Request, token: str):
    check_survey_rate_limit(request)
    form = await request.form()
    
    # Trampa oculta para bots (Honeypot)
    if form.get('website_url'):
        raise HTTPException(400, 'Solicitud no permitida.')
    
    secret = request.app.state.settings.secret
    company_id = verify_survey_token(secret, token)
    if not company_id:
        return render(request, 'public_survey_invalid.html', status_code=400, title='Enlace no válido o expirado', user=None)
    
    with request.app.state.Session() as db:
        company = db.get(Company, company_id)
        if not company:
            return render(request, 'public_survey_invalid.html', status_code=404, title='Empresa no encontrada', user=None)
        
        existing = db.query(Response).filter_by(company_id=company_id, category='mercado', status='complete').first()
        if existing:
            return render(request, 'public_survey_done.html', title='Encuesta ya respondida', company=company, response=existing, user=None)
        
        sections = filter_public_sections(QUESTION_SETS['mercado'])
        
        payload, errors = validate_answers('mercado', form, complete=True)
        # M23 es completada automáticamente para encuestas públicas autogestionadas
        if 'M23' in errors:
            del errors['M23']
        payload['M23'] = 'Respondida directamente por la empresa'
        
        if form.get('consent') != 'yes':
            errors['consent'] = 'Debe aceptar el consentimiento informado conforme a la Ley 1581 de 2012 para participar.'
        
        if errors:
            values = dict(form)
            for k in form.keys():
                v_list = form.getlist(k)
                if len(v_list) > 1:
                    values[k] = v_list
            return render(
                request,
                'public_survey.html',
                status_code=422,
                title=f'Paso 2: Encuesta de Mercado · {company.name}',
                company=company,
                token=token,
                sections=sections,
                consent_statement=CONSENT_STATEMENT_PUBLIC,
                q_help=PUBLIC_QUESTION_HELP,
                values=values,
                errors=errors,
                user=None
            )
        
        payload['M23'] = 'Respondida directamente por la empresa'
        participant_code = 'P-' + secrets.token_hex(5).upper()
        
        consent = Consent(
            company_id=company.id,
            participant_code=participant_code,
            instrument='mercado',
            version=VERSION,
            statement=CONSENT_STATEMENT_PUBLIC,
            recorded_by=f'Empresario ({company.name})'
        )
        db.add(consent)
        db.flush()
        
        record = Response(
            company_id=company.id,
            category='mercado',
            author=f'Empresario ({company.name})',
            data=payload,
            participant_code=participant_code,
            status='complete',
            updated_at=utcnow(),
            instrument_version=VERSION,
            consent_id=consent.id,
            survey_key=f'mercado:{company.id}'
        )
        db.add(record)
        
        try:
            db.flush()
            record.answers = [Answer(question_code=k, value=v) for k, v in payload.items() if v is not None]
            
            if payload.get('M04') and not company.respondent_role:
                company.respondent_role = payload['M04']
            
            # Homologación y verificación automática para empresas autogestionadas del sector objetivo:
            if company.source == 'Autoregistro web empresarial':
                if company.size == 'Microempresa':
                    company.size = 'Pequeña'
                if normalized(company.city) == 'bucaramanga' and company.activity in ('Comercio minorista', 'Comercio mayorista') and company.has_records == 'Sí, ambos':
                    company.verification_status = 'verificada'
            
            audit(db, f'Empresario ({company.name})', 'finalizar_web', 'response', record.id, {'token': 'individual', 'empresa': company.name})
            db.commit()
        except IntegrityError:
            db.rollback()
            return render(request, 'public_survey_done.html', title='Encuesta ya respondida', company=company, user=None)
        
        return render(
            request,
            'public_survey_success.html',
            title='¡Muchas gracias!',
            company=company,
            participant_code=participant_code,
            user=None
        )
