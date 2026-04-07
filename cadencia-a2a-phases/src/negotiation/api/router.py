# context.md §4: API prefix /v1/*, API-first modular monolith.
# Phase Four: Six negotiation routes + SSE streaming endpoint.
# Updated for DANP with intelligence debug endpoint.

from __future__ import annotations

import asyncio
import json
import uuid

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from src.identity.api.dependencies import get_current_user, require_role
from src.negotiation.api.dependencies import get_negotiation_service, get_sse_publisher
from src.negotiation.api.schemas import (
    CreateSessionRequest,
    HumanOverrideRequest,
    IntelligenceResponse,
    OfferResponse,
    SessionResponse,
    TerminateRequest,
)
from src.negotiation.application.commands import (
    CreateSessionCommand,
    HumanOverrideCommand,
    TerminateSessionCommand,
)
from src.negotiation.application.services import NegotiationService
from src.shared.api.responses import success_response

router = APIRouter(prefix="/v1/sessions", tags=["negotiation"])


def _session_to_response(session: object) -> SessionResponse:
    """Map domain NegotiationSession to API response."""
    offers = [
        OfferResponse(
            offer_id=o.id,
            session_id=o.session_id,
            round_number=o.round_number.value,
            proposer_role=o.proposer_role.value,
            price=o.price.amount,
            currency=o.price.currency,
            terms=o.terms,
            confidence=o.confidence.value if o.confidence else None,
            is_human_override=o.is_human_override,
            created_at=o.created_at,
        )
        for o in getattr(session, "offers", [])
    ]
    return SessionResponse(
        session_id=session.id,  # type: ignore[union-attr]
        rfq_id=session.rfq_id,  # type: ignore[union-attr]
        match_id=session.match_id,  # type: ignore[union-attr]
        buyer_enterprise_id=session.buyer_enterprise_id,  # type: ignore[union-attr]
        seller_enterprise_id=session.seller_enterprise_id,  # type: ignore[union-attr]
        status=session.status.value,  # type: ignore[union-attr]
        agreed_price=session.agreed_price.amount if session.agreed_price else None,  # type: ignore[union-attr]
        agreed_currency=session.agreed_price.currency if session.agreed_price else None,  # type: ignore[union-attr]
        agreed_terms=session.agreed_terms,  # type: ignore[union-attr]
        round_count=session.round_count.value,  # type: ignore[union-attr]
        offers=offers,
        created_at=session.created_at,  # type: ignore[union-attr]
        completed_at=session.completed_at,  # type: ignore[union-attr]
        expires_at=session.expires_at,  # type: ignore[union-attr]
        schema_failure_count=getattr(session, "schema_failure_count", 0),
        stall_counter=getattr(session, "stall_counter", 0),
    )


