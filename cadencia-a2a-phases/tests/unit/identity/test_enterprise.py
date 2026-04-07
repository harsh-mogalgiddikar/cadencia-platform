"""
Unit tests for Enterprise aggregate root — KYC state machine.

context.md §9.1: PENDING → KYC_SUBMITTED → VERIFIED → ACTIVE.
context.md §19: TC coverage for state transitions and policy violations.
"""

import uuid

import pytest

from src.identity.domain.enterprise import (
    Enterprise,
    EnterpriseActivated,
    EnterpriseKYCSubmitted,
    EnterpriseKYCVerified,
    KYCStatus,
    TradeRole,
)
from src.identity.domain.value_objects import AlgorandAddress, GSTIN, PAN
from src.shared.domain.exceptions import ConflictError, PolicyViolation, ValidationError


def _make_enterprise(**kwargs) -> Enterprise:
    """Factory helper with sensible defaults."""
    defaults = {
        "legal_name": "Test Corp",
        "pan": PAN(value="ABCDE1234F"),
        "gstin": GSTIN(value="27ABCDE1234F1Z5"),
        "trade_role": TradeRole.BUYER,
    }
    defaults.update(kwargs)
    return Enterprise(**defaults)


# ── KYC State Machine ─────────────────────────────────────────────────────────


class TestKYCStateMachine:
    def test_initial_status_is_pending(self):
        ent = _make_enterprise()
        assert ent.kyc_status == KYCStatus.PENDING

    def test_submit_kyc_transitions_to_submitted(self):
        ent = _make_enterprise()
        event = ent.submit_kyc({"doc": "pan_card.pdf"})
        assert ent.kyc_status == KYCStatus.KYC_SUBMITTED
        assert isinstance(event, EnterpriseKYCSubmitted)
        assert event.enterprise_id == ent.id

    def test_verify_kyc_transitions_to_verified(self):
        ent = _make_enterprise(kyc_status=KYCStatus.KYC_SUBMITTED)
        event = ent.verify_kyc()
        assert ent.kyc_status == KYCStatus.VERIFIED
        assert isinstance(event, EnterpriseKYCVerified)

    def test_activate_transitions_to_active(self):
        ent = _make_enterprise(kyc_status=KYCStatus.VERIFIED)
        event = ent.activate()
        assert ent.kyc_status == KYCStatus.ACTIVE
        assert isinstance(event, EnterpriseActivated)

    def test_full_lifecycle(self):
        """PENDING → KYC_SUBMITTED → VERIFIED → ACTIVE."""
        ent = _make_enterprise()
        ent.submit_kyc({"doc": "scan.pdf"})
        ent.verify_kyc()
        ent.activate()
        assert ent.kyc_status == KYCStatus.ACTIVE

    def test_cannot_skip_pending_to_verified(self):
        ent = _make_enterprise()
        with pytest.raises(ConflictError, match="expected KYC_SUBMITTED"):
            ent.verify_kyc()

    def test_cannot_skip_pending_to_active(self):
        ent = _make_enterprise()
        with pytest.raises(PolicyViolation, match="must be VERIFIED"):
            ent.activate()

    def test_cannot_submit_kyc_twice(self):
        ent = _make_enterprise()
        ent.submit_kyc({"doc": "first.pdf"})
        with pytest.raises(ConflictError, match="expected PENDING"):
            ent.submit_kyc({"doc": "second.pdf"})

    def test_cannot_activate_from_submitted(self):
        ent = _make_enterprise(kyc_status=KYCStatus.KYC_SUBMITTED)
        with pytest.raises(PolicyViolation, match="must be VERIFIED"):
            ent.activate()


# ── Wallet Linking ────────────────────────────────────────────────────────────


class TestWalletLinking:
    def test_link_algorand_wallet(self):
        ent = _make_enterprise()
        addr = AlgorandAddress(value="A" * 58)
        ent.link_algorand_wallet(addr)
        assert ent.algorand_wallet == addr

    def test_link_wallet_twice_raises_conflict(self):
        ent = _make_enterprise()
        ent.link_algorand_wallet(AlgorandAddress(value="A" * 58))
        with pytest.raises(ConflictError, match="already linked"):
            ent.link_algorand_wallet(AlgorandAddress(value="B" * 58))

    def test_no_wallet_by_default(self):
        ent = _make_enterprise()
        assert ent.algorand_wallet is None


# ── Agent Config ──────────────────────────────────────────────────────────────


class TestAgentConfig:
    def test_update_agent_config(self):
        ent = _make_enterprise()
        ent.update_agent_config({
            "industry_vertical": "STEEL",
            "commodities": ["HR_COIL", "TMT_BAR"],
            "min_order_value": 100000,
            "max_order_value": 5000000,
        })
        assert ent.industry_vertical == "STEEL"
        assert ent.commodities == ["HR_COIL", "TMT_BAR"]

    def test_min_greater_than_max_raises(self):
        ent = _make_enterprise()
        with pytest.raises(ValidationError, match="min_order_value"):
            ent.update_agent_config({
                "min_order_value": 5000000,
                "max_order_value": 100000,
            })
