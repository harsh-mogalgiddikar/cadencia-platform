# context.md §3: SQLAlchemy ORM models live ONLY in infrastructure/.
# context.md §5: async SQLAlchemy 2.0 with asyncpg driver.
# All models inherit from shared Base (single metadata for Alembic autogenerate).

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.db.base import Base


class AuditEntryModel(Base):
    """
    Append-only hash-chained audit log entry.

    Table: audit_entries
    Unique constraint on (escrow_id, sequence_no) prevents duplicate appends.
    Index on (escrow_id, created_at) for cursor-based pagination.

    NEVER updated or deleted after creation — append-only forever.
    context.md §1: Minimum 7-year retention.
    """

    __tablename__ = "audit_entries"
    __table_args__ = (
        sa.UniqueConstraint("escrow_id", "sequence_no", name="uq_audit_entries_escrow_seq"),
        sa.Index("ix_audit_entries_escrow_created", "escrow_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()
    )
    escrow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sequence_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(sa.Text, nullable=False)
    prev_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class FEMARecordModel(Base):
    """
    FEMA compliance records (Form 15CA/15CB equivalent).

    Table: fema_records
    One record per escrow (unique on escrow_id).
    context.md §1: Minimum 7-year retention.
    """

    __tablename__ = "fema_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()
    )
    escrow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    form_type: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    purpose_code: Mapped[str] = mapped_column(sa.String(6), nullable=False)
    buyer_pan: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    seller_pan: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    amount_inr: Mapped[sa.Numeric] = mapped_column(sa.Numeric(20, 2), nullable=False)
    amount_algo: Mapped[sa.Numeric] = mapped_column(sa.Numeric(20, 6), nullable=False)
    fx_rate_inr_per_algo: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(20, 6), nullable=False
    )
    merkle_root: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    generated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class GSTRecordModel(Base):
    """
    GST compliance records (IGST or CGST+SGST).

    Table: gst_records
    One record per escrow (unique on escrow_id).
    context.md §1: Minimum 7-year retention.
    """

    __tablename__ = "gst_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()
    )
    escrow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    hsn_code: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    buyer_gstin: Mapped[str] = mapped_column(sa.String(15), nullable=False)
    seller_gstin: Mapped[str] = mapped_column(sa.String(15), nullable=False)
    tax_type: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    taxable_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(20, 2), nullable=False)
    igst_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(20, 2), nullable=False)
    cgst_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(20, 2), nullable=False)
    sgst_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(20, 2), nullable=False)
    generated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class ExportJobModel(Base):
    """
    Async bulk ZIP export job tracking.

    Table: export_jobs
    Status: PENDING → DONE | FAILED
    ZIP payload stored in Redis (key = compliance:export:{job_id}), NOT in this table.
    """

    __tablename__ = "export_jobs"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('PENDING','DONE','FAILED')",
            name="ck_export_jobs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()
    )
    escrow_ids: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default=sa.text("'PENDING'")
    )
    redis_key: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    completed_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
