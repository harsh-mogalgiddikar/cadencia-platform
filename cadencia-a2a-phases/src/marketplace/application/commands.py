# context.md §3 — Commands are pure Python dataclasses.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class UploadRFQCommand:
    raw_text: str
    buyer_enterprise_id: uuid.UUID
    document_type: str = "free_text"


@dataclass(frozen=True)
class ConfirmRFQCommand:
    """Phase 3 fix: accepts seller_enterprise_id instead of match_id.
    The router resolves the match internally."""
    rfq_id: uuid.UUID
    seller_enterprise_id: uuid.UUID
    buyer_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class UpdateCapabilityProfileCommand:
    enterprise_id: uuid.UUID
    industry_vertical: str | None = None
    product_categories: list[str] = field(default_factory=list)
    geography_scope: list[str] = field(default_factory=list)
    trade_volume_min: Decimal | None = None
    trade_volume_max: Decimal | None = None
    profile_text: str | None = None
