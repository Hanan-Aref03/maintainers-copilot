from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domain.schemas import CurrentUser

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_PBKDF2_ITERATIONS = 260_000


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = hashed_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations_text)
        salt = _b64url_decode(salt_text)
        expected_digest = _b64url_decode(digest_text)
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(candidate, expected_digest)
    except Exception:
        return False


def _jwt_signing_input(payload: dict[str, Any]) -> tuple[str, str, bytes]:
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    header_b64 = _b64url_encode(header_json)
    payload_b64 = _b64url_encode(payload_json)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    return header_b64, payload_b64, signing_input


def create_access_token(
    user_id: UUID | str,
    role: str,
    token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    expiry = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_exp_minutes)
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "tv": int(token_version),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expiry.timestamp()),
    }
    _, payload_b64, signing_input = _jwt_signing_input(payload)
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{signing_input.decode('ascii')}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    provided_signature = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid token signature")

    header = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != settings.jwt_algorithm:
        raise ValueError("Unsupported token algorithm")

    payload = json.loads(_b64url_decode(payload_b64))
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < datetime.now(timezone.utc).timestamp():
        raise ValueError("Token expired")

    return payload


def build_dev_user() -> CurrentUser:
    return CurrentUser(id=_DEV_USER_ID, email="dev@example.com", role="maintainer")


def current_user() -> CurrentUser:
    """Backward-compatible helper for legacy imports."""
    return build_dev_user()
