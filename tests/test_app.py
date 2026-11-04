import io
from zipfile import ZipFile
import pytest
from conftest import csrf, login, add_company, company_data, survey_data

@pytest.mark.parametrize('path', ['/', '/empresas','/empresas/nueva','/instrumentos/mercado','/instrumentos/entrevista','/instrumentos/prototipo','/respuestas','/tareas','/analisis','/evidencias','/canvas','/finanzas','/notas','/guia','/reportes','/usuarios','/auditoria'])
def test_pages(admin_client, path):
    result=admin_client.get(path)
    assert result.status_code==200, result.text[:1000]
    assert '<html lang="es">' in result.text

def test_anonymous_and_readiness(client):
    assert client.get('/health').json()['status']=='ok'
    assert client.get('/ready').json()['database']=='ok'
    assert client.get('/empresas',follow_redirects=False).status_code==303

def test_hash_and_revocable_session(admin_client):
    from research.models import User, LoginSession
    with admin_client.app.state.Session() as db:
        assert db.query(User).filter_by(username='admin').one().password_hash.startswith('pbkdf2_sha256$')
        assert db.query(LoginSession).count()==1
    cookie=admin_client.cookies.get('datapyme_session')
    admin_client.post('/logout',data={'csrf_token':csrf(admin_client)})
    admin_client.cookies.set('datapyme_session',cookie)
    assert admin_client.get('/',follow_redirects=False).status_code==303

def test_role_and_deactivation_immediately_enforced(admin_client):
    from research.models import User
    with admin_client.app.state.Session() as db:
        user=db.query(User).filter_by(username='admin').one(); user.role='campo'; db.commit()
    assert admin_client.get('/exportar/xlsx').status_code==403
    with admin_client.app.state.Session() as db:
        db.query(User).filter_by(username='admin').one().active=False; db.commit()
    assert admin_client.get('/empresas',follow_redirects=False).status_code==303

def test_csrf_and_security_headers(admin_client):
    assert admin_client.post('/empresas/nueva',data={'name':'Inyectada'}).status_code==403
    page=admin_client.get('/')
    assert page.headers['X-Content-Type-Options']=='nosniff'
    assert page.headers['Cache-Control']=='no-store'
    assert "frame-ancestors 'none'" in page.headers['Content-Security-Policy']

def test_login_rate_limit(client):
    for _ in range(6): result=login(client,password='contraseña-incorrecta')
    assert result.status_code==429
    assert result.headers.get('Retry-After')

def test_rate_limit_normalizes_username_whitespace(client):
    for username in ('admin',' admin','admin ','\tadmin','admin\t','  admin  '):
        result=login(client,username=username,password='contraseña-incorrecta')
    assert result.status_code==429

def test_field_cannot_reactivate_withdrawn_response(admin_client):
    add_company(admin_client)
    admin_client.post('/logout',data={'csrf_token':csrf(admin_client)})
    login(admin_client,'investigador','Field-test-only-87654321')
    admin_client.post('/instrumentos/mercado',data=survey_data(admin_client))
    admin_client.post('/logout',data={'csrf_token':csrf(admin_client)})
    login(admin_client)
    admin_client.post('/respuestas/1/eliminar',data={'csrf_token':csrf(admin_client),'reason':'Retiro QA'})
    admin_client.post('/logout',data={'csrf_token':csrf(admin_client)})
    login(admin_client,'investigador','Field-test-only-87654321')
    result=admin_client.post('/instrumentos/mercado',data=survey_data(admin_client,response_id='1'))
    assert result.status_code==403

def test_field_permissions(field_client):
    for path in ('/reportes','/exportar/xlsx','/usuarios','/auditoria'):
        assert field_client.get(path).status_code==403
    assert field_client.get('/empresas').status_code==200

def test_production_rejects_unsafe_config(monkeypatch):
    from research.config import Settings
    monkeypatch.setenv('APP_ENV','production'); monkeypatch.setenv('SESSION_SECRET','weak'); monkeypatch.setenv('DATABASE_URL','sqlite:///bad.db')
    with pytest.raises(ValueError): Settings.from_env()

def test_eligibility_is_verified_and_not_microenterprise(admin_client):
    from research.models import Company
    for i,changes in enumerate(({'source':''},{'verification_status':'pendiente'},{'size':'Microempresa'},{'operating_status':'inactiva'},{'has_records':'No / no sabe'},{})):
        assert add_company(admin_client,name=f'Fixture QA {i}',**changes).status_code==303
    with admin_client.app.state.Session() as db:
        assert [c.eligible for c in db.query(Company).order_by(Company.id)]==[False,False,False,False,False,True]

