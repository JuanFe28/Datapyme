"""Puente de sincronización automático desde Datapyme Research Studio hacia Datapyme Empresarial."""

import csv
import io
import json
import re
import secrets
import sqlite3
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.models import CompanyUIPreference, Tenant, User, UserViewSetting
from app.core.provisioning_service import DENSITY_LABELS, FOCUS_LABELS
from app.core.security import hash_password
from app.telemetry.impact_service import is_demo_or_synthetic_tenant, normalize_real_subsector
from app.ui.ui_personalization_service import DiagnosisInput, compute_priority_weights

SUBSECTOR_MAP: dict[str, str] = {
    "Alimentos y bebidas": "Alimentos, Postres y Bebidas",
    "Ropa, calzado y accesorios": "Moda, Ropa y Accesorios",
    "Belleza y cuidado personal": "Belleza y Cuidado Personal",
    "Tecnología y electrónicos": "Tecnología y Electrónicos",
    "Ferretería y hogar": "Ferretería y Construcción",
    "Comercio mayorista no especializado": "Comercio Minorista General",
    "Otra actividad comercial": "Comercio Minorista General",
}

SIZE_MAP: dict[str, str] = {
    "Microempresa": "micro",
    "Pequeña": "pequena",
    "Mediana": "mediana",
}

# Los datos de participantes se leen únicamente de una fuente privada explícita.


def normalize_username(trade_name: str, fallback: str = "empresa") -> str:
    """Genera un nombre de usuario corto, único y sin espacios a partir del nombre comercial."""
    ascii_str = "".join(
        c for c in unicodedata.normalize("NFKD", trade_name or "") if not unicodedata.combining(c)
    )
    cleaned = re.sub(r"[^a-z0-9]", "", ascii_str.lower())
    return (cleaned or fallback)[:28]


def make_unique_username(db: Session, base_name: str, existing_user_id: str | None = None) -> str:
    """Garantiza unicidad de `users.username` agregando sufijo numérico solo si colisiona."""
    base = normalize_username(base_name)
    candidate = base
    suffix = 2
    while True:
        found = db.query(User).filter(User.username == candidate).first()
        if not found or (existing_user_id and found.id == existing_user_id):
            return candidate
        candidate = f"{base[:24]}{suffix}"
        suffix += 1


def extract_phone_and_email(detail: str, username: str) -> tuple[str | None, str]:
    """Extrae celular colombiano (10 dígitos) y correo electrónico desde contact.detail."""
    raw = (detail or "").strip()
    phone_match = re.search(r"\b(3\d{9})\b", re.sub(r"[^\d\s@A-Za-z._+-]", "", raw))
    phone = phone_match.group(1) if phone_match else None
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw)
    email = email_match.group(0).lower() if email_match else f"{username}@clientes.datapyme.co"
    return phone, email


def generate_temp_password() -> str:
    """Clave impredecible que se entrega una sola vez; solo se guarda su hash."""
    return secrets.token_urlsafe(24)


