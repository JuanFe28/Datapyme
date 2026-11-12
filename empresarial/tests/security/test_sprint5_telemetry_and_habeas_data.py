"""Tests de Seguridad de Sprint 5: Telemetría con k-Anonimato (k >= 3), Separación SuperAdmin y Habeas Data."""

import json
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.models import SessionToken, User, utcnow
from app.core.security import generate_session_token, hash_password, sha256_hex
from app.main import create_app


def _register_opt_in_tenant(client: TestClient, idx: int, subsector: str = "Ferretería") -> dict:
    resp = client.post(
        "/api/auth/register",
        json={
            "legal_name": f"Comercializadora Privada {idx} S.A.S.",
            "subsector": subsector,
            "email": f"gerencia{idx}@privada.co",
            "full_name": f"Representante {idx}",
            "password": "PasswordSeguro123!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "accept_aggregate_stats": True,
            "diagnosis": {
                "M10": ["Falta de control de inventario"],
                "M12": ["Alertas de stock bajo"],
                "M17": "Controlar inventario",
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_k_anonymity_suppression_role_segregation_and_habeas_data(tmp_path):
    db_file = tmp_path / "sprint5_telemetry.db"
    application = create_app(f"sqlite:///{db_file.as_posix()}", testing=True)

    with TestClient(application) as client:
        # Crear usuario SuperAdmin en la base de datos
        with application.state.Session() as db:
            admin = User(
                tenant_id=None,
                email="auditor.fdc125@uts.edu.co",
                full_name="Auditor F-DC-125",
                password_hash=hash_password("SuperAdminPass123!"),
                role="superadmin",
            )
            db.add(admin)
            db.flush()
            admin_tok, admin_tok_hash = generate_session_token()
            db.add(
                SessionToken(
                    user_id=admin.id,
                    token_hash=admin_tok_hash,
                    csrf_secret=sha256_hex(admin_tok + "|csrf"),
                    expires_at=utcnow() + timedelta(hours=8),
                    ip_hash=sha256_hex("127.0.0.1"),
                )
            )
            db.commit()

        admin_headers = {"Authorization": f"Bearer {admin_tok}"}

        # Registrar 2 empresas (k = 2 < 3)
        t1 = _register_opt_in_tenant(client, 1, subsector="Ferretería")
        t2 = _register_opt_in_tenant(client, 2, subsector="Ferretería")
        headers_t1 = {"Authorization": f"Bearer {t1['access_token']}"}

        # 1. Separación estricta de roles: Owner recibe 403 en /api/admin/impact y SuperAdmin recibe 403 en /api/products
        assert client.get("/api/admin/impact", headers=headers_t1).status_code == 403
        assert client.get("/api/products", headers=admin_headers).status_code == 403

        # 2. Con k = 2 (< 3), la telemetría global DEBE estar suprimida por k-anonimato
        impact_k2 = client.get("/api/admin/impact", headers=admin_headers).json()
        assert impact_k2["global"]["active_tenants"] == 2
        assert impact_k2["global"]["is_suppressed"] is True
        assert impact_k2["global"]["sales_amount_cop"] is None
        assert impact_k2["legal_consents_integrity"]["chain_intact"] is True

        # 3. Al registrar la 3ra empresa (k = 3), se desbloquea el agregado global SIN exponer PII ni tenant_id
        _register_opt_in_tenant(client, 3, subsector="Minimercado")
        impact_k3 = client.get("/api/admin/impact", headers=admin_headers).json()
        assert impact_k3["global"]["active_tenants"] == 3
        assert impact_k3["global"]["is_suppressed"] is False
        assert impact_k3["global"]["sales_amount_cop"] == "0"

        # Verificar que los subsectores con k < 3 (Ferretería tiene 2, Minimercado tiene 1) siguen suprimidos
        for sub in impact_k3["subsectors"]:
            assert sub["is_suppressed"] is True
            assert sub["sales_amount_cop"] is None

        # Verificar ausencia total de PII / nombres / correos / tenant_id en todo el JSON de telemetría
        raw_json = json.dumps(impact_k3)
        assert "Comercializadora Privada" not in raw_json
        assert "gerencia1@privada.co" not in raw_json
        assert t1["tenant_id"] not in raw_json
        assert t2["tenant_id"] not in raw_json

        # 4. Portabilidad Habeas Data (/api/me/export) devuelve solo los datos de la Empresa 1
        export_resp = client.get("/api/me/export", headers=headers_t1)
        assert export_resp.status_code == 200
        bundle = export_resp.json()
        assert bundle["tenant"]["id"] == t1["tenant_id"]
        assert len(bundle["legal_consents"]) == 3

        # 5. Solicitud de supresión Habeas Data (/api/me/deletion-request) revoca sesión y mantiene cadena SHA-256 íntegra
        del_resp = client.post(
            "/api/me/deletion-request",
            headers=headers_t1,
            json={"reason": "Cierre de operaciones comerciales del piloto"},
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "pending_deletion"
        assert del_resp.json()["sessions_revoked"] == 1

        # El token de t1 ya no puede operar porque la sesión fue revocada y el tenant pasó a pending_deletion
        assert client.get("/api/products", headers=headers_t1).status_code == 401

        # Y al bajar a 2 empresas activas nuevamente, la telemetría global vuelve a suprimirse automáticamente
        impact_after_del = client.get("/api/admin/impact", headers=admin_headers).json()
        assert impact_after_del["global"]["active_tenants"] == 2
        assert impact_after_del["global"]["is_suppressed"] is True
        assert impact_after_del["legal_consents_integrity"]["chain_intact"] is True
        assert impact_after_del["legal_consents_integrity"]["total_consent_nodes"] == 10
