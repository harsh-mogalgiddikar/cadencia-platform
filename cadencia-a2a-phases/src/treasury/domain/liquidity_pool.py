# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.
# context.md §4.2 — Treasury bounded context: LiquidityPool aggregate.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.shared.domain.base_entity import BaseEntity
from src.shared.domain.events import DomainEvent
from src.shared.domain.exceptions import PolicyViolation, ValidationError


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class LiquidityPool(BaseEntity):
    """
    Aggregate root: tracks an enterprise's liquidity across INR, USDC, and ALGO.

    context.md §4.2: Treasury bounded context aggregate.
    Pure Python — no framework imports.
    """

    enterprise_id: uuid.UUID = field(default_factory=uuid.uuid4)
    inr_balance: Decimal = Decimal("0")
    usdc_balance: Decimal = Decimal("0")
    algo_balance_microalgo: int = 0
    last_fx_rate_inr_usd: Decimal = Decimal("0")
    last_rate_updated_at: datetime = field(default_factory=_utcnow)

    # ── Balance Operations ────────────────────────────────────────────────────

    def deposit_inr(self, amount: Decimal) -> None:
        """Record an INR deposit into the pool."""
        if amount <= 0:
            raise ValidationError(
                f"Deposit amount must be positive, got {amount}",
                field="amount",
            )
        self.inr_balance += amount
        self.touch()

    def withdraw_inr(self, amount: Decimal) -> None:
        """Record an INR withdrawal from the pool."""
        if amount <= 0:
            raise ValidationError(
                f"Withdrawal amount must be positive, got {amount}",
                field="amount",
            )
        if amount > self.inr_balance:
            raise PolicyViolation(
                f"Insufficient INR balance: {self.inr_balance}, requested: {amount}"
            )
        self.inr_balance -= amount
        self.touch()

    def deposit_usdc(self, amount: Decimal) -> None:
        """Record a USDC deposit into the pool."""
        if amount <= 0:
            raise ValidationError(
                f"Deposit amount must be positive, got {amount}",
                field="amount",
            )
        self.usdc_balance += amount
        self.touch()

    def withdraw_usdc(self, amount: Decimal) -> None:
        """Record a USDC withdrawal from the pool."""
        if amount <= 0:
            raise ValidationError(
                f"Withdrawal amount must be positive, got {amount}",
                field="amount",
            )
        if amount > self.usdc_balance:
            raise PolicyViolation(
                f"Insufficient USDC balance: {self.usdc_balance}, requested: {amount}"
            )
        self.usdc_balance -= amount
        self.touch()

    def deposit_algo(self, microalgo: int) -> None:
        """Record an ALGO deposit (in microALGO)."""
        if microalgo <= 0:
            raise ValidationError(
                f"Deposit must be positive, got {microalgo}", field="microalgo"
            )
        self.algo_balance_microalgo += microalgo
        self.touch()

    def withdraw_algo(self, microalgo: int) -> None:
        """Record an ALGO withdrawal (in microALGO)."""
        if microalgo <= 0:
            raise ValidationError(
                f"Withdrawal must be positive, got {microalgo}", field="microalgo"
            )
        if microalgo > self.algo_balance_microalgo:
            raise PolicyViolation(
                f"Insufficient ALGO balance: {self.algo_balance_microalgo}, "
                f"requested: {microalgo}"
            )
        self.algo_balance_microalgo -= microalgo
        self.touch()

    # ── FX Rate ───────────────────────────────────────────────────────────────

    def update_fx_rate(self, rate: Decimal) -> FXRateUpdated:
        """Update the cached INR/USD FX rate and emit event if significant."""
        old_rate = self.last_fx_rate_inr_usd
        self.last_fx_rate_inr_usd = rate
        self.last_rate_updated_at = _utcnow()
        self.touch()
        return FXRateUpdated(
            aggregate_id=self.id,
            event_type="FXRateUpdated",
            enterprise_id=self.enterprise_id,
            old_rate=old_rate,
            new_rate=rate,
        )

    @property
    def algo_balance_algo(self) -> Decimal:
        """Convert microALGO to ALGO."""
        return Decimal(self.algo_balance_microalgo) / Decimal("1000000")

    @property
    def total_value_inr(self) -> Decimal:
        """Estimate total pool value in INR using last FX rate."""
        if self.last_fx_rate_inr_usd <= 0:
            return self.inr_balance
        usdc_in_inr = self.usdc_balance / self.last_fx_rate_inr_usd
        return self.inr_balance + usdc_in_inr


# ── Domain Events ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FXRateUpdated(DomainEvent):
    """Emitted when the cached FX rate changes."""

    enterprise_id: uuid.UUID = field(default_factory=uuid.uuid4)
    old_rate: Decimal = Decimal("0")
    new_rate: Decimal = Decimal("0")


@dataclass(frozen=True)
class LiquidityThresholdBreached(DomainEvent):
    """Emitted when liquidity drops below the configured threshold."""

    enterprise_id: uuid.UUID = field(default_factory=uuid.uuid4)
    currency: str = ""
    current_balance: Decimal = Decimal("0")
    threshold: Decimal = Decimal("0")
