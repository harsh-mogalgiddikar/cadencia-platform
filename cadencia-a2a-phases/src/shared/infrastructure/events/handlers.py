"""
Domain event handler registry.

context.md §7: Event handler subscriptions wired here.
Phase 0: No subscriptions.
Phase 2: EscrowFunded, EscrowReleased, SessionAgreedStub stub handlers.
Phase 3: Full compliance handlers replace Phase 2 stubs.
         + EscrowRefunded, EscrowFrozen compliance handlers.
         + HMAC-signed webhook notifiers for all settlement events.
"""

from src.shared.infrastructure.events.publisher import EventPublisher
from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)


def register_handlers(publisher: EventPublisher) -> None:
    """
    Register all Phase 0 + Phase 1 cross-domain event handlers.

    Called once at application startup (lifespan).
    Phase 0: No subscriptions.
    """
    log.info("event_handlers_registered", phase="0_and_1", handler_count=0)


# ── Phase Two — Compliance Stub Handlers ─────────────────────────────────────


async def handle_escrow_funded_stub(event: object) -> None:
    """
    Phase Two stub: log EscrowFunded event for compliance pipeline.
    Replaced by handle_escrow_funded_compliance in Phase Three.
    """
    log.info(
        "escrow_funded_event_received",
        escrow_id=str(getattr(event, "escrow_id", "")),
        session_id=str(getattr(event, "session_id", "")),
        amount_microalgo=getattr(event, "amount_microalgo", 0),
        fund_tx_id=getattr(event, "fund_tx_id", ""),
        phase="stub_phase_two",
    )


async def handle_escrow_released_stub(event: object) -> None:
    """
    Phase Two stub: log EscrowReleased event for compliance pipeline.
    Replaced by handle_escrow_released_compliance in Phase Three.
    """
    log.info(
        "escrow_released_event_received",
        escrow_id=str(getattr(event, "escrow_id", "")),
        session_id=str(getattr(event, "session_id", "")),
        merkle_root=getattr(event, "merkle_root", ""),
        release_tx_id=getattr(event, "release_tx_id", ""),
        phase="stub_phase_two",
    )


async def handle_session_agreed_stub(event: object) -> None:
    """
    Phase Two stub: log SessionAgreedStub event (does NOT auto-deploy escrow).

    Full auto-deploy wiring activated in Phase Four when NegotiationService
    publishes the real SessionAgreed event.
    context.md §7: SessionAgreed → settlement DeployEscrow (Phase Four)
    """
    log.info(
        "session_agreed_stub_received",
        session_id=str(getattr(event, "session_id", "")),
        buyer_enterprise_id=str(getattr(event, "buyer_enterprise_id", "")),
        seller_enterprise_id=str(getattr(event, "seller_enterprise_id", "")),
        agreed_price_microalgo=getattr(event, "agreed_price_microalgo", 0),
        phase="stub_phase_two",
    )
    # TODO Phase Four: SettlementService.deploy_escrow(DeployEscrowCommand(...))


def register_phase_two_handlers(publisher: EventPublisher) -> None:
    """
    Register Phase Two stub event handlers.

    Called in main.py lifespan AFTER register_handlers(). Additive only.
    Phase Three replaces EscrowFunded and EscrowReleased with full compliance handlers.
    """
    publisher.subscribe("EscrowFunded", handle_escrow_funded_stub)
    publisher.subscribe("EscrowReleased", handle_escrow_released_stub)
    publisher.subscribe("SessionAgreedStub", handle_session_agreed_stub)

    log.info(
        "phase_two_event_handlers_registered",
        handlers=["EscrowFunded", "EscrowReleased", "SessionAgreedStub"],
    )


# ── Phase Three — Full Compliance Handlers ────────────────────────────────────


def _build_compliance_service(session: object) -> object:
    """Construct ComplianceService with all concrete adapters for a given session."""
    from src.shared.infrastructure.merkle_service import MerkleService
    from src.shared.infrastructure.db.uow import SqlAlchemyUnitOfWork
    from src.compliance.application.services import ComplianceService
    from src.compliance.infrastructure.enterprise_reader import PostgresEnterpriseReader
    from src.compliance.infrastructure.fema_gst_exporter import FEMAGSTExporter
    from src.compliance.infrastructure.repositories import (
        PostgresAuditLogRepository,
        PostgresExportJobRepository,
        PostgresFEMARepository,
        PostgresGSTRepository,
    )
    return ComplianceService(
        audit_repo=PostgresAuditLogRepository(session),  # type: ignore[arg-type]
        fema_repo=PostgresFEMARepository(session),  # type: ignore[arg-type]
        gst_repo=PostgresGSTRepository(session),  # type: ignore[arg-type]
        export_job_repo=PostgresExportJobRepository(session),  # type: ignore[arg-type]
        enterprise_reader=PostgresEnterpriseReader(session),  # type: ignore[arg-type]
        merkle_service=MerkleService(),
        exporter=FEMAGSTExporter(),
        uow=SqlAlchemyUnitOfWork(session),  # type: ignore[arg-type]
    )


