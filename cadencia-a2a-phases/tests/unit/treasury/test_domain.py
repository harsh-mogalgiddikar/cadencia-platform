"""
Unit tests for Treasury domain entities and value objects.

context.md §4.2: Treasury bounded context — LiquidityPool, FXPosition, value objects.
context.md §15: domain/ ≥ 90% line coverage.
"""

import uuid
from decimal import Decimal

import pytest

from src.treasury.domain.fx_position import FXPosition
from src.treasury.domain.liquidity_pool import (
    FXRateUpdated,
    LiquidityPool,
)
from src.treasury.domain.value_objects import (
    ConversionResult,
    CurrencyPair,
    FXRate,
    LiquidityBalance,
)
from src.shared.domain.exceptions import PolicyViolation, ValidationError
from datetime import datetime, timezone


# ── CurrencyPair ──────────────────────────────────────────────────────────────


class TestCurrencyPair:
    def test_valid_pair(self):
        pair = CurrencyPair(base="inr", target="usd")
        assert pair.base == "INR"
        assert pair.target == "USD"

    def test_invalid_base(self):
        with pytest.raises(ValidationError, match="Invalid base currency"):
            CurrencyPair(base="", target="USD")

    def test_invalid_target(self):
        with pytest.raises(ValidationError, match="Invalid target currency"):
            CurrencyPair(base="INR", target="US")

    def test_str_representation(self):
        pair = CurrencyPair(base="INR", target="USD")
        assert str(pair) == "INR/USD"


# ── FXRate ────────────────────────────────────────────────────────────────────


class TestFXRate:
    def test_valid_rate(self):
        rate = FXRate(
            base="INR", target="USD",
            rate=Decimal("0.012"),
            fetched_at=datetime.now(tz=timezone.utc),
        )
        assert rate.pair == "INR/USD"
        assert rate.rate == Decimal("0.012")

    def test_zero_rate_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            FXRate(
                base="INR", target="USD",
                rate=Decimal("0"),
                fetched_at=datetime.now(tz=timezone.utc),
            )

    def test_negative_rate_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            FXRate(
                base="INR", target="USD",
                rate=Decimal("-1"),
                fetched_at=datetime.now(tz=timezone.utc),
            )

    def test_invert(self):
        rate = FXRate(
            base="INR", target="USD",
            rate=Decimal("0.012"),
            fetched_at=datetime.now(tz=timezone.utc),
        )
        inv = rate.invert()
        assert inv.base == "USD"
        assert inv.target == "INR"
        # 1 / 0.012 ≈ 83.33
        assert inv.rate > Decimal("80")


# ── LiquidityBalance ─────────────────────────────────────────────────────────


class TestLiquidityBalance:
    def test_valid_balance(self):
        bal = LiquidityBalance(
            inr_balance=Decimal("1000000"),
            usdc_balance=Decimal("5000"),
            algo_balance_microalgo=100_000_000,
        )
        assert bal.algo_balance_algo == Decimal("100")

    def test_negative_inr_raises(self):
        with pytest.raises(ValidationError, match="negative"):
            LiquidityBalance(
                inr_balance=Decimal("-1"),
                usdc_balance=Decimal("0"),
                algo_balance_microalgo=0,
            )


# ── LiquidityPool ────────────────────────────────────────────────────────────


