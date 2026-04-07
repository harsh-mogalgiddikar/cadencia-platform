"""Phase 3 compliance schema.

Revision ID: 003
Revises: 002
Create Date: 2026-04-02

Changes:
  1. Create audit_entries — append-only SHA-256 hash-chained audit log.
  2. Create fema_records — FEMA Form 15CA/15CB compliance records.
  3. Create gst_records — GST IGST/CGST+SGST compliance records.
  4. Create export_jobs — bulk ZIP export job tracking.

Note: The Phase 0 migration (001) created `audit_log` and `compliance_records`
tables as placeholder schema. Phase 3 replaces them with proper normalized tables.
The old tables are dropped in this migration (no live data yet — Phase 6 tests only).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop Phase 0 placeholder compliance tables ────────────────────────────
    op.execute("DROP TABLE IF EXISTS compliance_records CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")

    # ── 1. audit_entries ──────────────────────────────────────────────────────
    op.create_table(
        "audit_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("escrow_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_no", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("escrow_id", "sequence_no", name="uq_audit_entries_escrow_seq"),
        sa.UniqueConstraint("entry_hash", name="uq_audit_entries_entry_hash"),
    )
    op.create_index(
        "ix_audit_entries_escrow_created",
        "audit_entries",
        ["escrow_id", "created_at"],
    )

    # ── 2. fema_records ───────────────────────────────────────────────────────
    op.create_table(
        "fema_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("escrow_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("form_type", sa.String(4), nullable=False),
        sa.Column("purpose_code", sa.String(6), nullable=False),
        sa.Column("buyer_pan", sa.String(10), nullable=False),
        sa.Column("seller_pan", sa.String(10), nullable=False),
        sa.Column("amount_inr", sa.Numeric(20, 2), nullable=False),
        sa.Column("amount_algo", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_inr_per_algo", sa.Numeric(20, 6), nullable=False),
        sa.Column("merkle_root", sa.String(64), nullable=False),
        sa.Column("generated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_fema_records_escrow_id", "fema_records", ["escrow_id"])

    # ── 3. gst_records ────────────────────────────────────────────────────────
    op.create_table(
        "gst_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("escrow_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("hsn_code", sa.String(8), nullable=False),
        sa.Column("buyer_gstin", sa.String(15), nullable=False),
        sa.Column("seller_gstin", sa.String(15), nullable=False),
        sa.Column("tax_type", sa.String(10), nullable=False),
        sa.Column("taxable_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("igst_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("cgst_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("sgst_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("generated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("tax_type IN ('IGST','CGST_SGST')", name="ck_gst_records_tax_type"),
    )
    op.create_index("ix_gst_records_escrow_id", "gst_records", ["escrow_id"])

    # ── 4. export_jobs ────────────────────────────────────────────────────────
    op.create_table(
        "export_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("escrow_ids", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("redis_key", sa.String(200), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','DONE','FAILED')",
            name="ck_export_jobs_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("export_jobs")
    op.drop_table("gst_records")
    op.drop_table("fema_records")
    op.drop_index("ix_audit_entries_escrow_created", "audit_entries")
    op.drop_table("audit_entries")

    # Restore Phase 0 placeholder tables
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", JSONB, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_table(
        "compliance_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(10), nullable=False),
        sa.Column("record_data", JSONB, nullable=False),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("generated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
