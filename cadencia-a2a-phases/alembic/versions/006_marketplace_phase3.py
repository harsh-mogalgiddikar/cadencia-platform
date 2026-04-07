"""Phase 3 Marketplace — add industry_vertical to capability_profiles.

Revision ID: 006
Revises: 005_agent_memory
Create Date: 2026-04-06

This migration adds the `industry_vertical` column to the `capability_profiles`
table, enabling proper round-trip of the frontend's `industry` field.

The `raw_text` and `created_at` columns on `rfqs` already exist in the initial
migration (001) and do not need adding here.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005_agent_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add industry_vertical column to capability_profiles
    op.add_column(
        "capability_profiles",
        sa.Column("industry_vertical", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("capability_profiles", "industry_vertical")
