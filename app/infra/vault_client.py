import logging
import os
import hvac
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

class VaultClient:
    _client = None
    _secrets = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            session = requests.Session()
            session.trust_env = False
            cls._client = hvac.Client(
                url=settings.vault_addr,
                token=settings.vault_token,
                session=session,
            )
        return cls._client

    @classmethod
    def load_secrets(cls):
        """Load all secrets from Vault and set them as environment variables."""
        client = cls._get_client()
        try:
            secret = client.secrets.kv.v2.read_secret_version(mount_point="kv", path="copilot")
            cls._secrets = secret["data"]["data"]
            # Set as env vars for easy access by other modules
            for key, value in cls._secrets.items():
                os.environ[key.upper()] = str(value)
            return cls._secrets
        except Exception as e:
            cls._secrets = {}
            logger.warning("Vault secrets unavailable: %s", e)
            return cls._secrets

    @classmethod
    def get_secret(cls, key: str, default=None):
        if cls._secrets is None:
            cls.load_secrets()
        return cls._secrets.get(key, default) if cls._secrets else default

    @classmethod
    def get_gemini_api_key(cls):
        return (
            cls.get_secret("gemini_api_key")
            or os.getenv("GEMINI_API_KEY")
            or cls.get_voyage_api_key()
            or os.getenv("VOYAGE_API_KEY")
        )

    @classmethod
    def get_voyage_api_key(cls):
        return cls.get_secret("voyage_api_key") or os.getenv("VOYAGE_API_KEY")
