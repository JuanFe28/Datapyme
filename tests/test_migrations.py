import json
import sqlite3
from sqlalchemy import inspect,text
from research.database import make_engine,upgrade_database

def test_legacy_migration_preserves_records_and_is_repeatable(tmp_path):
    path=tmp_path/'legacy.db'
    connection=sqlite3.connect(path)
    connection.executescript('''
    CREATE TABLE companies (id INTEGER PRIMARY KEY,name VARCHAR(180) NOT NULL,barrio VARCHAR(120) NOT NULL,city VARCHAR(60) NOT NULL,activity VARCHAR(90) NOT NULL,ciiu VARCHAR(20),size VARCHAR(30) NOT NULL,source VARCHAR(90),has_records VARCHAR(40),respondent_role VARCHAR(90),willing VARCHAR(30),notes TEXT,owner VARCHAR(60) NOT NULL,created_at DATETIME);
    CREATE TABLE responses (id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),category VARCHAR(20) NOT NULL,data JSON NOT NULL,author VARCHAR(60) NOT NULL,created_at DATETIME);
    CREATE TABLE tasks (id INTEGER PRIMARY KEY,phase VARCHAR(5) NOT NULL,title VARCHAR(180) NOT NULL UNIQUE,completed BOOLEAN,assignee VARCHAR(120),evidence VARCHAR(300));
    INSERT INTO companies VALUES (1,'Empresa histórica QA','Centro','Bucaramanga','Comercio minorista','4711','Pequeña','Fuente histórica','Sí, ambos','Propietario','Sí','Conservar','admin','2026-01-01');
    INSERT INTO responses VALUES (1,1,'mercado','{"M04":"Propietario o socio"}','admin','2026-01-01');
    INSERT INTO tasks VALUES (1,'01','Actividad histórica QA',1,'QA','Acta QA');
    ''')
    connection.commit(); connection.close()
    engine=make_engine('sqlite:///'+path.as_posix())
    upgrade_database(engine); upgrade_database(engine)
    with engine.connect() as db:
        assert db.execute(text('SELECT name FROM companies')).scalar()=='Empresa histórica QA'
        assert db.execute(text('SELECT status FROM responses')).scalar()=='legacy_pending'
        assert db.execute(text('SELECT verification_status FROM companies')).scalar()=='pendiente'
        assert db.execute(text('SELECT status FROM tasks')).scalar()=='completada'
        assert db.execute(text('SELECT COUNT(*) FROM responses')).scalar()==1
    assert 'consent_id' in {x['constrained_columns'][0] for x in inspect(engine).get_foreign_keys('responses')}
    engine.dispose()

def test_persistence_after_recreating_application(tmp_path,monkeypatch):
    from app import create_app
    from fastapi.testclient import TestClient
    from conftest import login,add_company,csrf
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('SESSION_SECRET','persist-test-012345678901234567890123456789')
    monkeypatch.setenv('ADMIN_PASSWORD','Admin-test-only-87654321')
    url='sqlite:///'+(tmp_path/'restart.db').as_posix()
    first=create_app(url,testing=True)
    with TestClient(first) as browser:
        login(browser); add_company(browser)
        browser.post('/evidencias',data={'csrf_token':csrf(browser),'title':'Persistencia QA','authorized':'yes'},files={'file':('nota.txt',b'Conservar tras reinicio','text/plain')})
    second=create_app(url,testing=True)
    with TestClient(second) as browser:
        login(browser)
        assert browser.get('/api/analisis').json()['stats']['companies']==1
        assert browser.get('/evidencias/1/descargar').content==b'Conservar tras reinicio'

def test_survey_uniqueness_is_enforced_by_database(admin_client):
    from conftest import add_company,survey_data
    from research.models import Response
    from sqlalchemy.exc import IntegrityError
    import pytest
    add_company(admin_client)
    admin_client.post('/instrumentos/mercado',data=survey_data(admin_client))
    with admin_client.app.state.Session() as db:
        db.add(Response(company_id=1,category='mercado',data={},author='QA',status='complete',survey_key='mercado:1'))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()

def test_backup_preserves_binary_evidence_without_overwrite(admin_client,tmp_path):
    from conftest import csrf
    from manage import backup
    import pytest
    admin_client.post('/evidencias',data={'csrf_token':csrf(admin_client),'title':'Respaldo QA','authorized':'yes'},files={'file':('nota.txt',b'Archivo completo en respaldo','text/plain')})
    output=tmp_path/'backup.sqlite'
    backup(admin_client.app.state.settings,output)
    with sqlite3.connect(output) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT content FROM evidence_blobs').fetchone()[0]==b'Archivo completo en respaldo'
    assert output.with_suffix('.sqlite.json').exists()
    with pytest.raises(ValueError): backup(admin_client.app.state.settings,output)
