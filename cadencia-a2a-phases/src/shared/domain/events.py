# context.md §7 — Domain Event Bus:
#   All cross-domain communication happens via publisher.py → handlers.py.
#   Direct cross-context imports are PROHIBITED.
# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events across all bounded contexts.

    Events are immutable value objects — once emitted they must not change.
    They are identified by `event_id` (UUID) and carry the `aggregate_id`
    of the root entity that emitted them.

    Cross-domain communication via events only — never via direct imports
    (context.md §3, §7).

    Subclass and add domain-specific payload fields. Example:

        @dataclass(frozen=True)
        class RFQConfirmed(DomainEvent):
            rfq_id: uuid.UUID
            match_id: uuid.UUID
            buyer_id: uuid.UUID
            seller_id: uuid.UUID
    """

    aggregate_id: uuid.UUID
    event_type: str
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=_utcnow)
