"""
Mock On/Off-Ramp adapter — implements IPaymentProvider.

context.md §13: OnRampAdapter — convert_inr_to_usdc, convert_usdc_to_inr.
context.md §6: On/Off-Ramp Provider listed as external integration.

This is a prototype mock that uses Frankfurter FX rates for realistic
INR/USD rates and returns synthetic conversion results. Production
will replace this with a real on-ramp provider (MoonPay, Transak, etc.).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from src.shared.infrastructure.logging import get_logger
from src.treasury.domain.value_objects import ConversionResult

log = get_logger(__name__)

# Mock fee: 1.5% for on/off-ramp conversions
_MOCK_FEE_PCT = Decimal("0.015")

# Approximate INR/USD rate (used when FX provider unavailable)
_FALLBACK_RATE = Decimal("0.012")  # ~₹83/USD


class MockOnRampAdapter:
    """
    Mock implementation of IPaymentProvider for prototype stage.

    Uses real Frankfurter rates when available, falls back to a
    hardcoded rate. Generates synthetic transaction references.

    Production replacement: integrate with MoonPay, Transak, or Wyre API.
    """

    def __init__(self, fx_provider: object | None = None) -> None:
        """
        Args:
            fx_provider: Optional IFXProvider for realistic rates.
        """
        self._fx_provider = fx_provider

    async def get_exchange_rate(self, from_ccy: str, to_ccy: str) -> Decimal:
        """Get current exchange rate between currencies."""
        if self._fx_provider is not None:
            try:
                fx_rate = await self._fx_provider.get_rate(from_ccy, to_ccy)
                return fx_rate.rate
            except Exception:
                pass
        # Fallback
        if from_ccy.upper() == "INR" and to_ccy.upper() in ("USD", "USDC"):
            return _FALLBACK_RATE
        if from_ccy.upper() in ("USD", "USDC") and to_ccy.upper() == "INR":
            return Decimal("1") / _FALLBACK_RATE
        return Decimal("1")

    async def convert_inr_to_usdc(
        self,
        amount_inr: Decimal,
        enterprise_id: uuid.UUID,
    ) -> ConversionResult:
        """
        Convert INR to USDC for escrow funding.

        Mock: applies exchange rate + 1.5% fee, returns synthetic result.
        """
        rate = await self.get_exchange_rate("INR", "USD")
        gross_usdc = amount_inr * rate
        fee = gross_usdc * _MOCK_FEE_PCT
        net_usdc = gross_usdc - fee

        result = ConversionResult(
            source_amount=amount_inr,
            source_currency="INR",
            target_amount=net_usdc.quantize(Decimal("0.000001")),
            target_currency="USDC",
            rate_used=rate,
            fee=fee.quantize(Decimal("0.000001")),
            tx_reference=f"MOCK-INR-USDC-{uuid.uuid4().hex[:12]}",
            converted_at=datetime.now(tz=timezone.utc),
        )

        log.info(
            "mock_inr_to_usdc_conversion",
            enterprise_id=str(enterprise_id),
            amount_inr=str(amount_inr),
            usdc_received=str(result.target_amount),
            rate=str(rate),
            fee=str(result.fee),
            tx_ref=result.tx_reference,
        )
        return result

    async def convert_usdc_to_inr(
        self,
        amount_usdc: Decimal,
        enterprise_id: uuid.UUID,
    ) -> ConversionResult:
        """
        Convert USDC to INR after escrow release (seller receives INR).

        Mock: applies exchange rate + 1.5% fee, returns synthetic result.
        """
        rate = await self.get_exchange_rate("USD", "INR")
        gross_inr = amount_usdc * rate
        fee = gross_inr * _MOCK_FEE_PCT
        net_inr = gross_inr - fee

        result = ConversionResult(
            source_amount=amount_usdc,
            source_currency="USDC",
            target_amount=net_inr.quantize(Decimal("0.01")),
            target_currency="INR",
            rate_used=rate,
            fee=fee.quantize(Decimal("0.01")),
            tx_reference=f"MOCK-USDC-INR-{uuid.uuid4().hex[:12]}",
            converted_at=datetime.now(tz=timezone.utc),
        )

        log.info(
            "mock_usdc_to_inr_conversion",
            enterprise_id=str(enterprise_id),
            amount_usdc=str(amount_usdc),
            inr_received=str(result.target_amount),
            rate=str(rate),
            fee=str(result.fee),
            tx_ref=result.tx_reference,
        )
        return result
