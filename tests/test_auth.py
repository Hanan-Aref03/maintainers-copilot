from datetime import timedelta

from app.core.config import settings
from app.infra.auth import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip():
    hashed = hash_password("Maintainer123!")

    assert verify_password("Maintainer123!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_round_trip(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "unit-test-secret")
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")

    token = create_access_token("00000000-0000-0000-0000-000000000123", "admin", 2, timedelta(minutes=5))
    claims = decode_access_token(token)

    assert claims["sub"] == "00000000-0000-0000-0000-000000000123"
    assert claims["role"] == "admin"
    assert claims["tv"] == 2

