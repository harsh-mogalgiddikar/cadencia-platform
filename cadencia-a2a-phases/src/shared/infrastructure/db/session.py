"""
Async SQLAlchemy engine and session factory.

context.md §5: SQLAlchemy (async via asyncpg).
context.md §14: DATABASE_URL must include ssl=require in production.
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "See .env.example for required format."
        )
    return url


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """
    Create the async SQLAlchemy engine.

    Connection pool settings (context.md §15 — performance targets):
        pool_size=20, max_overflow=10  → max 30 concurrent DB connections.
    """
    url = database_url or _get_database_url()
    return create_async_engine(
        url,
        pool_size=5,              # Phase Five: min connections
        max_overflow=15,          # Phase Five: burst connections (total max=20)
        pool_timeout=30,          # Phase Five: wait before PoolTimeout
        pool_pre_ping=True,       # verify connections before checkout
        pool_recycle=1800,        # Phase Five: recycle every 30 min
        echo=os.environ.get("DEBUG", "false").lower() == "true",
    )


# Module-level engine and session factory — initialised once at startup.
# Replaced in tests via dependency injection.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,   # avoid lazy-load after commit
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency that yields a single AsyncSession per request.

    Usage in router:
        async def my_endpoint(session: AsyncSession = Depends(get_db_session)):
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
