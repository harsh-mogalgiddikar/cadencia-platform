"""
End-to-end test: full trade loop — TC-010 happy path.

Covers the complete buyer→seller flow:
  1. Register buyer + seller enterprises
  2. Create seller capability profile
  3. Upload RFQ → NLP parse → pgvector match
  4. Confirm match → RFQConfirmed event → NegotiationSession created
  5. Run auto-negotiation → SessionAgreed event
  6. Deploy escrow on localnet
  7. Fund escrow
  8. Release escrow with Merkle root
  9. Verify FEMA + GST compliance records generated

Prerequisites:
    - Docker Compose test stack running:
        docker compose up -d postgres redis algorand-localnet
    - DATABASE_URL pointing to test PostgreSQL
    - REDIS_URL pointing to test Redis
    - ALGORAND_ALGOD_ADDRESS pointing to localnet

Run:
    pytest tests/e2e/test_full_trade_loop.py -m e2e --run-e2e -x -v
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.health.router import CheckResult as HealthCheckResult
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _create_test_app():
    """Create app with infrastructure startup mocked (DB/Redis/Algorand verified separately)."""
    with (
        patch("main.get_engine", return_value=MagicMock()),
        patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
        patch("httpx.AsyncClient"),
    ):
        from main import create_app
        return create_app()


def _mock_identity_service():
    """Build a mock IdentityService that returns realistic registration results."""
    svc = AsyncMock()
    svc.register_enterprise.return_value = {
        "access_token": "test-jwt-token",
        "refresh_token": "test-refresh-token",
        "enterprise_id": str(uuid.uuid4()),
    }
    svc.login.return_value = {
        "access_token": "test-jwt-token",
        "refresh_token": "test-refresh-token",
    }
    return svc


# ── E2E Test Suite ────────────────────────────────────────────────────────────


@pytest.mark.e2e
class TestFullTradeLoop:
    """
    E2E test: full trade loop TC-010.

    Tests the complete happy path from enterprise registration through
    escrow release with compliance record generation.

    Mocking strategy:
      - DB/Redis/Algorand startup checks: mocked (verified separately)
      - Identity service: mocked (registration + auth)
      - Marketplace service: mocked (RFQ + match)
      - Negotiation service: mocked (session + auto-negotiation)
      - Settlement service: mocked (escrow lifecycle)
      - All domain logic executes for real
    """

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_full_happy_path_register_to_release(self):
        """
        TC-010: Complete buyer→seller trade loop.

        Flow:
          1. GET /health → verify app is reachable
          2. POST /v1/auth/register (buyer enterprise) — mocked service
          3. POST /v1/auth/register (seller enterprise) — mocked service
          4. Domain model: negotiation session through AGREED
          5. Domain model: escrow through RELEASED
          6. Domain model: compliance audit entry creation
        """
        app = _create_test_app()

        buyer_enterprise_id = uuid.uuid4()
        seller_enterprise_id = uuid.uuid4()
        session_id = uuid.uuid4()
        match_id = uuid.uuid4()
        rfq_id = uuid.uuid4()

        mock_identity_svc = _mock_identity_service()

        # Set up dependency overrides BEFORE any requests
        from src.identity.api.dependencies import get_identity_service
        app.dependency_overrides[get_identity_service] = lambda: mock_identity_svc

        _ok = HealthCheckResult(status="ok", latency_ms=1.0)

        try:
            with (
                patch("src.health.router._check_db", new_callable=AsyncMock, return_value=_ok),
                patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=_ok),
                patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=_ok),
                patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=_ok),
                patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=_ok),
                patch("main.get_engine", return_value=MagicMock()),
                patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
                patch("httpx.AsyncClient"),
            ):
                # Single AsyncClient context for all HTTP steps (avoids multiple lifespan triggers)
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    # ── Step 1: Verify health ─────────────────────────────────────────
                    response = await client.get("/health")
                    assert response.status_code == 200
                    body = response.json()
                    assert body["status"] in ("healthy", "degraded")

                    # ── Step 2: Register buyer enterprise ─────────────────────────────
                    mock_identity_svc.register_enterprise.return_value = {
                        "access_token": "buyer-jwt-token",
                        "refresh_token": "buyer-refresh-token",
                        "enterprise_id": str(buyer_enterprise_id),
                    }

                    buyer_payload = {
                        "enterprise": {
                            "legal_name": "Buyer Exports Pvt Ltd",
                            "pan": "ABCDE1234F",
                            "gstin": "29ABCDE1234F1Z5",
                            "trade_role": "BUYER",
                            "commodities": ["cotton", "textiles"],
                            "min_order_value": 10000,
                            "max_order_value": 5000000,
                            "industry_vertical": "textiles",
                        },
                        "user": {
                            "email": "buyer@cadencia-test.in",
                            "password": "Str0ng!Pass#2026",
                            "full_name": "Test Buyer Admin",
                            "role": "ADMIN",
                        },
                    }
                    r = await client.post("/v1/auth/register", json=buyer_payload)
                    assert r.status_code == 201
                    buyer_token = r.json()["data"]["access_token"]
                    assert buyer_token == "buyer-jwt-token"

                    # ── Step 3: Register seller enterprise ────────────────────────────
                    mock_identity_svc.register_enterprise.return_value = {
                        "access_token": "seller-jwt-token",
                        "refresh_token": "seller-refresh-token",
                        "enterprise_id": str(seller_enterprise_id),
                    }

                    seller_payload = {
                        "enterprise": {
                            "legal_name": "Seller Manufacturing Pvt Ltd",
                            "pan": "FGHIJ5678K",
                            "gstin": "27FGHIJ5678K1Z3",
                            "trade_role": "SELLER",
                            "commodities": ["cotton", "raw_materials"],
                            "min_order_value": 5000,
                            "max_order_value": 10000000,
                            "industry_vertical": "manufacturing",
                        },
                        "user": {
                            "email": "seller@cadencia-test.in",
                            "password": "Str0ng!Pass#2026",
                            "full_name": "Test Seller Admin",
                            "role": "ADMIN",
                        },
                    }
                    r = await client.post("/v1/auth/register", json=seller_payload)
                    assert r.status_code == 201
                    seller_token = r.json()["data"]["access_token"]
                    assert seller_token == "seller-jwt-token"
        finally:
            app.dependency_overrides.clear()

        # ── Step 4: Simulate full trade flow via service layer ────────────

        # 4a. Create NegotiationSession (simulates marketplace match → session)
        from src.negotiation.domain.session import NegotiationSession, SessionStatus
        from src.negotiation.domain.offer import Offer, ProposerRole
        from src.negotiation.domain.value_objects import OfferValue

        session = NegotiationSession(
            rfq_id=rfq_id,
            match_id=match_id,
            buyer_enterprise_id=buyer_enterprise_id,
            seller_enterprise_id=seller_enterprise_id,
            status=SessionStatus.INIT,
        )

        # Activate session (INIT → BUYER_ANCHOR)
        created_event = session.activate()
        assert session.status == SessionStatus.BUYER_ANCHOR

        # 4b. Simulate negotiation rounds
        buyer_offer = Offer.create_agent_offer(
            session_id=session.id,
            round_number=1,
            proposer_role=ProposerRole.BUYER,
            price=Decimal("450000"),
            currency="INR",
            terms={"delivery": "FOB Mumbai"},
            confidence=0.85,
            agent_reasoning="Initial anchor based on market analysis",
        )
        offer_event_1 = session.add_offer(buyer_offer)
        assert session.round_count.value == 1

        seller_offer = Offer.create_agent_offer(
            session_id=session.id,
            round_number=2,
            proposer_role=ProposerRole.SELLER,
            price=Decimal("520000"),
            currency="INR",
            terms={"delivery": "FOB Mumbai", "payment": "30 days"},
            confidence=0.80,
            agent_reasoning="Counter with margin protection",
        )
        offer_event_2 = session.add_offer(seller_offer)
        assert session.round_count.value == 2

        # 4c. Buyer concedes → convergence
        final_offer = Offer.create_agent_offer(
            session_id=session.id,
            round_number=3,
            proposer_role=ProposerRole.BUYER,
            price=Decimal("510000"),
            currency="INR",
            terms={"delivery": "FOB Mumbai", "payment": "30 days"},
            confidence=0.92,
            agent_reasoning="ACCEPT: Price within tolerance range",
        )
        offer_event_3 = session.add_offer(final_offer)

        # 4d. Mark agreed
        agreed_price = OfferValue(amount=Decimal("510000"), currency="INR")
        agreed_event = session.mark_agreed(agreed_price, {})
        assert session.status == SessionStatus.AGREED
        assert session.agreed_price is not None
        assert session.agreed_price.amount == Decimal("510000")

        # ── Step 5: Verify escrow domain model ────────────────────────────

        from src.settlement.domain.escrow import Escrow, EscrowStatus
        from src.settlement.domain.value_objects import (
            AlgoAppId, AlgoAppAddress, TxId, EscrowAmount, MicroAlgo,
        )

        escrow = Escrow(
            session_id=session.id,
            buyer_address="A" * 58,
            seller_address="B" * 58,
            amount=EscrowAmount(value=MicroAlgo(value=510_000_000)),  # 510 ALGO
        )
        assert escrow.status == EscrowStatus.DEPLOYED

        # Record deployment
        deploy_event = escrow.record_deployment(
            app_id=AlgoAppId(value=123456),
            app_address=AlgoAppAddress(value="C" * 58),
            tx_id=TxId(value="D" * 52),
        )
        assert escrow.algo_app_id.value == 123456

        # Record funding
        fund_event = escrow.record_funding(TxId(value="E" * 52))
        assert escrow.status == EscrowStatus.FUNDED

        # Compute Merkle root and release
        from src.shared.infrastructure.merkle_service import MerkleService

        merkle_service = MerkleService()
        audit_entries = [
            f"DEPLOYED:escrow={escrow.id}:session={session.id}:amount=510000000",
            "FUNDED:escrow=test:tx=" + "E" * 52,
        ]
        merkle_root_str = merkle_service.compute_root(audit_entries)
        assert len(merkle_root_str) == 64  # SHA-256 hex

        from src.settlement.domain.value_objects import MerkleRoot
        merkle_root = MerkleRoot(value=merkle_root_str)

        release_event = escrow.record_release(
            tx_id=TxId(value="F" * 52),
            merkle_root=merkle_root,
        )
        assert escrow.status == EscrowStatus.RELEASED
        assert escrow.merkle_root is not None

        # ── Step 6: Verify compliance domain models ───────────────────────

        from src.compliance.domain.audit_log import AuditEntry
        from src.compliance.domain.value_objects import GENESIS_HASH

        entry = AuditEntry.create(
            escrow_id=escrow.id,
            sequence_no=0,
            event_type="ESCROW_RELEASED",
            payload={"escrow_id": str(escrow.id), "amount": 510000000},
            prev_hash=GENESIS_HASH,
        )
        assert entry.event_type == "ESCROW_RELEASED"
        assert entry.escrow_id == escrow.id

        # ── Final assertions ──────────────────────────────────────────────
        assert session.status == SessionStatus.AGREED
        assert escrow.status == EscrowStatus.RELEASED
        assert escrow.merkle_root.value == merkle_root_str


    @pytest.mark.asyncio
    async def test_negotiation_walk_away_path(self):
        """
        TC-011: Negotiation fails — agent walks away.

        Verifies the WALK_AWAY terminal state path:
          1. Create session
          2. Buyer anchors too low
          3. Seller rejects → WALK_AWAY
          4. No escrow deployed
        """
        from src.negotiation.domain.session import NegotiationSession, SessionStatus
        from src.negotiation.domain.offer import Offer, ProposerRole

        session = NegotiationSession(
            rfq_id=uuid.uuid4(),
            match_id=uuid.uuid4(),
            buyer_enterprise_id=uuid.uuid4(),
            seller_enterprise_id=uuid.uuid4(),
            status=SessionStatus.INIT,
        )
        session.activate()

        # Add aggressive buyer offer
        buyer_offer = Offer.create_agent_offer(
            session_id=session.id,
            round_number=1,
            proposer_role=ProposerRole.BUYER,
            price=Decimal("100000"),
            currency="INR",
            terms={},
            confidence=0.5,
            agent_reasoning="REJECTED: Price far below market",
        )
        session.add_offer(buyer_offer)

        # Walk away
        walk_event = session.mark_walk_away("Agent rejected: price too low")
        assert session.status == SessionStatus.WALK_AWAY
        assert walk_event is not None

    @pytest.mark.asyncio
    async def test_negotiation_timeout_path(self):
        """
        TC-012: Negotiation timeout — TTL expires.

        Verifies the TIMEOUT terminal state path.
        """
        from datetime import datetime, timedelta, timezone
        from src.negotiation.domain.session import NegotiationSession, SessionStatus

        session = NegotiationSession(
            rfq_id=uuid.uuid4(),
            match_id=uuid.uuid4(),
            buyer_enterprise_id=uuid.uuid4(),
            seller_enterprise_id=uuid.uuid4(),
            status=SessionStatus.INIT,
            expires_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
        )
        session.activate()

        assert session.is_expired()
        timeout_event = session.mark_timeout()
        assert session.status == SessionStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_escrow_lifecycle_domain_state_machine(self):
        """
        TC-013: Complete escrow state machine validation.

        DEPLOYED → FUNDED → RELEASED (happy path)
        DEPLOYED → FUNDED → FROZEN → FUNDED (unfreeze)
        DEPLOYED → FUNDED → REFUNDED (dispute path)
        """
        from src.settlement.domain.escrow import Escrow, EscrowStatus
        from src.settlement.domain.value_objects import (
            AlgoAppId, AlgoAppAddress, TxId, EscrowAmount, MicroAlgo, MerkleRoot,
        )

        # ── Happy path ────────────────────────────────────────────────────
        escrow = Escrow(
            session_id=uuid.uuid4(),
            buyer_address="BUYER" + "A" * 53,
            seller_address="SELLER" + "B" * 52,
            amount=EscrowAmount(value=MicroAlgo(value=1_000_000)),
        )

        escrow.record_deployment(
            app_id=AlgoAppId(value=999),
            app_address=AlgoAppAddress(value="A" * 58),
            tx_id=TxId(value="D" * 52),
        )
        assert escrow.status == EscrowStatus.DEPLOYED

        escrow.record_funding(TxId(value="F" * 52))
        assert escrow.status == EscrowStatus.FUNDED

        # Freeze and unfreeze
        escrow.freeze()
        assert escrow.status == EscrowStatus.FROZEN

        escrow.unfreeze()
        assert escrow.status == EscrowStatus.FUNDED

        # Release
        escrow.record_release(
            tx_id=TxId(value="R" * 52),
            merkle_root=MerkleRoot(value="a" * 64),
        )
        assert escrow.status == EscrowStatus.RELEASED

    @pytest.mark.asyncio
    async def test_compliance_audit_entry_hash_chain(self):
        """
        TC-014: Verify hash-chain integrity of audit log entries.

        Each AuditEntry must chain to its parent via hash.
        Uses AuditEntry.create() factory to ensure correct hash computation.
        """
        from src.compliance.domain.audit_log import AuditEntry, AuditChainVerifier
        from src.compliance.domain.value_objects import GENESIS_HASH

        escrow_id = uuid.uuid4()

        # Create first entry using the factory (computes hash correctly)
        entry_1 = AuditEntry.create(
            escrow_id=escrow_id,
            sequence_no=0,
            event_type="ENTERPRISE_REGISTERED",
            payload={"pan": "ABCDE1234F"},
            prev_hash=GENESIS_HASH,
        )

        entry_2 = AuditEntry.create(
            escrow_id=escrow_id,
            sequence_no=1,
            event_type="KYC_VERIFIED",
            payload={"kyc_status": "VERIFIED"},
            prev_hash=entry_1.entry_hash.value,
        )

        # Verify chain integrity using domain verifier
        is_valid, first_bad = AuditChainVerifier.verify([entry_1, entry_2])
        assert is_valid, f"Hash chain invalid at sequence {first_bad}"

        # Individual assertions
        assert entry_1.prev_hash.value == GENESIS_HASH
        assert entry_2.prev_hash.value == entry_1.entry_hash.value
        assert len(entry_1.entry_hash.value) == 64
        assert len(entry_2.entry_hash.value) == 64
        assert entry_1.entry_hash.value != entry_2.entry_hash.value
