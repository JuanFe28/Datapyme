"""Alta interactiva de un administrador privado desde la consola del servidor."""

from getpass import getpass

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.models import User
from app.core.security import hash_password


def create_private_admin(db: Session, email: str, password: str) -> None:
    email = email.strip().lower()
    if (
        "@" not in email
        or email.startswith("demo.")
        or email == "superadmin.demo@datapyme.co"
        or len(password) < 12
    ):
        raise HTTPException(
            status_code=422,
            detail="Use un correo privado y una contraseña exclusiva de al menos 12 caracteres.",
        )
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(
            status_code=409, detail="La cuenta ya existe; no se modificó su rol ni su clave."
        )
    db.add(
        User(
            email=email,
            full_name="Administrador Datapyme",
            password_hash=hash_password(password),
            tenant_id=None,
            role="superadmin",
            is_active=True,
            must_change_password=False,
        )
    )
    db.commit()


def main() -> None:
    settings = Settings.from_env()
    email = input("Correo del administrador privado: ")
    password = getpass("Contraseña exclusiva (no se muestra): ")
    if password != getpass("Repita la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden; no se creó la cuenta.")
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as db:
            create_private_admin(db, email, password)
        print("Administrador privado creado. Active la verificación en dos pasos al ingresar.")
    except HTTPException as exc:
        raise SystemExit(exc.detail) from exc
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
