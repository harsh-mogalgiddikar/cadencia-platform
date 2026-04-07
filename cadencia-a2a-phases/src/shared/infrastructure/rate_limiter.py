# context.md §15: API rate limit per enterprise: 100 req / 60s (Redis sliding window).
# context.md §5: Redis 7.0+ for rate limiting.
# Returns HTTP 429 with Retry-After header per RFC 6585.

from __future__ import annotations

import time

from redis.asyncio import Redis

from src.shared.domain.exceptions import RateLimitError
from src.shared.infrastructure.logging import get_logger
from src.shared.infrastructure.metrics import RATE_LIMIT_HITS_TOTAL

log = get_logger(__name__)


async def check_rate_limit(
    enterprise_id: str,
    redis: Redis,  # type: ignore[type-arg]
    limit: int = 100,
    window: int = 60,
) -> None:
    """
    Redis-backed fixed-window rate limiter.

    Key pattern: rate:{enterprise_id}:{window_bucket}
    Window bucket = floor(unix_timestamp / window)

    On breach: raises RateLimitError (mapped to HTTP 429 + Retry-After header
    in error_handler.py).

    context.md §15: 100 req/60s per enterprise_id.
    """
    bucket = int(time.time() // window)
    key = f"rate:{enterprise_id}:{bucket}"

    count = await redis.incr(key)
    if count == 1:
        # First request in this window — set expiry
        await redis.expire(key, window + 1)   # +1s buffer for clock skew

    if count > limit:
        # SRS §10.5.5: cadencia_rate_limit_hits_total
        RATE_LIMIT_HITS_TOTAL.inc()

        log.warning(
            "rate_limit_exceeded",
            enterprise_id=enterprise_id,
            count=count,
            limit=limit,
            window=window,
        )
        raise RateLimitError(
            f"Rate limit exceeded: {limit} requests per {window}s. "
            f"Retry-After: {window}s"
        )

