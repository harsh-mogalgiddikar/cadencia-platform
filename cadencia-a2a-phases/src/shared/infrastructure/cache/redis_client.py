"""
Redis async client — singleton with typed helpers.

context.md §5: Redis 7.0+ for caching and rate limiting.
context.md §15: API rate limit 100 req/60s; LLM rate limit 50 req/min.
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis


def _get_redis_url() -> str:
    url = os.environ.get("REDIS_URL", "")
    if not url:
        raise RuntimeError(
            "REDIS_URL environment variable is not set. "
            "See .env.example for required format."
        )
    return url


# Module-level singleton — initialised once at startup.
_redis: Redis | None = None  # type: ignore[type-arg]


def get_redis_client() -> Redis:  # type: ignore[type-arg]
    """Return the module-level Redis singleton. Initialise if needed."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            _get_redis_url(),
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis


async def get_redis() -> Redis:  # type: ignore[type-arg]
    """
    FastAPI async dependency yielding the Redis client.

    Usage in router:
        async def my_endpoint(redis: Redis = Depends(get_redis)):
    """
    yield get_redis_client()


async def get_redis_instance() -> Redis:  # type: ignore[type-arg]
    """
    Return the Redis singleton directly (not a generator).

    Use this in non-DI contexts (e.g. wallet verifier called from within
    an endpoint handler). For FastAPI Depends(), use get_redis() instead.
    """
    return get_redis_client()


# ── Typed helpers ─────────────────────────────────────────────────────────────


async def ping() -> bool:
    """Health check — returns True if Redis is reachable."""
    try:
        result = await get_redis_client().ping()
        return bool(result)
    except Exception:
        return False


async def get_json(key: str) -> Any | None:
    """Get a JSON-deserialised value. Returns None if key does not exist."""
    client = get_redis_client()
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    """
    Serialise `value` to JSON and store it.

    ttl: optional expiry in seconds. None = no expiry.
    """
    client = get_redis_client()
    serialised = json.dumps(value, default=str)
    if ttl is not None:
        await client.setex(key, ttl, serialised)
    else:
        await client.set(key, serialised)


async def delete(key: str) -> int:
    """Delete key. Returns number of keys deleted (0 or 1)."""
    return int(await get_redis_client().delete(key))


async def incr(key: str) -> int:
    """Atomically increment integer counter. Returns new value."""
    return int(await get_redis_client().incr(key))


async def expire(key: str, ttl: int) -> bool:
    """Set TTL on an existing key. Returns True if key exists."""
    return bool(await get_redis_client().expire(key, ttl))


async def close() -> None:
    """Close the Redis connection — called at application shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
