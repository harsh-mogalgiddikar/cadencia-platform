# context.md §3.1: pgvector cosine similarity using ivfflat index.
# Imports of pgvector/sqlalchemy ONLY in infrastructure layer.

from __future__ import annotations

import hashlib
import random
import time
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.marketplace.infrastructure.models import CapabilityProfileModel
from src.shared.infrastructure.logging import get_logger
from src.shared.infrastructure.metrics import VECTOR_SEARCH_DURATION

if TYPE_CHECKING:
    from src.marketplace.domain.rfq import RFQ

log = get_logger(__name__)


class PgvectorMatchmaker:
    """Cosine similarity search via pgvector ivfflat. Implements IMatchmakingEngine."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_matches(
        self,
        rfq: "RFQ",
        rfq_embedding: list[float],
        top_n: int = 10,
    ) -> list[tuple[uuid.UUID, float]]:
        # Set ivfflat probes for accuracy
        search_start = time.monotonic()
        await self._session.execute(text("SET ivfflat.probes = 50"))

        # Cosine similarity = 1 - cosine_distance
        # <=> operator is cosine distance in pgvector
        stmt = (
            select(
                CapabilityProfileModel.enterprise_id,
                (
                    1 - CapabilityProfileModel.embedding.cosine_distance(rfq_embedding)
                ).label("similarity"),
            )
            .where(CapabilityProfileModel.embedding.is_not(None))
            .where(CapabilityProfileModel.enterprise_id != rfq.buyer_enterprise_id)
            .order_by(
                CapabilityProfileModel.embedding.cosine_distance(rfq_embedding).asc()
            )
            .limit(top_n)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        # Prometheus: record vector search latency
        VECTOR_SEARCH_DURATION.observe(time.monotonic() - search_start)

        matches = [
            (row.enterprise_id, max(0.0, min(1.0, float(row.similarity))))
            for row in rows
        ]
        log.info(
            "pgvector_match_complete",
            rfq_id=str(rfq.id),
            match_count=len(matches),
            top_score=matches[0][1] if matches else 0.0,
        )
        return matches


class StubMatchmakingEngine:
    """Deterministic stub — no pgvector. Implements IMatchmakingEngine."""

    async def find_matches(
        self,
        rfq: "RFQ",
        rfq_embedding: list[float],
        top_n: int = 10,
    ) -> list[tuple[uuid.UUID, float]]:
        # Deterministic based on RFQ id
        seed = int(hashlib.md5(str(rfq.id).encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        count = min(top_n, 5)
        return [
            (uuid.UUID(int=rng.getrandbits(128)), round(0.94 - i * 0.03, 2))
            for i in range(count)
        ]
