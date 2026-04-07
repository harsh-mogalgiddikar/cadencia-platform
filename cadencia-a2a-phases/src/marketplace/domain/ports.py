# context.md §3 — Ports are Protocol interfaces in the domain layer.
# Zero framework imports.

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from src.marketplace.domain.capability_profile import CapabilityProfile
from src.marketplace.domain.match import Match
from src.marketplace.domain.rfq import RFQ


class IRFQRepository(Protocol):
    async def save(self, rfq: RFQ) -> None: ...
    async def get_by_id(self, rfq_id: uuid.UUID) -> RFQ | None: ...
    async def update(self, rfq: RFQ) -> None: ...
    async def list_by_buyer(
        self,
        buyer_enterprise_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RFQ]: ...
    async def list_expired_candidates(self, cutoff: datetime) -> list[RFQ]: ...


class IMatchRepository(Protocol):
    async def save_bulk(self, matches: list[Match]) -> None: ...
    async def get_by_id(self, match_id: uuid.UUID) -> Match | None: ...
    async def list_by_rfq(self, rfq_id: uuid.UUID) -> list[Match]: ...
    async def update(self, match: Match) -> None: ...


class ICapabilityProfileRepository(Protocol):
    async def save(self, profile: CapabilityProfile) -> None: ...
    async def get_by_enterprise(
        self, enterprise_id: uuid.UUID
    ) -> CapabilityProfile | None: ...
    async def update(self, profile: CapabilityProfile) -> None: ...
    async def list_without_embeddings(self, limit: int = 100) -> list[CapabilityProfile]: ...


class IDocumentParser(Protocol):
    """Handles NLP field extraction AND embedding generation."""

    async def extract_rfq_fields(self, raw_text: str) -> dict: ...
    async def generate_embedding(self, text: str) -> list[float]: ...


class IMatchmakingEngine(Protocol):
    """pgvector cosine similarity search."""

    async def find_matches(
        self,
        rfq: RFQ,
        rfq_embedding: list[float],
        top_n: int = 10,
    ) -> list[tuple[uuid.UUID, float]]:
        """Returns list of (enterprise_id, similarity_score), ordered by score desc."""
        ...
