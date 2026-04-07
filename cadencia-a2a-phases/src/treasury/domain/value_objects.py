# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.
# context.md §4.2 — Treasury bounded context: value objects for FX rates and liquidity.
# Pure Python only — no FastAPI, SQLAlchemy, algosdk, httpx.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from src.shared.domain.exceptions import ValidationError


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True)
class CurrencyPair:
    """Immutable currency pair (e.g., INR/USD)."""

    base: str
    target: str

    def __post_init__(self) -> None:
        if not self.base or len(self.base) != 3:
            raise ValidationError(
                f"Invalid base currency: {self.base!r}. Must be 3-letter ISO code.",
                field="base",
            )
        if not self.target or len(self.target) != 3:
            raise ValidationError(
                f"Invalid target currency: {self.target!r}. Must be 3-letter ISO code.",
                field="target",
            )
        # Enforce uppercase via object.__setattr__ on frozen dataclass
        object.__setattr__(self, "base", self.base.upper())
        object.__setattr__(self, "target", self.target.upper())

    def __str__(self) -> str:
        return f"{self.base}/{self.target}"


@dataclass(frozen=True)
class FXRate:
    """Immutable snapshot of an FX exchange rate at a point in time."""

    base: str
    target: str
    rate: Decimal
    fetched_at: datetime
    source: str = "frankfurter"  # "frankfurter", "cache", "mock"

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValidationError(
                f"FX rate must be positive, got {self.rate}",
                field="rate",
            )

    @property
    def pair(self) -> str:
        return f"{self.base}/{self.target}"

    def invert(self) -> FXRate:
        """Return the inverse rate (e.g., INR/USD → USD/INR)."""
        return FXRate(
            base=self.target,
            target=self.base,
            rate=Decimal("1") / self.rate,
            fetched_at=self.fetched_at,
            source=self.source,
        )


@dataclass(frozen=True)
class LiquidityBalance:
    """Snapshot of an enterprise's liquidity position across currencies."""

    inr_balance: Decimal
    usdc_balance: Decimal
    algo_balance_microalgo: int

    def __post_init__(self) -> None:
        if self.inr_balance < 0:
            raise ValidationError("INR balance cannot be negative", field="inr_balance")
        if self.usdc_balance < 0:
            raise ValidationError("USDC balance cannot be negative", field="usdc_balance")
        if self.algo_balance_microalgo < 0:
            raise ValidationError(
                "ALGO balance cannot be negative", field="algo_balance_microalgo"
            )

    @property
    def algo_balance_algo(self) -> Decimal:
        """Convert microALGO to ALGO."""
        return Decimal(self.algo_balance_microalgo) / Decimal("1000000")


@dataclass(frozen=True)
class ConversionResult:
    """Result of a currency conversion (on/off-ramp)."""

    source_amount: Decimal
    source_currency: str
    target_amount: Decimal
    target_currency: str
    rate_used: Decimal
    fee: Decimal
    tx_reference: str
    converted_at: datetime
