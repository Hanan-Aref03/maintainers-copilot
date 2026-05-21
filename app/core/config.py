# Pydantic settings

from pydantic import model_validator
from pydantic_settings import BaseSettings

from app.infra.database import normalize_database_url

class Settings(BaseSettings):
    # Vault will inject these, but we set defaults for local dev
    database_url: str = "postgresql://copilot:changeme@db:5432/maintainers"
    redis_url: str = "redis://redis:6379/0"
    vault_addr: str = "http://vault:8200"
    vault_token: str = "devroot"
    minio_endpoint: str = "minio:9000"
    model_server_url: str = "http://model-server:8001"
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"
    gemini_api_key: str = ""
    voyage_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    voyage_embedding_model: str = "voyage-code-2"
    provider_timeout_seconds: float = 30.0
    jwt_secret: str = "change-me"
    cors_allow_origins: str = (
        "http://localhost:3000,"
        "http://localhost:5173,"
        "http://localhost:8080,"
        "http://localhost:8501,"
        "http://127.0.0.1:3000,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:8080,"
        "http://127.0.0.1:8501"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

    @model_validator(mode="after")
    def _normalize_database_url(self):
        self.database_url = normalize_database_url(self.database_url)
        return self

settings = Settings()
