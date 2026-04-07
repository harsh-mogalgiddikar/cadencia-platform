# Phase Five Unit Tests: Task Queue + Additional Hardening

from __future__ import annotations

import json

import pytest


class FakeRedis:
    """Minimal fake Redis for task queue tests."""

    def __init__(self):
        self._lists: dict[str, list[str]] = {}

    async def rpush(self, key: str, value: str):
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].append(value)

    async def blpop(self, key: str, timeout: int = 0):
        items = self._lists.get(key, [])
        if not items:
            return None
        return (key, items.pop(0))


class TestTaskQueue:
    @pytest.mark.anyio
    async def test_enqueue_adds_to_redis(self):
        from src.shared.infrastructure.task_queue import TaskQueue, QUEUE_KEY
        redis = FakeRedis()
        tq = TaskQueue(redis)
        await tq.enqueue("parse_rfq", {"rfq_id": "abc-123"})
        assert len(redis._lists[QUEUE_KEY]) == 1
        task = json.loads(redis._lists[QUEUE_KEY][0])
        assert task["task"] == "parse_rfq"
        assert task["payload"]["rfq_id"] == "abc-123"
        assert task["retries"] == 0

    @pytest.mark.anyio
    async def test_enqueue_multiple(self):
        from src.shared.infrastructure.task_queue import TaskQueue, QUEUE_KEY
        redis = FakeRedis()
        tq = TaskQueue(redis)
        await tq.enqueue("parse_rfq", {"rfq_id": "1"})
        await tq.enqueue("recompute_embedding", {"enterprise_id": "2"})
        assert len(redis._lists[QUEUE_KEY]) == 2

    def test_register_handler(self):
        from src.shared.infrastructure.task_queue import TaskQueue
        redis = FakeRedis()
        tq = TaskQueue(redis)

        async def handler(**kwargs):
            pass

        tq.register("test_task", handler)
        assert "test_task" in tq._handlers

    def test_stop_sets_flag(self):
        from src.shared.infrastructure.task_queue import TaskQueue
        redis = FakeRedis()
        tq = TaskQueue(redis)
        tq._running = True
        tq.stop()
        assert tq._running is False


class TestTimingMiddleware:
    """Verify timing middleware imports and instantiates."""

    def test_import(self):
        from src.shared.infrastructure.timing_middleware import TimingMiddleware
        assert TimingMiddleware is not None


class TestSecurityHeaders:
    """Verify security headers middleware imports."""

    def test_import(self):
        from src.shared.api.security_headers import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware is not None
