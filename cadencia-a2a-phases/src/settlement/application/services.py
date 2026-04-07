# context.md §4 DIP: SettlementService receives all dependencies via constructor.
# No algosdk, no sqlalchemy — only port interfaces from domain/ports.py.
# context.md §7.3: dry-run BEFORE every on-chain call (enforced in AlgorandGateway).
# context.md §9: idempotent deploy — check for existing escrow before calling gateway.

from __future__ import annotations

import time
import uuid

import structlog

from src.shared.domain.exceptions import (
    AuthorizationError,
    NotFoundError,
    PolicyViolation,
)
from src.shared.infrastructure.db.uow import AbstractUnitOfWork
from src.shared.infrastructure.events.publisher import EventPublisher
from src.settlement.application.commands import (
    DeployEscrowCommand,
    FreezeEscrowCommand,
    FundEscrowCommand,
    RefundEscrowCommand,
    ReleaseEscrowCommand,
    UnfreezeEscrowCommand,
)
from src.settlement.application.queries import (
    GetEscrowByIdQuery,
    GetEscrowQuery,
    GetSettlementsQuery,
)
from src.settlement.domain.escrow import Escrow, EscrowStatus
from src.settlement.domain.ports import (
    IAnchorService,
    IBlockchainGateway,
    IEscrowRepository,
    IMerkleService,
    ISettlementRepository,
)
from src.settlement.domain.settlement import Settlement
from src.settlement.domain.value_objects import (
    AlgoAppAddress,
    AlgoAppId,
    EscrowAmount,
    MicroAlgo,
    TxId,
)
from src.shared.infrastructure.metrics import (
    ESCROW_DEPLOY_DURATION,
    ESCROW_FUND_AMOUNT,
    ESCROW_STATE_TOTAL,
)

log = structlog.get_logger(__name__)


