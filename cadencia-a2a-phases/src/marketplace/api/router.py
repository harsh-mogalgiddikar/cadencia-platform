# context.md §10: marketplace API routes under /v1/marketplace/.
# Phase 3: all endpoints aligned with frontend TypeScript contracts.

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.api.dependencies import get_current_user
from src.identity.domain.user import User
from src.marketplace.api.schemas import (
    CapabilityProfileResponse,
    CapabilityProfileUpdateRequest,
    CapabilityProfileUpdateResponse,
    ConfirmRFQRequest,
    ConfirmRFQResponse,
    EmbeddingRecomputeResponse,
    MatchResponse,
    RFQResponse,
    RFQSubmitResponse,
    UploadRFQRequest,
)
from src.marketplace.application.commands import (
    ConfirmRFQCommand,
    UpdateCapabilityProfileCommand,
    UploadRFQCommand,
)
from src.marketplace.application.services import MarketplaceService
from src.marketplace.infrastructure.pgvector_matchmaker import StubMatchmakingEngine
from src.marketplace.infrastructure.repositories import (
    PostgresCapabilityProfileRepository,
    PostgresMatchRepository,
    PostgresRFQRepository,
)
from src.marketplace.infrastructure.rfq_parser import get_document_parser
from src.shared.api.responses import ApiResponse, success_response
from src.shared.infrastructure.db.session import get_db_session
from src.shared.infrastructure.events.publisher import get_publisher
from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/v1/marketplace", tags=["marketplace"])


async def _get_marketplace_service(
    session=Depends(get_db_session),
) -> MarketplaceService:
    """Build MarketplaceService with DI-injected infrastructure."""
    rfq_repo = PostgresRFQRepository(session)
    match_repo = PostgresMatchRepository(session)
    profile_repo = PostgresCapabilityProfileRepository(session)
    parser = get_document_parser()
    matchmaker = StubMatchmakingEngine()  # Use PgvectorMatchmaker when DB has pgvector
    publisher = get_publisher()
    return MarketplaceService(
        rfq_repo=rfq_repo,
        match_repo=match_repo,
        profile_repo=profile_repo,
        document_parser=parser,
        matchmaking_engine=matchmaker,
        event_publisher=publisher,
    )


def _rfq_to_response(rfq) -> RFQResponse:
    """Convert RFQ domain entity to frontend-compatible RFQResponse."""
    return RFQResponse(
        id=rfq.id,
        raw_text=rfq.raw_document or "",
        status=rfq.status.value,
        parsed_fields=rfq.parsed_fields,
        created_at=rfq.created_at,
    )


# ── POST /v1/marketplace/rfq ────────────────────────────────────────────────


@router.post(
    "/rfq",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[RFQSubmitResponse],
    summary="Submit an RFQ (async NLP parsing)",
)
async def upload_rfq(
    body: UploadRFQRequest,
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
):
    rfq = await svc.upload_rfq(
        UploadRFQCommand(
            raw_text=body.raw_text,
            buyer_enterprise_id=current_user.enterprise_id,
            document_type=body.document_type,
        )
    )
    return success_response(
        RFQSubmitResponse(
            rfq_id=str(rfq.id),
            status="DRAFT",
            message="RFQ submitted for processing.",
        )
    )


# ── GET /v1/marketplace/rfqs ────────────────────────────────────────────────


@router.get(
    "/rfqs",
    response_model=ApiResponse[list[RFQResponse]],
    summary="List RFQs for the current enterprise",
)
async def list_rfqs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
):
    statuses = None
    if status_filter:
        statuses = [s.strip().upper() for s in status_filter.split(",")]

    rfqs = await svc.list_rfqs(
        buyer_enterprise_id=current_user.enterprise_id,
        limit=limit,
        offset=offset,
        statuses=statuses,
    )
    return success_response([_rfq_to_response(rfq) for rfq in rfqs])


# ── GET /v1/marketplace/rfq/{rfq_id} ────────────────────────────────────────