@router.get("")
async def list_sessions(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    svc: NegotiationService = Depends(get_negotiation_service),
    user: object = Depends(get_current_user),
) -> dict:
    """GET /v1/sessions — list negotiation sessions for current user's enterprise."""
    enterprise_id = getattr(user, "enterprise_id", None)
    sessions = await svc.session_repo.list_by_enterprise(
        enterprise_id=enterprise_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [_session_to_response(s).model_dump(mode="json") for s in sessions]
    return success_response(data=items)


@router.post("", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    svc: NegotiationService = Depends(get_negotiation_service),
    _user: object = Depends(get_current_user),
) -> dict:
    """POST /v1/sessions — create negotiation session."""
    cmd = CreateSessionCommand(
        match_id=body.match_id,
        rfq_id=body.rfq_id,
        buyer_enterprise_id=body.buyer_enterprise_id,
        seller_enterprise_id=body.seller_enterprise_id,
    )
    session = await svc.create_session(cmd)
    return success_response(data=_session_to_response(session).model_dump(mode="json"))


@router.get("/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    svc: NegotiationService = Depends(get_negotiation_service),
    _user: object = Depends(get_current_user),
) -> dict:
    """GET /v1/sessions/{id} — full session state + offer history."""
    from src.shared.domain.exceptions import NotFoundError
    session = await svc.session_repo.get_by_id(session_id)  # type: ignore[union-attr]
    if not session:
        raise NotFoundError("NegotiationSession", session_id)
    return success_response(data=_session_to_response(session).model_dump(mode="json"))


@router.post("/{session_id}/turn")
async def run_turn(
    session_id: uuid.UUID,
    svc: NegotiationService = Depends(get_negotiation_service),
    _user: object = Depends(get_current_user),
) -> dict:
    """POST /v1/sessions/{id}/turn — trigger one agent turn."""
    offer = await svc.run_agent_turn(session_id)
    resp = OfferResponse(
        offer_id=offer.id,
        session_id=offer.session_id,
        round_number=offer.round_number.value,
        proposer_role=offer.proposer_role.value,
        price=offer.price.amount,
        currency=offer.price.currency,
        terms=offer.terms,
        confidence=offer.confidence.value if offer.confidence else None,
        is_human_override=offer.is_human_override,
        created_at=offer.created_at,
    )
    return success_response(data=resp.model_dump(mode="json"))


@router.post("/{session_id}/run-auto")
async def run_auto_negotiation(
    session_id: uuid.UUID,
    max_rounds: int = Query(default=20, ge=1, le=50, description="Maximum rounds to execute"),
    svc: NegotiationService = Depends(get_negotiation_service),
    _user: object = Depends(get_current_user),
) -> dict:
    """
    POST /v1/sessions/{id}/run-auto — Run autonomous agent-vs-agent negotiation.

    Executes buyer/seller turns in a loop until a terminal state is reached
    (AGREED, WALK_AWAY, TIMEOUT, POLICY_BREACH, FAILED) or max_rounds is exhausted.
    Returns the final session state with full offer history.
    """
    from src.shared.domain.exceptions import ConflictError, NotFoundError

    session = await svc.session_repo.get_by_id(session_id)  # type: ignore[union-attr]
    if not session:
        raise NotFoundError("NegotiationSession", session_id)

    offers_this_run: list[OfferResponse] = []
    terminal = False

    for round_num in range(max_rounds):
        # Check if session is still active before each turn
        session = await svc.session_repo.get_by_id(session_id)  # type: ignore[union-attr]
        if not session or not session.status.is_active:
            terminal = True
            break

        try:
            offer = await svc.run_agent_turn(session_id)
            offers_this_run.append(OfferResponse(
                offer_id=offer.id,
                session_id=offer.session_id,
                round_number=offer.round_number.value,
                proposer_role=offer.proposer_role.value,
                price=offer.price.amount,
                currency=offer.price.currency,
                terms=offer.terms,
                confidence=offer.confidence.value if offer.confidence else None,
                is_human_override=offer.is_human_override,
                created_at=offer.created_at,
            ))
        except ConflictError:
            # Session transitioned to terminal state during this turn
            terminal = True
            break
        except Exception:
            # LLM failure or other error — session paused, stop loop
            break

        # Reload session to check terminal status after the turn
        session = await svc.session_repo.get_by_id(session_id)  # type: ignore[union-attr]
        if session and not session.status.is_active:
            terminal = True
            break

    # Reload final session state
    session = await svc.session_repo.get_by_id(session_id)  # type: ignore[union-attr]
    if not session:
        raise NotFoundError("NegotiationSession", session_id)

    return success_response(data={
        "session": _session_to_response(session).model_dump(mode="json"),
        "rounds_executed": len(offers_this_run),
        "terminal": terminal,
        "final_status": session.status.value,
        "offers_this_run": [o.model_dump(mode="json") for o in offers_this_run],
    })


@router.post("/{session_id}/override")
async def human_override(
    session_id: uuid.UUID,
    body: HumanOverrideRequest,
    svc: NegotiationService = Depends(get_negotiation_service),
    user: object = Depends(get_current_user),
) -> dict:
    """POST /v1/sessions/{id}/override — human injects offer mid-session."""
    cmd = HumanOverrideCommand(
        session_id=session_id,
        price=body.price,
        currency=body.currency,
        terms=body.terms,
        user_id=getattr(user, "id", uuid.uuid4()),
        enterprise_id=getattr(user, "enterprise_id", uuid.uuid4()),
    )
    offer = await svc.apply_human_override(cmd)
    resp = OfferResponse(
        offer_id=offer.id,
        session_id=offer.session_id,
        round_number=offer.round_number.value,
        proposer_role=offer.proposer_role.value,
        price=offer.price.amount,
        currency=offer.price.currency,
        terms=offer.terms,
        confidence=None,
        is_human_override=True,
        created_at=offer.created_at,
    )
    return success_response(data=resp.model_dump(mode="json"))


@router.post("/{session_id}/terminate")
async def terminate_session(
    session_id: uuid.UUID,
    body: TerminateRequest = TerminateRequest(),
    svc: NegotiationService = Depends(get_negotiation_service),
    _user: object = Depends(require_role("ADMIN")),
) -> dict:
    """POST /v1/sessions/{id}/terminate — admin terminates session."""
    cmd = TerminateSessionCommand(session_id=session_id, reason=body.reason)
    await svc.terminate_session(cmd)
    return success_response(data={"terminated": True, "session_id": str(session_id)})


@router.get("/{session_id}/intelligence")
async def get_intelligence(
    session_id: uuid.UUID,
    svc: NegotiationService = Depends(get_negotiation_service),
    _user: object = Depends(get_current_user),
) -> dict:
    """
    GET /v1/sessions/{id}/intelligence — Debug: Bayesian beliefs.

    Returns opponent type classifications, flexibility scores,
    strategy modifiers, and convergence analysis.
    """
    data = await svc.get_session_intelligence(session_id)
    return success_response(data=data)


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: uuid.UUID,
    request: Request,
    last_event_id: str | None = Query(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """
    GET /v1/sessions/{id}/stream — SSE live agent turns.

    Supports Last-Event-ID header for reconnect replay.
    """
    sse_pub = await get_sse_publisher()

    async def event_generator():
        # Replay missed events on reconnect
        last_id = last_event_id or request.headers.get("Last-Event-ID")
        events = await sse_pub.get_events_since(session_id, last_id)
        for ev in events:
            event_id = ev.get("event_id", "")
            yield f"id: {event_id}\nevent: {ev.get('event', 'message')}\ndata: {json.dumps(ev)}\n\n"

        # Poll for new events
        current_last_id = events[-1]["event_id"] if events else last_id
        while True:
            if await request.is_disconnected():
                break
            new_events = await sse_pub.get_events_since(session_id, current_last_id)
            for ev in new_events:
                event_id = ev.get("event_id", "")
                yield f"id: {event_id}\nevent: {ev.get('event', 'message')}\ndata: {json.dumps(ev)}\n\n"
                current_last_id = event_id
                if ev.get("terminal"):
                    return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
