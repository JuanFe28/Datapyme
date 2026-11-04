from fastapi.testclient import TestClient
from conftest import login
import io
from zipfile import ZipFile

def test_review_does_not_import_real_bootstrap_credentials_from_dotenv(tmp_path,monkeypatch):
    from scripts.review_access import review_environment,prepare_review
    from research import config as settings_module
    from research.config import Settings
    from research.database import make_engine
    from research.models import User
    from research.security import bootstrap
    from sqlalchemy.orm import Session
    (tmp_path/'.env').write_text('ADMIN_USER=real_admin\nADMIN_PASSWORD=Real-only-test-87654321\nFIELD_USER=real_field\nFIELD_PASSWORD=Real-field-test-87654321\n',encoding='utf-8')
    monkeypatch.setattr(settings_module,'ROOT',tmp_path)
    config=prepare_review(tmp_path/'isolated')
    env=review_environment(config)
    for key in ('APP_ENV','DATABASE_URL','SESSION_SECRET','ALLOWED_HOSTS','ADMIN_USER','ADMIN_PASSWORD','FIELD_USER','FIELD_PASSWORD'):
        monkeypatch.setenv(key,env[key])
    Settings.from_env()  # Carga el .env local tal como ocurre al arrancar.
    engine=make_engine(config['database_url'])
    try:
        with Session(engine) as db:
            bootstrap(db);db.commit()
            assert {u.username for u in db.query(User)}=={'revision_admin','revision_campo'}
    finally: engine.dispose()

def test_review_uses_separate_secure_cookie_and_visible_warning(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_ENV','review')
    monkeypatch.setenv('SESSION_SECRET','review-test-secret-01234567890123456789012345')
    monkeypatch.setenv('ADMIN_PASSWORD','Admin-test-only-87654321')
    from app import create_app
    app=create_app('sqlite:///'+(tmp_path/'review.db').as_posix(),testing=True)
    with TestClient(app,base_url='https://testserver') as browser:
        response=browser.get('/login')
        cookie=response.headers['set-cookie']
        assert cookie.startswith('datapyme_revision_session=')
        assert 'secure' in cookie.lower() and 'httponly' in cookie.lower()
        assert 'REVISIÓN — DATOS DE PRUEBA' in response.text
        assert login(browser).status_code==303
        assert 'REVISIÓN — DATOS DE PRUEBA' in browser.get('/').text

def test_review_setup_is_repeatable_and_isolated(admin_client,tmp_path):
    from scripts.review_access import prepare_review
    from research.models import Company,User
    from research.database import make_engine
    from sqlalchemy.orm import Session
    directory=tmp_path/'review-only'
    first=prepare_review(directory)
    second=prepare_review(directory)
    assert first['secret']==second['secret']
    assert len(first['admin_password'])>=20
    assert first['database_url'].endswith('/review-only/revision.db')
    engine=make_engine(first['database_url'])
    with Session(engine) as db:
        assert db.query(Company).count()==1
        assert 'PRUEBA' in db.query(Company).one().name
        assert {u.username for u in db.query(User)}=={'revision_admin','revision_campo'}
    engine.dispose()
    with admin_client.app.state.Session() as db:
        assert db.query(Company).count()==0

def test_review_exports_are_clearly_identified_as_test_data(tmp_path,monkeypatch):
    from app import create_app
    from conftest import add_company
    monkeypatch.setenv('APP_ENV','review')
    monkeypatch.setenv('SESSION_SECRET','review-test-secret-01234567890123456789012345')
    monkeypatch.setenv('ADMIN_PASSWORD','Admin-test-only-87654321')
    app=create_app('sqlite:///'+(tmp_path/'review-export.db').as_posix(),testing=True)
    with TestClient(app,base_url='https://testserver') as browser:
        login(browser);add_company(browser)
        result=browser.get('/exportar/empresas')
        assert 'REVISION_' in result.headers['content-disposition']
        assert 'SOLO PRUEBAS' in result.text
        result=browser.get('/exportar/xlsx')
        with ZipFile(io.BytesIO(result.content)) as book:
            assert 'SOLO REVISION' in book.read('xl/workbook.xml').decode()
