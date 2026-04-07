"""Phase 2 settlement schema adjustments.

Revision ID: 002
Revises: 001
Create Date: 2026-04-02

Changes:
  1. Drop FK constraint on escrow_contracts.session_id → negotiation_sessions.id
     Reason: Phase 2 deploys escrows via direct API call before negotiation context
     (Phase 4) is implemented. FK is re-evaluated in Phase 4.
  2. Add settled_at column to escrow_contracts — records the moment funds moved.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the FK constraint from escrow_contracts.session_id.
    #    PostgreSQL auto-names FK constraints as <table>_<col>_fkey.
    #    Use IF EXISTS for safety across different PG versions.
    op.execute(
        "ALTER TABLE escrow_contracts "
        "DROP CONSTRAINT IF EXISTS escrow_contracts_session_id_fkey"
    )

    # 2. Add settled_at — nullable; set when status transitions to RELEASED or REFUNDED.
    op.add_column(
        "escrow_contracts",
        sa.Column("settled_at", TIMESTAMPTZ, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("escrow_contracts", "settled_at")
    # Re-add FK — only safe if negotiation_sessions rows exist for all escrow session_ids.
    op.create_foreign_key(
        "escrow_contracts_session_id_fkey",
        "escrow_contracts",
        "negotiation_sessions",
        ["session_id"],
        ["id"],
    )
