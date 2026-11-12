"""Tests de Seguridad Multi-Tenant, Argon2id, Inmutabilidad Legal (Ley 1581) y Aislamiento de Layout UI."""
import pytest
from sqlalchemy.exc import IntegrityError, InternalError, OperationalError


def test_argon2id_password_hashing():
    from app.core.security import hash_password, verify_password

    hashed = hash_password("ClaveSeguraPyme2026!")
    assert hashed.startswith("$argon2id$")
    assert verify_password("ClaveSeguraPyme2026!", hashed) is True
    assert verify_password("ClaveIncorrecta123!", hashed) is False


def test_legal_consents_immutability_and_hash_chain(client):
    """Verifica que legal_consents tenga hash chain SHA-256 y rechace UPDATE/DELETE por trigger."""
    # Registrar Empresa A con onboarding completo
    reg_a = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Ferretería Cabecera S.A.S.",
            "subsector": "ferreteria_hogar",
            "size": "pequena",
            "email": "gerencia@ferrecabecera.co",
            "full_name": "Carlos Gómez",
            "password": "FerreCabecera2026!Secure",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "accept_aggregate_stats": True,
            "diagnosis": {
                "M10": ["Diferencias en inventario", "No identifica fácilmente la rotación"],
                "M12": ["Existencias y alertas", "Rotación de productos"],
                "M17": "Inventarios y existencias",
                "M07": ["Hojas de cálculo"],
                "M08": ["Hojas de cálculo"],
                "M13": "No",
                "M15": ["Precio"],
            },
        },
    )
    assert reg_a.status_code == 201, reg_a.text

    from sqlalchemy import text

    from app.core.models import LegalConsent

    with client.app.state.Session() as db:
        consents = (
            db.query(LegalConsent)
            .order_by(LegalConsent.accepted_at.asc(), LegalConsent.id.asc())
            .all()
        )
        assert len(consents) == 3
        assert consents[0].prev_hash == "0" * 64
        assert consents[1].prev_hash == consents[0].row_hash
        assert consents[2].prev_hash == consents[1].row_hash

        # Intentar UPDATE o DELETE directo sobre legal_consents debe fallar por trigger inmutable
        with pytest.raises((OperationalError, IntegrityError, InternalError)):
            db.execute(text("UPDATE legal_consents SET action = 'revoke'"))
            db.commit()
        db.rollback()

        with pytest.raises((OperationalError, IntegrityError, InternalError)):
            db.execute(text("DELETE FROM legal_consents"))
            db.commit()
        db.rollback()


def test_multi_tenant_isolation_and_differentiated_adaptive_ui(client):
    """
    Verifica:
    1. Dos empresas con respuestas distintas (Empresa A Inventario vs Empresa B Ventas)
       obtienen layout_config diferente acorde a su diagnóstico.
    2. El usuario de la Empresa A recibe 404/403 al intentar leer datos de la Empresa B.
    3. El selector manual de vista (personalized -> general) funciona por usuario sin afectar a la otra empresa.
    """
    # 1. Registrar Empresa A (Foco Inventarios)
    res_a = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Ferretería El Martillo S.A.S.",
            "subsector": "ferreteria_hogar",
            "size": "pequena",
            "email": "admin@martillo.co",
            "full_name": "Ana Martínez",
            "password": "MartilloPassword2026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "accept_aggregate_stats": True,
            "diagnosis": {
                "M10": ["Diferencias en inventario", "No identifica fácilmente la rotación"],
                "M12": ["Existencias y alertas", "Rotación de productos"],
                "M17": "Inventarios y existencias",
                "M07": ["Hojas de cálculo"],
                "M08": ["Hojas de cálculo"],
                "M13": "No",
                "M15": ["Precio"],
            },
        },
    )
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]
    tenant_a_id = res_a.json()["tenant_id"]

    # 2. Registrar Empresa B (Foco Ventas)
    res_b = client.post(
        "/api/auth/register",
        json={
            "legal_name": "Boutique San Pío S.A.S.",
            "subsector": "ropa_calzado_accesorios",
            "size": "pequena",
            "email": "ventas@sanpio.co",
            "full_name": "Laura Rangel",
            "password": "BoutiquePassword2026!",
            "accept_data_policy": True,
            "accept_terms_mvp": True,
            "accept_aggregate_stats": False,
            "diagnosis": {
                "M10": ["Dificultad para analizar ventas", "Demora preparando informes"],
                "M12": ["Ventas por periodo", "Comparación entre periodos", "Tendencias o estimaciones"],
                "M17": "Consulta de ventas e indicadores",
                "M07": ["Software administrativo / ERP"],
                "M08": ["Software administrativo integrado"],
                "M13": "Sí",
                "M15": ["Precio"],
            },
        },
    )
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]
    tenant_b_id = res_b.json()["tenant_id"]
    assert tenant_a_id != tenant_b_id

    # 3. Consultar layout de Empresa A vs Empresa B
    layout_a = client.get("/api/ui/layout", headers={"Authorization": f"Bearer {token_a}"}).json()
    layout_b = client.get("/api/ui/layout", headers={"Authorization": f"Bearer {token_b}"}).json()

    assert layout_a["primary_focus"] == "inventory"
    assert layout_a["hero_row"][0]["widget"] == "stock_alerts"
    assert layout_b["primary_focus"] == "sales"
    assert layout_b["hero_row"][0]["widget"] == "sales_trend"

    # 4. Intento de acceso cruzado: Empresa A intenta leer preferencias de Empresa B pasando tenant_id ajeno
    cross = client.get(
        f"/api/tenants/{tenant_b_id}/preferences",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert cross.status_code in (403, 404)

    # 5. Sobreescritura manual de vista en Empresa A (personalized -> general)
    toggle = client.put(
        "/api/ui/view-mode",
        json={"view_mode": "general"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert toggle.status_code == 200
    assert toggle.json()["view_mode"] == "general"
    assert toggle.json()["primary_focus"] == "balanced"

    # Empresa B sigue viendo su vista personalizada de ventas intacta
    layout_b_after = client.get("/api/ui/layout", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert layout_b_after["view_mode"] == "personalized"
    assert layout_b_after["primary_focus"] == "sales"