async def handle_escrow_funded_compliance(event: object) -> None:
    """
    Phase Three: append EscrowFunded to hash-chained audit log.

    context.md §7: EscrowFunded -> ComplianceService.append_audit_event()
    """
    escrow_id = getattr(event, "escrow_id", None)
    if not escrow_id:
        log.warning("handle_escrow_funded_compliance_missing_escrow_id")
        return

    payload = {
        "escrow_id": str(escrow_id),
        "session_id": str(getattr(event, "session_id", "")),
        "amount_microalgo": getattr(event, "amount_microalgo", 0),
        "fund_tx_id": getattr(event, "fund_tx_id", ""),
    }

    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.compliance.application.commands import AppendAuditEventCommand
        async with get_session_factory()() as session:
            svc = _build_compliance_service(session)
            await svc.append_audit_event(  # type: ignore[union-attr]
                AppendAuditEventCommand(
                    escrow_id=escrow_id,
                    event_type="EscrowFunded",
                    payload=payload,
                )
            )
    except Exception:
        log.exception(
            "handle_escrow_funded_compliance_failed",
            escrow_id=str(escrow_id),
        )


async def handle_escrow_released_compliance(event: object) -> None:
    """
    Phase Three: append audit entry + generate FEMA/GST compliance records.

    context.md §7: EscrowReleased -> ComplianceService.generate_compliance_records()
    """
    import uuid
    escrow_id = getattr(event, "escrow_id", None)
    if not escrow_id:
        log.warning("handle_escrow_released_compliance_missing_escrow_id")
        return

    session_id = getattr(event, "session_id", uuid.uuid4())
    amount_microalgo = getattr(event, "amount_microalgo", 0)
    merkle_root = getattr(event, "merkle_root", "")
    buyer_enterprise_id = getattr(event, "buyer_enterprise_id", None)
    seller_enterprise_id = getattr(event, "seller_enterprise_id", None)

    audit_payload = {
        "escrow_id": str(escrow_id),
        "session_id": str(session_id),
        "amount_microalgo": amount_microalgo,
        "release_tx_id": getattr(event, "release_tx_id", ""),
        "merkle_root": merkle_root,
    }

    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.compliance.application.commands import (
            AppendAuditEventCommand,
            GenerateComplianceRecordsCommand,
        )
        async with get_session_factory()() as session:
            svc = _build_compliance_service(session)
            # 1. Append audit entry
            await svc.append_audit_event(  # type: ignore[union-attr]
                AppendAuditEventCommand(
                    escrow_id=escrow_id,
                    event_type="EscrowReleased",
                    payload=audit_payload,
                )
            )
            # 2. Generate FEMA + GST compliance records
            await svc.generate_compliance_records(  # type: ignore[union-attr]
                GenerateComplianceRecordsCommand(
                    escrow_id=escrow_id,
                    session_id=session_id,
                    amount_microalgo=amount_microalgo,
                    merkle_root=merkle_root,
                    buyer_enterprise_id=buyer_enterprise_id,
                    seller_enterprise_id=seller_enterprise_id,
                )
            )
    except Exception:
        log.exception(
            "handle_escrow_released_compliance_failed",
            escrow_id=str(escrow_id),
        )


async def handle_escrow_refunded_compliance(event: object) -> None:
    """
    Phase Three: append EscrowRefunded to hash-chained audit log.

    Refunds generate an audit entry but do NOT generate FEMA/GST records
    (no settlement occurred — funds returned to buyer).
    """
    escrow_id = getattr(event, "escrow_id", None)
    if not escrow_id:
        log.warning("handle_escrow_refunded_compliance_missing_escrow_id")
        return

    payload = {
        "escrow_id": str(escrow_id),
        "session_id": str(getattr(event, "session_id", "")),
        "amount_microalgo": getattr(event, "amount_microalgo", 0),
        "refund_tx_id": getattr(event, "refund_tx_id", ""),
        "reason": getattr(event, "reason", ""),
    }

    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.compliance.application.commands import AppendAuditEventCommand
        async with get_session_factory()() as session:
            svc = _build_compliance_service(session)
            await svc.append_audit_event(  # type: ignore[union-attr]
                AppendAuditEventCommand(
                    escrow_id=escrow_id,
                    event_type="EscrowRefunded",
                    payload=payload,
                )
            )
    except Exception:
        log.exception(
            "handle_escrow_refunded_compliance_failed",
            escrow_id=str(escrow_id),
        )


