"""
SQLAlchemy ORM models for the marketplace bounded context.

Tables: rfqs, capability_profiles, matches
context.md §11 — Database Schema.

Vector indexes:
    rfqs.embedding:                 HNSW (m=16, ef_construction=64)
    capability_profiles.embedding:  IVFFlat (lists=100, cosine distance)
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]

from src.shared.infrastructure.db.base import Base


class RFQModel(Base):
    """
    RFQ (Request for Quotation) aggregate root (marketplace bounded context).

    status: DRAFT | PARSED | MATCHED | CONFIRMED | SETTLED
    embedding: 1536-dimensional float32 vector for semantic matching.
    HNSW index: context.md §11 (m=16, ef_construction=64).
    """

    __tablename__ = "rfqs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PARSED','MATCHED','CONFIRMED','SETTLED')",
            name="ck_rfqs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="DRAFT"
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # LLM-extracted structured fields (context.md §8)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hsn_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    budget_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    delivery_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geography: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parsed_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # pgvector 1536-dim embedding (context.md §11)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    confirmed_match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    matches: Mapped[list[MatchModel]] = relationship("MatchModel", back_populates="rfq")


_rfqs_enterprise_status_idx = Index(
    "ix_rfqs_enterprise_id_status", RFQModel.enterprise_id, RFQModel.status
)
# HNSW vector index created via raw SQL in Alembic migration (context.md §11)


class CapabilityProfileModel(Base):
    """
    Seller capability profile (marketplace bounded context).

    embedding: 1536-dim float32 vector for IVFFlat cosine matching.
    context.md §11: IVFFlat index (lists=100, cosine distance).
    Target: Top-5 query < 2s at 10,000 rows.
    """

    __tablename__ = "capability_profiles"
    __table_args__ = (
        UniqueConstraint("enterprise_id", name="uq_capability_profiles_enterprise_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    commodities: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    hsn_codes: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    min_order_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_order_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    industry_vertical: Mapped[str | None] = mapped_column(String(200), nullable=True)
    geographies_served: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    certifications: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    profile_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pgvector 1536-dim embedding (context.md §11)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


# IVFFlat vector index created via raw SQL in Alembic migration (context.md §11)


class MatchModel(Base):
    """
    Match entity linking an RFQ to a ranked seller (marketplace bounded context).

    score: cosine similarity score from pgvector search.
    rank:  position in ranked results (1 = best match).
    """

    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfqs.id", ondelete="CASCADE"),
        nullable=False,
    )
    seller_enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    rfq: Mapped[RFQModel] = relationship("RFQModel", back_populates="matches")


_matches_rfq_idx = Index("ix_matches_rfq_id", MatchModel.rfq_id)
_matches_seller_idx = Index("ix_matches_seller_enterprise_id", MatchModel.seller_enterprise_id)
