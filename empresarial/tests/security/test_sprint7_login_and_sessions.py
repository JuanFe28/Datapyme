"""Tests de Sesion Web: login, bloqueo por fallos, cookie solo-lectura (anti-CSRF) y expiracion."""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.models import SessionToken, utcnow
from app.main import create_app

PASSWORD = "PasswordSeguro123!"


def _register(client: TestClient, email: str = "gerencia@pyme.co") -> dict:
    resp = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Comercial Login S.A.S.",
            "subsector": "Ferreteria",
            "email": email,
            "full_name": "Gerente Prueba",
            "password": PASSWORD,
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "diagnosis": {"M17": "Inventarios y existencias"},
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_login_flow_cookie_is_read_only_and_logout_revokes(tmp_path):
    application = create_app(f"sqlite:///{(tmp_path / 'login.db').as_posix()}", testing=True)
    with TestClient(application, follow_redirects=False) as client:
        _register(client)

        # Sin sesion: el navegador es enviado al login; la API responde 401 JSON
        redirect = client.get("/dashboard", headers={"accept": "text/html"})
        assert redirect.status_code == 303 and redirect.headers["location"] == "/login"
        assert client.get("/api/kpis").status_code == 401

        # Credenciales invalidas: mensaje generico
        bad = client.post("/login", data={"email": "gerencia@pyme.co", "password": "incorrecta-123"})
        assert bad.status_code == 401
        assert "Credenciales inválidas" in bad.text

        ok = client.post("/login", data={"email": "gerencia@pyme.co", "password": PASSWORD})
        assert ok.status_code == 303 and ok.headers["location"] == "/dashboard"
        set_cookie = ok.headers["set-cookie"].lower()
        assert "httponly" in set_cookie and ("samesite=lax" in set_cookie or "samesite=strict" in set_cookie)

        # Con cookie: lectura permitida (GET) y escritura rechazada (403)
        assert client.get("/dashboard").status_code == 200
        assert client.get("/api/kpis").status_code == 200
        write = client.post("/api/products", json={"sku": "X", "name": "X", "cost_price": "1", "sale_price": "2"})
        assert write.status_code == 403

        # Logout revoca la sesion en servidor
        assert client.post("/logout").status_code == 303
        client.cookies.clear()
        assert client.get("/api/kpis").status_code == 401


def test_lockout_after_repeated_failures_and_session_expiry(tmp_path):
    application = create_app(f"sqlite:///{(tmp_path / 'lock.db').as_posix()}", testing=True)
    with TestClient(application) as client:
        reg = _register(client)

        for _ in range(5):
            assert client.post(
                "/api/auth/login", json={"email": "gerencia@pyme.co", "password": "equivocada-999"}
            ).status_code == 401
        # Tras 5 fallos, incluso la contrasena correcta queda bloqueada temporalmente
        locked = client.post("/api/auth/login", json={"email": "gerencia@pyme.co", "password": PASSWORD})
        assert locked.status_code == 429

        # Una sesion expirada deja de ser valida
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        assert client.get("/api/kpis", headers=headers).status_code == 200
        with application.state.Session() as db:
            sess = db.query(SessionToken).first()
            sess.expires_at = utcnow() - timedelta(minutes=1)
            db.commit()
        assert client.get("/api/kpis", headers=headers).status_code == 401
