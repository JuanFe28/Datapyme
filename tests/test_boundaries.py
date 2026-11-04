import io
from zipfile import ZipFile,ZIP_DEFLATED
import pytest
from conftest import add_company,csrf

def test_financial_limits_do_not_raise_server_error(admin_client):
    data=dict(csrf_token=csrf(admin_client),name='Límite QA',initial_investment='1000000000000',monthly_fixed='1000000000000',unit_price='1000000000000',unit_variable='0',initial_customers='1000000',monthly_growth='100',months='60',source='Supuesto extremo QA',assumptions='Solo verificación de rango')
    assert admin_client.post('/finanzas',data=data).status_code==200
    response=admin_client.get('/api/finanzas/1')
    assert response.status_code==200
    assert len(response.json()['cash_flow'])==60

def test_candidate_size_and_activity_distributions_include_unverified(admin_client):
    add_company(admin_client,name='QA Micro',size='Microempresa',verification_status='pendiente')
    add_company(admin_client,name='QA Mediana',size='Mediana')
    result=admin_client.get('/api/analisis').json()
    sizes=result['distributions']['company_size']
    assert sizes['n']==2
    assert {r['label']:r['percent'] for r in sizes['rows']}=={'Microempresa':50.0,'Mediana':50.0}

def test_expanding_office_archive_is_rejected_before_storage(admin_client):
    output=io.BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml','<Types/>')
        archive.writestr('xl/workbook.xml',b'A'*(40*1024*1024+1))
    result=admin_client.post('/evidencias',data={'csrf_token':csrf(admin_client),'title':'Archivo QA','authorized':'yes'},files={'file':('grande.xlsx',output.getvalue(),'application/octet-stream')})
    assert result.status_code==422
    from research.models import Evidence,EvidenceBlob
    with admin_client.app.state.Session() as db:
        assert db.query(Evidence).count()==0 and db.query(EvidenceBlob).count()==0

def test_request_size_is_limited(admin_client):
    result=admin_client.post('/evidencias',content=b'x',headers={'content-length':str(13*1024*1024)})
    assert result.status_code==413
