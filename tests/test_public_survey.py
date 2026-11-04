import pytest
from conftest import add_company, csrf
from research.tokens import generate_survey_token, verify_survey_token
from questions import Q_MAP

def test_survey_token_lifecycle():
    secret = 'test-secret-012345678901234567890123456789'
    token = generate_survey_token(secret, 42)
    assert verify_survey_token(secret, token) == 42
    
    # Manipulación rechazada
    assert verify_survey_token(secret, token + 'tampered') is None
    
    # Secreto incorrecto rechazado
    assert verify_survey_token('wrong-secret-000000000000000000000000', token) is None
    
    # Expiración
    assert verify_survey_token(secret, token, max_age=-1) is None

def test_company_edit_page_contains_survey_link(admin_client):
    add_company(admin_client, name='Tienda Los Andes')
    page = admin_client.get('/empresas/1/editar')
    assert page.status_code == 200
    assert '/encuesta/' in page.text
    assert 'Enviar por WhatsApp' in page.text
    assert 'Tienda Los Andes' in page.text

def test_public_survey_anonymous_access(client, admin_client):
    add_company(admin_client, name='Calzado Bucaramanga')
    secret = client.app.state.settings.secret
    token = generate_survey_token(secret, 1)
    
    # Simular empresario externo (sin cookies de sesión interna)
    client.cookies.clear()
    response = client.get(f'/encuesta/{token}')
    assert response.status_code == 200
    assert 'Calzado Bucaramanga' in response.text
    assert 'Consentimiento Informado' in response.text
    assert 'Ley 1581 de 2012' in response.text
    # No debe filtrar elementos privados del panel
    assert 'sidebar' not in response.text
    assert 'Cerrar sesión' not in response.text
    # No debe mostrar instrumentos internos
    assert 'Entrevista semiestructurada' not in response.text
    assert 'Validación de prototipo' not in response.text

def test_public_survey_invalid_token(client):
    client.cookies.clear()
    response = client.get('/encuesta/token-invalido-o-falso')
    assert response.status_code == 400
    assert 'Enlace no válido o expirado' in response.text

def test_public_survey_submission_and_uniqueness(client, admin_client):
    add_company(admin_client, name='Ferretería Santander')
    secret = client.app.state.settings.secret
    token = generate_survey_token(secret, 1)
    client.cookies.clear()
    
    # Preparar respuestas válidas de mercado
    form_data = {
        'consent': 'yes',
        'website_url': '',  # Honeypot vacío
        'M04': 'Propietario o socio',
        'M05': 'Ferretería y hogar',
        'M06': '1',
        'M07': ['Facturación / punto de venta'],
        'M08': ['Software de inventarios'],
        'M09': 'Diariamente',
        'M10': ['Datos dispersos'],
        'M11': '5',
        'M12': ['Existencias y alertas'],
        'M13': 'Sí',
        'M14': 'Limitaciones de integración',
        'M15': ['Precio'],
        'M16': '4',
        'M17': 'Inventarios y existencias',
        'M18': ['Precio accesible'],
        'M19': 'Suscripción mensual',
        'M20': '80000',
        'M21': 'Sí',
        'M22': 'Interesado en demostración',
        'M23': 'Respondida directamente por la empresa'
    }
    
    # 1. Envío válido
    submit_res = client.post(f'/encuesta/{token}', data=form_data)
    assert submit_res.status_code == 200
    assert '¡Muchas gracias por su valiosa colaboración!' in submit_res.text
    assert 'P-' in submit_res.text
    
    # 2. Verificar que la respuesta se guardó en la base de datos
    from research.models import Response, Consent
    with client.app.state.Session() as db:
        saved = db.query(Response).filter_by(company_id=1, category='mercado').one()
        assert saved.status == 'complete'
        assert saved.author == 'Empresario (Ferretería Santander)'
        assert saved.data['M23'] == 'Respondida directamente por la empresa'
        assert saved.data['M20'] == 80000
        consent = db.query(Consent).filter_by(company_id=1).one()
        assert consent.recorded_by == 'Empresario (Ferretería Santander)'
        assert 'Ley 1581 de 2012' in consent.statement
    
    # 3. Intentar responder de nuevo con el mismo token -> Ya completada
    again_res = client.get(f'/encuesta/{token}')
    assert again_res.status_code == 200
    assert 'Esta encuesta ya fue completada' in again_res.text
    
    # 4. Intentar enviar POST de nuevo -> Ya completada
    post_again = client.post(f'/encuesta/{token}', data=form_data)
    assert post_again.status_code == 200
    assert 'Esta encuesta ya fue completada' in post_again.text

