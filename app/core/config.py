#Pydantic settings
from pydantic_settings import BaseSettings

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
    jwt_secret: str = "change-me"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()