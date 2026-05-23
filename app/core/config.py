"""Runtime settings for the application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.infra.database import normalize_database_url

_DEFAULT_DATABASE_URL = "postgresql://copilot:changeme@db:5432/maintainers"
_DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://localhost:3000,"
    "http://localhost:5173,"
    "http://localhost:8080,"
    "http://localhost:8501,"
    "http://127.0.0.1:3000,"
    "http://127.0.0.1:5173,"
    "http://127.0.0.1:8080,"
    "http://127.0.0.1:8501"
)


def _read_dotenv_values() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in values:
            values[key] = value
    return values


_DOTENV_VALUES = _read_dotenv_values()


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name) or _DOTENV_VALUES.get(name) or default


def _get_int_env(name: str, default: int) -> int:
    raw = _get_env(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    raw = _get_env(name, "")
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # Vault will inject these, but we set defaults for local dev
    database_url: str = normalize_database_url(_get_env("DATABASE_URL", _DEFAULT_DATABASE_URL))
    redis_url: str = _get_env("REDIS_URL", "redis://redis:6379/0")
    vault_addr: str = _get_env("VAULT_ADDR", "http://vault:8200")
    vault_token: str = _get_env("VAULT_TOKEN", "devroot")
    jwt_algorithm: str = _get_env("JWT_ALGORITHM", "HS256")
    access_token_exp_minutes: int = _get_int_env("ACCESS_TOKEN_EXP_MINUTES", 60 * 24)
    short_term_memory_ttl_seconds: int = _get_int_env("SHORT_TERM_MEMORY_TTL_SECONDS", 60 * 60 * 24)
    minio_endpoint: str = _get_env("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = _get_env("MINIO_ACCESS_KEY", _get_env("MINIO_ROOT_USER", "minioadmin"))
    minio_secret_key: str = _get_env("MINIO_SECRET_KEY", _get_env("MINIO_ROOT_PASSWORD", "minioadmin"))
    minio_bucket: str = _get_env("MINIO_BUCKET", "copilot-attachments")
    minio_model_bucket: str = _get_env("MINIO_MODEL_BUCKET", "copilot-model-artifacts")
    minio_eval_bucket: str = _get_env("MINIO_EVAL_BUCKET", "copilot-eval-artifacts")
    minio_snapshot_bucket: str = _get_env("MINIO_SNAPSHOT_BUCKET", "copilot-conversation-snapshots")
    minio_region: str = _get_env("MINIO_REGION", "us-east-1")
    max_attachment_bytes: int = _get_int_env("MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024)
    max_conversation_snapshots: int = _get_int_env("MAX_CONVERSATION_SNAPSHOTS", 25)
    model_server_url: str = _get_env("MODEL_SERVER_URL", "http://model-server:8001")
    otel_exporter_otlp_endpoint: str = _get_env("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    gemini_api_key: str = _get_env("GEMINI_API_KEY", "")
    voyage_api_key: str = _get_env("VOYAGE_API_KEY", "")
    gemini_model: str = _get_env("GEMINI_MODEL", "gemini-2.5-flash")
    voyage_embedding_model: str = _get_env("VOYAGE_EMBEDDING_MODEL", "voyage-code-2")
    provider_timeout_seconds: float = float(_get_env("PROVIDER_TIMEOUT_SECONDS", "30.0") or 30.0)
    jwt_secret: str = _get_env("JWT_SECRET", "change-me")
    cors_allow_origins: str = _get_env("CORS_ALLOW_ORIGINS", _DEFAULT_CORS_ALLOW_ORIGINS)
    bootstrap_demo_data: bool = _get_bool_env("BOOTSTRAP_DEMO_DATA", True)
    bootstrap_admin_email: str = _get_env("BOOTSTRAP_ADMIN_EMAIL", "admin@copilot.local")
    bootstrap_admin_password: str = _get_env("BOOTSTRAP_ADMIN_PASSWORD", "AdminDemo123!")
    demo_widget_public_id: str = _get_env("DEMO_WIDGET_PUBLIC_ID", "demo123")
    demo_widget_allowed_origins: str = _get_env(
        "DEMO_WIDGET_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    demo_widget_greeting: str = _get_env(
        "DEMO_WIDGET_GREETING",
        "Hi! How can I help with issue triage?",
    )
    fine_tuned_model_dir: str = _get_env("FINE_TUNED_MODEL_DIR", "artifacts/classification")

    def __post_init__(self) -> None:
        self.database_url = normalize_database_url(self.database_url)


settings = Settings()
