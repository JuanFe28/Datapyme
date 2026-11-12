import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    from app.main import create_app

    db_url = f"sqlite:///{(tmp_path / 'test_saas.db').as_posix()}"
    app = create_app(database_url=db_url, testing=True)
    with TestClient(app) as c:
        yield c
