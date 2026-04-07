# context.md §4 DIP: dependencies wired here via FastAPI Depends().
# context.md §3: FastAPI imports ONLY in api/ layer.

from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.infrastructure.db.session import get_db_session
from src.shared.infrastructure.db.uow import SqlAlchemyUnitOfWork
from src.shared.infrastructure.events.publisher import get_publisher
from src.shared.infrastructure.merkle_service import MerkleService as _SharedMerkleService
from src.settlement.domain.ports import (
    IAnchorService,
    IBlockchainGateway,
    IEscrowRepository,
    IMerkleService,
    ISettlementRepository,
)
from src.settlement.infrastructure.algorand_gateway import AlgorandGateway
from src.settlement.infrastructure.anchor_service import AnchorService, _load_creator_sk
from src.settlement.infrastructure.repositories import (
    PostgresEscrowRepository,
    PostgresSettlementRepository,
)

# ── Repository factories ──────────────────────────────────────────────────────


def get_escrow_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IEscrowRepository:
    return PostgresEscrowRepository(session)


def get_settlement_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ISettlementRepository:
    return PostgresSettlementRepository(session)


# ── Service factories ─────────────────────────────────────────────────────────


def get_merkle_service() -> IMerkleService:
    return _SharedMerkleService()  # type: ignore[return-value]


def get_blockchain_gateway() -> IBlockchainGateway:
    """
    Singleton-style: AlgorandGateway is expensive to init (loads keys, connects algod).
    In production, mount via app.state or use lru_cache. For Phase 2, construct each
    request (acceptable cost for low-volume blockchain operations).
    """
    return AlgorandGateway()


def get_anchor_service() -> IAnchorService:
    """Build AnchorService with algod client and creator SK from env."""
    from algokit_utils import AlgorandClient  # type: ignore[import-untyped]

    algorand = AlgorandClient.from_environment()
    algod = algorand.client.algod  # type: ignore[attr-defined]
    creator_sk = _load_creator_sk()
    return AnchorService(algod_client=algod, creator_sk=creator_sk)


# ── SettlementService factory ─────────────────────────────────────────────────


def get_settlement_service(
    session: AsyncSession = Depends(get_db_session),
    escrow_repo: IEscrowRepository = Depends(get_escrow_repository),
    settlement_repo: ISettlementRepository = Depends(get_settlement_repository),
    merkle_service: IMerkleService = Depends(get_merkle_service),
) -> "SettlementServiceDep":
    """Wire SettlementService with all concrete adapters."""
    from src.settlement.application.services import SettlementService

    return SettlementService(
        escrow_repo=escrow_repo,
        settlement_repo=settlement_repo,
        blockchain_gateway=get_blockchain_gateway(),
        merkle_service=merkle_service,
        anchor_service=get_anchor_service(),
        event_publisher=get_publisher(),
        uow=SqlAlchemyUnitOfWork(session),
    )


# Type alias for mypy
from src.settlement.application.services import SettlementService as SettlementServiceDep  # noqa: E402
