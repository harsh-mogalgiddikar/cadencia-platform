"""
SQLAlchemy ORM models for the treasury bounded context.

Tables: liquidity_pools, fx_positions
context.md §11 — Database Schema.
context.md §4.2 — Treasury bounded context.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.db.base import Base


class LiquidityPoolModel(Base):
    """
    Liquidity pool aggregate (treasury bounded context).

    Tracks INR, USDC, and ALGO balances per enterprise.
    One pool per enterprise (unique constraint on enterprise_id).
    """

    __tablename__ = "liquidity_pools"
    __table_args__ = (
        CheckConstraint(
            "inr_balance >= 0",
            name="ck_liquidity_pools_inr_non_negative",
        ),
        CheckConstraint(
            "usdc_balance >= 0",
            name="ck_liquidity_pools_usdc_non_negative",
        ),
        CheckConstraint(
            "algo_balance_microalgo >= 0",
            name="ck_liquidity_pools_algo_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id"),
        nullable=False,
        unique=True,
    )
    inr_balance: Mapped[float] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False, server_default="0"
    )
    usdc_balance: Mapped[float] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False, server_default="0"
    )
    algo_balance_microalgo: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    last_fx_rate_inr_usd: Mapped[float] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False, server_default="0"
    )
    last_rate_updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


_pool_enterprise_idx = Index(
    "ix_liquidity_pools_enterprise_id", LiquidityPoolModel.enterprise_id, unique=True
)


class FXPositionModel(Base):
    """
    FX exposure position (treasury bounded context).

    Tracks currency pair positions and unrealized PnL.
    """

    __tablename__ = "fx_positions"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('LONG', 'SHORT')",
            name="ck_fx_positions_direction",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED')",
            name="ck_fx_positions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id"),
        nullable=False,
    )
    currency_pair: Mapped[str] = mapped_column(String(10), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    notional_amount: Mapped[float] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False
    )
    entry_rate: Mapped[float] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False
    )
    current_rate: Mapped[float] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="OPEN"
    )
    closed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


_fx_enterprise_idx = Index(
    "ix_fx_positions_enterprise_id", FXPositionModel.enterprise_id
)
_fx_status_idx = Index(
    "ix_fx_positions_status", FXPositionModel.status
)
