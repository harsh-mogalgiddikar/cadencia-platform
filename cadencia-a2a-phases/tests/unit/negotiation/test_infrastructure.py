# Phase Four Unit Tests: Infrastructure Layer
# Tests for NeutralEngine, PersonalizationBuilder, StubAgentDriver, LLM sanitizer integration.

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.negotiation.domain.agent_profile import AgentProfile
from src.negotiation.domain.offer import ProposerRole
from src.negotiation.domain.playbook import IndustryPlaybook
from src.negotiation.domain.session import NegotiationSession, SessionStatus
from src.negotiation.domain.value_objects import (
    AutomationLevel,
    OfferValue,
    RiskProfile,
    RoundNumber,
    StrategyWeights,
)
from src.negotiation.infrastructure.llm_agent_driver import StubAgentDriver
from src.negotiation.infrastructure.neutral_engine import NeutralEngine
from src.negotiation.infrastructure.personalization import PersonalizationBuilder


# ═══════════════════════════════════════════════════════════════════════════════
# PersonalizationBuilder Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPersonalizationBuilder:
    def test_build_returns_string(self):
        profile = AgentProfile()
        builder = PersonalizationBuilder()
        result = builder.build(profile, None, "BUYER")
        assert isinstance(result, str)
        assert "BUYER" in result

    def test_build_never_includes_exact_budget(self):
        profile = AgentProfile(
            risk_profile=RiskProfile(budget_ceiling=Decimal("7777777")),
        )
        builder = PersonalizationBuilder()
        result = builder.build(profile, None, "BUYER")
        assert "7777777" not in result

    def test_build_includes_budget_bucket(self):
        profile = AgentProfile(
            risk_profile=RiskProfile(budget_ceiling=Decimal("5000000")),
        )
        builder = PersonalizationBuilder()
        result = builder.build(profile, None, "BUYER")
        assert "HIGH" in result

    def test_build_with_playbook(self):
        profile = AgentProfile()
        playbook = IndustryPlaybook(
            vertical="steel",
            playbook_config={"pricing_norms": ["bulk discount 5-10%"]},
        )
        builder = PersonalizationBuilder()
        result = builder.build(profile, playbook, "SELLER")
        assert "steel" in result
        assert "SELLER" in result

    def test_build_conservative_strategy(self):
        profile = AgentProfile(
            strategy_weights=StrategyWeights(concession_rate=0.03),
        )
        builder = PersonalizationBuilder()
        result = builder.build(profile, None, "BUYER")
        assert "conservative" in result


# ═══════════════════════════════════════════════════════════════════════════════
# StubAgentDriver Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStubAgentDriver:
    @pytest.mark.anyio
    async def test_generate_offer_returns_valid_dict(self):
        driver = StubAgentDriver()
        result = await driver.generate_offer(
            system_prompt="test",
            session_context={"round_count": 1},
            offer_history=[{"price": 100000.0}],
        )
        assert "action" in result
        assert "price" in result
        assert "reasoning" in result
        assert result["price"] > 0

    @pytest.mark.anyio
    async def test_stub_accepts_after_five_rounds(self):
        driver = StubAgentDriver()
        result = await driver.generate_offer(
            system_prompt="test",
            session_context={"round_count": 5},
            offer_history=[{"price": 100000.0}],
        )
        assert result["action"] == "ACCEPT"

    @pytest.mark.anyio
    async def test_stub_offers_before_round_five(self):
        driver = StubAgentDriver()
        result = await driver.generate_offer(
            system_prompt="test",
            session_context={"round_count": 2},
            offer_history=[{"price": 100000.0}],
        )
        assert result["action"] == "OFFER"


# ═══════════════════════════════════════════════════════════════════════════════
# NeutralEngine Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestNeutralEngine:
    def _make_session(self) -> NegotiationSession:
        return NegotiationSession(
            rfq_id=uuid.uuid4(),
            match_id=uuid.uuid4(),
            buyer_enterprise_id=uuid.uuid4(),
            seller_enterprise_id=uuid.uuid4(),
        )

    def _make_profile(self, budget=Decimal("1000000")) -> AgentProfile:
        return AgentProfile(
            risk_profile=RiskProfile(budget_ceiling=budget),
        )

    @pytest.mark.anyio
    async def test_process_turn_first_turn_is_buyer(self):
        mock_driver = AsyncMock()
        mock_driver.generate_offer.return_value = {
            "action": "OFFER",
            "price": 50000.0,
            "reasoning": "Starting offer",
            "confidence": 0.8,
        }
        engine = NeutralEngine(agent_driver=mock_driver)
        session = self._make_session()
        buyer = self._make_profile()
        seller = self._make_profile()

        offer, is_terminal = await engine.process_turn(
            session, buyer, seller, None, None
        )
        assert offer.proposer_role == ProposerRole.BUYER
        assert offer.price.amount == Decimal("50000")
        assert is_terminal is False

    @pytest.mark.anyio
    async def test_process_turn_accept_is_terminal(self):
        mock_driver = AsyncMock()
        mock_driver.generate_offer.return_value = {
            "action": "ACCEPT",
            "price": 50000.0,
            "reasoning": "Acceptable price",
            "confidence": 0.95,
        }
        engine = NeutralEngine(agent_driver=mock_driver)
        session = self._make_session()
        buyer = self._make_profile()
        seller = self._make_profile()

        offer, is_terminal = await engine.process_turn(
            session, buyer, seller, None, None
        )
        assert is_terminal is True

    @pytest.mark.anyio
    async def test_process_turn_reject_is_terminal(self):
        mock_driver = AsyncMock()
        mock_driver.generate_offer.return_value = {
            "action": "REJECT",
            "price": 1.0,
            "reasoning": "Price too high",
            "confidence": 0.9,
        }
        engine = NeutralEngine(agent_driver=mock_driver)
        session = self._make_session()
        buyer = self._make_profile()
        seller = self._make_profile()

        offer, is_terminal = await engine.process_turn(
            session, buyer, seller, None, None
        )
        assert is_terminal is True
        assert "REJECT" in (offer.agent_reasoning or "")

    @pytest.mark.anyio
    async def test_engine_publishes_sse_event(self):
        mock_driver = AsyncMock()
        mock_driver.generate_offer.return_value = {
            "action": "OFFER",
            "price": 50000.0,
            "reasoning": "test",
            "confidence": 0.7,
        }
        mock_sse = AsyncMock()
        engine = NeutralEngine(agent_driver=mock_driver, sse_publisher=mock_sse)
        session = self._make_session()
        buyer = self._make_profile()
        seller = self._make_profile()

        await engine.process_turn(session, buyer, seller, None, None)
        mock_sse.publish_turn.assert_called_once()

    @pytest.mark.anyio
    async def test_determine_turn_alternates(self):
        engine = NeutralEngine(agent_driver=AsyncMock())
        session = self._make_session()
        # First turn: buyer
        assert engine._determine_turn(session) == ProposerRole.BUYER
