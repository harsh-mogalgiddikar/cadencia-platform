# NegotiationService — orchestrates all negotiation use cases.
# context.md §1.4 DIP: receives all dependencies via constructor.
# Updated for DANP FSM with full 9-state support.

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog

from src.negotiation.application.commands import (
    CreateSessionCommand,
    HumanOverrideCommand,
    TerminateSessionCommand,
)
from src.negotiation.domain.agent_profile import AgentProfile
from src.negotiation.domain.events import (
    AgentProfileUpdated,
    HumanOverrideApplied,
    SessionCreated,
)
from src.negotiation.domain.offer import Offer, ProposerRole
from src.negotiation.domain.session import NegotiationSession, SessionStatus
from src.negotiation.domain.value_objects import OfferValue, RiskProfile, StrategyWeights
from src.negotiation.infrastructure.llm_agent_driver import LLMExhaustedException
from src.shared.domain.exceptions import ConflictError, NotFoundError
from src.shared.infrastructure.metrics import (
    ACTIVE_SESSIONS,
    NEGOTIATION_ROUNDS_TOTAL,
    NEGOTIATION_SESSION_DURATION,
)

log = structlog.get_logger(__name__)

SESSION_TTL_HOURS = 24
MAX_ROUNDS = 20


class NegotiationService:
    """Orchestrates negotiation lifecycle. All ports injected via constructor (DIP)."""

    def __init__(
        self,
        session_repo: object,
        offer_repo: object,
        profile_repo: object,
        playbook_repo: object,
        neutral_engine: object,
        sse_publisher: object,
        event_publisher: object,
        uow: object,
        session_ttl_hours: int = SESSION_TTL_HOURS,
        max_rounds: int = MAX_ROUNDS,
    ) -> None:
        self.session_repo = session_repo
        self.offer_repo = offer_repo
        self.profile_repo = profile_repo
        self.playbook_repo = playbook_repo
        self.neutral_engine = neutral_engine
        self.sse_publisher = sse_publisher
        self.event_publisher = event_publisher
        self.uow = uow
        self.session_ttl_hours = session_ttl_hours
        self.max_rounds = max_rounds

    async def create_session(self, cmd: CreateSessionCommand) -> NegotiationSession:
        """Create a new negotiation session from a marketplace match."""
        # Idempotency check
        existing = await self.session_repo.get_by_match_id(cmd.match_id)  # type: ignore[union-attr]
        if existing:
            raise ConflictError(f"Session already exists for match_id {cmd.match_id}")

        # Load or create default agent profiles
        buyer_profile = await self.profile_repo.get_by_enterprise(cmd.buyer_enterprise_id)  # type: ignore[union-attr]
        if not buyer_profile:
            buyer_profile = AgentProfile(enterprise_id=cmd.buyer_enterprise_id)
            await self.profile_repo.save(buyer_profile)  # type: ignore[union-attr]

        seller_profile = await self.profile_repo.get_by_enterprise(cmd.seller_enterprise_id)  # type: ignore[union-attr]
        if not seller_profile:
            seller_profile = AgentProfile(enterprise_id=cmd.seller_enterprise_id)
            await self.profile_repo.save(seller_profile)  # type: ignore[union-attr]

        # Create session in INIT state (DANP)
        session = NegotiationSession(
            rfq_id=cmd.rfq_id,
            match_id=cmd.match_id,
            buyer_enterprise_id=cmd.buyer_enterprise_id,
            seller_enterprise_id=cmd.seller_enterprise_id,
            status=SessionStatus.INIT,
            expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=self.session_ttl_hours),
        )

        # Activate: INIT → BUYER_ANCHOR
        created_event = session.activate()

        await self.session_repo.save(session)  # type: ignore[union-attr]
        await self.uow.commit()  # type: ignore[union-attr]

        # Publish SessionCreated
        await self.event_publisher.publish(created_event)  # type: ignore[union-attr]

        # Prometheus: track active session count
        ACTIVE_SESSIONS.inc()

        log.info("session_created", session_id=str(session.id), match_id=str(cmd.match_id),
                 status=session.status.value)
        return session

    async def run_agent_turn(self, session_id: uuid.UUID) -> Offer:
        """Execute one turn of the negotiation (4-layer pipeline via NeutralEngine)."""
        session = await self.session_repo.get_by_id(session_id)  # type: ignore[union-attr]
        if not session:
            raise NotFoundError("NegotiationSession", session_id)

        # Check if session accepts turns
        if not session.status.is_active:
            raise ConflictError(f"Session {session_id} is {session.status.value}, cannot run turn")

        # Check timeout
        if session.is_expired():
            await self._handle_timeout(session)
            raise ConflictError(f"Session {session_id} has expired (TIMEOUT)")

        buyer_profile = await self.profile_repo.get_by_enterprise(  # type: ignore[union-attr]
            session.buyer_enterprise_id
        ) or AgentProfile(enterprise_id=session.buyer_enterprise_id)
        seller_profile = await self.profile_repo.get_by_enterprise(  # type: ignore[union-attr]
            session.seller_enterprise_id
        ) or AgentProfile(enterprise_id=session.seller_enterprise_id)

        buyer_playbook = await self.playbook_repo.get_by_vertical("general")  # type: ignore[union-attr]
        seller_playbook = buyer_playbook

        try:
            offer, is_terminal = await self.neutral_engine.process_turn(  # type: ignore[union-attr]
                session=session,
                buyer_profile=buyer_profile,
                seller_profile=seller_profile,
                buyer_playbook=buyer_playbook,
                seller_playbook=seller_playbook,
            )
        except LLMExhaustedException:
            # Emit SSE pause, do NOT terminate session
            if self.sse_publisher:
                await self.sse_publisher.publish_turn(  # type: ignore[union-attr]
                    session_id,
                    {"event": "paused", "reason": "llm_unavailable", "session_id": str(session_id)},
                )
            log.warning("llm_exhausted_session_paused", session_id=str(session_id))
            raise

        # Add offer to session and persist
        offer_event = session.add_offer(offer)
        await self.offer_repo.save(offer)  # type: ignore[union-attr]
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.event_publisher.publish(offer_event)  # type: ignore[union-attr]

        if is_terminal:
            reasoning = offer.agent_reasoning or ""
            if "REJECTED" in reasoning or "WALK_AWAY" in reasoning:
                await self._handle_walk_away(session, f"Agent rejected at round {session.round_count.value}")
            elif "POLICY_BREACH" in reasoning:
                await self._handle_policy_breach(session)
            elif "TIMEOUT" in reasoning:
                await self._handle_timeout(session)
            elif session.stall_counter >= 3:
                await self._handle_stall(session)
            else:
                await self._handle_agreement(session, offer, buyer_profile, seller_profile)

        await self.uow.commit()  # type: ignore[union-attr]
        return offer

    async def _handle_agreement(
        self,
        session: NegotiationSession,
        offer: Offer,
        buyer_profile: AgentProfile,
        seller_profile: AgentProfile,
    ) -> None:
        """ROUND_LOOP → AGREED: convergence detected."""
        agreed_price = OfferValue(amount=offer.price.amount, currency="INR")
        event = session.mark_agreed(agreed_price, {})
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.event_publisher.publish(event)  # type: ignore[union-attr]

        # Prometheus: session completed — decrement active, observe duration, record round outcome
        ACTIVE_SESSIONS.dec()
        if session.created_at:
            duration = (time.time() - session.created_at.timestamp())
            NEGOTIATION_SESSION_DURATION.observe(duration)
        NEGOTIATION_ROUNDS_TOTAL.labels(outcome="accept").inc()

        if self.sse_publisher:
            await self.sse_publisher.publish_terminal(  # type: ignore[union-attr]
                session.id,
                {"event": "agreed", "final_price": float(offer.price.amount), "session_id": str(session.id)},
            )

        # Update profiles (learning via EMA)
        for profile in [buyer_profile, seller_profile]:
            profile.update_after_session(
                session_agreed=True,
                rounds_taken=session.round_count.value,
                final_price=offer.price.amount,
                budget_ceiling=profile.risk_profile.budget_ceiling,
            )
            await self.profile_repo.update(profile)  # type: ignore[union-attr]

        log.info("session_agreed", session_id=str(session.id), price=float(offer.price.amount))

    async def _handle_walk_away(self, session: NegotiationSession, reason: str) -> None:
        """ROUND_LOOP → WALK_AWAY: agent rejected."""
        event = session.mark_walk_away(reason)
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.event_publisher.publish(event)  # type: ignore[union-attr]

        # Prometheus: terminal state
        ACTIVE_SESSIONS.dec()
        NEGOTIATION_ROUNDS_TOTAL.labels(outcome="reject").inc()

        if self.sse_publisher:
            await self.sse_publisher.publish_terminal(  # type: ignore[union-attr]
                session.id,
                {"event": "walk_away", "reason": reason, "session_id": str(session.id)},
            )
        log.info("session_walk_away", session_id=str(session.id), reason=reason)

    async def _handle_failure(self, session: NegotiationSession, reason: str) -> None:
        """Generic failure handler (backward compat)."""
        event = session.mark_failed(reason)
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.event_publisher.publish(event)  # type: ignore[union-attr]

        if self.sse_publisher:
            await self.sse_publisher.publish_terminal(  # type: ignore[union-attr]
                session.id,
                {"event": "failed", "reason": reason, "session_id": str(session.id)},
            )
        log.info("session_failed", session_id=str(session.id), reason=reason)

    async def _handle_stall(self, session: NegotiationSession) -> None:
        """ROUND_LOOP → STALLED → HUMAN_REVIEW."""
        stall_event = session.mark_stalled()
        escalation_event = session.escalate_to_human_review()
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.event_publisher.publish(escalation_event)  # type: ignore[union-attr]

        # Prometheus: stall detection
        NEGOTIATION_ROUNDS_TOTAL.labels(outcome="stall").inc()

        if self.sse_publisher:
            await self.sse_publisher.publish_turn(  # type: ignore[union-attr]
                session.id,
                {"event": "escalated", "reason": "stall_detected",
                 "round": session.round_count.value, "session_id": str(session.id)},
            )
        log.info("session_stalled", session_id=str(session.id))

    async def _handle_timeout(self, session: NegotiationSession) -> None:
        """ROUND_LOOP → TIMEOUT: TTL expired."""
        event = session.mark_timeout()
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.event_publisher.publish(event)  # type: ignore[union-attr]

        # Prometheus: terminal state
        ACTIVE_SESSIONS.dec()
        NEGOTIATION_ROUNDS_TOTAL.labels(outcome="timeout").inc()

        if self.sse_publisher:
            await self.sse_publisher.publish_terminal(  # type: ignore[union-attr]
                session.id,
                {"event": "timeout", "session_id": str(session.id)},
            )
        log.info("session_timeout", session_id=str(session.id))

    async def _handle_policy_breach(self, session: NegotiationSession) -> None:
        """ROUND_LOOP → POLICY_BREACH: 3x schema failures."""
        event = session.mark_policy_breach()
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.event_publisher.publish(event)  # type: ignore[union-attr]

        if self.sse_publisher:
            await self.sse_publisher.publish_terminal(  # type: ignore[union-attr]
                session.id,
                {"event": "policy_breach", "session_id": str(session.id)},
            )
        log.info("session_policy_breach", session_id=str(session.id))

    async def apply_human_override(self, cmd: HumanOverrideCommand) -> Offer:
        """Human injects an offer mid-session, overriding the agent."""
        session = await self.session_repo.get_by_id(cmd.session_id)  # type: ignore[union-attr]
        if not session:
            raise NotFoundError("NegotiationSession", cmd.session_id)

        if session.status == SessionStatus.HUMAN_REVIEW:
            session.resume_from_human_review()
        elif session.status == SessionStatus.STALLED:
            session.resume_from_human_review()  # STALLED → will go through escalation first
        elif not session.status.is_active:
            raise ConflictError(f"Session {cmd.session_id} is {session.status.value}")

        # Determine role — human overrides are always from the buyer's side
        current_round = session.round_count.value + 1
        offer = Offer.create_human_offer(
            session_id=session.id,
            round_number=current_round,
            proposer_role=ProposerRole.BUYER,
            price=cmd.price,
            currency=cmd.currency,
            terms=cmd.terms,
        )

        offer_event = session.add_offer(offer)
        await self.offer_repo.save(offer)  # type: ignore[union-attr]
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.uow.commit()  # type: ignore[union-attr]

        # Publish events
        await self.event_publisher.publish(offer_event)  # type: ignore[union-attr]
        override_event = HumanOverrideApplied(
            aggregate_id=session.id,
            event_type="HumanOverrideApplied",
            session_id=session.id,
            offer_id=offer.id,
            price=cmd.price,
            applied_by_user_id=cmd.user_id,
        )
        await self.event_publisher.publish(override_event)  # type: ignore[union-attr]

        if self.sse_publisher:
            await self.sse_publisher.publish_turn(  # type: ignore[union-attr]
                session.id,
                {"event": "override", "price": float(cmd.price), "by": "human",
                 "session_id": str(session.id)},
            )

        log.info("human_override_applied", session_id=str(session.id), price=float(cmd.price))
        return offer

    async def terminate_session(self, cmd: TerminateSessionCommand) -> None:
        """Admin terminates a session."""
        session = await self.session_repo.get_by_id(cmd.session_id)  # type: ignore[union-attr]
        if not session:
            raise NotFoundError("NegotiationSession", cmd.session_id)

        event = session.mark_failed(cmd.reason)
        await self.session_repo.update(session)  # type: ignore[union-attr]
        await self.uow.commit()  # type: ignore[union-attr]
        await self.event_publisher.publish(event)  # type: ignore[union-attr]

        if self.sse_publisher:
            await self.sse_publisher.publish_terminal(  # type: ignore[union-attr]
                session.id,
                {"event": "terminated", "reason": cmd.reason, "session_id": str(session.id)},
            )
        log.info("session_terminated", session_id=str(session.id))

    async def get_session_intelligence(self, session_id: uuid.UUID) -> dict:
        """Get intelligence data for the debug endpoint."""
        session = await self.session_repo.get_by_id(session_id)  # type: ignore[union-attr]
        if not session:
            raise NotFoundError("NegotiationSession", session_id)

        return self.neutral_engine.get_session_intelligence(session)  # type: ignore[union-attr]

    async def cleanup_expired_sessions(self) -> int:
        """Expire sessions that have passed their TTL."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self.session_ttl_hours)
        candidates = await self.session_repo.list_expired_candidates(cutoff)  # type: ignore[union-attr]
        count = 0
        for session in candidates[:100]:
            try:
                event = session.mark_expired()
                await self.session_repo.update(session)  # type: ignore[union-attr]
                await self.event_publisher.publish(event)  # type: ignore[union-attr]
                count += 1
            except Exception:
                log.exception("cleanup_expired_error", session_id=str(session.id))
        if count > 0:
            await self.uow.commit()  # type: ignore[union-attr]
        log.info("cleanup_expired_sessions", expired_count=count)
        return count
