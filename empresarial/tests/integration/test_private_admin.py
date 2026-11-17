import pytest
from fastapi import HTTPException

from app.core.models import User
from app.core.security import verify_password


def test_private_admin_is_created_without_overwriting_an_existing_account(client):
    from app.core.admin_cli import create_private_admin

    with client.app.state.Session() as db:
        create_private_admin(db, "soporte@example.test", "PasswordSintetica2026!")
        user = db.query(User).one()
        assert user.role == "superadmin" and user.tenant_id is None
        assert verify_password("PasswordSintetica2026!", user.password_hash)
        with pytest.raises(HTTPException):
            create_private_admin(db, "soporte@example.test", "OtroPassword2026!")
        assert db.query(User).count() == 1


def test_bootstrap_rejects_public_demo_account(client):
    from app.core.admin_cli import create_private_admin

    with client.app.state.Session() as db:
        with pytest.raises(HTTPException):
            create_private_admin(db, "superadmin.demo@datapyme.co", "PasswordSintetica2026!")
        assert db.query(User).count() == 0


def test_admin_provision_uses_unique_generated_temporary_passwords(client):
    from test_company_tax import account

    h = account(client, "soporte@example.test")
    with client.app.state.Session() as db:
        user = db.query(User).one()
        user.role, user.tenant_id = "superadmin", None
        db.commit()
    secrets = []
    for i in range(2):
        r = client.post(
            "/api/admin/tenants/provision",
            headers=h,
            json={
                "trade_name": f"Empresa QA {i}",
                "owner_full_name": "Persona Sintética",
                "email": f"empresa{i}@example.test",
            },
        )
        assert r.status_code == 201, r.text
        secret = r.json()["whatsapp_handoff_text"].split("Clave temporal: ", 1)[1].splitlines()[0]
        assert len(secret) >= 24
        secrets.append(secret)
    assert secrets[0] != secrets[1]