def test_duplicates_on_creation_and_edit(admin_client):
    from research.models import Company, AuditLog
    add_company(admin_client,name='Comercial ÁRBOL')
    assert add_company(admin_client,name='  comercial   arbol ').status_code==409
    add_company(admin_client,name='Otra empresa QA')
    assert admin_client.post('/empresas/2/editar',data=company_data(name='COMERCIAL ARBOL',csrf_token=csrf(admin_client))).status_code==409
    with admin_client.app.state.Session() as db:
        assert db.query(Company).count()==2
        assert db.get(Company,2).name=='Otra empresa QA'
        assert db.query(AuditLog).filter_by(entity_type='company').count()==2

def test_draft_exclusion_and_completion(admin_client):
    from research.models import Response, Consent, Answer
    add_company(admin_client)
    assert admin_client.post('/instrumentos/mercado',data={'csrf_token':csrf(admin_client),'company_id':'1','action':'draft','M04':'Gerente o administrador'}).status_code==200
    assert admin_client.get('/api/analisis').json()['stats']['valid_surveys']==0
    assert admin_client.post('/instrumentos/mercado',data=survey_data(admin_client,response_id='1')).status_code==200
    with admin_client.app.state.Session() as db:
        assert db.query(Response).count()==1
        assert db.get(Response,1).status=='complete'
        assert db.query(Consent).count()==1 and db.query(Answer).count()>10
    assert admin_client.post('/instrumentos/mercado',data=survey_data(admin_client)).status_code==409

def test_consent_and_conditional_validation(admin_client):
    from research.models import Response
    add_company(admin_client)
    data=survey_data(admin_client,consent='',M13='Sí',M14='')
    assert admin_client.post('/instrumentos/mercado',data=data).status_code==422
    data['consent']='yes'
    assert admin_client.post('/instrumentos/mercado',data=data).status_code==422
    data.update(M13='No',M14='Ignorar por salto',M19='Solo una opción gratuita',M20='99999')
    assert admin_client.post('/instrumentos/mercado',data=data).status_code==200
    with admin_client.app.state.Session() as db:
        r=db.query(Response).one(); assert r.data['M14']=='' and r.data['M20'] is None
        assert r.participant_code.startswith('P-')

def test_exclusive_multi_and_duplicate_choices(admin_client):
    add_company(admin_client)
    assert admin_client.post('/instrumentos/mercado',data=survey_data(admin_client,M15=['Ninguno','Precio'])).status_code==422
    assert admin_client.post('/instrumentos/mercado',data=survey_data(admin_client,M15=['Precio','Precio'])).status_code==422

def test_private_contacts(admin_client):
    add_company(admin_client,contact_name='Persona privada QA',contact_detail='privado@example.org')
    assert 'privado@example.org' in admin_client.get('/empresas/1/editar').text
    assert 'privado@example.org' not in admin_client.get('/exportar/empresas').text
    admin_client.post('/logout',data={'csrf_token':csrf(admin_client)})
    login(admin_client,'investigador','Field-test-only-87654321')
    page=admin_client.get('/empresas/1/editar').text
    assert 'privado@example.org' not in page and 'Persona privada QA' not in page

def test_prototype_reference(admin_client):
    add_company(admin_client)
    assert admin_client.post('/instrumentos/prototipo',data=survey_data(admin_client,'prototipo',prototype_reference='')).status_code==422
    assert admin_client.post('/instrumentos/prototipo',data=survey_data(admin_client,'prototipo')).status_code==200

def test_multiple_choice_denominator(admin_client):
    add_company(admin_client,name='QA Uno'); add_company(admin_client,name='QA Dos',size='Mediana')
    admin_client.post('/instrumentos/mercado',data=survey_data(admin_client,M15=['Precio','Tiempo de implementación']))
    admin_client.post('/instrumentos/mercado',data=survey_data(admin_client,company_id=2,M15=['Precio']))
    dist=admin_client.get('/api/analisis').json()['distributions']['M15']
    assert dist['n']==2
    assert dist['rows'][0]=={'label':'Precio','count':2,'percent':100.0}
    assert {x['label']:x['percent'] for x in dist['rows']}['Tiempo de implementación']==50.0
    filtered=admin_client.get('/api/analisis?size=Mediana').json()
    assert filtered['stats']['valid_surveys']==1 and filtered['distributions']['M15']['n']==1

def test_filters_exports_and_bad_dates(admin_client):
    add_company(admin_client,name='QA Pequeña'); add_company(admin_client,name='QA Mediana',size='Mediana')
    assert admin_client.get('/api/analisis?size=Mediana').json()['stats']['companies']==1
    text=admin_client.get('/exportar/empresas?size=Mediana').text
    assert 'QA Mediana' in text and 'QA Pequeña' not in text
    assert admin_client.get('/api/analisis?from_date=2026-99-99').status_code==422
    assert admin_client.get('/api/analisis?from_date=2026-10-22&to_date=2026-01-01').status_code==422

