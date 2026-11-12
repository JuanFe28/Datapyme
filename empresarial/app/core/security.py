"""Seguridad criptográfica: Argon2id, tokens de sesión y cadena SHA-256 de consentimientos."""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_ph = PasswordHasher(time_cost=2, memory_cost=32768, parallelism=2)


def hash_password(password: str) -> str:
    if not (10 <= len(password) <= 512):
        raise ValueError("La contraseña debe tener entre 10 y 512 caracteres.")
    return _ph.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return _ph.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_session_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(36)
    return raw, sha256_hex(raw)


def compute_consent_row_hash(
    tenant_id: str,
    user_id: str,
    document_type: str,
    document_version: str,
    document_sha256: str,
    action: str,
    accepted_iso: str,
    prev_hash: str,
) -> str:
    payload = f"{tenant_id}|{user_id}|{document_type}|{document_version}|{document_sha256}|{action}|{accepted_iso}|{prev_hash}"
    return sha256_hex(payload)
