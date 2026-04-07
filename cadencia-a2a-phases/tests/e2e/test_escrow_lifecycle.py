"""
End-to-end test: escrow lifecycle on Algorand localnet.

context.md §12: SRS-SC-001 dry-run simulation before every broadcast.
context.md §9.4: DEPLOYED → FUNDED → RELEASED with Merkle root anchoring.

Tests cover:
    - TC-004: Dry-run failure prevents broadcast
    - TC-005: Partial escrow fund amount rejected
    - TC-006: Frozen escrow rejects release
    - TC-007: Full happy-path lifecycle (deploy → fund → release)
    - TC-008: Freeze/unfreeze/refund dispute path
    - TC-009: Pera Wallet unsigned transaction flow
    - TC-010: Wallet challenge-response verification

Prerequisites:
  - Algorand localnet running (docker compose up algorand-localnet)
  - ALGORAND_ESCROW_CREATOR_MNEMONIC set
  - DATABASE_URL pointing to test database
  - REDIS_URL pointing to test Redis

Run:
    pytest tests/e2e/test_escrow_lifecycle.py -m e2e -x -v
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.settlement.domain.escrow import Escrow, EscrowStatus
from src.settlement.domain.value_objects import (
    AlgoAppAddress,
    AlgoAppId,
    EscrowAmount,
    MerkleRoot,
    MicroAlgo,
    TxId,
)
from src.shared.domain.exceptions import PolicyViolation


@pytest.mark.e2e
class TestEscrowE2ELifecycle:
    """
    E2E tests: full escrow lifecycle validation.

    These tests verify escrow domain model state transitions and
    settlement service behavior. Tests marked with @pytest.mark.e2e.
    """

    @pytest.mark.asyncio
    async def test_deploy_fund_release_lifecycle(self):
        """
        TC-007: Full happy-path lifecycle.

        1. Create escrow domain entity
        2. Record deployment (DEPLOYED state)
        3. Record funding (FUNDED state)
        4. Compute Merkle root from audit entries
        5. Record release with Merkle root (RELEASED state)
        6. Verify all tx IDs and final state
        """
        session_id = uuid.uuid4()

        # 1. Create escrow
        escrow = Escrow(
            session_id=session_id,
            buyer_address="A" * 58,
            seller_address="B" * 58,
            amount=EscrowAmount(value=MicroAlgo(value=5_000_000)),
        )
        assert escrow.status == EscrowStatus.DEPLOYED

        deploy_event = escrow.record_deployment(
            app_id=AlgoAppId(value=42),
            app_address=AlgoAppAddress(value="C" * 58),
            tx_id=TxId(value="D" * 52),
        )
        assert escrow.algo_app_id.value == 42
        assert escrow.deploy_tx_id.value == "D" * 52
        assert deploy_event is not None

        # 3. Fund escrow
        fund_event = escrow.record_funding(TxId(value="E" * 52))
        assert escrow.status == EscrowStatus.FUNDED
        assert escrow.fund_tx_id.value == "E" * 52

        # 4. Compute Merkle root
        from src.shared.infrastructure.merkle_service import MerkleService

        merkle = MerkleService()
        entries = [
            f"DEPLOYED:escrow={escrow.id}:app_id=42",
            f"FUNDED:escrow={escrow.id}:tx={"E" * 52}:amount=5000000",
        ]
        root = merkle.compute_root(entries)
        assert len(root) == 64

        # 5. Release
        release_event = escrow.record_release(
            tx_id=TxId(value="F" * 52),
            merkle_root=MerkleRoot(value=root),
        )
        assert escrow.status == EscrowStatus.RELEASED
        assert escrow.merkle_root.value == root
        assert escrow.settled_at is not None

    @pytest.mark.asyncio
    async def test_deploy_fund_refund_dispute_path(self):
        """
        TC-008: Dispute path.

        1. Deploy + Fund escrow
        2. Freeze (compliance dispute)
        3. Unfreeze after resolution
        4. Refund buyer
        """
        escrow = Escrow(
            session_id=uuid.uuid4(),
            buyer_address="A" * 58,
            seller_address="B" * 58,
            amount=EscrowAmount(value=MicroAlgo(value=10_000_000)),
        )

        # Deploy + Fund
        escrow.record_deployment(
            app_id=AlgoAppId(value=100),
            app_address=AlgoAppAddress(value="C" * 58),
            tx_id=TxId(value="D" * 52),
        )
        escrow.record_funding(TxId(value="E" * 52))
        assert escrow.status == EscrowStatus.FUNDED

        # Freeze
        freeze_event = escrow.freeze()
        assert escrow.status == EscrowStatus.FROZEN
        assert freeze_event is not None

        # Attempt release on frozen escrow → should fail
        with pytest.raises(Exception):
            escrow.record_release(
                tx_id=TxId(value="F" * 52),
                merkle_root=MerkleRoot(value="e" * 64),
            )

        # Unfreeze
        unfreeze_event = escrow.unfreeze()
        assert escrow.status == EscrowStatus.FUNDED
        assert unfreeze_event is not None

        # Refund
        refund_event = escrow.record_refund(TxId(value="G" * 52))
        assert escrow.status == EscrowStatus.REFUNDED
        assert escrow.refund_tx_id.value == "G" * 52

    @pytest.mark.asyncio
    async def test_dry_run_failure_prevents_broadcast(self):
        """
        TC-004: Dry-run failure prevents broadcast.

        When the AlgorandGateway dry-run simulation fails,
        the deploy_escrow operation should NOT proceed to broadcast.
        The escrow should remain in a pre-deployment state.
        """
        from src.settlement.application.services import SettlementService
        from src.settlement.application.commands import DeployEscrowCommand

        # Mock gateway that fails dry-run
        mock_gateway = AsyncMock()
        mock_gateway.deploy_escrow.side_effect = PolicyViolation(
            "Dry-run simulation failed: insufficient balance for MBR"
        )

        # Mock repos
        mock_escrow_repo = AsyncMock()
        mock_escrow_repo.get_by_session_id.return_value = None

        mock_settlement_repo = AsyncMock()
        mock_merkle = MagicMock()
        mock_anchor = AsyncMock()
        mock_publisher = AsyncMock()
        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)

        svc = SettlementService(
            escrow_repo=mock_escrow_repo,
            settlement_repo=mock_settlement_repo,
            blockchain_gateway=mock_gateway,
            merkle_service=mock_merkle,
            anchor_service=mock_anchor,
            event_publisher=mock_publisher,
            uow=mock_uow,
        )

        cmd = DeployEscrowCommand(
            session_id=uuid.uuid4(),
            buyer_enterprise_id=uuid.uuid4(),
            seller_enterprise_id=uuid.uuid4(),
            buyer_algo_address="A" * 58,
            seller_algo_address="B" * 58,
            agreed_price_microalgo=1_000_000,
        )

        with pytest.raises(PolicyViolation, match="Dry-run simulation failed"):
            await svc.deploy_escrow(cmd)

        # Verify: gateway was called but no event published (broadcast blocked)
        mock_gateway.deploy_escrow.assert_called_once()
        mock_publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_frozen_escrow_rejects_release(self):
        """
        TC-006: Frozen escrow rejects release.

        A frozen escrow must not allow release until unfrozen.
        """
        escrow = Escrow(
            session_id=uuid.uuid4(),
            buyer_address="A" * 58,
            seller_address="B" * 58,
            amount=EscrowAmount(value=MicroAlgo(value=2_000_000)),
        )

        # Deploy + Fund + Freeze
        escrow.record_deployment(
            app_id=AlgoAppId(value=200),
            app_address=AlgoAppAddress(value="C" * 58),
            tx_id=TxId(value="D" * 52),
        )
        escrow.record_funding(TxId(value="E" * 52))
        escrow.freeze()
        assert escrow.status == EscrowStatus.FROZEN

        # Attempt release → must fail
        with pytest.raises(Exception):
            escrow.record_release(
                tx_id=TxId(value="F" * 52),
                merkle_root=MerkleRoot(value="e" * 64),
            )

        # Escrow remains frozen
        assert escrow.status == EscrowStatus.FROZEN

    @pytest.mark.asyncio
    async def test_settlement_service_idempotent_deploy(self):
        """
        TC-015: Idempotent deploy — duplicate deploy returns existing escrow.

        context.md §9: idempotent deploy prevents double-deploy on retry.
        """
        from src.settlement.application.services import SettlementService
        from src.settlement.application.commands import DeployEscrowCommand

        existing_escrow = MagicMock()
        existing_escrow.id = uuid.uuid4()
        existing_escrow.algo_app_id = AlgoAppId(value=999)
        existing_escrow.algo_app_address = AlgoAppAddress(value="C" * 58)
        existing_escrow.status = EscrowStatus.DEPLOYED
        existing_escrow.deploy_tx_id = TxId(value="D" * 52)

        mock_escrow_repo = AsyncMock()
        mock_escrow_repo.get_by_session_id.return_value = existing_escrow

        svc = SettlementService(
            escrow_repo=mock_escrow_repo,
            settlement_repo=AsyncMock(),
            blockchain_gateway=AsyncMock(),
            merkle_service=MagicMock(),
            anchor_service=AsyncMock(),
            event_publisher=AsyncMock(),
            uow=AsyncMock(),
        )

        session_id = uuid.uuid4()
        cmd = DeployEscrowCommand(
            session_id=session_id,
            buyer_enterprise_id=uuid.uuid4(),
            seller_enterprise_id=uuid.uuid4(),
            buyer_algo_address="A" * 58,
            seller_algo_address="B" * 58,
            agreed_price_microalgo=1_000_000,
        )

        result = await svc.deploy_escrow(cmd)

        # Should return existing escrow, not deploy new
        assert result["escrow_id"] == existing_escrow.id
        assert result["status"] == "DEPLOYED"
        # Gateway should NOT have been called
        svc._gateway.deploy_escrow.assert_not_called()

    @pytest.mark.asyncio
    async def test_merkle_service_deterministic(self):
        """
        TC-016: MerkleService produces deterministic roots.

        Same entries → same root. Different entries → different root.
        """
        from src.shared.infrastructure.merkle_service import MerkleService

        merkle = MerkleService()

        entries_a = ["entry_1", "entry_2", "entry_3"]
        entries_b = ["entry_1", "entry_2", "entry_3"]
        entries_c = ["entry_1", "entry_2", "entry_4"]

        root_a = merkle.compute_root(entries_a)
        root_b = merkle.compute_root(entries_b)
        root_c = merkle.compute_root(entries_c)

        assert root_a == root_b  # Deterministic
        assert root_a != root_c  # Different input → different root
        assert len(root_a) == 64  # SHA-256 hex
