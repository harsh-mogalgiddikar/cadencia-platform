"""add_llm_call_logs_and_broadcasts

Revision ID: ea191f1c2d48
Revises: 005
Create Date: 2026-04-06 17:08:12.263161+00:00

New tables for Admin module:
  - llm_call_logs: persistent audit trail of LLM API calls
  - broadcasts:   platform-wide notification records
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'ea191f1c2d48'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)


def upgrade() -> None:
    # ── llm_call_logs ─────────────────────────────────────────────────────────
    op.create_table(
        'llm_call_logs',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'),
                  primary_key=True),
        sa.Column('session_id', UUID(as_uuid=True),
                  sa.ForeignKey('negotiation_sessions.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('agent_role', sa.String(length=10), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completion_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('latency_ms', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=10), server_default='SUCCESS', nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('created_at', TIMESTAMPTZ, server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("agent_role IN ('BUYER','SELLER')",
                           name='ck_llm_call_logs_agent_role'),
        sa.CheckConstraint("status IN ('SUCCESS','TIMEOUT','ERROR')",
                           name='ck_llm_call_logs_status'),
    )
    op.create_index('ix_llm_call_logs_session_id', 'llm_call_logs', ['session_id'])
    op.create_index('ix_llm_call_logs_created_at', 'llm_call_logs', ['created_at'])

    # ── broadcasts ────────────────────────────────────────────────────────────
    op.create_table(
        'broadcasts',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'),
                  primary_key=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('target', sa.String(length=25), nullable=False),
        sa.Column('priority', sa.String(length=10), server_default='normal', nullable=False),
        sa.Column('sender_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('recipient_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', TIMESTAMPTZ, server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("target IN ('all','active_enterprises','admins_only')",
                           name='ck_broadcasts_target'),
        sa.CheckConstraint("priority IN ('low','normal','high','critical')",
                           name='ck_broadcasts_priority'),
    )
    op.create_index('ix_broadcasts_created_at', 'broadcasts', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_broadcasts_created_at', table_name='broadcasts')
    op.drop_table('broadcasts')
    op.drop_index('ix_llm_call_logs_created_at', table_name='llm_call_logs')
    op.drop_index('ix_llm_call_logs_session_id', table_name='llm_call_logs')
    op.drop_table('llm_call_logs')
