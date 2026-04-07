# Redis-backed simple task queue for persistent background processing.
# Survives server restarts — tasks stored in Redis list.
# context.md §9: background tasks for RFQ parsing, embedding recompute, etc.

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Coroutine

from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)

QUEUE_KEY = "cadencia:tasks"
MAX_RETRIES = 3


class TaskQueue:
    """
    Redis List-backed task queue.

    Producer: RPUSH cadencia:tasks {task_name, payload, retries}
    Consumer: background asyncio task that BLPOP + executes registered handlers.
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis
        self._handlers: dict[str, Callable[..., Coroutine]] = {}  # type: ignore[type-arg]
        self._running = False

    def register(self, task_name: str, handler: Callable[..., Coroutine]) -> None:  # type: ignore[type-arg]
        """Register a named task handler."""
        self._handlers[task_name] = handler
        log.debug("task_registered", task=task_name)

    async def enqueue(self, task_name: str, payload: dict) -> None:
        """Add a task to the queue."""
        task = json.dumps({"task": task_name, "payload": payload, "retries": 0})
        await self._redis.rpush(QUEUE_KEY, task)
        log.debug("task_enqueued", task=task_name)

    async def run_worker(self) -> None:
        """
        Consumer loop — runs as a background asyncio task.

        BLPOP with 5s timeout to allow graceful shutdown checks.
        Failed tasks are requeued up to MAX_RETRIES.
        """
        self._running = True
        log.info("task_queue_worker_started")

        while self._running:
            try:
                raw = await self._redis.blpop(QUEUE_KEY, timeout=5)
                if raw is None:
                    continue

                # BLPOP returns (key, value) tuple
                task_data = json.loads(
                    raw[1].decode() if isinstance(raw[1], bytes) else raw[1]
                )
                task_name = task_data["task"]
                payload = task_data["payload"]
                retries = task_data.get("retries", 0)

                handler = self._handlers.get(task_name)
                if handler is None:
                    log.error("task_handler_not_found", task=task_name)
                    continue

                try:
                    await handler(**payload)
                    log.info("task_completed", task=task_name)
                except Exception as e:
                    retries += 1
                    if retries < MAX_RETRIES:
                        retry_task = json.dumps({
                            "task": task_name,
                            "payload": payload,
                            "retries": retries,
                        })
                        await self._redis.rpush(QUEUE_KEY, retry_task)
                        log.warning(
                            "task_retried",
                            task=task_name,
                            retries=retries,
                            error=str(e),
                        )
                    else:
                        log.error(
                            "task_failed_max_retries",
                            task=task_name,
                            retries=retries,
                            error=str(e),
                        )

            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("task_queue_worker_error")
                await asyncio.sleep(1)

        log.info("task_queue_worker_stopped")

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False
