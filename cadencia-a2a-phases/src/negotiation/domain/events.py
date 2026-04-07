# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.
# context.md §7 — All domain events extend DomainEvent. Immutable frozen dataclasses.

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from src.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class SessionCreated(DomainEvent):
    session_id: uuid.UUID = uuid.UUID(int=0)
    rfq_id: uuid.UUID = uuid.UUID(int=0)
    match_id: uuid.UUID = uuid.UUID(int=0)
    buyer_enterprise_id: uuid.UUID = uuid.UUID(int=0)
    seller_enterprise_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class OfferSubmitted(DomainEvent):
    session_id: uuid.UUID = uuid.UUID(int=0)
    offer_id: uuid.UUID = uuid.UUID(int=0)
    round_number: int = 0
    proposer_role: str = ""
    price: Decimal = Decimal("0")
    is_human_override: bool = False


@dataclass(frozen=True)
class SessionAgreed(DomainEvent):
    """Critical event consumed by settlement/ (Phase Two) and compliance/ (Phase Three)."""
    session_id: uuid.UUID = uuid.UUID(int=0)
    rfq_id: uuid.UUID = uuid.UUID(int=0)
    match_id: uuid.UUID = uuid.UUID(int=0)
    buyer_enterprise_id: uuid.UUID = uuid.UUID(int=0)
    seller_enterprise_id: uuid.UUID = uuid.UUID(int=0)
    buyer_algo_address: str | None = None
    seller_algo_address: str | None = None
    agreed_price: Decimal = Decimal("0")
    agreed_currency: str = "INR"
    agreed_terms: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.agreed_terms is None:
            object.__setattr__(self, "agreed_terms", {})


@dataclass(frozen=True)
class SessionFailed(DomainEvent):
    session_id: uuid.UUID = uuid.UUID(int=0)
    reason: str = ""
    round_count: int = 0


@dataclass(frozen=True)
class SessionEscalated(DomainEvent):
    session_id: uuid.UUID = uuid.UUID(int=0)
    round_count: int = 0
    escalation_reason: str = "stall_detected"


@dataclass(frozen=True)
class SessionExpired(DomainEvent):
    session_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class HumanOverrideApplied(DomainEvent):
    session_id: uuid.UUID = uuid.UUID(int=0)
    offer_id: uuid.UUID = uuid.UUID(int=0)
    price: Decimal = Decimal("0")
    applied_by_user_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class AgentProfileUpdated(DomainEvent):
    enterprise_id: uuid.UUID = uuid.UUID(int=0)
    session_agreed: bool = False
    rounds_taken: int = 0
