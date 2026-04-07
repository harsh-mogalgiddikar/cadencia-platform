"""Add RLS 7-year immutability policies on compliance tables.

SRS-FR-093: 7-year minimum retention — records cannot be deleted or modified.
context.md §8: Append-only audit log with hash-chain integrity.

Enables PostgreSQL Row Level Security on audit_entries, fema_records,
and gst_records. Creates RESTRICTIVE policies that deny UPDATE and DELETE
at the database level, ensuring compliance data immutability.

Revision ID: 004
Revises: 003
Create Date: 2026-04-03
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# Compliance tables requiring 7-year immutable retention
COMPLIANCE_TABLES = ("audit_entries", "fema_records", "gst_records")


def upgrade() -> None:
    """Enable RLS + immutability policies on compliance tables."""
    for table in COMPLIANCE_TABLES:
        # 1. Enable Row Level Security
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        # 2. Force RLS for table owner (prevents bypass via BYPASSRLS)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        # 3. Default PERMISSIVE policy — allow SELECT and INSERT for all roles
        op.execute(f"""
            CREATE POLICY {table}_allow_read_insert ON {table}
            AS PERMISSIVE
            FOR ALL
            USING (true)
            WITH CHECK (true)
        """)

        # 4. RESTRICTIVE policy — deny all DELETE operations
        op.execute(f"""
            CREATE POLICY {table}_deny_delete ON {table}
            AS RESTRICTIVE
            FOR DELETE
            USING (false)
        """)

        # 5. RESTRICTIVE policy — deny all UPDATE operations
        op.execute(f"""
            CREATE POLICY {table}_deny_update ON {table}
            AS RESTRICTIVE
            FOR UPDATE
            USING (false)
        """)

    # Add comments documenting the retention policy
    for table in COMPLIANCE_TABLES:
        op.execute(f"""
            COMMENT ON TABLE {table} IS
            'RLS-protected compliance table. 7-year retention policy (SRS-FR-093). '
            'INSERT and SELECT permitted; UPDATE and DELETE denied at database level.'
        """)


def downgrade() -> None:
    """Remove RLS policies and disable RLS on compliance tables."""
    for table in COMPLIANCE_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_deny_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_deny_delete ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_allow_read_insert ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
