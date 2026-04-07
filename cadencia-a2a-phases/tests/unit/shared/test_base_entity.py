"""
Unit tests for shared/domain primitives.

context.md §3 — Hexagonal Architecture: domain layer has zero framework imports.
These tests run in pure Python — no I/O, no infrastructure.

Tests:
    test_entity_equality_by_id
    test_entity_inequality_different_id
    test_entity_has_no_framework_imports
    test_value_object_immutability
    test_domain_event_has_required_fields
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import uuid
from datetime import datetime

import pytest

from src.shared.domain.base_entity import BaseEntity
from src.shared.domain.base_value_object import BaseValueObject
from src.shared.domain.events import DomainEvent


# ── BaseEntity ────────────────────────────────────────────────────────────────

@dataclasses.dataclass(eq=False)
class ConcreteEntity(BaseEntity):
    name: str = ""


def test_entity_equality_by_id() -> None:
    """Two entities with the same id must be equal."""
    shared_id = uuid.uuid4()
    e1 = ConcreteEntity(id=shared_id, name="Alpha")
    e2 = ConcreteEntity(id=shared_id, name="Beta")
    assert e1 == e2


def test_entity_inequality_different_id() -> None:
    """Two entities with different ids must not be equal."""
    e1 = ConcreteEntity()
    e2 = ConcreteEntity()
    assert e1 != e2
    assert e1.id != e2.id


def test_entity_hash_is_id_based() -> None:
    """Entity hash must be based on id only."""
    shared_id = uuid.uuid4()
    e1 = ConcreteEntity(id=shared_id)
    e2 = ConcreteEntity(id=shared_id)
    assert hash(e1) == hash(e2)
    assert {e1, e2} == {e1}  # set deduplication works


def test_entity_has_required_fields() -> None:
    """BaseEntity must have id, created_at, updated_at."""
    entity = BaseEntity()
    assert isinstance(entity.id, uuid.UUID)
    assert isinstance(entity.created_at, datetime)
    assert isinstance(entity.updated_at, datetime)


def test_entity_touch_updates_updated_at() -> None:
    """touch() must update updated_at without changing created_at."""
    entity = BaseEntity()
    original_created = entity.created_at
    original_updated = entity.updated_at

    import time
    time.sleep(0.001)
    entity.touch()

    assert entity.created_at == original_created
    assert entity.updated_at >= original_updated


def test_entity_has_no_framework_imports() -> None:
    """
    context.md §3 — Hexagonal Architecture:
    domain layer MUST NOT import FastAPI, SQLAlchemy, or algosdk.
    """
    import src.shared.domain.base_entity as module

    source = inspect.getsource(module)
    tree = ast.parse(source)

    banned = {"fastapi", "sqlalchemy", "algosdk", "starlette", "pydantic"}
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    violations = banned & imported_modules
    assert not violations, (
        f"context.md §3 violated: base_entity.py imports banned modules: {violations}"
    )


# ── BaseValueObject ───────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class ConcreteValueObject(BaseValueObject):
    value: str = ""
    amount: int = 0


def test_value_object_immutability() -> None:
    """
    Attempting to set any attribute on a frozen value object must raise
    FrozenInstanceError (or AttributeError in some Python versions).
    """
    vo = ConcreteValueObject(value="test", amount=42)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        vo.value = "mutated"  # type: ignore[misc]


def test_value_object_structural_equality() -> None:
    """Two value objects with identical fields must be equal."""
    vo1 = ConcreteValueObject(value="abc", amount=10)
    vo2 = ConcreteValueObject(value="abc", amount=10)
    assert vo1 == vo2


def test_value_object_structural_inequality() -> None:
    """Two value objects with different fields must not be equal."""
    vo1 = ConcreteValueObject(value="abc", amount=10)
    vo2 = ConcreteValueObject(value="xyz", amount=10)
    assert vo1 != vo2


# ── DomainEvent ───────────────────────────────────────────────────────────────

def test_domain_event_has_required_fields() -> None:
    """DomainEvent must carry event_id, occurred_at, aggregate_id, event_type."""
    agg_id = uuid.uuid4()
    event = DomainEvent(aggregate_id=agg_id, event_type="TestEvent")

    assert isinstance(event.event_id, uuid.UUID)
    assert isinstance(event.occurred_at, datetime)
    assert event.aggregate_id == agg_id
    assert event.event_type == "TestEvent"


def test_domain_event_is_immutable() -> None:
    """DomainEvent is frozen — mutation must raise FrozenInstanceError."""
    event = DomainEvent(aggregate_id=uuid.uuid4(), event_type="TestEvent")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        event.event_type = "Mutated"  # type: ignore[misc]


def test_domain_event_unique_ids() -> None:
    """Each DomainEvent must get a unique event_id."""
    agg_id = uuid.uuid4()
    e1 = DomainEvent(aggregate_id=agg_id, event_type="TestEvent")
    e2 = DomainEvent(aggregate_id=agg_id, event_type="TestEvent")
    assert e1.event_id != e2.event_id


def test_domain_event_subclass() -> None:
    """Domain events should be subclassable to carry typed payloads."""

    @dataclasses.dataclass(frozen=True)
    class RFQConfirmed(DomainEvent):
        rfq_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)

    agg_id = uuid.uuid4()
    event = RFQConfirmed(aggregate_id=agg_id, event_type="RFQConfirmed")
    assert isinstance(event, DomainEvent)
    assert isinstance(event.rfq_id, uuid.UUID)
