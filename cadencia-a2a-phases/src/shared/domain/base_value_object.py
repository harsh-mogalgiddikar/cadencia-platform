# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BaseValueObject:
    """
    Root base class for all domain value objects.

    Value objects are immutable (frozen=True). Equality is structural —
    two value objects with identical fields are equal. Attempting to set
    any attribute after creation raises dataclasses.FrozenInstanceError.

    Subclasses should add __post_init__ validation where applicable.
    No imports of FastAPI, SQLAlchemy, or algosdk — pure Python.
    """
