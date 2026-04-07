"""
Integration tests for Treasury FX adapter (Frankfurter API).

Requires: REDIS_URL (optional for cache tests, uses mock if unavailable).
Tests real HTTP calls to Frankfurter API.
"""

import pytest

from decimal import Decimal

from src.treasury.infrastructure.frankfurter_fx_adapter import FrankfurterFXAdapter


@pytest.mark.integration
class TestFrankfurterFXAdapter:
    """
    Integration tests: live HTTP calls to https://api.frankfurter.app.

    These tests require network access. Run with:
        pytest -m integration tests/integration/
    """

    @pytest.mark.asyncio
    async def test_get_rate_inr_usd(self):
        """Verify we get a real INR/USD rate from Frankfurter."""
        adapter = FrankfurterFXAdapter(redis=None)
        rate = await adapter.get_rate("INR", "USD")

        assert rate.base == "INR"
        assert rate.target == "USD"
        assert rate.rate > Decimal("0")
        assert rate.source == "frankfurter"
        assert rate.pair == "INR/USD"

    @pytest.mark.asyncio
    async def test_get_rate_usd_inr(self):
        """Verify reverse pair works."""
        adapter = FrankfurterFXAdapter(redis=None)
        rate = await adapter.get_rate("USD", "INR")

        assert rate.base == "USD"
        assert rate.target == "INR"
        assert rate.rate > Decimal("50")  # 1 USD > 50 INR

    @pytest.mark.asyncio
    async def test_get_historical_rates(self):
        """Verify historical rates endpoint."""
        adapter = FrankfurterFXAdapter(redis=None)
        rates = await adapter.get_historical_rates("INR", "USD", days=5)

        # Should have at least 1 rate (weekdays only)
        assert len(rates) >= 1
        for r in rates:
            assert r.base == "INR"
            assert r.target == "USD"
            assert r.rate > Decimal("0")

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_pair(self):
        """Verify graceful fallback for unsupported currency pair."""
        adapter = FrankfurterFXAdapter(redis=None)
        rate = await adapter.get_rate("XYZ", "ABC")

        # Should return mock fallback
        assert rate.source == "mock"
