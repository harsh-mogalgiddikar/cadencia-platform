# context.md §3 — Hexagonal Architecture: domain layer MUST NOT import
# FastAPI, SQLAlchemy, algosdk, or any infrastructure library.
# This file: zero framework imports. Pure Python only.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class BaseEntity:
    """
    Root base class for all domain entities.

    Identity is defined by `id` (UUID) alone — two entities with the same id
    are equal regardless of their other fields (context.md §1.2 Hexagonal).

    Intentionally NOT frozen: entities are mutable aggregates whose state
    transitions are governed by domain policies.

    No imports of FastAPI, SQLAlchemy, or algosdk — pure Python.
    """

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def touch(self) -> None:
        """Update `updated_at` to now. Call after any state mutation."""
        self.updated_at = _utcnow()