def test_public_survey_honeypot_rejects_bots(client, admin_client):
    add_company(admin_client, name='Bot Target Store')
    secret = client.app.state.settings.secret
    token = generate_survey_token(secret, 1)
    client.cookies.clear()
    
    # Envío con campo trampa lleno
    bot_res = client.post(f'/encuesta/{token}', data={'website_url': 'http://spam-bot.com'})
    assert bot_res.status_code == 400

def test_public_survey_requires_consent(client, admin_client):
    add_company(admin_client, name='Comercial Sin Consentimiento')
    secret = client.app.state.settings.secret
    token = generate_survey_token(secret, 1)
    client.cookies.clear()
    
    res = client.post(f'/encuesta/{token}', data={'consent': 'no'})
    assert res.status_code == 422
    assert 'consentimiento' in res.text


def test_public_company_register_page(client):
    client.cookies.clear()
    res = client.get('/registro-empresa')
    assert res.status_code == 200
    assert 'Registro de Empresa' in res.text
    assert 'Nombre comercial' in res.text
    assert 'Ley 1581 de 2012' in res.text
    # No debe filtrar elementos privados del panel
    assert 'sidebar' not in res.text
    assert 'Cerrar sesión' not in res.text
    # No debe filtrar instrumentos internos
    assert 'Entrevista semiestructurada' not in res.text
    assert 'Validación de prototipo' not in res.text

def test_public_company_register_alias(client):
    client.cookies.clear()
    res = client.get('/registro', follow_redirects=False)
    assert res.status_code == 303
    assert res.headers['location'] == '/registro-empresa'

def test_public_company_register_honeypot(client):
    client.cookies.clear()
    data = {
        'website_url': 'http://automated-spam-bot.net',
        'name': 'Empresa Spam',
        'barrio': 'Centro',
        'consent': 'yes'
    }
    res = client.post('/registro-empresa', data=data)
    assert res.status_code == 400

def test_public_company_register_validation_errors(client):
    client.cookies.clear()
    # Missing required fields
    res = client.post('/registro-empresa', data={'name': 'X', 'consent': 'no'})
    assert res.status_code == 422
    assert '2 caracteres' in res.text
    assert 'consentimiento' in res.text

def test_public_company_register_success_and_survey_flow(client):
    client.cookies.clear()
    data = {
        'name': 'Distribuciones Del Oriente',
        'barrio': 'Cabecera',
        'city': 'Bucaramanga',
        'activity': 'Comercio mayorista',
        'size': 'Pequeña',
        'has_records': 'Sí, ambos',
        'respondent_role': 'Gerente o administrador',
        'contact_name': 'Mauricio Prada',
        'contact_detail': '312 987 6543 / mprada@oriente.com',
        'notes': 'Disponibilidad en las mañanas',
        'consent': 'yes'
    }
    res = client.post('/registro-empresa', data=data)
    assert res.status_code == 200
    assert '¡Bienvenido al Proyecto Datapyme!' in res.text
    assert 'Distribuciones Del Oriente' in res.text
    assert 'DP-' in res.text
    assert '/encuesta/' in res.text
    assert 'Responder Encuesta Ahora Mismo' in res.text
    assert 'api.whatsapp.com' in res.text

    # Verificar en la base de datos
    from research.models import Company, CompanyContact, AuditLog
    with client.app.state.Session() as db:
        c = db.query(Company).filter_by(name='Distribuciones Del Oriente').one()
        assert c.barrio == 'Cabecera'
        assert c.source == 'Autoregistro web empresarial'
        assert c.verification_status == 'pendiente'
        assert c.operating_status == 'activa'
        assert c.owner == 'Autoregistro web'
        assert c.contact.name == 'Mauricio Prada'
        assert '312 987 6543' in c.contact.detail
        
        # Verificar audit log
        audit = db.query(AuditLog).filter_by(entity_type='company', entity_id=c.id).one()
        assert audit.action == 'crear_publico'
        assert audit.actor == 'Autoregistro web'