async def handle_escrow_frozen_compliance(event: object) -> None:
    """
    Phase Three: append EscrowFrozen to hash-chained audit log.

    Freeze events generate an audit entry for dispute tracking.
    """
    escrow_id = getattr(event, "escrow_id", None)
    if not escrow_id:
        log.warning("handle_escrow_frozen_compliance_missing_escrow_id")
        return

    payload = {
        "escrow_id": str(escrow_id),
        "session_id": str(getattr(event, "session_id", "")),
        "frozen_by": getattr(event, "frozen_by", "ADMIN"),
    }

    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.compliance.application.commands import AppendAuditEventCommand
        async with get_session_factory()() as session:
            svc = _build_compliance_service(session)
            await svc.append_audit_event(  # type: ignore[union-attr]
                AppendAuditEventCommand(
                    escrow_id=escrow_id,
                    event_type="EscrowFrozen",
                    payload=payload,
                )
            )
    except Exception:
        log.exception(
            "handle_escrow_frozen_compliance_failed",
            escrow_id=str(escrow_id),
        )


async def handle_escrow_deployed_compliance(event: object) -> None:
    """
    Phase Three: append EscrowDeployed to hash-chained audit log.

    context.md §7: EscrowDeployed → compliance (AppendAuditEvent ESCROW_DEPLOYED)
    """
    escrow_id = getattr(event, "escrow_id", None)
    if not escrow_id:
        log.warning("handle_escrow_deployed_compliance_missing_escrow_id")
        return

    payload = {
        "escrow_id": str(escrow_id),
        "session_id": str(getattr(event, "session_id", "")),
        "algo_app_id": getattr(event, "algo_app_id", 0),
        "deploy_tx_id": getattr(event, "deploy_tx_id", ""),
    }

    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.compliance.application.commands import AppendAuditEventCommand
        async with get_session_factory()() as session:
            svc = _build_compliance_service(session)
            await svc.append_audit_event(  # type: ignore[union-attr]
                AppendAuditEventCommand(
                    escrow_id=escrow_id,
                    event_type="EscrowDeployed",
                    payload=payload,
                )
            )
    except Exception:
        log.exception(
            "handle_escrow_deployed_compliance_failed",
            escrow_id=str(escrow_id),
        )


def register_phase_three_handlers(publisher: EventPublisher) -> None:
    """
    Replace Phase Two stub handlers with full Phase Three compliance handlers
    and register HMAC-signed webhook notifiers.

    Unsubscribes Phase Two stubs for EscrowFunded and EscrowReleased,
    then subscribes the real compliance handlers + webhook notifiers.

    Called in main.py lifespan AFTER register_phase_two_handlers().
    """
    # ── Replace EscrowFunded stub with compliance handler ─────────────────────
    publisher.unsubscribe("EscrowFunded", handle_escrow_funded_stub)
    publisher.subscribe("EscrowFunded", handle_escrow_funded_compliance)

    # ── Replace EscrowReleased stub with compliance handler ───────────────────
    publisher.unsubscribe("EscrowReleased", handle_escrow_released_stub)
    publisher.subscribe("EscrowReleased", handle_escrow_released_compliance)

    # ── Subscribe EscrowRefunded compliance handler (new in Phase Three) ──────
    publisher.subscribe("EscrowRefunded", handle_escrow_refunded_compliance)

    # ── Subscribe EscrowFrozen compliance handler (new in Phase Three) ────────
    publisher.subscribe("EscrowFrozen", handle_escrow_frozen_compliance)

    # ── Subscribe EscrowDeployed compliance handler (context.md §7) ───────────
    publisher.subscribe("EscrowDeployed", handle_escrow_deployed_compliance)

    # ── Subscribe HMAC-signed webhook notifiers for all settlement events ─────
    from src.shared.infrastructure.webhook_notifier import (
        notify_escrow_funded,
        notify_escrow_released,
        notify_escrow_refunded,
        notify_escrow_frozen,
    )
    publisher.subscribe("EscrowFunded", notify_escrow_funded)
    publisher.subscribe("EscrowReleased", notify_escrow_released)
    publisher.subscribe("EscrowRefunded", notify_escrow_refunded)
    publisher.subscribe("EscrowFrozen", notify_escrow_frozen)

    log.info(
        "phase_three_event_handlers_registered",
        handlers=[
            "EscrowDeployed->compliance",
            "EscrowFunded->compliance",
            "EscrowReleased->compliance",
            "EscrowRefunded->compliance",
            "EscrowFrozen->compliance",
            "EscrowFunded->webhook",
            "EscrowReleased->webhook",
            "EscrowRefunded->webhook",
            "EscrowFrozen->webhook",
        ],
    )


