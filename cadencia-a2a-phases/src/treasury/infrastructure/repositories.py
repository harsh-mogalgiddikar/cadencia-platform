"""
PostgreSQL repository implementations for the treasury bounded context.

context.md §3: Infrastructure layer — concrete adapters implementing domain ports.
context.md §4 DIP: depends on domain interfaces, never the reverse.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.treasury.domain.fx_position import FXPosition
from src.treasury.domain.liquidity_pool import LiquidityPool
from src.treasury.infrastructure.models import FXPositionModel, LiquidityPoolModel


class PostgresLiquidityRepository:
    """Concrete adapter implementing ILiquidityRepository using PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, pool: LiquidityPool) -> None:
        model = LiquidityPoolModel(
            id=pool.id,
            enterprise_id=pool.enterprise_id,
            inr_balance=pool.inr_balance,
            usdc_balance=pool.usdc_balance,
            algo_balance_microalgo=pool.algo_balance_microalgo,
            last_fx_rate_inr_usd=pool.last_fx_rate_inr_usd,
            last_rate_updated_at=pool.last_rate_updated_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_enterprise_id(
        self, enterprise_id: uuid.UUID
    ) -> LiquidityPool | None:
        stmt = select(LiquidityPoolModel).where(
            LiquidityPoolModel.enterprise_id == enterprise_id
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        if m is None:
            return None
        return self._to_domain(m)

    async def update(self, pool: LiquidityPool) -> None:
        stmt = select(LiquidityPoolModel).where(
            LiquidityPoolModel.id == pool.id
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            return
        existing.inr_balance = pool.inr_balance
        existing.usdc_balance = pool.usdc_balance
        existing.algo_balance_microalgo = pool.algo_balance_microalgo
        existing.last_fx_rate_inr_usd = pool.last_fx_rate_inr_usd
        existing.last_rate_updated_at = pool.last_rate_updated_at
        await self._session.flush()

    @staticmethod
    def _to_domain(m: LiquidityPoolModel) -> LiquidityPool:
        return LiquidityPool(
            id=m.id,
            enterprise_id=m.enterprise_id,
            inr_balance=Decimal(str(m.inr_balance)),
            usdc_balance=Decimal(str(m.usdc_balance)),
            algo_balance_microalgo=int(m.algo_balance_microalgo),
            last_fx_rate_inr_usd=Decimal(str(m.last_fx_rate_inr_usd)),
            last_rate_updated_at=m.last_rate_updated_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class PostgresFXPositionRepository:
    """Concrete adapter implementing IFXPositionRepository using PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, position: FXPosition) -> None:
        model = FXPositionModel(
            id=position.id,
            enterprise_id=position.enterprise_id,
            currency_pair=position.currency_pair,
            direction=position.direction,
            notional_amount=position.notional_amount,
            entry_rate=position.entry_rate,
            current_rate=position.current_rate,
            status=position.status,
            closed_at=position.closed_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, position_id: uuid.UUID) -> FXPosition | None:
        stmt = select(FXPositionModel).where(FXPositionModel.id == position_id)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        if m is None:
            return None
        return self._to_domain(m)

    async def list_open_by_enterprise(
        self, enterprise_id: uuid.UUID
    ) -> list[FXPosition]:
        stmt = (
            select(FXPositionModel)
            .where(
                FXPositionModel.enterprise_id == enterprise_id,
                FXPositionModel.status == "OPEN",
            )
            .order_by(FXPositionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def update(self, position: FXPosition) -> None:
        stmt = select(FXPositionModel).where(FXPositionModel.id == position.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            return
        existing.current_rate = position.current_rate
        existing.status = position.status
        existing.closed_at = position.closed_at
        await self._session.flush()

    @staticmethod
    def _to_domain(m: FXPositionModel) -> FXPosition:
        return FXPosition(
            id=m.id,
            enterprise_id=m.enterprise_id,
            currency_pair=m.currency_pair,
            direction=m.direction,
            notional_amount=Decimal(str(m.notional_amount)),
            entry_rate=Decimal(str(m.entry_rate)),
            current_rate=Decimal(str(m.current_rate)),
            status=m.status,
            closed_at=m.closed_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
