"""Servicio de aprovisionamiento para entrega de perfiles a empresas reales (F-DC-124 / F-DC-125)."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.commercial_service import create_product_with_initial_stock
from app.core.models import (
    CompanyTaxChange,
    CompanyUIPreference,
    LegalConsent,
    Tenant,
    User,
    UserViewSetting,
    utcnow,
)
from app.core.security import compute_consent_row_hash, hash_password, sha256_hex
from app.ui.ui_personalization_service import DiagnosisInput, compute_priority_weights

FOCUS_LABELS: dict[str, str] = {
    "sales": "Prioridad en Ventas y Rentabilidad",
    "inventory": "Prioridad en Inventarios y Rotación",
    "predictive": "Prioridad en Proyección Estadística",
    "balanced": "Enfoque Balanceado (3 áreas)",
}

DENSITY_LABELS: dict[str, str] = {
    "simple": "Compacta / Esencial",
    "standard": "Estándar",
    "detailed": "Detallada / Completa",
}

STARTER_CATALOGS: dict[str, list[dict[str, Any]]] = {
    "ferreteria_hogar": [
        (
            "FER-001",
            "Cemento Gris 50kg (Ejemplo)",
            "Construcción",
            "bulto",
            "22500",
            "31000",
            "19.00",
            "20",
            "5",
        ),
        (
            "FER-002",
            "Taladro Percutor 650W (Ejemplo)",
            "Herramientas",
            "und",
            "145000",
            "215000",
            "19.00",
            "6",
            "2",
        ),
        (
            "FER-003",
            "Pintura Vinilo Blanco 5Gal (Ejemplo)",
            "Pinturas",
            "cuñete",
            "98000",
            "142000",
            "19.00",
            "10",
            "3",
        ),
    ],
    "ropa_calzado_accesorios": [
        (
            "MOD-001",
            "Camiseta Algodón Básica (Ejemplo)",
            "Prendas",
            "und",
            "18000",
            "38000",
            "19.00",
            "24",
            "6",
        ),
        (
            "MOD-002",
            "Jean Clásico Hombre/Mujer (Ejemplo)",
            "Pantalones",
            "und",
            "48000",
            "95000",
            "19.00",
            "16",
            "4",
        ),
        (
            "MOD-003",
            "Tenis Deportivos Urbanos (Ejemplo)",
            "Calzado",
            "par",
            "72000",
            "139000",
            "19.00",
            "12",
            "3",
        ),
    ],
    "minimercado_alimentos": [
        (
            "ALI-001",
            "Arroz Blanco Premium 1kg (Ejemplo)",
            "Despensa",
            "und",
            "3200",
            "4600",
            "0.00",
            "50",
            "12",
        ),
        (
            "ALI-002",
            "Aceite Vegetal 1L (Ejemplo)",
            "Despensa",
            "und",
            "6800",
            "9400",
            "19.00",
            "30",
            "8",
        ),
        (
            "ALI-003",
            "Café Molido Tradicional 500g (Ejemplo)",
            "Bebidas",
            "und",
            "14200",
            "20500",
            "5.00",
            "25",
            "6",
        ),
    ],
    "cafe_restaurante": [
        (
            "GAS-001",
            "Café Espresso / Americano (Ejemplo)",
            "Bebidas",
            "und",
            "1400",
            "4500",
            "0.00",
            "100",
            "20",
        ),
        (
            "GAS-002",
            "Almuerzo Ejecutivo del Día (Ejemplo)",
            "Platos",
            "und",
            "9200",
            "17500",
            "0.00",
            "40",
            "10",
        ),
        (
            "GAS-003",
            "Pastel / Panadería Artesanal (Ejemplo)",
            "Repostería",
            "und",
            "2800",
            "6500",
            "5.00",
            "30",
            "8",
        ),
    ],
    "general": [
        (
            "GEN-001",
            "Producto Principal A (Ejemplo)",
            "General",
            "und",
            "12000",
            "20000",
            "19.00",
            "20",
            "5",
        ),
        (
            "GEN-002",
            "Producto Principal B (Ejemplo)",
            "General",
            "und",
            "8500",
            "15000",
            "19.00",
            "15",
            "4",
        ),
    ],
}


def record_legal_consents_chain(
    db: Session,
    tenant_id: str,
    user_id: str,
    accept_aggregate_stats: bool,
    ip_raw: str,
    ua_raw: str,
) -> None:
    """Registra la cadena inmutable SHA-256 de consentimientos (Ley 1581 de 2012)."""
    ip_h = sha256_hex(ip_raw or "127.0.0.1")
    ua_h = sha256_hex(ua_raw or "browser")
    latest = (
        db.query(LegalConsent)
        .filter_by(tenant_id=tenant_id)
        .order_by(LegalConsent.accepted_at.desc(), LegalConsent.id.desc())
        .first()
    )
    prev_h = latest.row_hash if latest else ("0" * 64)

    docs = [
        ("data_policy", "v1.0", "accept"),
        ("terms_mvp", "v1.0", "accept"),
        ("aggregate_stats_research", "v1.0", "accept" if accept_aggregate_stats else "revoke"),
    ]
    for idx, (doc_type, doc_ver, action) in enumerate(docs):
        ts = utcnow() + timedelta(milliseconds=idx)
        doc_sha = sha256_hex(f"{doc_type}:{doc_ver}")
        row_h = compute_consent_row_hash(
            tenant_id=tenant_id,
            user_id=user_id,
            document_type=doc_type,
            document_version=doc_ver,
            document_sha256=doc_sha,
            action=action,
            accepted_iso=ts.isoformat(),
            prev_hash=prev_h,
        )
        db.add(
            LegalConsent(
                tenant_id=tenant_id,
                user_id=user_id,
                document_type=doc_type,
                document_version=doc_ver,
                document_sha256=doc_sha,
                action=action,
                accepted_at=ts,
                ip_hash=ip_h,
                user_agent_hash=ua_h,
                prev_hash=prev_h,
                row_hash=row_h,
            )
        )
        prev_h = row_h


def diagnosis_for_target_focus(priority_focus: str, density: str) -> DiagnosisInput:
    """Construye un DiagnosisInput determinista que mapea al foco y densidad deseados."""
    if density == "simple":
        m07, m13 = ["Papel / cuaderno"], "No"
    elif density == "detailed":
        m07, m13 = ["Software administrativo integrado"], "No"
    else:
        m07, m13 = ["Hojas de cálculo"], "No"

    if priority_focus == "sales":
        return DiagnosisInput(
            M10=["Dificultad para analizar ventas", "Demora preparando informes"],
            M12=["Ventas por periodo", "Comparación entre periodos"],
            M17="Consulta de ventas e indicadores",
            M07=m07,
            M13=m13,
        )
    if priority_focus == "inventory":
        return DiagnosisInput(
            M10=["Diferencias en inventario", "No identifica fácilmente la rotación"],
            M12=["Existencias y alertas", "Rotación de productos"],
            M17="Inventarios y existencias",
            M07=m07,
            M13=m13,
        )
    if priority_focus == "predictive":
        return DiagnosisInput(
            M10=[],
            M12=["Tendencias o estimaciones"],
            M17="Tendencias o estimaciones",
            M07=m07,
            M13=m13,
        )
    return DiagnosisInput(
        M10=[],
        M12=["Ventas por periodo", "Existencias y alertas", "Tendencias o estimaciones"],
        M17="",
        M07=m07,
        M13=m13,
    )


def provision_real_client_tenant(
    db: Session,
    *,
    trade_name: str,
    legal_name: str | None,
    subsector: str,
    size: str,
    municipality: str,
    owner_full_name: str,
    email: str,
    temporary_password: str,
    priority_focus: str = "balanced",
    density: str = "standard",
    tax_status: str = "pending",
    starter_catalog: bool = False,
    access_url: str = "",
    phone: str | None = None,
) -> dict[str, Any]:
    """Crea una PyME cliente real con contraseña temporal (`must_change_password=True`)."""
    from app.core.research_sync_service import extract_phone_and_email, make_unique_username

    norm_email = email.strip().lower()
    if db.query(User).filter_by(email=norm_email).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta registrada con ese correo.")
    if len(temporary_password) < 10:
        raise HTTPException(
            status_code=422, detail="La contraseña temporal debe tener al menos 10 caracteres."
        )

    clean_trade = trade_name.strip()
    clean_legal = (legal_name or clean_trade).strip()
    norm_phone, _ = extract_phone_and_email(phone or "", "cliente")
    if norm_phone and db.query(User).filter_by(phone=norm_phone).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta registrada con ese celular.")

    tenant = Tenant(
        legal_name=clean_legal,
        trade_name=clean_trade,
        subsector=subsector.strip() or "general",
        size=size,
        municipality=municipality.strip() or "Bucaramanga",
        onboarding_tour_completed=False,
        research_stats_opt_in=False,
        status="active",
    )
    db.add(tenant)
    db.flush()

    username = make_unique_username(db, clean_trade)
    user = User(
        tenant_id=tenant.id,
        email=norm_email,
        username=username,
        phone=norm_phone,
        full_name=owner_full_name.strip(),
        password_hash=hash_password(temporary_password),
        role="owner",
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()

    if tax_status in ("responsible", "not_responsible"):
        db.add(
            CompanyTaxChange(
                tenant_id=tenant.id,
                revision=1,
                status=tax_status,
                reason="Condición inicial configurada en entrega de perfil",
                changed_by=user.id,
            )
        )

    diag_in = diagnosis_for_target_focus(priority_focus, density)
    profile = compute_priority_weights(diag_in)
    db.add(
        CompanyUIPreference(
            tenant_id=tenant.id,
            source="survey_provisioning",
            diagnosis_answers=diag_in.to_dict(),
            mapping_version=profile.mapping_version,
            priority_weights={
                "weight_sales": profile.weight_sales,
                "weight_inventory": profile.weight_inventory,
                "weight_predictive": profile.weight_predictive,
            },
            weight_sales=Decimal(str(profile.weight_sales)),
            weight_inventory=Decimal(str(profile.weight_inventory)),
            weight_predictive=Decimal(str(profile.weight_predictive)),
            primary_focus=profile.primary_focus,
            secondary_focus=profile.secondary_focus,
            preferred_chart_density=profile.preferred_chart_density,
        )
    )
    db.add(UserViewSetting(user_id=user.id, tenant_id=tenant.id, view_mode="personalized"))

    seeded_count = 0
    if starter_catalog:
        rows = STARTER_CATALOGS.get(subsector, STARTER_CATALOGS["general"])
        for sku, name, cat, unit, cost_s, price_s, vat_s, stock_s, min_s in rows:
            create_product_with_initial_stock(
                db=db,
                tenant_id=tenant.id,
                user_id=user.id,
                sku=sku,
                name=name,
                category=cat,
                unit=unit,
                cost_price=Decimal(cost_s),
                sale_price=Decimal(price_s),
                vat_rate=Decimal(vat_s),
                initial_stock=Decimal(stock_s),
                min_stock=Decimal(min_s),
            )
            seeded_count += 1

    db.commit()

    focus_label = FOCUS_LABELS.get(profile.primary_focus, profile.primary_focus)
    density_label = DENSITY_LABELS.get(profile.preferred_chart_density, profile.preferred_chart_density)
    login_link = f"{access_url.rstrip('/')}/login" if access_url else "/login"
    whatsapp_msg = (
        f"Hola {owner_full_name.strip()}, te entregamos el acceso personalizado a Datapyme Empresarial "
        f"para {clean_trade}.\n\n"
        f"Enlace de acceso: {login_link}\n"
        f"Usuario corto: {username}\n"
        f"Correo: {norm_email}\n"
        f"Clave temporal: {temporary_password}\n"
        f"Configuracion adaptativa: {focus_label} (Densidad {density_label}).\n\n"
        "En tu primer ingreso el sistema te pedira crear tu clave privada definitiva y aceptar "
        "la politica de tratamiento de datos (Ley 1581)."
    )

    return {
        "tenant_id": tenant.id,
        "user_id": user.id,
        "trade_name": clean_trade,
        "username": username,
        "phone": norm_phone,
        "email": norm_email,
        "must_change_password": True,
        "primary_focus": profile.primary_focus,
        "primary_focus_label": focus_label,
        "density": profile.preferred_chart_density,
        "density_label": density_label,
        "starter_products_created": seeded_count,
        "whatsapp_handoff_text": whatsapp_msg,
    }


def main_cli() -> None:
    import argparse

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import Settings
    from app.core.models import Base

    parser = argparse.ArgumentParser(description="Provisionar perfil de empresa cliente real")
    parser.add_argument("--trade-name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--owner-name", required=True)
    parser.add_argument("--temp-password", required=True)
    parser.add_argument("--subsector", default="general")
    parser.add_argument(
        "--focus", default="balanced", choices=["sales", "inventory", "predictive", "balanced"]
    )
    parser.add_argument("--density", default="standard", choices=["simple", "standard", "detailed"])
    parser.add_argument("--starter-catalog", action="store_true")
    parser.add_argument("--url", default="https://driving-where-bicycle-indiana.trycloudflare.com")
    args = parser.parse_args()

    engine = create_engine(Settings.from_env().database_url)
    Base.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        res = provision_real_client_tenant(
            db,
            trade_name=args.trade_name,
            legal_name=args.trade_name,
            subsector=args.subsector,
            size="micro",
            municipality="Bucaramanga",
            owner_full_name=args.owner_name,
            email=args.email,
            temporary_password=args.temp_password,
            priority_focus=args.focus,
            density=args.density,
            starter_catalog=args.starter_catalog,
            access_url=args.url,
        )
        print(res["whatsapp_handoff_text"])


if __name__ == "__main__":
    main_cli()
