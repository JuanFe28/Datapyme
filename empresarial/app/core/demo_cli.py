"""CLI operativa para sembrar o limpiar las empresas demo `[DEMO-FDC125]`.

Uso (dentro del contenedor o con el venv activo):
    python -m app.core.demo_cli seed    # crea 3 empresas + SuperAdmin con contrasenas aleatorias
    python -m app.core.demo_cli clear   # elimina solo las empresas con la etiqueta [DEMO-FDC125]

Las credenciales se imprimen UNA sola vez en la salida estandar y no se almacenan en texto plano.
"""
import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.demo_seed import clear_contrast_demo_tenants, seed_contrast_demo_tenants
from app.core.models import Base


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestion de empresas demo Datapyme Empresarial")
    parser.add_argument("action", choices=["seed", "clear"])
    args = parser.parse_args()

    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        if args.action == "clear":
            print(clear_contrast_demo_tenants(db))
            return
        summary = seed_contrast_demo_tenants(db)

    print("Credenciales de validacion (se muestran una sola vez):")
    for key, data in summary.items():
        print(f"- {key}: {data['email']} / {data['password']}")


if __name__ == "__main__":
    main()