@router.get(
    "/rfq/{rfq_id}",
    response_model=ApiResponse[RFQResponse],
    summary="Get RFQ details + parsed fields",
)
async def get_rfq(
    rfq_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
):
    rfq = await svc.get_rfq(rfq_id)

    # Ownership check
    if str(rfq.buyer_enterprise_id) != str(current_user.enterprise_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return success_response(_rfq_to_response(rfq))


# ── GET /v1/marketplace/rfq/{rfq_id}/matches ────────────────────────────────


@router.get(
    "/rfq/{rfq_id}/matches",
    response_model=ApiResponse[list[MatchResponse]],
    summary="Get ranked matches for RFQ",
)
async def get_rfq_matches(
    rfq_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
    session=Depends(get_db_session),
):
    rfq = await svc.get_rfq(rfq_id)

    # Ownership check
    if str(rfq.buyer_enterprise_id) != str(current_user.enterprise_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Status check — matches only available after matching completes
    if rfq.status.value not in ("MATCHED", "CONFIRMED"):
        raise HTTPException(
            status_code=400,
            detail=f"RFQ is in status '{rfq.status.value}'. "
                   "Matches are only available when status is 'MATCHED' or 'CONFIRMED'.",
        )

    # Use the detailed query that joins Enterprise + CapabilityProfile
    match_repo = PostgresMatchRepository(session)
    match_details = await match_repo.get_matches_with_details(rfq_id)

    return success_response(
        [MatchResponse(**md) for md in match_details]
    )


# ── POST /v1/marketplace/rfq/{rfq_id}/confirm ───────────────────────────────


@router.post(
    "/rfq/{rfq_id}/confirm",
    response_model=ApiResponse[ConfirmRFQResponse],
    summary="Confirm RFQ match → start negotiation",
)
async def confirm_rfq(
    rfq_id: uuid.UUID,
    body: ConfirmRFQRequest,
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
):
    # Pre-validate RFQ status — return 400 (not 409 ConflictError)
    rfq = await svc.get_rfq(rfq_id)
    if str(rfq.buyer_enterprise_id) != str(current_user.enterprise_id):
        raise HTTPException(status_code=403, detail="Access denied")
    if rfq.status.value != "MATCHED":
        raise HTTPException(
            status_code=400,
            detail=f"RFQ cannot be confirmed — current status is '{rfq.status.value}'. Must be 'MATCHED'.",
        )

    try:
        result = await svc.confirm_rfq(
            ConfirmRFQCommand(
                rfq_id=rfq_id,
                seller_enterprise_id=uuid.UUID(body.seller_enterprise_id),
                buyer_enterprise_id=current_user.enterprise_id,
            )
        )
    except Exception as exc:
        # NotFoundError for match → 404 with spec-required message
        if "Match not found" in str(exc):
            raise HTTPException(
                status_code=404,
                detail="No match found for this seller and RFQ combination",
            )
        raise

    return success_response(
        ConfirmRFQResponse(
            message=result["message"],
            session_id=result["session_id"],
        )
    )


# ── GET /v1/marketplace/capability-profile ───────────────────────────────────


@router.get(
    "/capability-profile",
    response_model=ApiResponse[CapabilityProfileResponse],
    summary="Get seller capability profile",
)
async def get_capability_profile(
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
    session=Depends(get_db_session),
):
    profile_repo = PostgresCapabilityProfileRepository(session)
    profile = await profile_repo.get_by_enterprise(current_user.enterprise_id)

    if not profile:
        # Return defaults — new sellers have no profile yet (NOT a 404)
        return success_response(CapabilityProfileResponse())

    # Derive embedding_status
    embedding_status = "outdated"
    if profile.embedding is not None:
        embedding_status = "active"

    return success_response(
        CapabilityProfileResponse(
            industry=profile.industry_vertical or "",
            geographies=profile.geography_scope or [],
            products=profile.product_categories or [],
            min_order_value=float(profile.trade_volume_min) if profile.trade_volume_min else 0.0,
            max_order_value=float(profile.trade_volume_max) if profile.trade_volume_max else 0.0,
            description=profile.profile_text or "",
            embedding_status=embedding_status,
            last_embedded=None,  # TODO: track last_embedded_at in profile model
        )
    )


# ── PUT /v1/marketplace/capability-profile ───────────────────────────────────


@router.put(
    "/capability-profile",
    response_model=ApiResponse[CapabilityProfileUpdateResponse],
    summary="Update seller capability profile",
)
async def update_capability_profile(
    body: CapabilityProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
    session: AsyncSession = Depends(get_db_session),
):
    # Authorization: only sellers can update capability profile
    from src.identity.infrastructure.repositories import PostgresEnterpriseRepository
    enterprise_repo = PostgresEnterpriseRepository(session)
    enterprise = await enterprise_repo.get_by_id(current_user.enterprise_id)
    if enterprise and str(enterprise.trade_role.value) not in ("SELLER", "BOTH"):
        raise HTTPException(
            status_code=403,
            detail="Only enterprises with trade role SELLER or BOTH can maintain a capability profile",
        )

    await svc.update_capability_profile(
        UpdateCapabilityProfileCommand(
            enterprise_id=current_user.enterprise_id,
            industry_vertical=body.industry,
            product_categories=body.products,
            geography_scope=body.geographies,
            trade_volume_min=body.min_order_value if body.min_order_value else None,
            trade_volume_max=body.max_order_value if body.max_order_value else None,
            profile_text=body.description,
        )
    )
    return success_response(
        CapabilityProfileUpdateResponse(
            message="Seller profile updated successfully",
            embedding_status="queued",
        )
    )


# ── POST /v1/marketplace/capability-profile/embeddings ──────────────────────


@router.post(
    "/capability-profile/embeddings",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[EmbeddingRecomputeResponse],
    summary="Trigger background embedding recompute",
)
async def recompute_embeddings(
    current_user: User = Depends(get_current_user),
    svc: MarketplaceService = Depends(_get_marketplace_service),
    session=Depends(get_db_session),
):
    # Verify profile exists
    profile_repo = PostgresCapabilityProfileRepository(session)
    profile = await profile_repo.get_by_enterprise(current_user.enterprise_id)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No capability profile found. Please create a profile before triggering embedding.",
        )

    await svc._recompute_embedding(current_user.enterprise_id)
    return success_response(
        EmbeddingRecomputeResponse(
            message="Embeddings recomputation queued. Profile will be active for matching in ~30 seconds."
        )
    )
