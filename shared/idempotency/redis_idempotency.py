import json
import logging
from typing import Optional, Dict, Any, Tuple
import redis.asyncio as aioredis
from shared.config import settings
from shared.logging import setup_logger

logger = setup_logger("redis-idempotency")


class RedisIdempotencyManager:
    """
    Distributed idempotency manager backed by Redis with atomic SETNX locks.
    Handles duplicate HTTP requests and event message deduplication with graceful fallback.
    """
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[aioredis.Redis] = None

    async def get_client(self) -> Optional[aioredis.Redis]:
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable for idempotency checks: {e}. Falling back to DB-level safety.")
                self._redis = None
        return self._redis

    async def check_and_lock(
        self,
        key: str,
        ttl_seconds: int = 86400,
        lock_ttl_seconds: int = 60,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Attempts to acquire an idempotency lock for the given key.
        Returns (is_new, cached_data):
        - If is_new is True: Lock acquired, caller must process the request and call save_result.
        - If is_new is False and cached_data is not None: Previously completed, return cached_data.
        - If is_new is False and cached_data is None: Currently PROCESSING by concurrent request.
        """
        client = await self.get_client()
        if not client:
            return True, None  # Graceful fallback: allow execution, relying on DB unique constraints

        redis_key = f"idempotency:{key}"
        try:
            # Check existing entry
            existing = await client.get(redis_key)
            if existing:
                parsed = json.loads(existing)
                if parsed.get("status") == "COMPLETED":
                    return False, parsed.get("result")
                elif parsed.get("status") == "PROCESSING":
                    return False, None

            # Attempt atomic set with NX
            initial_val = json.dumps({"status": "PROCESSING"})
            acquired = await client.set(redis_key, initial_val, nx=True, ex=lock_ttl_seconds)
            if acquired:
                return True, None
            else:
                # Concurrent request set it just before us
                return False, None
        except Exception as e:
            logger.error(f"Redis error during check_and_lock: {e}")
            return True, None

    async def save_result(self, key: str, result: Dict[str, Any], ttl_seconds: int = 86400) -> None:
        """Saves the completed execution result to Redis with TTL."""
        client = await self.get_client()
        if not client:
            return

        redis_key = f"idempotency:{key}"
        try:
            payload = json.dumps({"status": "COMPLETED", "result": result})
            await client.set(redis_key, payload, ex=ttl_seconds)
        except Exception as e:
            logger.error(f"Redis error during save_result for key {key}: {e}")

    async def release_lock(self, key: str) -> None:
        """Releases the lock upon failure so request can be retried."""
        client = await self.get_client()
        if not client:
            return

        redis_key = f"idempotency:{key}"
        try:
            await client.delete(redis_key)
        except Exception as e:
            logger.error(f"Redis error during release_lock for key {key}: {e}")

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
