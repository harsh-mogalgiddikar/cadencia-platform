"""Add agent_memory table for pgvector RAG storage.

context.md §11: HNSW index for <50ms Top-5 cosine similarity queries.
Converts raw SQL migration (src/negotiation/migrations/006_agent_memory.sql)
to Alembic-managed migration for production deployment consistency.

Stores 512-token document chunks with 1536-dim Gemini embeddings.
Tenant-isolated. Used by Layer 3 LLM advisory in NeutralEngine.

Revision ID: 005
Revises: 004
Create Date: 2026-04-03
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Create agent_memory table with pgvector HNSW index."""

    # Ensure pgvector extension is available (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create table using raw SQL to properly handle VECTOR(1536) type
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            role VARCHAR(10) NOT NULL DEFAULT 'buyer',
            content TEXT NOT NULL,
            embedding VECTOR(1536),
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

            CONSTRAINT ck_agent_memory_role CHECK (role IN ('buyer', 'seller'))
        )
    """)

    # ── Indexes ───────────────────────────────────────────────────────────────

    # Tenant isolation index
    op.create_index("ix_agent_memory_tenant_id", "agent_memory", ["tenant_id"])

    # Composite index for role-scoped retrieval
    op.create_index("ix_agent_memory_tenant_role", "agent_memory", ["tenant_id", "role"])

    # HNSW index for <50ms Top-5 cosine similarity queries
    # m=16, ef_construction=64 balances build speed vs recall
    op.execute("""
        CREATE INDEX IF NOT EXISTS agent_memory_hnsw
        ON agent_memory USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # ── Documentation comments ────────────────────────────────────────────────
    op.execute("""
        COMMENT ON TABLE agent_memory IS
        'pgvector-backed agent memory for RAG retrieval. '
        'Stores 512-token document chunks with 1536-dim Gemini embeddings. '
        'Tenant-isolated. Used by Layer 3 LLM advisory.'
    """)
    op.execute("""
        COMMENT ON COLUMN agent_memory.embedding IS
        '1536-dimensional vector from Gemini text-embedding-004. '
        'Indexed with HNSW for sub-50ms cosine similarity search.'
    """)
    op.execute("""
        COMMENT ON COLUMN agent_memory.metadata IS
        'JSONB: {source: s3_key, chunk_index, total_chunks, original_filename}'
    """)


def downgrade() -> None:
    """Drop agent_memory table and associated indexes."""
    op.execute("DROP INDEX IF EXISTS agent_memory_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_agent_memory_tenant_role")
    op.execute("DROP INDEX IF EXISTS ix_agent_memory_tenant_id")
    op.drop_table("agent_memory")
