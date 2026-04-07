"""
In-process domain event publisher.

context.md §7: All cross-domain communication happens via publisher.py → handlers.py.
Direct cross-context imports are PROHIBITED. Use domain events only.

This publisher is synchronous dispatch (in-process). For async handlers,
wrap with asyncio.create_task() in the handler registration.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

from src.shared.domain.events import DomainEvent
from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)

# Handler type: async or sync callable accepting a DomainEvent subclass
HandlerFn = Callable[[Any], Awaitable[None] | None]


class EventPublisher:
    """
    In-process event publisher with handler registry.

    Publishers are injected into application services via FastAPI Depends().
    A single shared instance is used per application process.

    Usage:
        publisher = EventPublisher()
        publisher.subscribe("RFQConfirmed", handle_rfq_confirmed)

        # In a service:
        await publisher.publish(RFQConfirmed(aggregate_id=rfq.id, ...))
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerFn]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: HandlerFn) -> None:
        """Register a handler for a given event_type string."""
        self._handlers[event_type].append(handler)
        log.debug("event_handler_registered", event_type=event_type, handler=handler.__name__)

    def unsubscribe(self, event_type: str, handler: HandlerFn) -> None:
        """
        Remove a previously registered handler.

        Used in Phase 3 to replace Phase 2 stub handlers with full implementations.
        No-op if handler is not registered for the given event_type.
        """
        handlers = self._handlers.get(event_type, [])
        try:
            handlers.remove(handler)
            log.debug(
                "event_handler_unsubscribed",
                event_type=event_type,
                handler=handler.__name__,
            )
        except ValueError:
            pass  # handler not registered — silently ignore

    async def publish(self, event: DomainEvent) -> None:
        """
        Dispatch event to all registered handlers.

        Handlers are called in registration order.
        Async handlers are awaited; sync handlers are called directly.
        Exceptions in handlers are logged but do NOT propagate — the
        publisher is best-effort for cross-domain side effects.
        """
        handlers = self._handlers.get(event.event_type, [])
        log.debug(
            "domain_event_published",
            event_type=event.event_type,
            event_id=str(event.event_id),
            aggregate_id=str(event.aggregate_id),
            handler_count=len(handlers),
        )
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.exception(
                    "event_handler_error",
                    event_type=event.event_type,
                    handler=handler.__name__,
                )

    async def publish_many(self, events: list[DomainEvent]) -> None:
        """Dispatch multiple events in order."""
        for event in events:
            await self.publish(event)


# Module-level shared publisher instance.
# Wired at startup in handlers.py; injected via Depends() in services.
_publisher: EventPublisher | None = None


def get_publisher() -> EventPublisher:
    """Return the shared EventPublisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher
