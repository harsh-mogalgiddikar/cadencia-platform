"""Initial schema — all 14 Cadencia tables.

Revision ID: 001
Revises:
Create Date: 2026-04-02

All 14 tables:
  identity:     enterprises, users, api_keys
  marketplace:  rfqs, capability_profiles, matches
  negotiation:  negotiation_sessions, offers, agent_profiles, industry_playbooks
  settlement:   escrow_contracts, settlements
  compliance:   audit_log, compliance_records

Vector indexes:
  rfqs.embedding:                 HNSW (m=16, ef_construction=64)    — context.md §11
  capability_profiles.embedding:  IVFFlat (lists=100, cosine)        — context.md §11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# SQLAlchemy doesn't export TIMESTAMPTZ directly — use TIMESTAMP(timezone=True)
TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    # pgvector must be enabled before creating vector columns
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── enterprises ───────────────────────────────────────────────────────────
    op.create_table(
        "enterprises",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pan", sa.String(10), nullable=False),
        sa.Column("gstin", sa.String(15), nullable=False),
        sa.Column("kyc_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("trade_role", sa.String(10), nullable=False),
        sa.Column("algorand_wallet", sa.String(58), nullable=True),
        sa.Column("kyc_documents", JSONB, nullable=True),
        sa.Column("agent_config", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("pan", name="uq_enterprises_pan"),
        sa.UniqueConstraint("gstin", name="uq_enterprises_gstin"),
        sa.CheckConstraint(
            "kyc_status IN ('PENDING','KYC_SUBMITTED','VERIFIED','ACTIVE')",
            name="ck_enterprises_kyc_status",
        ),
        sa.CheckConstraint(
            "trade_role IN ('BUYER','SELLER','BOTH')",
            name="ck_enterprises_trade_role",
        ),
    )
    op.create_index("ix_enterprises_pan", "enterprises", ["pan"])
    op.create_index("ix_enterprises_gstin", "enterprises", ["gstin"])

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "role IN ('ADMIN','BUYER','SELLER','COMPLIANCE_OFFICER','TREASURY_MANAGER','AUDITOR')",
            name="ck_users_role",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_enterprise_id", "users", ["enterprise_id"])

    # ── api_keys ──────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=True),
        sa.Column("last_used_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_enterprise_id", "api_keys", ["enterprise_id"])

    # ── rfqs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "rfqs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("hsn_code", sa.String(8), nullable=True),
        sa.Column("quantity", sa.Float, nullable=True),
        sa.Column("quantity_unit", sa.String(20), nullable=True),
        sa.Column("budget_min", sa.Float, nullable=True),
        sa.Column("budget_max", sa.Float, nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("delivery_window_days", sa.Integer, nullable=True),
        sa.Column("geography", sa.String(100), nullable=True),
        sa.Column("parsed_fields", JSONB, nullable=True),
        # pgvector column: vector(1536)
        sa.Column("embedding", sa.Text, nullable=True),   # placeholder; altered below
        sa.Column("confirmed_match_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('DRAFT','PARSED','MATCHED','CONFIRMED','SETTLED')",
            name="ck_rfqs_status",
        ),
    )
    # Replace placeholder text column with proper vector type
    op.execute("ALTER TABLE rfqs DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE rfqs ADD COLUMN embedding vector(1536)")
    op.create_index("ix_rfqs_enterprise_id_status", "rfqs", ["enterprise_id", "status"])
    # context.md §11: HNSW index for RFQ embeddings (m=16, ef_construction=64)
    op.execute(
        """
        CREATE INDEX ix_rfqs_embedding_hnsw
        ON rfqs
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # ── capability_profiles ───────────────────────────────────────────────────
    op.create_table(
        "capability_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("commodities", sa.ARRAY(sa.String), nullable=True),
        sa.Column("hsn_codes", sa.ARRAY(sa.String), nullable=True),
        sa.Column("min_order_value", sa.Float, nullable=True),
        sa.Column("max_order_value", sa.Float, nullable=True),
        sa.Column("geographies_served", sa.ARRAY(sa.String), nullable=True),
        sa.Column("lead_time_days", sa.Integer, nullable=True),
        sa.Column("certifications", sa.ARRAY(sa.String), nullable=True),
        sa.Column("profile_text", sa.Text, nullable=True),
        sa.Column("embedding", sa.Text, nullable=True),   # placeholder; altered below
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("enterprise_id", name="uq_capability_profiles_enterprise_id"),
    )
    op.execute("ALTER TABLE capability_profiles DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE capability_profiles ADD COLUMN embedding vector(1536)")
    # context.md §11: IVFFlat index (lists=100, cosine) — requires rows to exist first;
    # run `SELECT ivfflat_check('capability_profiles')` after bulk insert to build index.
    # Index created with lists=1 here (safe on empty table); re-index with lists=100 after data load.
    op.execute(
        """
        CREATE INDEX ix_capability_profiles_embedding_ivfflat
        ON capability_profiles
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 1)
        """
    )

    # ── matches ───────────────────────────────────────────────────────────────
    op.create_table(
        "matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfq_id", UUID(as_uuid=True),
                  sa.ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_matches_rfq_id", "matches", ["rfq_id"])
    op.create_index("ix_matches_seller_enterprise_id", "matches", ["seller_enterprise_id"])

    # ── negotiation_sessions ──────────────────────────────────────────────────
    op.create_table(
        "negotiation_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfq_id", UUID(as_uuid=True), nullable=False),
        sa.Column("match_id", UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("seller_enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("current_round", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stall_threshold", sa.Integer, nullable=False, server_default="10"),
        sa.Column("convergence_threshold_pct", sa.Float, nullable=False,
                  server_default="2.0"),
        sa.Column("agreed_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("agreed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('ACTIVE','AGREED','FAILED','EXPIRED','HUMAN_REVIEW')",
            name="ck_negotiation_sessions_status",
        ),
    )
    op.create_index("ix_negotiation_sessions_rfq_id", "negotiation_sessions", ["rfq_id"])
    op.create_index("ix_negotiation_sessions_status", "negotiation_sessions", ["status"])
    op.create_index(
        "ix_negotiation_sessions_buyer_enterprise_id",
        "negotiation_sessions",
        ["buyer_enterprise_id"],
    )

    # ── offers ────────────────────────────────────────────────────────────────
    op.create_table(
        "offers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("negotiation_sessions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("proposer_role", sa.String(10), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("is_human_override", sa.Boolean, nullable=False,
                  server_default="false"),
        sa.Column("raw_llm_output", JSONB, nullable=True),
        sa.Column("archived_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "proposer_role IN ('BUYER','SELLER','HUMAN')",
            name="ck_offers_proposer_role",
        ),
    )
    op.create_index(
        "ix_offers_session_id_round_number", "offers", ["session_id", "round_number"]
    )

    # ── agent_profiles ────────────────────────────────────────────────────────
    op.create_table(
        "agent_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("automation_level", sa.String(20), nullable=False,
                  server_default="SUPERVISED"),
        sa.Column("risk_profile", JSONB, nullable=True),
        sa.Column("strategy_weights", JSONB, nullable=True),
        sa.Column("budget_ceiling", sa.Float, nullable=True),
        sa.Column("max_rounds", sa.Integer, nullable=False, server_default="10"),
        sa.Column("history_embedding", sa.Text, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("enterprise_id", name="uq_agent_profiles_enterprise_id"),
        sa.CheckConstraint(
            "automation_level IN ('FULLY_AUTONOMOUS','SUPERVISED','MANUAL')",
            name="ck_agent_profiles_automation_level",
        ),
    )
    op.execute("ALTER TABLE agent_profiles DROP COLUMN IF EXISTS history_embedding")
    op.execute("ALTER TABLE agent_profiles ADD COLUMN history_embedding vector(1536)")

    # ── industry_playbooks ────────────────────────────────────────────────────
    op.create_table(
        "industry_playbooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("hsn_prefix", sa.String(8), nullable=False),
        sa.Column("industry_name", sa.String(100), nullable=False),
        sa.Column("playbook_text", sa.Text, nullable=False),
        sa.Column("strategy_hints", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_industry_playbooks_hsn_prefix", "industry_playbooks", ["hsn_prefix"])

    # ── escrow_contracts ──────────────────────────────────────────────────────
    op.create_table(
        "escrow_contracts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("negotiation_sessions.id"),
                  nullable=False, unique=True),
        sa.Column("algo_app_id", sa.BigInteger, nullable=True, unique=True),
        sa.Column("amount_microalgo", sa.BigInteger, nullable=False),
        sa.Column("buyer_algorand_address", sa.String(58), nullable=False),
        sa.Column("seller_algorand_address", sa.String(58), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DEPLOYED"),
        sa.Column("is_frozen", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deploy_tx_id", sa.String(52), nullable=True),
        sa.Column("fund_tx_id", sa.String(52), nullable=True),
        sa.Column("release_tx_id", sa.String(52), nullable=True),
        sa.Column("refund_tx_id", sa.String(52), nullable=True),
        sa.Column("merkle_root", sa.String(64), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", name="uq_escrow_contracts_session_id"),
        sa.UniqueConstraint("algo_app_id", name="uq_escrow_contracts_algo_app_id"),
        sa.CheckConstraint(
            "status IN ('DEPLOYED','FUNDED','RELEASED','REFUNDED')",
            name="ck_escrow_contracts_status",
        ),
    )
    op.create_index("ix_escrow_contracts_session_id", "escrow_contracts", ["session_id"])
    op.create_index("ix_escrow_contracts_algo_app_id", "escrow_contracts", ["algo_app_id"])

    # ── settlements ───────────────────────────────────────────────────────────
    op.create_table(
        "settlements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("escrow_id", UUID(as_uuid=True),
                  sa.ForeignKey("escrow_contracts.id"), nullable=False),
        sa.Column("milestone_index", sa.Integer, nullable=False),
        sa.Column("amount_microalgo", sa.BigInteger, nullable=False),
        sa.Column("tx_id", sa.String(52), nullable=True),
        sa.Column("oracle_confirmation", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_settlements_escrow_id", "settlements", ["escrow_id"])

    # ── audit_log ─────────────────────────────────────────────────────────────
    # context.md §11: 7-year minimum retention; append-only; hash-chained.
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", JSONB, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
    )
    # context.md §11: audit_log_enterprise_idx
    op.create_index(
        "ix_audit_log_enterprise_id_created_at", "audit_log",
        ["enterprise_id", "created_at"]
    )
    op.create_index("ix_audit_log_session_id", "audit_log", ["session_id"])

    # ── compliance_records ────────────────────────────────────────────────────
    # context.md §11: 7-year minimum retention.
    op.create_table(
        "compliance_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("negotiation_sessions.id"), nullable=False),
        sa.Column("record_type", sa.String(10), nullable=False),
        sa.Column("record_data", JSONB, nullable=False),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("generated_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "record_type IN ('FEMA','GST')",
            name="ck_compliance_records_record_type",
        ),
    )
    op.create_index(
        "ix_compliance_records_enterprise_id_record_type",
        "compliance_records",
        ["enterprise_id", "record_type"],
    )
    op.create_index(
        "ix_compliance_records_session_id", "compliance_records", ["session_id"]
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("compliance_records")
    op.drop_table("audit_log")
    op.drop_table("settlements")
    op.drop_table("escrow_contracts")
    op.drop_table("industry_playbooks")
    op.drop_table("agent_profiles")
    op.drop_table("offers")
    op.drop_table("negotiation_sessions")
    op.drop_table("matches")
    op.drop_table("capability_profiles")
    op.drop_table("rfqs")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("enterprises")
