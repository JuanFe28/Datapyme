import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

@dataclass
class Settings:
    environment: str
    database_url: str
    secret: str
    allowed_hosts: list[str]
    max_upload: int = 10 * 1024 * 1024

    @property
    def production(self): return self.environment == 'production'

    @classmethod
    def from_env(cls, database_url=None):
        load_dotenv(ROOT / '.env', override=False)
        env = os.getenv('APP_ENV', 'local')
        url = database_url or os.getenv('DATABASE_URL', 'sqlite:///' + (ROOT / 'datapyme_local.db').as_posix())
        if url.startswith(('postgres://', 'postgresql://')):
            url = 'postgresql+psycopg://' + url.split('://',1)[1]
        secret = os.getenv('SESSION_SECRET', '')
        hosts = [x.strip() for x in os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(',') if x.strip()]
        if env == 'production':
            if not url.startswith('postgresql+psycopg://'): raise ValueError('Producción requiere PostgreSQL persistente.')
            if len(secret) < 32 or any(x in secret.lower() for x in ('reemplazar','cambiar','example','test-only')):
                raise ValueError('SESSION_SECRET debe ser aleatorio y tener al menos 32 caracteres.')
            if not hosts or any(x in hosts for x in ('*','testserver')): raise ValueError('ALLOWED_HOSTS debe especificar los dominios de producción.')
            if 'sslmode=' not in url: url += ('&' if '?' in url else '?') + 'sslmode=require'
        elif not secret:
            directory = ROOT / '.local'; directory.mkdir(exist_ok=True)
            path = directory / 'session-secret'
            if not path.exists():
                try: path.write_text(secrets.token_urlsafe(48), encoding='utf-8')
                except FileExistsError: pass
            secret = path.read_text(encoding='utf-8').strip()
        return cls(env,url,secret,hosts)