def load_companies_from_research_sqlite(sqlite_path: str | Path) -> list[dict[str, Any]]:
    """Lee las empresas con encuesta `mercado` completa desde una BD SQLite de Research Studio."""
    path = Path(sqlite_path)
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.name, c.city, c.size,
                   COALESCE(cc.name, c.name), COALESCE(cc.detail, ''),
                   r.data
            FROM companies c
            JOIN responses r ON r.company_id = c.id
            LEFT JOIN company_contacts cc ON cc.company_id = c.id
            WHERE r.category = 'mercado' AND r.status = 'complete'
            ORDER BY c.id ASC
            """
        ).fetchall()
    finally:
        conn.close()

    results: list[dict[str, Any]] = []
    for cid, name, city, size, owner_name, detail, raw_json in rows:
        if "[DEMO-FDC125]" in (name or ""):
            continue
        ans = json.loads(raw_json) if isinstance(raw_json, str) else (raw_json or {})
        clean_city = "Bucaramanga" if not city or "verificar" in str(city).lower() else str(city)
        results.append(
            {
                "research_company_id": int(cid),
                "trade_name": str(name).strip(),
                "city": clean_city,
                "size": str(size or "Pequeña"),
                "owner_full_name": (str(owner_name).strip() or str(name).strip()),
                "contact_detail": str(detail or "").strip(),
                "answers": ans,
            }
        )
    return results


def _build_whatsapp_handoff(
    *,
    owner_full_name: str,
    trade_name: str,
    username: str,
    phone: str | None,
    email: str,
    temp_password: str,
    focus_label: str,
    density_label: str,
    access_url: str,
) -> str:
    login_link = f"{access_url.rstrip('/')}/login" if access_url else "/login"
    phone_note = f" o {phone}" if phone else ""
    return (
        f"Hola {owner_full_name}, ya está lista tu cuenta privada de Datapyme Empresarial para {trade_name}.\n\n"
        f"Enlace de acceso: {login_link}\n"
        f"Usuario corto: {username}{phone_note}\n"
        f"Correo: {email}\n"
        f"Contraseña temporal: {temp_password}\n"
        f"Configuración adaptada a tu negocio: {focus_label} (Densidad {density_label}).\n\n"
        "Al entrar por primera vez, el sistema te pedirá crear tu contraseña privada, aceptar la "
        "política de privacidad (Ley 1581) y te guiará con un recorrido interactivo de arranque."
    )


def sync_research_companies(
    db: Session,
    *,
    sqlite_path: str | Path | None = None,
    access_url: str = "",
) -> list[dict[str, Any]]:
    """Sincroniza una fuente privada explícita sin inventar empresas ni respuestas."""
    source_rows = (
        load_companies_from_research_sqlite(sqlite_path)
        if sqlite_path and Path(sqlite_path).exists()
        else []
    )
    if not source_rows:
        raise HTTPException(
            status_code=409,
            detail="No hay una fuente privada de investigación con empresas completas. No se crearon cuentas.",
        )

    summary: list[dict[str, Any]] = []
    for item in source_rows:
        cid = int(item["research_company_id"])
        trade_name = str(item["trade_name"]).strip()
        owner_name = str(item.get("owner_full_name") or trade_name).strip()
        ans = item.get("answers") or {}

        raw_sub = str(ans.get("M05") or "Otra actividad comercial")
        subsector = normalize_real_subsector(SUBSECTOR_MAP.get(raw_sub, raw_sub), trade_name)
        size_code = SIZE_MAP.get(str(item.get("size") or "Pequeña"), "pequena")
        municipality = str(item.get("city") or "Bucaramanga").strip()

        diag_in = DiagnosisInput(
            M10=list(ans.get("M10") or []),
            M12=list(ans.get("M12") or []),
            M17=str(ans.get("M17") or ""),
            M07=list(ans.get("M07") or []),
            M08=list(ans.get("M08") or []),
            M13=str(ans.get("M13") or "No"),
            M15=list(ans.get("M15") or []),
        )
        profile = compute_priority_weights(diag_in)

        tenant = db.query(Tenant).filter_by(research_company_id=cid).first()
        if not tenant:
            tenant = db.query(Tenant).filter(Tenant.trade_name == trade_name).first()

        created = False
        if not tenant:
            created = True
            tenant = Tenant(
                legal_name=trade_name,
                trade_name=trade_name,
                subsector=subsector,
                size=size_code,
                municipality=municipality,
                research_company_id=cid,
                onboarding_tour_completed=False,
                research_stats_opt_in=False,
                status="active",
            )
            db.add(tenant)
            db.flush()
        else:
            tenant.research_company_id = cid
            tenant.subsector = subsector

        user = db.query(User).filter_by(tenant_id=tenant.id, role="owner").first()
        base_username = normalize_username(trade_name)
        phone, email = extract_phone_and_email(str(item.get("contact_detail") or ""), base_username)
        temp_password = generate_temp_password()

        if not user:
            unique_username = make_unique_username(db, base_username)
            if db.query(User).filter_by(email=email).first():
                email = f"{unique_username}@clientes.datapyme.co"
            if phone and db.query(User).filter_by(phone=phone).first():
                phone = None
            user = User(
                tenant_id=tenant.id,
                email=email,
                username=unique_username,
                phone=phone,
                full_name=owner_name,
                password_hash=hash_password(temp_password),
                role="owner",
                is_active=True,
                must_change_password=True,
                mfa_enabled=False,
            )
            db.add(user)
            db.flush()
        else:
            if not user.username:
                user.username = make_unique_username(db, base_username, existing_user_id=user.id)
            if phone and not user.phone and not db.query(User).filter_by(phone=phone).first():
                user.phone = phone

        pref = db.query(CompanyUIPreference).filter_by(tenant_id=tenant.id).first()
        weights_dict = {
            "weight_sales": profile.weight_sales,
            "weight_inventory": profile.weight_inventory,
            "weight_predictive": profile.weight_predictive,
        }
        if not pref:
            db.add(
                CompanyUIPreference(
                    tenant_id=tenant.id,
                    source="research_studio_sync",
                    diagnosis_answers=diag_in.to_dict(),
                    mapping_version=profile.mapping_version,
                    priority_weights=weights_dict,
                    weight_sales=Decimal(str(profile.weight_sales)),
                    weight_inventory=Decimal(str(profile.weight_inventory)),
                    weight_predictive=Decimal(str(profile.weight_predictive)),
                    primary_focus=profile.primary_focus,
                    secondary_focus=profile.secondary_focus,
                    preferred_chart_density=profile.preferred_chart_density,
                )
            )
        else:
            pref.diagnosis_answers = diag_in.to_dict()
            pref.priority_weights = weights_dict
            pref.weight_sales = Decimal(str(profile.weight_sales))
            pref.weight_inventory = Decimal(str(profile.weight_inventory))
            pref.weight_predictive = Decimal(str(profile.weight_predictive))
            pref.primary_focus = profile.primary_focus
            pref.secondary_focus = profile.secondary_focus
            pref.preferred_chart_density = profile.preferred_chart_density

        if not db.query(UserViewSetting).filter_by(user_id=user.id, tenant_id=tenant.id).first():
            db.add(UserViewSetting(user_id=user.id, tenant_id=tenant.id, view_mode="personalized"))

        focus_label = FOCUS_LABELS.get(profile.primary_focus, profile.primary_focus)
        density_label = DENSITY_LABELS.get(
            profile.preferred_chart_density, profile.preferred_chart_density
        )
        temp_disp = temp_password if created else "(No recuperable; solicite una nueva clave temporal)"
        summary.append(
            {
                "tenant_id": tenant.id,
                "user_id": user.id,
                "research_company_id": cid,
                "created_now": created,
                "trade_name": trade_name,
                "owner_full_name": user.full_name,
                "username": user.username,
                "phone": user.phone or "",
                "email": user.email,
                "temporary_password": temp_disp,
                "must_change_password": bool(user.must_change_password),
                "mfa_enabled": bool(user.mfa_enabled),
                "primary_focus": profile.primary_focus,
                "primary_focus_label": focus_label,
                "density": profile.preferred_chart_density,
                "density_label": density_label,
                "whatsapp_handoff_text": _build_whatsapp_handoff(
                    owner_full_name=user.full_name,
                    trade_name=trade_name,
                    username=user.username or base_username,
                    phone=user.phone,
                    email=user.email,
                    temp_password=temp_disp,
                    focus_label=focus_label,
                    density_label=density_label,
                    access_url=access_url,
                ),
            }
        )

    db.commit()
    return summary


def list_real_client_credentials(
    db: Session,
    access_url: str = "",
) -> list[dict[str, Any]]:
    """Lista todas las empresas reales (no demos) para gestión de entrega y soporte MFA."""
    tenants = [
        t
        for t in db.query(Tenant)
        .order_by(Tenant.research_company_id.asc().nullslast(), Tenant.created_at.asc())
        .all()
        if not is_demo_or_synthetic_tenant(db, t)
    ]
    rows: list[dict[str, Any]] = []
    for tenant in tenants:
        user = db.query(User).filter_by(tenant_id=tenant.id, role="owner").first()
        if not user:
            continue
        pref = db.query(CompanyUIPreference).filter_by(tenant_id=tenant.id).first()
        focus = pref.primary_focus if pref else "balanced"
        density = pref.preferred_chart_density if pref else "standard"
        focus_label = FOCUS_LABELS.get(focus, focus)
        density_label = DENSITY_LABELS.get(density, density)

        if tenant.research_company_id and user.must_change_password:
            temp_disp = "(No recuperable; solicite una nueva clave temporal)"
        elif user.must_change_password:
            temp_disp = "(Definida al provisionar)"
        else:
            temp_disp = "(Ya activada por cliente)"

        rows.append(
            {
                "tenant_id": tenant.id,
                "user_id": user.id,
                "research_company_id": tenant.research_company_id,
                "trade_name": tenant.trade_name or tenant.legal_name,
                "owner_full_name": user.full_name,
                "username": user.username or "",
                "phone": user.phone or "",
                "email": user.email,
                "temporary_password": temp_disp,
                "must_change_password": bool(user.must_change_password),
                "mfa_enabled": bool(user.mfa_enabled),
                "primary_focus": focus,
                "primary_focus_label": focus_label,
                "density": density,
                "density_label": density_label,
                "whatsapp_handoff_text": _build_whatsapp_handoff(
                    owner_full_name=user.full_name,
                    trade_name=tenant.trade_name or tenant.legal_name,
                    username=user.username or normalize_username(tenant.trade_name or tenant.legal_name),
                    phone=user.phone,
                    email=user.email,
                    temp_password=temp_disp,
                    focus_label=focus_label,
                    density_label=density_label,
                    access_url=access_url,
                ),
            }
        )
    return rows


def build_credentials_report_csv(rows: list[dict[str, Any]]) -> str:
    """Exporta reporte CSV de credenciales de entrega para el equipo investigador."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "ID Research Studio",
            "Empresa",
            "Propietario",
            "Usuario Corto",
            "Celular",
            "Correo",
            "Clave Temporal",
            "Primer Ingreso Pendiente",
            "MFA Activo",
            "Enfoque UI",
            "Densidad",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.get("research_company_id") or "",
                r["trade_name"],
                r["owner_full_name"],
                r["username"],
                r["phone"],
                r["email"],
                r["temporary_password"],
                "Sí" if r["must_change_password"] else "No",
                "Sí" if r["mfa_enabled"] else "No",
                r["primary_focus"],
                r["density"],
            ]
        )
    return buf.getvalue()
