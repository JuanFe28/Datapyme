"""Puente de sincronización automático desde Datapyme Research Studio hacia Datapyme Empresarial."""

import csv
import io
import json
import re
import sqlite3
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.models import CompanyUIPreference, Tenant, User, UserViewSetting
from app.core.provisioning_service import DENSITY_LABELS, FOCUS_LABELS
from app.core.security import hash_password
from app.ui.ui_personalization_service import DiagnosisInput, compute_priority_weights

SUBSECTOR_MAP: dict[str, str] = {
    "Alimentos y bebidas": "minimercado",
    "Ropa, calzado y accesorios": "boutique",
    "Belleza y cuidado personal": "belleza",
    "Tecnología y electrónicos": "tecnologia",
    "Ferretería y hogar": "ferreteria",
    "Comercio mayorista no especializado": "mayorista",
    "Otra actividad comercial": "general",
}

SIZE_MAP: dict[str, str] = {
    "Microempresa": "micro",
    "Pequeña": "pequena",
    "Mediana": "mediana",
}

# Catálogo exacto de las 13 empresas reales con encuesta de mercado completa en Research Studio
PRODUCTION_SURVEYED_COMPANIES: list[dict[str, Any]] = [
    {
        "research_company_id": 4,
        "trade_name": "VaFel Sweet",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Valentina Naranjo",
        "contact_detail": "3052621817",
        "answers": {
            "M05": "Alimentos y bebidas",
            "M07": ["Hojas de cálculo"],
            "M08": ["Hojas de cálculo"],
            "M10": ["Demora preparando informes"],
            "M12": [
                "Ventas por periodo",
                "Productos más y menos vendidos",
                "Comparación entre periodos",
            ],
            "M13": "No",
            "M15": ["Precio"],
            "M17": "Consulta de ventas e indicadores",
        },
    },
    {
        "research_company_id": 5,
        "trade_name": "Eat healthy",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Laura Sofía Fandiño Bautista",
        "contact_detail": "3133063165",
        "answers": {
            "M05": "Alimentos y bebidas",
            "M07": [
                "Registros manuales",
                "Hojas de cálculo",
                "Facturación / punto de venta",
                "Software administrativo / ERP",
                "Comercio electrónico",
            ],
            "M08": ["Registros manuales", "Hojas de cálculo"],
            "M10": [
                "Datos dispersos",
                "No identifica fácilmente la rotación",
                "Información desactualizada",
            ],
            "M12": [
                "Productos más y menos vendidos",
                "Rotación de productos",
                "Comparación entre periodos",
            ],
            "M13": "No",
            "M15": ["Precio", "Tiempo de implementación", "Falta de soporte / capacitación"],
            "M17": "Rotación de productos",
        },
    },
    {
        "research_company_id": 7,
        "trade_name": "BV Elixir",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Brandon Stiven Velasco Molina",
        "contact_detail": "3053782020",
        "answers": {
            "M05": "Belleza y cuidado personal",
            "M07": ["Registros manuales", "Hojas de cálculo"],
            "M08": ["Registros manuales", "Hojas de cálculo"],
            "M10": [
                "Datos dispersos",
                "No identifica fácilmente la rotación",
                "Demora preparando informes",
            ],
            "M12": [
                "Productos más y menos vendidos",
                "Rotación de productos",
                "Comparación entre periodos",
            ],
            "M13": "No",
            "M15": ["Precio", "Falta de conocimientos tecnológicos", "Tiempo de implementación"],
            "M17": "Inventarios y existencias",
        },
    },
    {
        "research_company_id": 8,
        "trade_name": "My Dulce Encanto",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Carol Molina",
        "contact_detail": "Velascobrandon1908@gmail.com",
        "answers": {
            "M05": "Belleza y cuidado personal",
            "M07": ["Registros manuales", "Hojas de cálculo"],
            "M08": ["Registros manuales", "Hojas de cálculo"],
            "M10": [
                "Datos dispersos",
                "No identifica fácilmente la rotación",
                "Diferencias en inventario",
            ],
            "M12": ["Ventas por periodo", "Productos más y menos vendidos", "Rotación de productos"],
            "M13": "No",
            "M15": ["Precio", "Falta de conocimientos tecnológicos", "Falta de soporte / capacitación"],
            "M17": "Inventarios y existencias",
        },
    },
    {
        "research_company_id": 9,
        "trade_name": "Susifashion",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Azucena Castillo",
        "contact_detail": "3133967722",
        "answers": {
            "M05": "Ropa, calzado y accesorios",
            "M07": ["Registros manuales"],
            "M08": ["Registros manuales"],
            "M10": ["No enfrenta dificultades relevantes"],
            "M12": ["Rotación de productos"],
            "M13": "No",
            "M15": ["Ninguno"],
            "M17": "Ninguna de las anteriores",
        },
    },
    {
        "research_company_id": 10,
        "trade_name": "Cookie Bites",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Maria Paula Castañeda",
        "contact_detail": "3156925655",
        "answers": {
            "M05": "Alimentos y bebidas",
            "M07": ["Registros manuales"],
            "M08": ["Registros manuales"],
            "M10": ["No enfrenta dificultades relevantes"],
            "M12": ["Ventas por periodo"],
            "M13": "No",
            "M15": ["Precio", "Falta de conocimientos tecnológicos", "Tiempo de implementación"],
            "M17": "Consulta de ventas e indicadores",
        },
    },
    {
        "research_company_id": 11,
        "trade_name": "Ghostline",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Juan Felipe Leon Efres",
        "contact_detail": "3236181171",
        "answers": {
            "M05": "Ropa, calzado y accesorios",
            "M07": ["Registros manuales"],
            "M08": ["Registros manuales"],
            "M10": ["Datos dispersos", "Información desactualizada"],
            "M12": ["Ventas por periodo"],
            "M13": "No",
            "M15": ["Confidencialidad y seguridad"],
            "M17": "Tendencias o estimaciones",
        },
    },
    {
        "research_company_id": 12,
        "trade_name": "Style Stamp",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Valentina Carreño",
        "contact_detail": "3212440920",
        "answers": {
            "M05": "Ropa, calzado y accesorios",
            "M07": ["Registros manuales", "Hojas de cálculo"],
            "M08": ["No lleva control sistemático"],
            "M10": [
                "Datos dispersos",
                "No identifica fácilmente la rotación",
                "Información desactualizada",
            ],
            "M12": ["Ventas por periodo", "Rotación de productos", "Tablero resumen de indicadores"],
            "M13": "No está seguro",
            "M15": ["Precio"],
            "M17": "Inventarios y existencias",
        },
    },
    {
        "research_company_id": 13,
        "trade_name": "Sala de belleza Nancy Spa",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Nancy Marlene Bonna García",
        "contact_detail": "3108057903",
        "answers": {
            "M05": "Belleza y cuidado personal",
            "M07": ["Registros manuales"],
            "M08": ["Registros manuales"],
            "M10": ["No enfrenta dificultades relevantes"],
            "M12": ["Tendencias o estimaciones"],
            "M13": "No",
            "M15": ["Falta de conocimientos tecnológicos"],
            "M17": "Inventarios y existencias",
        },
    },
    {
        "research_company_id": 14,
        "trade_name": "Matilde",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Anderson Martinez",
        "contact_detail": "3043613953",
        "answers": {
            "M05": "Alimentos y bebidas",
            "M07": ["Facturación / punto de venta"],
            "M08": ["Software administrativo integrado"],
            "M10": ["No identifica fácilmente la rotación", "Demora preparando informes"],
            "M12": ["Productos más y menos vendidos", "Existencias y alertas", "Rotación de productos"],
            "M13": "No",
            "M15": ["Precio", "Tiempo de implementación", "Integración de datos"],
            "M17": "Consulta de ventas e indicadores",
        },
    },
    {
        "research_company_id": 15,
        "trade_name": "Bioasesores sas",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Luis Carlos Rincón Delgado",
        "contact_detail": "3222542932",
        "answers": {
            "M05": "Otra actividad comercial",
            "M07": ["Hojas de cálculo", "Facturación / punto de venta"],
            "M08": ["Hojas de cálculo"],
            "M10": [
                "Información desactualizada",
                "Dificultad para analizar ventas",
                "Demora preparando informes",
            ],
            "M12": [
                "Ventas por periodo",
                "Productos más y menos vendidos",
                "Tablero resumen de indicadores",
            ],
            "M13": "No",
            "M15": [
                "Falta de conocimientos tecnológicos",
                "Tiempo de implementación",
                "Falta de soporte / capacitación",
            ],
            "M17": "Inventarios y existencias",
        },
    },
    {
        "research_company_id": 16,
        "trade_name": "El esquinazo de los remates",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Lucia Castellanos",
        "contact_detail": "3185086362",
        "answers": {
            "M05": "Otra actividad comercial",
            "M07": ["Registros manuales"],
            "M08": ["Registros manuales"],
            "M10": ["No identifica fácilmente la rotación"],
            "M12": ["Productos más y menos vendidos", "Rotación de productos"],
            "M13": "No",
            "M15": ["Tiempo de implementación"],
            "M17": "Rotación de productos",
        },
    },
    {
        "research_company_id": 17,
        "trade_name": "La Bodega Virtual",
        "city": "Bucaramanga",
        "size": "Pequeña",
        "owner_full_name": "Sebastián Camacho",
        "contact_detail": "3151279284",
        "answers": {
            "M05": "Ropa, calzado y accesorios",
            "M07": [
                "Registros manuales",
                "Hojas de cálculo",
                "Facturación / punto de venta",
                "Software administrativo / ERP",
            ],
            "M08": ["Registros manuales", "Hojas de cálculo", "Software de inventarios"],
            "M10": ["Información desactualizada", "Herramientas costosas o complejas"],
            "M12": [
                "Ventas por periodo",
                "Productos más y menos vendidos",
                "Tablero resumen de indicadores",
            ],
            "M13": "No",
            "M15": [
                "Falta de conocimientos tecnológicos",
                "Tiempo de implementación",
                "Falta de soporte / capacitación",
            ],
            "M17": "Inventarios y existencias",
        },
    },
]


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


