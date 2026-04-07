"""
Unit of Work pattern for atomic database commits.

context.md §15: Unit of Work atomicity: 100% — no partial commits.
context.md §4: DIP — services receive UoW via FastAPI Depends().
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.infrastructure.db.session import get_session_factory


@runtime_checkable
class AbstractUnitOfWork(Protocol):
    """
    Port interface for the Unit of Work.

    Infrastructure adapters implement this Protocol; services declare it
    as a dependency (context.md §4 DIP).
    """

    async def __aenter__(self) -> "AbstractUnitOfWork":
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        ...

    async def commit(self) -> None:
        """Persist all changes atomically."""
        ...

    async def rollback(self) -> None:
        """Discard all pending changes."""
        ...


class SqlAlchemyUnitOfWork:
    """
    SQLAlchemy implementation of AbstractUnitOfWork.

    Usage:
        async with SqlAlchemyUnitOfWork() as uow:
            repo.save(entity)
            await uow.commit()

    On exception: rollback is called automatically in __aexit__.
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._external_session = session
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        if self._external_session is not None:
            self._session = self._external_session
        else:
            factory = get_session_factory()
            self._session = factory()
            await self._session.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._external_session is None and self._session is not None:
            await self._session.__aexit__(exc_type, exc_val, exc_tb)

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active — use as async context manager")
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            return
        await self._session.rollback()

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active — use as async context manager")
        return self._session