def test_public_company_register_duplicate_handling(client, admin_client):
    # Crear una empresa previa
    add_company(admin_client, name='Supermercado Los Andes', barrio='San Francisco')
    client.cookies.clear()

    # Intentar autoregistrar la misma empresa
    data = {
        'name': 'Supermercado Los Andes',
        'barrio': 'San Francisco',
        'city': 'Bucaramanga',
        'activity': 'Comercio minorista',
        'size': 'Microempresa',
        'has_records': 'Sí, ambos',
        'respondent_role': 'Propietario o socio',
        'contact_detail': '300 111 2233',
        'consent': 'yes'
    }
    res = client.post('/registro-empresa', data=data)
    assert res.status_code == 200
    assert '¡Su empresa ya está en Datapyme!' in res.text
    assert 'Supermercado Los Andes' in res.text
    assert '/encuesta/' in res.text

def test_microempresa_mapping_and_eligibility(client):
    from research.models import Company, Response
    from research.tokens import generate_survey_token
    from research.analytics import build_analysis, filtered_records
    
    client.cookies.clear()
    reg_data = {
        'name': 'MiniMarket Provenza Test',
        'barrio': 'Provenza',
        'city': 'Bucaramanga',
        'activity': 'Comercio minorista',
        'size': 'Microempresa',
        'has_records': 'Sí, ambos',
        'respondent_role': 'Propietario o socio',
        'contact_detail': '318 555 4433',
        'consent': 'yes'
    }
    res = client.post('/registro-empresa', data=reg_data)
    assert res.status_code == 200
    
    with client.app.state.Session() as db:
        c = db.query(Company).filter_by(name='MiniMarket Provenza Test').one()
        assert c.size == 'Pequeña'
        assert c.eligibility_status != 'fuera'
        cid = c.id
    
    # Responder la encuesta completa
    secret = client.app.state.settings.secret
    token = generate_survey_token(secret, cid)
    survey_data = {
        'consent': 'yes',
        'M04': 'Propietario o socio',
        'M05': 'Alimentos y bebidas',
        'M06': '1',
        'M07': ['Facturación / punto de venta'],
        'M08': ['Software de inventarios'],
        'M09': 'Diariamente',
        'M10': ['Datos dispersos'],
        'M11': '5',
        'M12': ['Existencias y alertas'],
        'M13': 'Sí',
        'M14': 'Limitaciones de integración',
        'M15': ['Precio'],
        'M16': '5',
        'M17': 'Inventarios y existencias',
        'M18': ['Precio accesible'],
        'M19': 'Suscripción mensual',
        'M20': '60000',
        'M21': 'Sí',
        'M22': 'Ninguna'
    }
    sub_res = client.post(f'/encuesta/{token}', data=survey_data)
    assert sub_res.status_code == 200
    
    with client.app.state.Session() as db:
        c = db.query(Company).filter_by(id=cid).one()
        assert c.verification_status == 'verificada'
        assert c.eligible is True
        assert c.eligibility_status == 'elegible'
        
        comps, responses, _ = filtered_records(db, {})
        analysis = build_analysis(db, comps, responses)
        assert analysis['stats']['valid_surveys'] >= 1
        assert analysis['sizes']['Pequeña'] >= 1
