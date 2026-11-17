"""Servicio de Autenticación Multifactor (MFA / 2FA) TOTP RFC 6238 gratuito y 100% offline."""

import io
import secrets
from typing import Any

import pyotp
import segno

from app.core.models import User
from app.core.security import sha256_hex


def generate_totp_secret() -> str:
    """Genera secreto Base32 de 160 bits compatible con RFC 6238."""
    return pyotp.random_base32()


def build_totp_uri(secret: str, account_label: str, issuer: str = "Datapyme Empresarial") -> str:
    """Construye la URI otpauth:// estándar para Google/Microsoft Authenticator y Authy."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=account_label, issuer_name=issuer)


def render_qr_svg_inline(uri: str) -> str:
    """Genera el código QR en SVG puro en memoria (sin Pillow ni archivos temporales)."""
    qr = segno.make(uri, micro=False)
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=5, border=2, xmldecl=False, dark="#0F172A", light="#FFFFFF")
    return buf.getvalue().decode("utf-8")


def verify_totp_code(secret: str | None, code: str) -> bool:
    """Valida un código TOTP de 6 dígitos con ventana de tolerancia de +-30 segundos."""
    if not secret:
        return False
    clean_code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(clean_code) != 6:
        return False
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(clean_code, valid_window=1))


def generate_backup_codes(count: int = 5) -> tuple[list[str], list[dict[str, Any]]]:
    """Genera 5 códigos de recuperación legibles (XXXX-XXXX) y su versión hasheada SHA-256."""
    plain_codes: list[str] = []
    stored: list[dict[str, Any]] = []
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    for _ in range(count):
        part_a = "".join(secrets.choice(alphabet) for _ in range(4))
        part_b = "".join(secrets.choice(alphabet) for _ in range(4))
        raw = f"{part_a}-{part_b}"
        plain_codes.append(raw)
        stored.append({"hash": sha256_hex(raw.replace("-", "")), "used": False})
    return plain_codes, stored


def verify_or_consume_backup_code(user: User, code: str) -> bool:
    """Verifica y consume (un solo uso) un código de respaldo si es válido."""
    normalized = "".join(ch for ch in (code or "").upper() if ch.isalnum())
    if len(normalized) < 8 or not user.mfa_backup_codes:
        return False
    candidate_hash = sha256_hex(normalized)
    updated_codes: list[dict[str, Any]] = []
    matched = False
    for entry in list(user.mfa_backup_codes):
        if isinstance(entry, dict) and not entry.get("used") and entry.get("hash") == candidate_hash:
            updated_codes.append({"hash": entry["hash"], "used": True})
            matched = True
        else:
            updated_codes.append(
                dict(entry) if isinstance(entry, dict) else {"hash": str(entry), "used": True}
            )
    if matched:
        user.mfa_backup_codes = updated_codes
    return matched
