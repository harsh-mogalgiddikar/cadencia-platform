# context.md §10: All endpoints versioned under /v1/.
# context.md §10: All responses use ApiResponse[T] envelope.
# context.md §14: Auth via Phase One get_current_user + require_role.

from __future__ import annotations

import uuid

import algosdk.mnemonic as algo_mnemonic  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Query, status

from src.shared.api.responses import ApiResponse, success_response
from src.shared.infrastructure.logging import get_logger
from src.identity.api.dependencies import (
    get_current_user,
    rate_limit,
    require_role,
)
from src.identity.domain.user import User
from src.settlement.api.dependencies import get_settlement_service, SettlementServiceDep
from src.settlement.api.schemas import (
    DeployEscrowRequest,
    DeployEscrowResponse,
    EscrowResponse,
    FreezeEscrowRequest,
    FundEscrowRequest,
    RefundEscrowRequest,
    ReleaseEscrowRequest,
    SettlementResponse,
)
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

log = get_logger(__name__)

router = APIRouter(prefix="/v1/escrow", tags=["escrow"])


# ── GET /v1/escrow — list escrows ─────────────────────────────────────────────


@router.get(
    "",
    response_model=ApiResponse[list[EscrowResponse]],
    summary="List escrow contracts for current user's enterprise",
    dependencies=[Depends(rate_limit)],
)
async def list_escrows(
    escrow_status: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[list[EscrowResponse]]:
    escrows = await svc.list_escrows(
        enterprise_id=current_user.enterprise_id,
        status=escrow_status,
        limit=limit,
        offset=offset,
    )
    return success_response([EscrowResponse.from_domain(e) for e in escrows])


# ── GET /v1/escrow/{session_id} ───────────────────────────────────────────────


@router.get(
    "/{session_id}",
    response_model=ApiResponse[EscrowResponse],
    summary="Get escrow state by negotiation session ID",
    dependencies=[Depends(rate_limit)],
)
async def get_escrow(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[EscrowResponse]:
    escrow = await svc.get_escrow(
        GetEscrowQuery(
            session_id=session_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )
    return success_response(EscrowResponse.from_domain(escrow))


# ── POST /v1/escrow/{session_id}/deploy ───────────────────────────────────────


@router.post(
    "/{session_id}/deploy",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[DeployEscrowResponse],
    summary="Deploy Algorand escrow contract (ADMIN only — Phase 2 testing convenience)",
    dependencies=[Depends(require_role("ADMIN")), Depends(rate_limit)],
)
async def deploy_escrow(
    session_id: uuid.UUID,
    request_body: DeployEscrowRequest,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[DeployEscrowResponse]:
    """
    Phase Two convenience endpoint: deploy escrow directly via API.
    In Phase Four+, this is triggered automatically by the SessionAgreed domain event.
    """
    result = await svc.deploy_escrow(
        DeployEscrowCommand(
            session_id=session_id,
            buyer_enterprise_id=request_body.buyer_enterprise_id,
            seller_enterprise_id=request_body.seller_enterprise_id,
            buyer_algo_address=request_body.buyer_algo_address,
            seller_algo_address=request_body.seller_algo_address,
            agreed_price_microalgo=request_body.agreed_price_microalgo,
        )
    )
    return success_response(
        DeployEscrowResponse(
            escrow_id=result["escrow_id"],
            algo_app_id=result["algo_app_id"],
            algo_app_address=result["algo_app_address"],
            status=result["status"],
            tx_id=result["tx_id"],
        )
    )


# ── POST /v1/escrow/{escrow_id}/fund ─────────────────────────────────────────


@router.post(
    "/{escrow_id}/fund",
    response_model=ApiResponse[EscrowResponse],
    summary="Fund escrow from buyer wallet (ADMIN only in Phase 2)",
    dependencies=[Depends(require_role("ADMIN")), Depends(rate_limit)],
)
async def fund_escrow(
    escrow_id: uuid.UUID,
    request_body: FundEscrowRequest,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[EscrowResponse]:
    """
    SECURITY: mnemonic → private key conversion happens here in the API layer.
    The raw mnemonic is NEVER passed further into the application/domain.
    """
    # Convert mnemonic → sk here — never log either value
    funder_sk = algo_mnemonic.to_private_key(request_body.funder_algo_mnemonic)

    await svc.fund_escrow(
        FundEscrowCommand(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
            funder_algo_sk=funder_sk,
        )
    )
    # Reload escrow for response
    escrow = await svc.get_escrow_by_id(
        GetEscrowByIdQuery(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )
    return success_response(EscrowResponse.from_domain(escrow))


# ── POST /v1/escrow/{escrow_id}/release ──────────────────────────────────────


@router.post(
    "/{escrow_id}/release",
    response_model=ApiResponse[EscrowResponse],
    summary="Release funds to seller with Merkle root anchoring (ADMIN only)",
    dependencies=[Depends(require_role("ADMIN")), Depends(rate_limit)],
)
async def release_escrow(
    escrow_id: uuid.UUID,
    request_body: ReleaseEscrowRequest,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[EscrowResponse]:
    await svc.release_escrow(
        ReleaseEscrowCommand(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )
    escrow = await svc.get_escrow_by_id(
        GetEscrowByIdQuery(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )
    return success_response(EscrowResponse.from_domain(escrow))


# ── POST /v1/escrow/{escrow_id}/refund ───────────────────────────────────────


@router.post(
    "/{escrow_id}/refund",
    response_model=ApiResponse[EscrowResponse],
    summary="Refund buyer (ADMIN only)",
    dependencies=[Depends(require_role("ADMIN")), Depends(rate_limit)],
)
async def refund_escrow(
    escrow_id: uuid.UUID,
    request_body: RefundEscrowRequest,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[EscrowResponse]:
    await svc.refund_escrow(
        RefundEscrowCommand(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
            reason=request_body.reason,
        )
    )
    escrow = await svc.get_escrow_by_id(
        GetEscrowByIdQuery(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )
    return success_response(EscrowResponse.from_domain(escrow))


# ── POST /v1/escrow/{escrow_id}/freeze ───────────────────────────────────────


@router.post(
    "/{escrow_id}/freeze",
    response_model=ApiResponse[EscrowResponse],
    summary="Freeze escrow to halt state transitions",
    dependencies=[Depends(rate_limit)],
)
async def freeze_escrow(
    escrow_id: uuid.UUID,
    request_body: FreezeEscrowRequest,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[EscrowResponse]:
    await svc.freeze_escrow(
        FreezeEscrowCommand(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
            frozen_by_role=request_body.frozen_by_role,
        )
    )
    escrow = await svc.get_escrow_by_id(
        GetEscrowByIdQuery(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )
    return success_response(EscrowResponse.from_domain(escrow))


# ── GET /v1/escrow/{escrow_id}/settlements ────────────────────────────────────


@router.get(
    "/{escrow_id}/settlements",
    response_model=ApiResponse[list[SettlementResponse]],
    summary="List settlement records for an escrow",
    dependencies=[Depends(rate_limit)],
)
async def get_settlements(
    escrow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[list[SettlementResponse]]:
    settlements = await svc.get_settlements(
        GetSettlementsQuery(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )
    return success_response([SettlementResponse.from_domain(s) for s in settlements])


# ── Pera Wallet Endpoints (RW-02) ────────────────────────────────────────────


from pydantic import BaseModel, Field


class BuildFundTxnResponse(BaseModel):
    """Unsigned atomic transaction group for Pera Wallet signing."""

    unsigned_transactions: list[str] = Field(
        description="Base64-encoded unsigned transactions"
    )
    group_id: str = Field(description="Base64-encoded atomic group ID")
    transaction_count: int
    description: str


class SubmitSignedFundRequest(BaseModel):
    """Pre-signed transaction group from Pera Wallet."""

    signed_transactions: list[str] = Field(
        description="Base64-encoded signed transactions from Pera Wallet"
    )


class SubmitSignedFundResponse(BaseModel):
    """Result of submitting signed transactions to Algorand."""

    tx_id: str = Field(description="Algorand transaction ID")
    confirmed_round: int = Field(description="Block round when confirmed")


@router.get(
    "/{escrow_id}/build-fund-txn",
    response_model=ApiResponse[BuildFundTxnResponse],
    summary="Build unsigned atomic group for Pera Wallet escrow funding",
    dependencies=[Depends(rate_limit)],
)
async def build_fund_transaction(
    escrow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[BuildFundTxnResponse]:
    """
    Build unsigned escrow funding transactions for Pera Wallet signing.

    Returns a base64-encoded atomic group [PaymentTxn, AppCallTxn(fund)]
    that the frontend passes to PeraWallet.signTransactions().

    context.md §12: backend NEVER handles user private keys.
    """
    from fastapi import HTTPException
    from src.settlement.application.queries import GetEscrowByIdQuery

    # Get escrow details
    escrow = await svc.get_escrow_by_id(
        GetEscrowByIdQuery(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )

    if not escrow.algo_app_id:
        raise HTTPException(
            status_code=400,
            detail="Escrow not deployed — no Algorand app ID",
        )

    if escrow.status.value != "DEPLOYED":
        raise HTTPException(
            status_code=409,
            detail=f"Escrow cannot be funded in state: {escrow.status.value}",
        )

    # Build unsigned transactions
    from src.settlement.infrastructure.algorand_gateway import AlgorandGateway
    gateway = AlgorandGateway()

    # Calculate app address from app_id
    from algosdk.logic import get_application_address
    app_address = get_application_address(escrow.algo_app_id)

    result = await gateway.build_fund_transaction(
        app_id=escrow.algo_app_id,
        app_address=app_address,
        amount_microalgo=escrow.amount_microalgo.value,
        funder_address=escrow.buyer_algorand_address,
    )

    return success_response(BuildFundTxnResponse(**result))


@router.post(
    "/{escrow_id}/submit-signed-fund",
    response_model=ApiResponse[SubmitSignedFundResponse],
    summary="Submit Pera Wallet pre-signed transaction group",
    dependencies=[Depends(rate_limit)],
)
async def submit_signed_fund(
    escrow_id: uuid.UUID,
    request_body: SubmitSignedFundRequest,
    current_user: User = Depends(get_current_user),
    svc: SettlementServiceDep = Depends(get_settlement_service),
) -> ApiResponse[SubmitSignedFundResponse]:
    """
    Submit pre-signed transactions from Pera Wallet.

    1. Validates escrow is in DEPLOYED state
    2. Runs mandatory dry-run simulation (SRS-SC-001)
    3. Broadcasts to Algorand network
    4. Updates escrow status to FUNDED

    context.md §7.3: dry-run BEFORE every broadcast.
    context.md §12: backend NEVER sees private keys.
    """
    from fastapi import HTTPException
    from src.settlement.application.queries import GetEscrowByIdQuery

    # Validate escrow state
    escrow = await svc.get_escrow_by_id(
        GetEscrowByIdQuery(
            escrow_id=escrow_id,
            requesting_enterprise_id=current_user.enterprise_id,
        )
    )

    if escrow.status.value != "DEPLOYED":
        raise HTTPException(
            status_code=409,
            detail=f"Escrow cannot be funded in state: {escrow.status.value}",
        )

    # Submit signed transactions
    from src.settlement.infrastructure.algorand_gateway import AlgorandGateway
    gateway = AlgorandGateway()

    result = await gateway.submit_signed_fund(
        signed_txn_bytes_list=request_body.signed_transactions,
    )

    log.info(
        "escrow_funded_via_pera_wallet",
        escrow_id=str(escrow_id),
        tx_id=result["tx_id"],
        confirmed_round=result["confirmed_round"],
    )

    return success_response(SubmitSignedFundResponse(**result))