class TestLiquidityPool:
    def _make_pool(self, **kwargs) -> LiquidityPool:
        defaults = {"enterprise_id": uuid.uuid4()}
        defaults.update(kwargs)
        return LiquidityPool(**defaults)

    def test_initial_zero_balances(self):
        pool = self._make_pool()
        assert pool.inr_balance == Decimal("0")
        assert pool.usdc_balance == Decimal("0")
        assert pool.algo_balance_microalgo == 0

    # ── INR ──

    def test_deposit_inr(self):
        pool = self._make_pool()
        pool.deposit_inr(Decimal("100000"))
        assert pool.inr_balance == Decimal("100000")

    def test_withdraw_inr(self):
        pool = self._make_pool(inr_balance=Decimal("50000"))
        pool.withdraw_inr(Decimal("30000"))
        assert pool.inr_balance == Decimal("20000")

    def test_withdraw_inr_insufficient_raises(self):
        pool = self._make_pool(inr_balance=Decimal("100"))
        with pytest.raises(PolicyViolation, match="Insufficient INR"):
            pool.withdraw_inr(Decimal("200"))

    def test_deposit_zero_raises(self):
        pool = self._make_pool()
        with pytest.raises(ValidationError, match="positive"):
            pool.deposit_inr(Decimal("0"))

    # ── USDC ──

    def test_deposit_usdc(self):
        pool = self._make_pool()
        pool.deposit_usdc(Decimal("1000"))
        assert pool.usdc_balance == Decimal("1000")

    def test_withdraw_usdc_insufficient_raises(self):
        pool = self._make_pool(usdc_balance=Decimal("50"))
        with pytest.raises(PolicyViolation, match="Insufficient USDC"):
            pool.withdraw_usdc(Decimal("100"))

    # ── ALGO ──

    def test_deposit_algo(self):
        pool = self._make_pool()
        pool.deposit_algo(10_000_000)
        assert pool.algo_balance_microalgo == 10_000_000
        assert pool.algo_balance_algo == Decimal("10")

    def test_withdraw_algo_insufficient_raises(self):
        pool = self._make_pool(algo_balance_microalgo=5_000_000)
        with pytest.raises(PolicyViolation, match="Insufficient ALGO"):
            pool.withdraw_algo(10_000_000)

    # ── FX Rate ──

    def test_update_fx_rate(self):
        pool = self._make_pool()
        event = pool.update_fx_rate(Decimal("0.012"))
        assert pool.last_fx_rate_inr_usd == Decimal("0.012")
        assert isinstance(event, FXRateUpdated)
        assert event.new_rate == Decimal("0.012")

    def test_total_value_inr(self):
        pool = self._make_pool(
            inr_balance=Decimal("100000"),
            usdc_balance=Decimal("1200"),
            last_fx_rate_inr_usd=Decimal("0.012"),
        )
        # total = 100000 + (1200 / 0.012) = 100000 + 100000 = 200000
        assert pool.total_value_inr == Decimal("200000")


# ── FXPosition ────────────────────────────────────────────────────────────────


class TestFXPosition:
    def _make_position(self, **kwargs) -> FXPosition:
        defaults = {
            "enterprise_id": uuid.uuid4(),
            "currency_pair": "INR/USD",
            "direction": "LONG",
            "notional_amount": Decimal("100000"),
            "entry_rate": Decimal("0.012"),
            "current_rate": Decimal("0.012"),
        }
        defaults.update(kwargs)
        return FXPosition(**defaults)

    def test_unrealized_pnl_no_change(self):
        pos = self._make_position()
        assert pos.unrealized_pnl == Decimal("0")

    def test_unrealized_pnl_long_profit(self):
        pos = self._make_position(
            direction="LONG",
            entry_rate=Decimal("0.012"),
            current_rate=Decimal("0.013"),
        )
        pnl = pos.unrealized_pnl
        assert pnl > 0

    def test_unrealized_pnl_short_profit(self):
        pos = self._make_position(
            direction="SHORT",
            entry_rate=Decimal("0.012"),
            current_rate=Decimal("0.011"),
        )
        pnl = pos.unrealized_pnl
        assert pnl > 0

    def test_close_position(self):
        pos = self._make_position(
            current_rate=Decimal("0.013"),
        )
        pnl = pos.close()
        assert pos.status == "CLOSED"
        assert pos.closed_at is not None
        assert pnl > 0

    def test_close_already_closed_raises(self):
        pos = self._make_position()
        pos.close()
        with pytest.raises(PolicyViolation, match="already closed"):
            pos.close()

    def test_invalid_direction_raises(self):
        with pytest.raises(PolicyViolation, match="LONG or SHORT"):
            self._make_position(direction="NEUTRAL")

    def test_update_current_rate(self):
        pos = self._make_position()
        pos.update_current_rate(Decimal("0.015"))
        assert pos.current_rate == Decimal("0.015")
