# DANP Negotiation Engine — Neutral Protocol Engine (Backbone)
# context.md §6.1: NeutralEngine — stateless protocol enforcer.
# Buyer and seller NEVER communicate directly. ALL exchange flows through here.
#
# Implements the full 4-layer pipeline:
#   Layer 1: VALUATION    → Math only (reservation/target price)
#   Layer 2: STRATEGY     → Game theory (8 strategies)
#   Layer 3: LLM ADVISORY → Classifies opponent
#   Layer 4: GUARDRAIL    → Veto (budget/margin/compliance)
#
# Also handles:
#   - Turn enforcement (strict BUYER→SELLER alternation)
#   - Schema validation (ActionEnvelope)
#   - Metrics computation (flexibility, response time)
#   - Bayesian belief update
#   - Stall/timeout detection
#   - Convergence → AGREED trigger

from __future__ import annotations

import time
from decimal import Decimal

import structlog

from src.negotiation.domain.agent_profile import AgentProfile
from src.negotiation.domain.guardrails import (
    ActionEnvelope,
    GuardrailEngine,
    validate_raw_envelope,
)
from src.negotiation.domain.offer import Offer, ProposerRole
from src.negotiation.domain.opponent_model import (
    BayesianOpponentModel,
    OpponentBelief,
    compute_opponent_metrics,
)
from src.negotiation.domain.playbook import IndustryPlaybook
from src.negotiation.domain.policies import NegotiationPolicy
from src.negotiation.domain.session import (
    CONVERGENCE_TOLERANCE,
    NegotiationSession,
    SessionStatus,
)
from src.negotiation.domain.strategy import StrategyEngine, adaptive_concession
from src.negotiation.domain.valuation import (
    Valuation,
    compute_buyer_valuation,
    compute_seller_valuation,
)
from src.negotiation.infrastructure.personalization import PersonalizationBuilder

log = structlog.get_logger(__name__)


