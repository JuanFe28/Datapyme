import os
import secrets
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    environment: str = "development"

    @classmethod
    def from_env(cls, database_url: str | None = None) -> "Settings":
        url = database_url or os.getenv(
            "DATABASE_URL", f"sqlite:///{(ROOT / 'datapyme_empresarial.db').as_posix()}"
        )
        secret = os.getenv("SESSION_SECRET", secrets.token_urlsafe(32))
        env = os.getenv("APP_ENV", "development")
        return cls(database_url=url, secret_key=secret, environment=env)