def generate_deterministic_temp_password(username: str, research_company_id: int) -> str:
    """Contraseña temporal limpia y reproducible de mínimo 10 caracteres."""
    prefix = re.sub(r"[^a-zA-Z]", "", username)[:6].capitalize() or "Cliente"
    return f"Dp{prefix}{2026 + research_company_id}!"


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
    access_url: str = "https://driving-where-bicycle-indiana.trycloudflare.com",
) -> list[dict[str, Any]]:
    """Sincroniza idempotente las 13 empresas reales hacia Datapyme Empresarial (en cero)."""
    source_rows = (
        load_companies_from_research_sqlite(sqlite_path)
        if sqlite_path and Path(sqlite_path).exists()
        else []
    )
    if not source_rows:
        source_rows = PRODUCTION_SURVEYED_COMPANIES

    summary: list[dict[str, Any]] = []
    for item in source_rows:
        cid = int(item["research_company_id"])
        trade_name = str(item["trade_name"]).strip()
        owner_name = str(item.get("owner_full_name") or trade_name).strip()
        ans = item.get("answers") or {}

        raw_sub = str(ans.get("M05") or "Otra actividad comercial")
        subsector = SUBSECTOR_MAP.get(raw_sub, "general")
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
            if not tenant.subsector:
                tenant.subsector = subsector

        user = db.query(User).filter_by(tenant_id=tenant.id, role="owner").first()
        base_username = normalize_username(trade_name)
        phone, email = extract_phone_and_email(str(item.get("contact_detail") or ""), base_username)
        temp_password = generate_deterministic_temp_password(base_username, cid)

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
        temp_disp = temp_password if user.must_change_password else "(Ya activada por cliente)"
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
    access_url: str = "https://driving-where-bicycle-indiana.trycloudflare.com",
) -> list[dict[str, Any]]:
    """Lista todas las empresas reales (no demos) para gestión de entrega y soporte MFA."""
    tenants = (
        db.query(Tenant)
        .filter(~Tenant.legal_name.like("[DEMO-FDC125]%"))
        .order_by(Tenant.research_company_id.asc().nullslast(), Tenant.created_at.asc())
        .all()
    )
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
            temp_disp = generate_deterministic_temp_password(
                normalize_username(tenant.trade_name or tenant.legal_name),
                int(tenant.research_company_id),
            )
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