# ── Phase Four — Negotiation Event Handlers ───────────────────────────────────
# WIRING: shared/handlers.py is the cross-domain event bus.
# It imports from bounded contexts to wire event → command.
# This is the ONLY permitted cross-domain import outside domain.
# REF: context.md §1.3, §3.2


async def handle_session_agreed_deploy(event: object) -> None:
    """
    Phase Four: SessionAgreed → SettlementService.deploy_escrow().

    Replaces handle_session_agreed_stub from Phase Two.
    context.md §3.2: SessionAgreed → settlement DeployEscrow

    Builds a standalone SettlementService with its own DB session and
    calls deploy_escrow with the agreed-upon escrow parameters.
    """
    import uuid
    from decimal import Decimal

    session_id = getattr(event, "session_id", None)
    if not session_id:
        log.warning("handle_session_agreed_deploy_missing_session_id")
        return

    buyer_enterprise_id = getattr(event, "buyer_enterprise_id", None)
    seller_enterprise_id = getattr(event, "seller_enterprise_id", None)
    agreed_price = getattr(event, "agreed_price", 0)

    if not all([buyer_enterprise_id, seller_enterprise_id]):
        log.error(
            "handle_session_agreed_deploy_missing_enterprise_ids",
            session_id=str(session_id),
        )
        return

    # ── INR → microALGO conversion via TreasuryService FX ─────────────────
    try:
        from src.treasury.infrastructure.frankfurter_fx_adapter import FrankfurterFXAdapter
        fx_adapter = FrankfurterFXAdapter()
        fx_rate = await fx_adapter.get_rate("INR", "USD")
        # 1 ALGO ≈ 1 USD for testnet; production uses real ALGO/USD rate
        price_algo = Decimal(str(agreed_price)) * fx_rate.rate
        price_microalgo = int(price_algo * Decimal("1000000"))
    except Exception as fx_exc:
        # Fallback: approximate conversion using static rate
        log.warning(
            "fx_conversion_fallback",
            error=str(fx_exc),
            session_id=str(session_id),
        )
        price_microalgo = int(Decimal(str(agreed_price)) * Decimal("0.012") * Decimal("1000000"))

    log.info(
        "session_agreed_deploy_escrow_triggered",
        session_id=str(session_id),
        agreed_price=str(agreed_price),
        price_microalgo=price_microalgo,
        buyer_enterprise_id=str(buyer_enterprise_id),
        seller_enterprise_id=str(seller_enterprise_id),
    )

    # ── Build SettlementService and call deploy_escrow ─────────────────────
    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.shared.infrastructure.db.uow import SqlAlchemyUnitOfWork
        from src.shared.infrastructure.events.publisher import get_publisher
        from src.shared.infrastructure.merkle_service import MerkleService
        from src.settlement.application.services import SettlementService
        from src.settlement.application.commands import DeployEscrowCommand
        from src.settlement.infrastructure.algorand_gateway import AlgorandGateway
        from src.settlement.infrastructure.repositories import (
            PostgresEscrowRepository,
            PostgresSettlementRepository,
        )

        # Resolve wallet addresses from enterprise profiles
        buyer_address = ""
        seller_address = ""
        async with get_session_factory()() as db_session:
            from src.identity.infrastructure.repositories import PostgresEnterpriseRepository
            ent_repo = PostgresEnterpriseRepository(db_session)
            buyer_ent = await ent_repo.get_by_id(buyer_enterprise_id)
            seller_ent = await ent_repo.get_by_id(seller_enterprise_id)
            if buyer_ent and buyer_ent.algorand_wallet:
                buyer_address = buyer_ent.algorand_wallet.value
            if seller_ent and seller_ent.algorand_wallet:
                seller_address = seller_ent.algorand_wallet.value

        if not buyer_address or not seller_address:
            log.warning(
                "session_agreed_deploy_skipped_no_wallets",
                session_id=str(session_id),
                buyer_has_wallet=bool(buyer_address),
                seller_has_wallet=bool(seller_address),
            )
            return

        async with get_session_factory()() as db_session:
            svc = SettlementService(
                escrow_repo=PostgresEscrowRepository(db_session),
                settlement_repo=PostgresSettlementRepository(db_session),
                blockchain_gateway=AlgorandGateway(),
                merkle_service=MerkleService(),
                anchor_service=None,  # Anchor wired separately after deploy
                event_publisher=get_publisher(),
                uow=SqlAlchemyUnitOfWork(db_session),
            )
            await svc.deploy_escrow(
                DeployEscrowCommand(
                    session_id=session_id,
                    buyer_algorand_address=buyer_address,
                    seller_algorand_address=seller_address,
                    amount_microalgo=price_microalgo,
                )
            )
            log.info(
                "session_agreed_escrow_deployed",
                session_id=str(session_id),
                amount_microalgo=price_microalgo,
            )
    except Exception:
        log.exception(
            "handle_session_agreed_deploy_failed",
            session_id=str(session_id),
        )


