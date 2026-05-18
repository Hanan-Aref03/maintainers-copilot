#simplified, caches secrets
import os
import hvac
from functools import lru_cache

class VaultClient:
    _client = None
    _secrets = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            cls._client = hvac.Client(
                url=os.getenv("VAULT_ADDR", "http://vault:8200"),
                token=os.getenv("VAULT_TOKEN", "devroot")
            )
        return cls._client

    @classmethod
    def load_secrets(cls):
        """Load all secrets from Vault and set them as environment variables."""
        client = cls._get_client()
        try:
            secret = client.secrets.kv.v2.read_secret_version(path="copilot")
            cls._secrets = secret["data"]["data"]
            # Set as env vars for easy access by other modules
            for key, value in cls._secrets.items():
                os.environ[key.upper()] = str(value)
            return cls._secrets
        except Exception as e:
            raise RuntimeError(f"Failed to load secrets from Vault: {e}")

    @classmethod
    def get_secret(cls, key: str, default=None):
        if cls._secrets is None:
            cls.load_secrets()
        return cls._secrets.get(key, default)

    @classmethod
    def get_gemini_api_key(cls):
        return cls.get_secret("gemini_api_key")
