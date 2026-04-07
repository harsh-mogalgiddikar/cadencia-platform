# context.md §3 — domain events: zero framework imports.
# All cross-domain communication via event bus only.

from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class RFQUploaded(DomainEvent):
    rfq_id: uuid.UUID = uuid.UUID(int=0)
    buyer_enterprise_id: uuid.UUID = uuid.UUID(int=0)
    raw_document_length: int = 0


@dataclass(frozen=True)
class RFQParsed(DomainEvent):
    rfq_id: uuid.UUID = uuid.UUID(int=0)
    buyer_enterprise_id: uuid.UUID = uuid.UUID(int=0)
    hsn_code: str | None = None
    has_budget: bool = False
    has_delivery_window: bool = False


@dataclass(frozen=True)
class RFQMatched(DomainEvent):
    rfq_id: uuid.UUID = uuid.UUID(int=0)
    buyer_enterprise_id: uuid.UUID = uuid.UUID(int=0)
    match_count: int = 0
    top_score: float = 0.0


@dataclass(frozen=True)
class RFQConfirmed(DomainEvent):
    """Consumed by negotiation/ to create a NegotiationSession."""
    rfq_id: uuid.UUID = uuid.UUID(int=0)
    match_id: uuid.UUID = uuid.UUID(int=0)
    buyer_enterprise_id: uuid.UUID = uuid.UUID(int=0)
    seller_enterprise_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class RFQSettled(DomainEvent):
    rfq_id: uuid.UUID = uuid.UUID(int=0)
    session_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class RFQExpired(DomainEvent):
    rfq_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class CapabilityProfileUpdated(DomainEvent):
    enterprise_id: uuid.UUID = uuid.UUID(int=0)
    profile_id: uuid.UUID = uuid.UUID(int=0)
