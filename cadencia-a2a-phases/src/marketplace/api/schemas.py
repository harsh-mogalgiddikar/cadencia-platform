# Marketplace API schemas — Pydantic models matching the frontend TypeScript contracts.

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Requests ──────────────────────────────────────────────────────────────────


class UploadRFQRequest(BaseModel):
    raw_text: str = Field(..., min_length=10, max_length=50000)
    document_type: str = Field(default="free_text")


class ConfirmRFQRequest(BaseModel):
    """POST /rfq/:id/confirm — frontend sends seller_enterprise_id, not match_id."""
    seller_enterprise_id: str    # UUID as string — matches what frontend sends


class CapabilityProfileUpdateRequest(BaseModel):
    """PUT /marketplace/capability-profile — matches frontend form fields."""
    industry: str = ""
    products: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    min_order_value: float = 0.0
    max_order_value: float = 0.0
    description: str = ""

    @field_validator("min_order_value", "max_order_value")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Order values must be non-negative")
        return v


# Legacy request — kept for backward compat if needed
class UpdateCapabilityProfileRequest(BaseModel):
    industry_vertical: str | None = None
    product_categories: list[str] = Field(default_factory=list)
    geography_scope: list[str] = Field(default_factory=list)
    trade_volume_min: Decimal | None = None
    trade_volume_max: Decimal | None = None
    profile_text: str | None = None


# ── Responses ─────────────────────────────────────────────────────────────────


class RFQResponse(BaseModel):
    """Matches frontend RFQ TypeScript interface exactly."""
    id: uuid.UUID
    raw_text: str = ""                                    # ADDED
    status: str                                           # DRAFT | PARSED | MATCHED | CONFIRMED
    parsed_fields: Optional[dict] = None                  # Record<string, string> | null
    created_at: str = ""                                  # ADDED — ISO 8601

    @field_validator("created_at", mode="before")
    @classmethod
    def serialize_datetime(cls, v: object) -> str:
        if isinstance(v, datetime):
            return v.isoformat().replace("+00:00", "Z")
        return str(v) if v else ""


class RFQSubmitResponse(BaseModel):
    """POST /marketplace/rfq — 202 response."""
    rfq_id: str                                           # UUID as string
    status: str = "DRAFT"
    message: str = "RFQ submitted for processing."


class MatchResponse(BaseModel):
    """Matches frontend SellerMatch TypeScript interface exactly."""
    enterprise_id: str                                    # RENAMED from seller_enterprise_id
    enterprise_name: str = ""                             # ADDED — from Enterprise join
    score: float                                          # RENAMED from similarity_score (0-100)
    rank: int
    capabilities: list[str] = Field(default_factory=list) # ADDED — from capability profile


class ConfirmRFQResponse(BaseModel):
    """POST /rfq/:id/confirm — response."""
    message: str = "Negotiation session created"
    session_id: str                                       # UUID of NegotiationSession


class CapabilityProfileResponse(BaseModel):
    """Matches frontend CapabilityProfile TypeScript interface exactly."""
    industry: str = ""
    geographies: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    min_order_value: float = 0.0
    max_order_value: float = 0.0
    description: str = ""
    embedding_status: str = "outdated"                    # active | queued | failed | outdated
    last_embedded: Optional[str] = None                   # ISO 8601 or null


class CapabilityProfileUpdateResponse(BaseModel):
    """PUT /marketplace/capability-profile — response."""
    message: str = "Seller profile updated successfully"
    embedding_status: str = "queued"


class EmbeddingRecomputeResponse(BaseModel):
    """POST /marketplace/capability-profile/embeddings — response."""
    message: str = "Embeddings recomputation queued. Profile will be active for matching in ~30 seconds."
