# context.md §4 DIP: dependencies wired here via FastAPI Depends().

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.infrastructure.cache import redis_client
from src.shared.infrastructure.db.session import get_db_session
from src.shared.infrastructure.db.uow import SqlAlchemyUnitOfWork
from src.shared.infrastructure.events.publisher import get_publisher
from src.negotiation.application.services import NegotiationService
from src.negotiation.infrastructure.llm_agent_driver import get_agent_driver
from src.negotiation.infrastructure.neutral_engine import NeutralEngine
from src.negotiation.infrastructure.personalization import PersonalizationBuilder
from src.negotiation.infrastructure.repositories import (
    PostgresAgentProfileRepository,
    PostgresOfferRepository,
    PostgresPlaybookRepository,
    PostgresSessionRepository,
)
from src.negotiation.infrastructure.sse_publisher import RedisSSEPublisher


async def get_sse_publisher() -> RedisSSEPublisher:
    redis = await redis_client.get_redis()
    return RedisSSEPublisher(redis)


def get_negotiation_service(
    session: AsyncSession = Depends(get_db_session),
) -> NegotiationService:
    """Wire NegotiationService with all concrete adapters."""
    agent_driver = get_agent_driver()

    # Attempt to wire SSE publisher — falls back to None if Redis unavailable
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        # Use synchronous check since FastAPI DI doesn't support async Depends here
        sse_pub = None
        redis = redis_client._redis  # type: ignore[attr-defined]
        if redis is not None:
            sse_pub = RedisSSEPublisher(redis)
    except Exception:
        sse_pub = None

    neutral_engine = NeutralEngine(
        agent_driver=agent_driver,
        personalization_builder=PersonalizationBuilder(),
        sse_publisher=sse_pub,
    )

    return NegotiationService(
        session_repo=PostgresSessionRepository(session),
        offer_repo=PostgresOfferRepository(session),
        profile_repo=PostgresAgentProfileRepository(session),
        playbook_repo=PostgresPlaybookRepository(session),
        neutral_engine=neutral_engine,
        sse_publisher=sse_pub,
        event_publisher=get_publisher(),
        uow=SqlAlchemyUnitOfWork(session),
    )
