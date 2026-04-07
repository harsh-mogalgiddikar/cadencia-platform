# context.md §3 — zero framework imports in domain layer.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from src.shared.domain.base_entity import BaseEntity
from src.shared.domain.exceptions import ValidationError

_EMBEDDING_DIM = 1536


@dataclass
class CapabilityProfile(BaseEntity):
    """Seller capability profile for pgvector matching."""

    enterprise_id: uuid.UUID = field(default_factory=uuid.uuid4)
    industry_vertical: str | None = None
    product_categories: list[str] = field(default_factory=list)
    geography_scope: list[str] = field(default_factory=list)
    trade_volume_min: Decimal | None = None
    trade_volume_max: Decimal | None = None
    embedding: list[float] | None = None
    profile_text: str | None = None

    def update_profile(
        self,
        industry_vertical: str | None,
        product_categories: list[str],
        geography_scope: list[str],
        trade_volume_min: Decimal | None,
        trade_volume_max: Decimal | None,
        profile_text: str | None = None,
    ) -> dict:
        """Update profile fields — nullifies stale embedding."""
        self.industry_vertical = industry_vertical
        self.product_categories = product_categories
        self.geography_scope = geography_scope
        self.trade_volume_min = trade_volume_min
        self.trade_volume_max = trade_volume_max
        self.profile_text = profile_text
        self.embedding = None  # Stale after profile change
        self.touch()
        return {
            "enterprise_id": self.enterprise_id,
            "profile_id": self.id,
        }

    def set_embedding(self, embedding: list[float]) -> None:
        """Set the 1536-dim embedding vector."""
        if len(embedding) != _EMBEDDING_DIM:
            raise ValidationError(
                f"Embedding must be {_EMBEDDING_DIM} dims, got {len(embedding)}.",
                field="embedding",
            )
        self.embedding = embedding
        self.touch()