async def handle_session_agreed_audit(event: object) -> None:
    """Phase Four: append SESSION_AGREED audit entry."""
    session_id = getattr(event, "session_id", None)
    if not session_id:
        return

    payload = {
        "session_id": str(session_id),
        "agreed_price": str(getattr(event, "agreed_price", "")),
        "agreed_currency": getattr(event, "agreed_currency", "INR"),
        "buyer_enterprise_id": str(getattr(event, "buyer_enterprise_id", "")),
        "seller_enterprise_id": str(getattr(event, "seller_enterprise_id", "")),
    }

    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.compliance.application.commands import AppendAuditEventCommand
        async with get_session_factory()() as session:
            svc = _build_compliance_service(session)
            await svc.append_audit_event(  # type: ignore[union-attr]
                AppendAuditEventCommand(
                    escrow_id=session_id,
                    event_type="SessionAgreed",
                    payload=payload,
                )
            )
    except Exception:
        log.exception("handle_session_agreed_audit_failed", session_id=str(session_id))


async def handle_offer_submitted_audit(event: object) -> None:
    """Phase Four: append OFFER_SUBMITTED audit entry."""
    session_id = getattr(event, "session_id", None)
    if not session_id:
        return
    log.info(
        "offer_submitted_audit",
        session_id=str(session_id),
        offer_id=str(getattr(event, "offer_id", "")),
        round_number=getattr(event, "round_number", 0),
        proposer_role=getattr(event, "proposer_role", ""),
    )


async def handle_human_override_audit(event: object) -> None:
    """Phase Four: append HUMAN_OVERRIDE audit entry."""
    session_id = getattr(event, "session_id", None)
    if not session_id:
        return
    log.info(
        "human_override_audit",
        session_id=str(session_id),
        offer_id=str(getattr(event, "offer_id", "")),
        price=str(getattr(event, "price", "")),
        applied_by_user_id=str(getattr(event, "applied_by_user_id", "")),
    )


async def handle_session_failed_audit(event: object) -> None:
    """Phase Four: append SESSION_FAILED audit entry."""
    session_id = getattr(event, "session_id", None)
    if not session_id:
        return
    log.info(
        "session_failed_audit",
        session_id=str(session_id),
        reason=getattr(event, "reason", ""),
        round_count=getattr(event, "round_count", 0),
    )


def register_phase_four_handlers(publisher: EventPublisher) -> None:
    """
    Replace SessionAgreedStub with real handlers and register
    negotiation audit event handlers.

    Called in main.py lifespan AFTER register_phase_three_handlers().
    """
    # Replace SessionAgreedStub with real SessionAgreed handlers
    publisher.unsubscribe("SessionAgreedStub", handle_session_agreed_stub)
    publisher.subscribe("SessionAgreed", handle_session_agreed_deploy)
    publisher.subscribe("SessionAgreed", handle_session_agreed_audit)

    # Wire negotiation audit events
    publisher.subscribe("OfferSubmitted", handle_offer_submitted_audit)
    publisher.subscribe("HumanOverrideApplied", handle_human_override_audit)
    publisher.subscribe("SessionFailed", handle_session_failed_audit)

    log.info(
        "phase_four_event_handlers_registered",
        handlers=[
            "SessionAgreed->deploy",
            "SessionAgreed->audit",
            "OfferSubmitted->audit",
            "HumanOverrideApplied->audit",
            "SessionFailed->audit",
        ],
    )