class NeutralEngine:
    """
    Neutral Protocol Engine — stateless backbone of the DANP system.

    Implements INeutralEngine protocol.
    All state lives in NegotiationSession — NeutralEngine is pure orchestration.

    4-Layer Pipeline per turn:
      1. Valuation  (deterministic math)
      2. Strategy   (game theory selection)
      3. LLM        (Gemini advisory — opponent classification)
      4. Guardrail  (absolute veto)
    """

    def __init__(
        self,
        agent_driver: object,  # IAgentDriver
        personalization_builder: PersonalizationBuilder | None = None,
        sse_publisher: object | None = None,  # ISSEPublisher
        strategy_engine: StrategyEngine | None = None,
        guardrail_engine: GuardrailEngine | None = None,
        bayesian_model: BayesianOpponentModel | None = None,
        personalization_service: object | None = None,  # PersonalizationService (RAG)
    ) -> None:
        self.agent_driver = agent_driver
        self.personalization = personalization_builder or PersonalizationBuilder()
        self.sse_publisher = sse_publisher
        self.strategy_engine = strategy_engine or StrategyEngine()
        self.guardrail_engine = guardrail_engine or GuardrailEngine()
        self.bayesian_model = bayesian_model or BayesianOpponentModel()
        self.personalization_service = personalization_service
        # Per-session belief cache (session_id → {role → belief})
        self._belief_cache: dict[str, dict[str, OpponentBelief]] = {}

    async def process_turn(
        self,
        session: NegotiationSession,
        buyer_profile: AgentProfile,
        seller_profile: AgentProfile,
        buyer_playbook: IndustryPlaybook | None,
        seller_playbook: IndustryPlaybook | None,
    ) -> tuple[Offer, bool]:
        """
        Execute one full negotiation turn through the 4-layer pipeline.

        Returns (offer, is_terminal).
        """
        turn_start = time.monotonic()

        # 0. Check timeout
        if session.is_expired():
            return self._create_timeout_offer(session), True

        # 1. Determine whose turn
        current_role = self._determine_turn(session)
        current_profile = (
            buyer_profile if current_role == ProposerRole.BUYER else seller_profile
        )
        current_playbook = (
            buyer_playbook if current_role == ProposerRole.BUYER else seller_playbook
        )
        is_buyer = current_role == ProposerRole.BUYER

        # 2. Check turn order
        NegotiationPolicy.check_turn_order(session.offers, current_role.value)

        # ── LAYER 1: VALUATION ──
        valuation = self._compute_valuation(current_profile, is_buyer)

        # ── LAYER 2: STRATEGY ──
        opponent_prices = (
            session.get_seller_prices() if is_buyer else session.get_buyer_prices()
        )
        my_prices = (
            session.get_buyer_prices() if is_buyer else session.get_seller_prices()
        )

        # Get Bayesian belief for opponent
        belief = self._get_or_compute_belief(session, current_role, opponent_prices)

        strategy_rec = self.strategy_engine.select_strategy(
            round_num=session.round_count.value,
            my_last_price=my_prices[-1] if my_prices else None,
            opponent_last_price=opponent_prices[-1] if opponent_prices else None,
            reservation_price=valuation.reservation_price,
            target_price=valuation.target_price,
            opponent_flexibility=belief.cooperative + belief.strategic * 0.5,
            rounds_since_concession=session.stall_counter,
            time_remaining_pct=self._time_remaining_pct(session),
            is_buyer=is_buyer,
        )

        # Apply Bayesian modifier to concession
        modifier = self.bayesian_model.strategy_modifier(belief)
        if strategy_rec.concession_fraction > Decimal("0"):
            adjusted_concession = adaptive_concession(
                strategy_rec.concession_fraction,
                opponent_flexibility=belief.cooperative,
                opponent_type=belief.dominant_type.value,
            )
        else:
            adjusted_concession = Decimal("0")

        # ── LAYER 3: LLM ADVISORY ──
        system_prompt = self.personalization.build(
            profile=current_profile,
            playbook=current_playbook,
            role=current_role.value,
        )
        offer_history = self._serialize_offer_history(session.offers)
        session_context = {
            "session_id": str(session.id),
            "round_count": session.round_count.value,
            "rfq_id": str(session.rfq_id),
            "strategy_suggestion": strategy_rec.strategy.value,
            "suggested_price": float(strategy_rec.suggested_price),
            "opponent_belief": belief.to_dict(),
            "concession_modifier": float(adjusted_concession),
        }

        # ── RAG MEMORY INJECTION ──
        # Retrieve Top-5 similar past negotiations from pgvector agent_memory
        if self.personalization_service is not None:
            try:
                enterprise_id = (
                    session.buyer_enterprise_id
                    if is_buyer
                    else session.seller_enterprise_id
                )
                # Build query from current negotiation context
                rag_query = (
                    f"Negotiation for RFQ {session.rfq_id} "
                    f"round {session.round_count.value} "
                    f"price range {strategy_rec.suggested_price}"
                )
                memory_chunks = await self.personalization_service.retrieve_context_for_negotiation(
                    tenant_id=enterprise_id,
                    session_context=rag_query,
                    limit=5,
                )
                if memory_chunks:
                    session_context["past_negotiation_context"] = memory_chunks
                    log.info(
                        "rag_context_injected",
                        enterprise_id=str(enterprise_id),
                        chunks=len(memory_chunks),
                    )
            except Exception as e:
                log.warning("rag_retrieval_failed", error=str(e))

        raw_output = await self.agent_driver.generate_offer(  # type: ignore[union-attr]
            system_prompt=system_prompt,
            session_context=session_context,
            offer_history=offer_history,
        )

        action = raw_output.get("action", "OFFER").upper()
        llm_price = Decimal(str(raw_output.get("price", strategy_rec.suggested_price)))
        confidence = raw_output.get("confidence", 0.5)
        reasoning = raw_output.get("reasoning", "")

        # ── LAYER 4: GUARDRAIL VETO ──
        # Use strategy price as fallback if LLM price violates guardrails
        final_price = llm_price
        is_terminal = False

        if action in ("OFFER", "COUNTER"):
            # Construct envelope for guardrail validation
            envelope = ActionEnvelope(
                session_id=session.id,
                agent_role=current_role.value.lower(),
                round=session.round_count.value + 1,
                action=action.lower(),
                offer_value=llm_price,
                confidence=confidence,
                strategy_tag=strategy_rec.strategy.value,
                rationale=reasoning,
            )

            violations = self.guardrail_engine.validate_envelope(
                envelope=envelope,
                reservation_price=valuation.reservation_price,
                budget_ceiling=(
                    current_profile.risk_profile.budget_ceiling if is_buyer else None
                ),
                margin_floor=(
                    current_profile.risk_profile.margin_floor if not is_buyer else None
                ),
            )

            if violations:
                # Use strategy-recommended price instead
                log.warning(
                    "guardrail_override",
                    violations=[v.message for v in violations],
                    llm_price=float(llm_price),
                    strategy_price=float(strategy_rec.suggested_price),
                )
                final_price = strategy_rec.suggested_price
                reasoning = f"Guardrail override: {reasoning}"

                # Record schema failure if needed
                if session.record_schema_failure():
                    return self._create_policy_breach_offer(session, current_role), True

            # Budget guard for buyer
            if is_buyer:
                try:
                    NegotiationPolicy.check_budget_guard(
                        final_price, current_profile.risk_profile.budget_ceiling
                    )
                except Exception:
                    final_price = min(
                        final_price, current_profile.risk_profile.budget_ceiling
                    )

        elif action == "ACCEPT":
            # Accept the last counter from other side
            last_counter = (
                session.get_last_seller_offer()
                if is_buyer
                else session.get_last_buyer_offer()
            )
            final_price = last_counter.price.amount if last_counter else llm_price
            is_terminal = True

        elif action == "REJECT":
            final_price = (
                llm_price if llm_price > Decimal("0") else Decimal("1")
            )
            is_terminal = True

        else:
            # Unknown action — treat as counter
            action = "COUNTER"

        # Create the offer
        offer = Offer.create_agent_offer(
            session_id=session.id,
            round_number=session.round_count.value + 1,
            proposer_role=current_role,
            price=final_price,
            currency="INR",
            terms={},
            confidence=confidence,
            agent_reasoning=f"{action}: {reasoning}" if action == "REJECT" else reasoning,
        )

        # Track concession / stall
        if not is_terminal and action in ("OFFER", "COUNTER"):
            self._track_concession(session, current_role, final_price)

        # Check convergence after non-terminal offers
        if not is_terminal and action in ("OFFER", "COUNTER"):
            last_buyer = session.get_last_buyer_offer()
            last_seller = session.get_last_seller_offer()
            b_price = (
                final_price if is_buyer else (last_buyer.price.amount if last_buyer else None)
            )
            s_price = (
                final_price if not is_buyer else (last_seller.price.amount if last_seller else None)
            )
            if NegotiationPolicy.check_convergence(b_price, s_price):
                is_terminal = True

        # Check stall threshold
        if not is_terminal:
            stall_threshold = current_profile.strategy_weights.stall_threshold
            if NegotiationPolicy.check_stall(
                session.round_count.value + 1, stall_threshold
            ):
                is_terminal = True

        # Update Bayesian belief
        self._update_belief_cache(session, current_role, opponent_prices)

        # Publish SSE event
        elapsed = time.monotonic() - turn_start
        if self.sse_publisher:
            sse_event = {
                "event": "offer" if not is_terminal else action.lower(),
                "round": session.round_count.value + 1,
                "proposer": current_role.value,
                "price": float(final_price),
                "confidence": confidence,
                "action": action,
                "strategy": strategy_rec.strategy.value,
                "opponent_belief": belief.to_dict(),
                "session_id": str(session.id),
                "elapsed_ms": round(elapsed * 1000),
            }
            await self.sse_publisher.publish_turn(session.id, sse_event)  # type: ignore[union-attr]

        return offer, is_terminal

    # ── Intelligence Methods (for Debug API) ──────────────────────────────────

    def get_session_intelligence(
        self, session: NegotiationSession
    ) -> dict:
        """
        Return intelligence data for the debug endpoint.

        Includes:
        - Current Bayesian beliefs for both sides
        - Flexibility scores
        - Strategy recommendations
        - Stall/convergence status
        """
        sid = str(session.id)
        buyer_prices = session.get_buyer_prices()
        seller_prices = session.get_seller_prices()

        buyer_metrics = compute_opponent_metrics(buyer_prices) if buyer_prices else None
        seller_metrics = compute_opponent_metrics(seller_prices) if seller_prices else None

        # Get cached beliefs or compute
        beliefs = self._belief_cache.get(sid, {})
        buyer_belief = beliefs.get("buyer", BayesianOpponentModel.PRIOR)
        seller_belief = beliefs.get("seller", BayesianOpponentModel.PRIOR)

        if buyer_metrics:
            buyer_belief = self.bayesian_model.update_belief(buyer_metrics)
        if seller_metrics:
            seller_belief = self.bayesian_model.update_belief(seller_metrics)

        return {
            "session_id": sid,
            "round_count": session.round_count.value,
            "status": session.status.value,
            "buyer_intelligence": {
                "belief": buyer_belief.to_dict(),
                "dominant_type": buyer_belief.dominant_type.value,
                "confidence": buyer_belief.confidence,
                "flexibility": (
                    buyer_metrics.flexibility_score if buyer_metrics else None
                ),
                "consistency": (
                    buyer_metrics.consistency if buyer_metrics else None
                ),
                "prices": [float(p) for p in buyer_prices],
            },
            "seller_intelligence": {
                "belief": seller_belief.to_dict(),
                "dominant_type": seller_belief.dominant_type.value,
                "confidence": seller_belief.confidence,
                "flexibility": (
                    seller_metrics.flexibility_score if seller_metrics else None
                ),
                "consistency": (
                    seller_metrics.consistency if seller_metrics else None
                ),
                "prices": [float(p) for p in seller_prices],
            },
            "convergence": session.check_convergence(),
            "stall_counter": session.stall_counter,
            "schema_failures": session.schema_failure_count,
        }

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _determine_turn(self, session: NegotiationSession) -> ProposerRole:
        """Determine whose turn it is next."""
        return session.next_proposer

    def _compute_valuation(
        self, profile: AgentProfile, is_buyer: bool
    ) -> Valuation:
        """Layer 1: Compute valuation from profile."""
        if is_buyer:
            return compute_buyer_valuation(
                fair_price=profile.risk_profile.budget_ceiling * Decimal("0.80"),
                risk_appetite=profile.risk_profile.risk_appetite,
                budget_ceiling=profile.risk_profile.budget_ceiling,
            )
        else:
            cost_basis = profile.risk_profile.budget_ceiling * Decimal("0.60")
            return compute_seller_valuation(
                cost_basis=cost_basis,
                margin_floor=profile.risk_profile.margin_floor,
                risk_appetite=profile.risk_profile.risk_appetite,
            )

    def _get_or_compute_belief(
        self,
        session: NegotiationSession,
        current_role: ProposerRole,
        opponent_prices: list[Decimal],
    ) -> OpponentBelief:
        """Get cached belief or compute fresh from opponent prices."""
        sid = str(session.id)
        role_key = current_role.value.lower()

        if sid in self._belief_cache and role_key in self._belief_cache[sid]:
            prior = self._belief_cache[sid][role_key]
        else:
            prior = BayesianOpponentModel.PRIOR

        if len(opponent_prices) < 2:
            return prior

        metrics = compute_opponent_metrics(opponent_prices)
        return self.bayesian_model.update_belief(metrics, prior)

    def _update_belief_cache(
        self,
        session: NegotiationSession,
        current_role: ProposerRole,
        opponent_prices: list[Decimal],
    ) -> None:
        """Update the belief cache after a turn."""
        if len(opponent_prices) < 2:
            return

        sid = str(session.id)
        role_key = current_role.value.lower()

        if sid not in self._belief_cache:
            self._belief_cache[sid] = {}

        metrics = compute_opponent_metrics(opponent_prices)
        prior = self._belief_cache[sid].get(role_key, BayesianOpponentModel.PRIOR)
        self._belief_cache[sid][role_key] = self.bayesian_model.update_belief(
            metrics, prior
        )

    def _track_concession(
        self,
        session: NegotiationSession,
        role: ProposerRole,
        new_price: Decimal,
    ) -> None:
        """Track whether a meaningful concession was made."""
        is_buyer = role == ProposerRole.BUYER
        my_prices = (
            session.get_buyer_prices() if is_buyer else session.get_seller_prices()
        )
        if not my_prices:
            session.reset_stall_counter()
            return

        last_price = my_prices[-1]
        if last_price == Decimal("0"):
            session.reset_stall_counter()
            return

        change = abs(new_price - last_price) / last_price
        if change < 0.002:  # Less than 0.2% change = no concession
            session.record_no_concession()
        else:
            session.reset_stall_counter()

    def _time_remaining_pct(self, session: NegotiationSession) -> float:
        """Fraction of max rounds remaining."""
        from src.negotiation.domain.session import MAX_ROUNDS

        used = session.round_count.value
        return max(0.0, (MAX_ROUNDS - used) / MAX_ROUNDS)

    def _serialize_offer_history(self, offers: list[Offer]) -> list[dict]:
        """Serialize last 20 offers for LLM context (no PII)."""
        return [
            {
                "round": o.round_number.value,
                "role": o.proposer_role.value,
                "price": float(o.price.amount),
                "terms": o.terms,
                "is_human": o.is_human_override,
            }
            for o in offers[-20:]
        ]

    def _create_timeout_offer(
        self, session: NegotiationSession
    ) -> Offer:
        """Create a placeholder offer for timeout termination."""
        return Offer.create_agent_offer(
            session_id=session.id,
            round_number=session.round_count.value + 1,
            proposer_role=session.next_proposer,
            price=Decimal("1"),
            currency="INR",
            terms={},
            confidence=0.0,
            agent_reasoning="TIMEOUT: Session TTL expired.",
        )

    def _create_policy_breach_offer(
        self, session: NegotiationSession, role: ProposerRole
    ) -> Offer:
        """Create a placeholder offer for policy breach termination."""
        return Offer.create_agent_offer(
            session_id=session.id,
            round_number=session.round_count.value + 1,
            proposer_role=role,
            price=Decimal("1"),
            currency="INR",
            terms={},
            confidence=0.0,
            agent_reasoning="POLICY_BREACH: Schema validation failed 3 times.",
        )