def test_all_export_formats(admin_client):
    add_company(admin_client,name='=QA Formula')
    admin_client.post('/instrumentos/mercado',data=survey_data(admin_client))
    result=admin_client.get('/exportar/xlsx'); assert result.content.startswith(b'PK')
    with ZipFile(io.BytesIO(result.content)) as book:
        assert b'<f>' not in b''.join(book.read(p) for p in book.namelist() if p.endswith('.xml'))
        assert 'Actividades' in book.read('xl/workbook.xml').decode()
    assert "'=QA Formula" in admin_client.get('/exportar/empresas').text
    assert admin_client.get('/exportar/pdf').content.startswith(b'%PDF')
    png=admin_client.get('/exportar/grafico/M15.png').content
    assert png.startswith(b'\x89PNG\r\n\x1a\n') and int.from_bytes(png[16:20],'big')>=1200

def test_empty_chart_not_exported(admin_client):
    assert admin_client.get('/exportar/grafico/M15.png').status_code==422
    assert admin_client.get('/exportar/grafico/INVALID.png').status_code==404

def test_persistent_private_evidence_and_spoofed_type(admin_client):
    add_company(admin_client)
    data={'csrf_token':csrf(admin_client),'title':'Evidencia QA','authorized':'yes','company_id':'1'}
    assert admin_client.post('/evidencias',data=data,files={'file':('nota.txt',b'Evidencia QA privada','text/plain')}).status_code==200
    assert admin_client.get('/evidencias/1/descargar').content==b'Evidencia QA privada'
    assert admin_client.post('/evidencias',data=data,files={'file':('falsa.png',b'<script>x</script>','image/png')}).status_code==422
    admin_client.post('/logout',data={'csrf_token':csrf(admin_client)})
    login(admin_client,'investigador','Field-test-only-87654321')
    assert admin_client.get('/evidencias/1/descargar').status_code==403

def test_task_completion_needs_evidence(admin_client):
    from research.models import Task
    data=dict(csrf_token=csrf(admin_client),status='completada',assignee='QA',due_date='2026-11-01',evidence='')
    assert admin_client.post('/tareas/1',data=data).status_code==422
    data['evidence']='Acta de revisión metodológica QA'
    assert admin_client.post('/tareas/1',data=data).status_code==200
    with admin_client.app.state.Session() as db:
        t=db.get(Task,1); assert t.completed and t.status=='completada' and str(t.due_date)=='2026-11-01'

def test_canvas_versions_and_validation(admin_client):
    from research.models import CanvasVersion
    data={key:'Hipótesis QA' for key in ('segments','value','channels','relationships','revenue','resources','activities','partners','costs')}
    data.update(csrf_token=csrf(admin_client),title='QA 1',hypothesis_status='validada',conclusion='')
    assert admin_client.post('/canvas',data=data).status_code==422
    data['hypothesis_status']='pendiente'
    assert admin_client.post('/canvas',data=data).status_code==200
    data['title']='QA 2'; assert admin_client.post('/canvas',data=data).status_code==200
    with admin_client.app.state.Session() as db: assert db.query(CanvasVersion).count()==2
    assert admin_client.get('/canvas?compare=1').status_code==200
    assert admin_client.get('/exportar/canvas/2.pdf').content.startswith(b'%PDF')

def test_financial_scenario_calculations(admin_client):
    data=dict(csrf_token=csrf(admin_client),name='Escenario QA',initial_investment='1000000',monthly_fixed='600000',unit_price='50000',unit_variable='10000',initial_customers='20',monthly_growth='0',months='3',source='Supuestos QA',assumptions='Clientes constantes')
    assert admin_client.post('/finanzas',data=data).status_code==200
    result=admin_client.get('/api/finanzas/1').json()
    assert result['contribution']=='40000.00' and result['break_even_customers']==15
    assert result['cash_flow'][0]['net']=='200000.00' and result['cash_flow'][2]['balance']=='-400000.00'
    assert admin_client.get('/exportar/finanzas/1.xlsx').content.startswith(b'PK')
    assert admin_client.get('/exportar/finanzas/1.pdf').content.startswith(b'%PDF')
    data['unit_variable']='50000'; admin_client.post('/finanzas',data=data)
    assert admin_client.get('/api/finanzas/2').json()['break_even_customers'] is None

def test_sourced_notes(admin_client):
    data=dict(csrf_token=csrf(admin_client),kind='ambiental',title='Evaluación QA',content='Observación QA',source='')
    assert admin_client.post('/notas',data=data).status_code==422
    data['source']='Documento técnico QA'; assert admin_client.post('/notas',data=data).status_code==200