# ── Phase Five — Marketplace → Negotiation Handlers ────────────────────────


async def handle_rfq_confirmed(event: object) -> None:
    """
    Phase Five: RFQConfirmed → NegotiationService.create_session().

    Builds a standalone NegotiationService with its own DB session
    and creates a negotiation session from the confirmed RFQ match.
    """
    rfq_id = getattr(event, "rfq_id", None)
    match_id = getattr(event, "match_id", None)
    buyer_id = getattr(event, "buyer_enterprise_id", None)
    seller_id = getattr(event, "seller_enterprise_id", None)

    if not all([rfq_id, match_id, buyer_id, seller_id]):
        log.error("rfq_confirmed_missing_fields", event=str(event))
        return

    log.info(
        "rfq_confirmed_creating_session",
        rfq_id=str(rfq_id),
        match_id=str(match_id),
        buyer_enterprise_id=str(buyer_id),
        seller_enterprise_id=str(seller_id),
    )

    try:
        from src.shared.infrastructure.db.session import get_session_factory
        from src.shared.infrastructure.db.uow import SqlAlchemyUnitOfWork
        from src.shared.infrastructure.events.publisher import get_publisher
        from src.negotiation.application.services import NegotiationService
        from src.negotiation.application.commands import CreateSessionCommand
        from src.negotiation.infrastructure.llm_agent_driver import get_agent_driver
        from src.negotiation.infrastructure.neutral_engine import NeutralEngine
        from src.negotiation.infrastructure.personalization import PersonalizationBuilder
        from src.negotiation.infrastructure.repositories import (
            PostgresAgentProfileRepository,
            PostgresOfferRepository,
            PostgresPlaybookRepository,
            PostgresSessionRepository,
        )

        async with get_session_factory()() as db_session:
            engine = NeutralEngine(
                agent_driver=get_agent_driver(),
                personalization_builder=PersonalizationBuilder(),
                sse_publisher=None,
            )
            svc = NegotiationService(
                session_repo=PostgresSessionRepository(db_session),
                offer_repo=PostgresOfferRepository(db_session),
                profile_repo=PostgresAgentProfileRepository(db_session),
                playbook_repo=PostgresPlaybookRepository(db_session),
                neutral_engine=engine,
                sse_publisher=None,
                event_publisher=get_publisher(),
                uow=SqlAlchemyUnitOfWork(db_session),
            )
            session = await svc.create_session(
                CreateSessionCommand(
                    match_id=match_id,
                    rfq_id=rfq_id,
                    buyer_enterprise_id=buyer_id,
                    seller_enterprise_id=seller_id,
                )
            )
            log.info(
                "rfq_confirmed_session_created",
                session_id=str(session.id),
                rfq_id=str(rfq_id),
                match_id=str(match_id),
            )
    except Exception:
        log.exception(
            "handle_rfq_confirmed_create_session_failed",
            rfq_id=str(rfq_id),
            match_id=str(match_id),
        )


async def handle_rfq_parsed_audit(event: object) -> None:
    """Phase Five: log RFQParsed for observability."""
    log.info(
        "rfq_parsed_audit",
        rfq_id=str(getattr(event, "rfq_id", "")),
        hsn_code=getattr(event, "hsn_code", None),
        has_budget=getattr(event, "has_budget", False),
    )


async def handle_rfq_matched_audit(event: object) -> None:
    """Phase Five: log RFQMatched for observability."""
    log.info(
        "rfq_matched_audit",
        rfq_id=str(getattr(event, "rfq_id", "")),
        match_count=getattr(event, "match_count", 0),
        top_score=getattr(event, "top_score", 0.0),
    )


def register_phase_five_handlers(publisher: EventPublisher) -> None:
    """
    Register marketplace event handlers.

    Called in main.py lifespan AFTER register_phase_four_handlers().
    """
    publisher.subscribe("RFQConfirmed", handle_rfq_confirmed)
    publisher.subscribe("RFQParsed", handle_rfq_parsed_audit)
    publisher.subscribe("RFQMatched", handle_rfq_matched_audit)

    log.info(
        "phase_five_event_handlers_registered",
        handlers=[
            "RFQConfirmed->create_session",
            "RFQParsed->audit",
            "RFQMatched->audit",
        ],
    )

