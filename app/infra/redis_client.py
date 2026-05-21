import redis.asyncio as redis
import json
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
_redis_client = None

async def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client

class ShortTermMemory:
    @staticmethod
    async def save_conversation(thread_id: str, messages: list, ttl_seconds: int = 86400):
        r = await get_redis()
        key = f"conv:{thread_id}"
        await r.setex(key, ttl_seconds, json.dumps(messages))
    
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
        messages.append({"role": role, "content": content})
        await ShortTermMemory.save_conversation(thread_id, messages, ttl_seconds)