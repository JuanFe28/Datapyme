"""Tests Unitarios para Verificación en Dos Pasos (MFA / TOTP RFC 6238 y Respaldos)."""

import pyotp

from app.core.mfa_service import (
    build_totp_uri,
    generate_backup_codes,
    generate_totp_secret,
    render_qr_svg_inline,
    verify_or_consume_backup_code,
    verify_totp_code,
)
from app.core.models import User


def test_totp_rfc6238_qr_svg_and_backup_codes():
    secret = generate_totp_secret()
    assert len(secret) >= 32

    uri = build_totp_uri(secret, "vafelsweet")
    assert uri.startswith("otpauth://totp/")
    assert "Datapyme" in uri

    svg = render_qr_svg_inline(uri)
    assert "<svg" in svg
    assert "</svg>" in svg

    valid_code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret, valid_code) is True
    assert verify_totp_code(secret, "000000") in (False, valid_code == "000000")
    assert verify_totp_code(secret, "abc") is False

    plain_codes, hashed_codes = generate_backup_codes(count=5)
    assert len(plain_codes) == 5
    assert len(hashed_codes) == 5

    user = User(
        email="vafel@datapyme.co",
        full_name="Valentina",
        password_hash="x",
        role="owner",
        mfa_enabled=True,
        mfa_secret=secret,
        mfa_backup_codes=hashed_codes,
    )

    first_backup = plain_codes[0]
    assert verify_or_consume_backup_code(user, first_backup) is True
    # Segundo uso del mismo código de respaldo debe fallar (un solo uso)
    assert verify_or_consume_backup_code(user, first_backup) is False
    # Código distinto aún válido
    assert verify_or_consume_backup_code(user, plain_codes[1].replace("-", "").lower()) is True
