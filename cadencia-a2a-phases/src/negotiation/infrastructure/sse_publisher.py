# Redis-backed SSE event queue with Last-Event-ID replay.
# context.md §5.3: SSE streaming for live agent turns.

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog

log = structlog.get_logger(__name__)

SSE_EVENTS_KEY = "sse:{session_id}"
SSE_CONN_KEY = "sse_conn:{enterprise_id}"
MAX_EVENTS_PER_SESSION = 1000
MAX_CONNECTIONS_PER_ENTERPRISE = 10


class RedisSSEPublisher:
    """Redis-backed SSE publisher implementing ISSEPublisher."""

    def __init__(self, redis: object) -> None:
        self.redis = redis

    async def publish_turn(self, session_id: uuid.UUID, event: dict) -> None:
        event["event_id"] = str(uuid.uuid4())
        event["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        key = SSE_EVENTS_KEY.format(session_id=str(session_id))
        await self.redis.rpush(key, json.dumps(event))  # type: ignore[union-attr]
        await self.redis.ltrim(key, -MAX_EVENTS_PER_SESSION, -1)  # type: ignore[union-attr]
        await self.redis.expire(key, 90000)  # 25 hours  # type: ignore[union-attr]

    async def publish_terminal(self, session_id: uuid.UUID, event: dict) -> None:
        event["terminal"] = True
        await self.publish_turn(session_id, event)

    async def get_events_since(
        self,
        session_id: uuid.UUID,
        last_event_id: str | None,
    ) -> list[dict]:
        key = SSE_EVENTS_KEY.format(session_id=str(session_id))
        all_events_raw = await self.redis.lrange(key, 0, -1)  # type: ignore[union-attr]
        all_events = [json.loads(e) for e in all_events_raw]
        if last_event_id is None:
            return all_events
        for i, event in enumerate(all_events):
            if event.get("event_id") == last_event_id:
                return all_events[i + 1:]
        return all_events

    async def check_connection_limit(self, enterprise_id: uuid.UUID) -> bool:
        key = SSE_CONN_KEY.format(enterprise_id=str(enterprise_id))
        count = await self.redis.get(key)  # type: ignore[union-attr]
        return (int(count or 0)) < MAX_CONNECTIONS_PER_ENTERPRISE

    async def increment_connection(self, enterprise_id: uuid.UUID) -> None:
        key = SSE_CONN_KEY.format(enterprise_id=str(enterprise_id))
        await self.redis.incr(key)  # type: ignore[union-attr]
        await self.redis.expire(key, 86400)  # type: ignore[union-attr]

    async def decrement_connection(self, enterprise_id: uuid.UUID) -> None:
        key = SSE_CONN_KEY.format(enterprise_id=str(enterprise_id))
        await self.redis.decr(key)  # type: ignore[union-attr]