class SettlementService:
    """
    Orchestrates the full escrow lifecycle.

    Dependencies injected via constructor (DIP — context.md §4).
    Never imports concrete implementations — only Protocol interfaces.
    """

    def __init__(
        self,
        escrow_repo: IEscrowRepository,
        settlement_repo: ISettlementRepository,
        blockchain_gateway: IBlockchainGateway,
        merkle_service: IMerkleService,
        anchor_service: IAnchorService,
        event_publisher: EventPublisher,
        uow: AbstractUnitOfWork,
    ) -> None:
        self._escrow_repo = escrow_repo
        self._settlement_repo = settlement_repo
        self._gateway = blockchain_gateway
        self._merkle = merkle_service
        self._anchor = anchor_service
        self._publisher = event_publisher
        self._uow = uow

    # ── Deploy ─────────────────────────────────────────────────────────────────

    async def deploy_escrow(self, cmd: DeployEscrowCommand) -> dict:
        """
        Deploy a new Algorand escrow contract.

        Idempotent: if an escrow already exists for session_id, returns it.
        context.md §9: idempotency prevents double-deploy on retry.
        """
        # 1. Idempotency check
        existing = await self._escrow_repo.get_by_session_id(cmd.session_id)
        if existing is not None:
            log.info(
                "deploy_escrow_idempotent",
                escrow_id=str(existing.id),
                session_id=str(cmd.session_id),
            )
            return {
                "escrow_id": existing.id,
                "algo_app_id": existing.algo_app_id.value if existing.algo_app_id else None,
                "algo_app_address": (
                    existing.algo_app_address.value if existing.algo_app_address else None
                ),
                "status": existing.status.value,
                "tx_id": existing.deploy_tx_id.value if existing.deploy_tx_id else None,
            }

        # 2. Create domain aggregate (DEPLOYED status, no app_id yet)
        escrow = Escrow(
            session_id=cmd.session_id,
            buyer_address=cmd.buyer_algo_address,
            seller_address=cmd.seller_algo_address,
            amount=EscrowAmount(value=MicroAlgo(value=cmd.agreed_price_microalgo)),
        )

        # 3. Persist BEFORE calling blockchain (get escrow_id first)
        async with self._uow:
            await self._escrow_repo.save(escrow)
            await self._uow.commit()

        # 4. Call gateway — dry-run is enforced inside the gateway
        deploy_start = time.monotonic()
        blockchain_result = await self._gateway.deploy_escrow(
            buyer_address=cmd.buyer_algo_address,
            seller_address=cmd.seller_algo_address,
            amount_microalgo=cmd.agreed_price_microalgo,
            session_id=str(cmd.session_id),
        )
        ESCROW_DEPLOY_DURATION.observe(time.monotonic() - deploy_start)

        # 5. Record deployment on domain aggregate
        event = escrow.record_deployment(
            app_id=AlgoAppId(value=blockchain_result["app_id"]),
            app_address=AlgoAppAddress(value=blockchain_result["app_address"]),
            tx_id=TxId(value=blockchain_result["tx_id"]),
        )

        # 6. Persist updated escrow
        async with self._uow:
            await self._escrow_repo.update(escrow)
            await self._uow.commit()

        # 7. Publish domain event
        await self._publisher.publish(event)

        log.info(
            "escrow_deployed",
            escrow_id=str(escrow.id),
            session_id=str(cmd.session_id),
            app_id=blockchain_result["app_id"],
            tx_id=blockchain_result["tx_id"],
        )

        # Prometheus: escrow state transition
        ESCROW_STATE_TOTAL.labels(state="DEPLOYED").inc()

        return {
            "escrow_id": escrow.id,
            "algo_app_id": blockchain_result["app_id"],
            "algo_app_address": blockchain_result["app_address"],
            "status": escrow.status.value,
            "tx_id": blockchain_result["tx_id"],
        }

    # ── Fund ───────────────────────────────────────────────────────────────────

    async def fund_escrow(self, cmd: FundEscrowCommand) -> dict:
        """
        Fund an escrow from the buyer's wallet.

        SECURITY: cmd.funder_algo_sk is NEVER logged — only escrow_id and tx_id.
        """
        escrow = await self._escrow_repo.get_by_id(cmd.escrow_id)
        if escrow is None:
            raise NotFoundError("Escrow", cmd.escrow_id)

        # Verify caller is the buyer enterprise
        # NOTE: In Phase 2, buyer_enterprise association is implicit via session.
        # Full enterprise lookup added in Phase 4. For now, we trust the caller.

        if escrow.algo_app_id is None or escrow.algo_app_address is None:
            raise PolicyViolation(
                f"Escrow {cmd.escrow_id} has no deployed app — cannot fund."
            )

        # 4. Call gateway (dry-run enforced inside)
        # SECURITY: funder_algo_sk logged NOWHERE — only passed to gateway
        blockchain_result = await self._gateway.fund_escrow(
            app_id=escrow.algo_app_id.value,
            app_address=escrow.algo_app_address.value,
            amount_microalgo=escrow.amount.value.value,
            funder_sk=cmd.funder_algo_sk,
        )

        # 5. Record on domain aggregate
        fund_event = escrow.record_funding(TxId(value=blockchain_result["tx_id"]))

        # 6. Persist
        async with self._uow:
            await self._escrow_repo.update(escrow)
            await self._uow.commit()

        # 7. Publish
        await self._publisher.publish(fund_event)

        log.info(
            "escrow_funded",
            escrow_id=str(escrow.id),
            tx_id=blockchain_result["tx_id"],
            # NOTE: funder_algo_sk is intentionally NOT logged here
        )

        # Prometheus: escrow state transition + fund amount
        ESCROW_STATE_TOTAL.labels(state="FUNDED").inc()
        ESCROW_FUND_AMOUNT.observe(escrow.amount.value.value)

        return {
            "escrow_id": escrow.id,
            "status": escrow.status.value,
            "tx_id": blockchain_result["tx_id"],
        }

    # ── Release ────────────────────────────────────────────────────────────────

    async def release_escrow(self, cmd: ReleaseEscrowCommand) -> dict:
        """
        Release funds to seller. Computes Merkle root and anchors on-chain.
        """
        escrow = await self._escrow_repo.get_by_id(cmd.escrow_id)
        if escrow is None:
            raise NotFoundError("Escrow", cmd.escrow_id)

        if escrow.algo_app_id is None:
            raise PolicyViolation(
                f"Escrow {cmd.escrow_id} has no deployed app — cannot release."
            )

        # 4. Compute Merkle root from audit entries
        # Attempt real audit_log entries from ComplianceService; fallback to stub
        audit_entries = await _get_real_audit_entries(escrow)
        # Shared MerkleService returns str; wrap in domain value object.
        from src.settlement.domain.value_objects import MerkleRoot as _MerkleRoot
        merkle_root = _MerkleRoot(value=self._merkle.compute_root(audit_entries))

        # 5. Release on-chain (dry-run enforced in gateway)
        blockchain_result = await self._gateway.release_escrow(
            app_id=escrow.algo_app_id.value,
            merkle_root=merkle_root.value,
        )

        # 6. Anchor Merkle root in Algorand Note field
        anchor_tx_id = await self._anchor.anchor_root(
            merkle_root=merkle_root,
            session_id=escrow.session_id,
        )

        # 7. Record on domain aggregate
        release_event = escrow.record_release(
            tx_id=TxId(value=blockchain_result["tx_id"]),
            merkle_root=merkle_root,
        )

        # 8. Save Settlement record (milestone_index=0, full amount)
        settlement = Settlement(
            escrow_id=escrow.id,
            milestone_index=0,
            amount=escrow.amount.value,
            tx_id=TxId(value=blockchain_result["tx_id"]),
            settled_at=escrow.settled_at,  # type: ignore[arg-type]
        )

        # 9. Persist all in single UoW
        async with self._uow:
            await self._escrow_repo.update(escrow)
            await self._settlement_repo.save(settlement)
            await self._uow.commit()

        # 10. Publish
        await self._publisher.publish(release_event)

        log.info(
            "escrow_released",
            escrow_id=str(escrow.id),
            tx_id=blockchain_result["tx_id"],
            merkle_root=merkle_root.value,
            anchor_tx_id=anchor_tx_id.value,
        )

        # Prometheus: escrow state transition
        ESCROW_STATE_TOTAL.labels(state="RELEASED").inc()

        return {
            "escrow_id": escrow.id,
            "status": escrow.status.value,
            "tx_id": blockchain_result["tx_id"],
            "merkle_root": merkle_root.value,
            "anchor_tx_id": anchor_tx_id.value,
        }

    # ── Refund ─────────────────────────────────────────────────────────────────

    async def refund_escrow(self, cmd: RefundEscrowCommand) -> dict:
        """Refund buyer. Admin-only."""
        escrow = await self._escrow_repo.get_by_id(cmd.escrow_id)
        if escrow is None:
            raise NotFoundError("Escrow", cmd.escrow_id)

        if escrow.algo_app_id is None:
            raise PolicyViolation(
                f"Escrow {cmd.escrow_id} has no deployed app — cannot refund."
            )

        blockchain_result = await self._gateway.refund_escrow(
            app_id=escrow.algo_app_id.value,
            reason=cmd.reason,
        )

        refund_event = escrow.record_refund(TxId(value=blockchain_result["tx_id"]))
        # Patch reason into event
        from src.settlement.domain.escrow import EscrowRefunded
        refund_event_with_reason = EscrowRefunded(
            aggregate_id=refund_event.aggregate_id,
            event_type=refund_event.event_type,
            escrow_id=refund_event.escrow_id,
            session_id=refund_event.session_id,
            amount_microalgo=refund_event.amount_microalgo,
            refund_tx_id=refund_event.refund_tx_id,
            reason=cmd.reason,
        )

        async with self._uow:
            await self._escrow_repo.update(escrow)
            await self._uow.commit()

        await self._publisher.publish(refund_event_with_reason)

        log.info(
            "escrow_refunded",
            escrow_id=str(escrow.id),
            tx_id=blockchain_result["tx_id"],
            reason=cmd.reason,
        )

        # Prometheus: escrow state transition
        ESCROW_STATE_TOTAL.labels(state="REFUNDED").inc()

        return {
            "escrow_id": escrow.id,
            "status": escrow.status.value,
            "tx_id": blockchain_result["tx_id"],
            "reason": cmd.reason,
        }

    # ── Freeze ─────────────────────────────────────────────────────────────────

    async def freeze_escrow(self, cmd: FreezeEscrowCommand) -> dict:
        """Freeze escrow. Buyer, seller, or admin."""
        escrow = await self._escrow_repo.get_by_id(cmd.escrow_id)
        if escrow is None:
            raise NotFoundError("Escrow", cmd.escrow_id)

        if escrow.algo_app_id is None:
            raise PolicyViolation(
                f"Escrow {cmd.escrow_id} has no deployed app — cannot freeze."
            )

        await self._gateway.freeze_escrow(app_id=escrow.algo_app_id.value)

        from src.settlement.domain.escrow import EscrowFrozen
        freeze_event = escrow.freeze()
        # Patch frozen_by from command
        freeze_event_with_role = EscrowFrozen(
            aggregate_id=freeze_event.aggregate_id,
            event_type=freeze_event.event_type,
            escrow_id=freeze_event.escrow_id,
            session_id=freeze_event.session_id,
            frozen_by=cmd.frozen_by_role,
        )

        async with self._uow:
            await self._escrow_repo.update(escrow)
            await self._uow.commit()

        await self._publisher.publish(freeze_event_with_role)

        log.info("escrow_frozen", escrow_id=str(escrow.id), frozen_by=cmd.frozen_by_role)

        # Prometheus: escrow state transition
        ESCROW_STATE_TOTAL.labels(state="FROZEN").inc()

        return {"escrow_id": escrow.id, "status": escrow.status.value}

    # ── Unfreeze ───────────────────────────────────────────────────────────────

    async def unfreeze_escrow(self, cmd: UnfreezeEscrowCommand) -> dict:
        """Unfreeze escrow. Platform admin only."""
        escrow = await self._escrow_repo.get_by_id(cmd.escrow_id)
        if escrow is None:
            raise NotFoundError("Escrow", cmd.escrow_id)

        if escrow.algo_app_id is None:
            raise PolicyViolation(
                f"Escrow {cmd.escrow_id} has no deployed app — cannot unfreeze."
            )

        await self._gateway.unfreeze_escrow(app_id=escrow.algo_app_id.value)

        unfreeze_event = escrow.unfreeze()

        async with self._uow:
            await self._escrow_repo.update(escrow)
            await self._uow.commit()

        await self._publisher.publish(unfreeze_event)
        log.info("escrow_unfrozen", escrow_id=str(escrow.id))

        return {"escrow_id": escrow.id, "status": escrow.status.value}

    # ── Queries ────────────────────────────────────────────────────────────────

    async def list_escrows(
        self,
        enterprise_id: uuid.UUID,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Escrow]:
        """List escrow contracts filtered by enterprise and optional status."""
        return await self._escrow_repo.list_by_enterprise(
            enterprise_id=enterprise_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_escrow(self, query: GetEscrowQuery) -> Escrow:
        """Load escrow by session_id. Raises NotFoundError if missing."""
        escrow = await self._escrow_repo.get_by_session_id(query.session_id)
        if escrow is None:
            raise NotFoundError("Escrow", query.session_id)
        return escrow

    async def get_escrow_by_id(self, query: GetEscrowByIdQuery) -> Escrow:
        """Load escrow by escrow_id. Raises NotFoundError if missing."""
        escrow = await self._escrow_repo.get_by_id(query.escrow_id)
        if escrow is None:
            raise NotFoundError("Escrow", query.escrow_id)
        return escrow

    async def get_settlements(self, query: GetSettlementsQuery) -> list[Settlement]:
        """List all settlement records for an escrow."""
        escrow = await self._escrow_repo.get_by_id(query.escrow_id)
        if escrow is None:
            raise NotFoundError("Escrow", query.escrow_id)
        return await self._settlement_repo.list_by_escrow(query.escrow_id)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _build_stub_audit_entries(escrow: Escrow) -> list[str]:
    """
    Build audit trail entries for Merkle root computation.

    Fallback stub: derives entries from known escrow state when no
    hash-chained audit entries exist (backward compat for pre-Phase-3 escrows).
    """
    entries = [
        f"DEPLOYED:escrow={escrow.id}:session={escrow.session_id}:"
        f"amount={escrow.amount.value.value}",
    ]
    if escrow.deploy_tx_id:
        entries.append(f"DEPLOY_TX:{escrow.deploy_tx_id.value}")
    if escrow.fund_tx_id:
        entries.append(
            f"FUNDED:escrow={escrow.id}:tx={escrow.fund_tx_id.value}:"
            f"amount={escrow.amount.value.value}"
        )
    return entries


async def _get_real_audit_entries(escrow: Escrow) -> list[str]:
    """
    Retrieve real hash-chained audit entries from the compliance context.

    Queries PostgresAuditLogRepository for all entries linked to this escrow.
    Falls back to _build_stub_audit_entries if no entries exist or on DB error.
    """
    import structlog
    _log = structlog.get_logger(__name__)
    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.compliance.infrastructure.repositories import PostgresAuditLogRepository

        async with get_session_factory()() as db_session:
            audit_repo = PostgresAuditLogRepository(db_session)
            entries = await audit_repo.list_all_entries(escrow.id)

            if entries:
                # Use real hash-chained payloads for Merkle computation
                return [
                    f"{e.event_type}:{e.payload_json}:hash={e.entry_hash.value}"
                    for e in entries
                ]

        # No entries found — fall back to stub
        _log.info(
            "audit_entries_fallback_to_stub",
            escrow_id=str(escrow.id),
            reason="no_audit_entries_found",
        )
    except Exception as exc:
        _log.warning(
            "audit_entries_fallback_to_stub",
            escrow_id=str(escrow.id),
            reason=str(exc),
        )

    return _build_stub_audit_entries(escrow)
