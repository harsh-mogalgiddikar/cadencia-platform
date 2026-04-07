# context.md §3 — Application layer: pure frozen query dataclasses.

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GetEscrowQuery:
    """Look up escrow by negotiation session_id."""

    session_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class GetEscrowByIdQuery:
    """Look up escrow directly by its escrow_id."""

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class GetSettlementsQuery:
    """List all settlement records for an escrow."""

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID
