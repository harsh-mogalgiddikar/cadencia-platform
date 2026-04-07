# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.
# context.md §4.2 — Treasury bounded context: FXPosition entity.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.shared.domain.base_entity import BaseEntity
from src.shared.domain.exceptions import PolicyViolation


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class FXPosition(BaseEntity):
    """
    Entity tracking FX exposure for an enterprise.

    Tracks unrealized PnL from currency pair positions arising
    from trade operations (e.g., buyer pays INR, escrow holds USDC).
    """

    enterprise_id: uuid.UUID = field(default_factory=uuid.uuid4)
    currency_pair: str = "INR/USD"  # e.g., "INR/USD"
    direction: str = "LONG"  # "LONG" or "SHORT"
    notional_amount: Decimal = Decimal("0")
    entry_rate: Decimal = Decimal("0")
    current_rate: Decimal = Decimal("0")
    status: str = "OPEN"  # "OPEN" or "CLOSED"
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.direction not in ("LONG", "SHORT"):
            raise PolicyViolation(
                f"FX position direction must be LONG or SHORT, got {self.direction!r}"
            )

    @property
    def unrealized_pnl(self) -> Decimal:
        """
        Calculate unrealized PnL based on current vs entry rate.

        LONG position: profit when rate goes up.
        SHORT position: profit when rate goes down.
        """
        if self.entry_rate == 0:
            return Decimal("0")
        rate_delta = self.current_rate - self.entry_rate
        if self.direction == "SHORT":
            rate_delta = -rate_delta
        return self.notional_amount * (rate_delta / self.entry_rate)

    def update_current_rate(self, rate: Decimal) -> None:
        """Update the current market rate for PnL calculation."""
        self.current_rate = rate
        self.touch()

    def close(self) -> Decimal:
        """Close the position and return realized PnL."""
        if self.status == "CLOSED":
            raise PolicyViolation(f"FX position {self.id} is already closed")
        pnl = self.unrealized_pnl
        self.status = "CLOSED"
        self.closed_at = _utcnow()
        self.touch()
        return pnl
