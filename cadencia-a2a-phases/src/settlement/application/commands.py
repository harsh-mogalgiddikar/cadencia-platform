# context.md §3 — Application layer: pure frozen dataclasses.
# No Pydantic, no FastAPI. These are internal application commands, NOT HTTP DTOs.

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class DeployEscrowCommand:
    """
    Deploy a new Algorand escrow contract for a negotiation session.
    Triggered by SessionAgreed domain event (stub in Phase Two).
    """

    session_id: uuid.UUID
    buyer_enterprise_id: uuid.UUID
    seller_enterprise_id: uuid.UUID
    buyer_algo_address: str
    seller_algo_address: str
    agreed_price_microalgo: int


@dataclass(frozen=True)
class FundEscrowCommand:
    """
    Fund an existing escrow from the buyer's Algorand wallet.

    SECURITY: funder_algo_sk is the buyer's Algorand signing key.
    It is NEVER logged or persisted — used once in-memory for signing.
    """

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID
    funder_algo_sk: str  # Buyer's Algorand private key — NEVER log this field


@dataclass(frozen=True)
class ReleaseEscrowCommand:
    """
    Release funds to the seller. Admin-only operation.
    Merkle root is computed internally by SettlementService from the audit trail.
    """

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class RefundEscrowCommand:
    """Refund buyer. Admin-only. Reason required for audit trail."""

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID
    reason: str


@dataclass(frozen=True)
class FreezeEscrowCommand:
    """Freeze escrow to halt all state transitions. Buyer, seller, or admin."""

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID
    frozen_by_role: str  # "BUYER" | "SELLER" | "ADMIN"


@dataclass(frozen=True)
class UnfreezeEscrowCommand:
    """Unfreeze escrow after dispute resolution. Platform admin only."""

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID
