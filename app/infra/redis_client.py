from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from app.infra.redaction import redact_payload

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover - optional dependency fallback
    redis = None

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
_redis_client = None
_in_memory_store: dict[str, tuple[float | None, str]] = {}


@dataclass
class _InMemoryRedis:
    async def setex(self, key: str, ttl_seconds: int, value: str):
        expiry = time.monotonic() + max(int(ttl_seconds), 1)
        _in_memory_store[key] = (expiry, value)

    async def get(self, key: str):
        record = _in_memory_store.get(key)
        if record is None:
            return None

        expiry, value = record
        if expiry is not None and expiry < time.monotonic():
            _in_memory_store.pop(key, None)
            return None
        return value


async def get_redis():
    global _redis_client
    if _redis_client is None:
        if redis is None:
            _redis_client = _InMemoryRedis()
        else:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


class ShortTermMemory:
    @staticmethod
    async def save_conversation(thread_id: str, messages: list, ttl_seconds: int = 86400):
        r = await get_redis()
        key = f"conv:{thread_id}"
        await r.setex(key, ttl_seconds, json.dumps(redact_payload(messages)))

    @staticmethod
    async def load_conversation(thread_id: str) -> list:
        r = await get_redis()
        key = f"conv:{thread_id}"
        data = await r.get(key)
        if data:
            return json.loads(data)
        return []

    @staticmethod
    async def append_message(thread_id: str, role: str, content: str, ttl_seconds: int = 86400):
        messages = await ShortTermMemory.load_conversation(thread_id)
        messages.append({"role": role, "content": redact_payload(content)})
        await ShortTermMemory.save_conversation(thread_id, messages, ttl_seconds)
