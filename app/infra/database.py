"""SQLAlchemy base and lazy engine helpers."""

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

_DEFAULT_DATABASE_URL = "postgresql://copilot:changeme@db:5432/maintainers"
_DEFAULT_DB_HOST_PORT = 5433


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def _read_dotenv_value(name: str) -> str | None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")

    return None


def _resolve_db_host_port() -> int:
    raw_value = os.getenv("DB_HOST_PORT") or _read_dotenv_value("DB_HOST_PORT")
    if raw_value is None:
        return _DEFAULT_DB_HOST_PORT

    try:
        port = int(raw_value)
    except ValueError:
        return _DEFAULT_DB_HOST_PORT

    return port if 1 <= port <= 65535 else _DEFAULT_DB_HOST_PORT


def normalize_database_url(url: str) -> str:
    """Rewrite Docker-only hostnames when running on the host machine."""
    try:
        parsed = make_url(url)
    except Exception:
        return url

    if not _running_in_docker() and parsed.get_backend_name() == "postgresql" and parsed.host == "db":
        parsed = parsed.set(host="127.0.0.1", port=_resolve_db_host_port())

    return parsed.render_as_string(hide_password=False)


def resolve_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL") or _read_dotenv_value("DATABASE_URL") or _DEFAULT_DATABASE_URL
    return normalize_database_url(raw_url)


DATABASE_URL = resolve_database_url()

Base = declarative_base()


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_local():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


class _SessionLocalProxy:
    def __call__(self):
        return get_session_local()()


SessionLocal = _SessionLocalProxy()
