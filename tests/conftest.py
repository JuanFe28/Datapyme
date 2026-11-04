import re
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def csrf(client, path='/'):
    found = re.search(r'name="csrf_token" value="([a-f0-9]+)"', client.get(path).text)
    assert found, f'No hay token CSRF en {path}'
    return found.group(1)

def login(client, username='admin', password='Admin-test-only-87654321'):
    return client.post('/login', data={'csrf_token':csrf(client, '/login'), 'username':username, 'password':password}, follow_redirects=False)

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('SESSION_SECRET', 'test-only-secret-012345678901234567890123456789')
    monkeypatch.setenv('ADMIN_PASSWORD', 'Admin-test-only-87654321')
    monkeypatch.setenv('FIELD_PASSWORD', 'Field-test-only-87654321')
    from app import create_app
    application = create_app(database_url='sqlite:///' + (tmp_path / 'research.db').as_posix(), testing=True)
    with TestClient(application) as browser:
        yield browser
    application.state.engine.dispose()

@pytest.fixture
def admin_client(client):
    assert login(client).status_code == 303
    return client

@pytest.fixture
def field_client(client):
    assert login(client, 'investigador', 'Field-test-only-87654321').status_code == 303
    return client

def company_data(**updates):
    data = dict(name='Empresa sintética QA', barrio='Centro', city='Bucaramanga', activity='Comercio minorista', ciiu='4711', size='Pequeña', source='Registro mercantil revisado QA', has_records='Sí, ambos', respondent_role='Propietario', willing='Sí', verification_status='verificada', operating_status='activa', notes='Fixture aislado; no es investigación')
    data.update(updates)
    return data

def add_company(client, **updates):
    return client.post('/empresas/nueva', data=company_data(csrf_token=csrf(client, '/empresas/nueva'), **updates), follow_redirects=False)

def survey_data(client, category='mercado', company_id=1, **updates):
    from questions import Q_MAP
    data = dict(csrf_token=csrf(client, '/instrumentos/' + category), company_id=str(company_id), consent='yes', action='complete', prototype_reference='https://example.org/prototipo-qa')
    for code, question in Q_MAP[category].items():
        if question['kind']=='scale': data[code]='4'
        elif question['kind'] in ('select','multi'): data[code]=question['choices'][0]
        elif question['kind']=='number': data[code]='85000'
        else: data[code]='Respuesta sintética QA'
    data.update(updates)
    return data
