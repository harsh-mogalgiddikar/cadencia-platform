# context.md §3 — Hexagonal Architecture: commands are pure Python dataclasses.
# No FastAPI, SQLAlchemy, or infrastructure imports here.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class AppendAuditEventCommand:
    """
    Append a single event to the hash-chained audit log for an escrow.

    Called by Phase 3 event handlers when EscrowFunded, EscrowReleased, etc. fire.
    Advisory lock is acquired inside ComplianceService.append_audit_event().
    """

    escrow_id: uuid.UUID
    event_type: str
    payload: dict  # Serialisable event payload


@dataclass(frozen=True)
class GenerateComplianceRecordsCommand:
    """
    Generate FEMA and GST compliance records after escrow release.

    Called by Phase 3 handler for EscrowReleased event.
    Idempotent: if records already exist for escrow_id, returns existing.
    """

    escrow_id: uuid.UUID
    session_id: uuid.UUID
    amount_microalgo: int
    merkle_root: str

    # Enterprise IDs for looking up PAN / GSTIN via IEnterpriseReader
    buyer_enterprise_id: uuid.UUID | None = None
    seller_enterprise_id: uuid.UUID | None = None

    # Optional FX rate override (e.g., from treasury service)
    # If None, ComplianceService uses a stub rate of INR 15 per microAlgo
    fx_rate_inr_per_algo: Decimal | None = None

    # HSN code for GST (default: 8471 — computers/electronics)
    hsn_code: str = "8471"


@dataclass(frozen=True)
class RequestBulkExportCommand:
    """
    Request a bulk ZIP export of FEMA + GST records for a list of escrows.

    Creates an ExportJob row (PENDING); background task generates the ZIP
    and stores in Redis with 1-hour TTL.
    """

    escrow_ids: list[uuid.UUID]
    requested_by_enterprise_id: uuid.UUID
    job_id: uuid.UUID = field(default_factory=uuid.uuid4)
