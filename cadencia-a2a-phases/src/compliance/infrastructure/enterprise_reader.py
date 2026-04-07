# context.md §3: Concrete adapter — reads enterprise data directly from DB.
# context.md §7: IEnterpriseReader lets compliance access enterprise data
#   without importing from identity/ (modular monolith — same DB, read-only).
#
# This adapter queries the `enterprises` table directly via SQLAlchemy.
# It implements the IEnterpriseReader protocol from shared/domain/protocols.py.

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.domain.protocols import EnterpriseSnapshot


class PostgresEnterpriseReader:
    """
    Read-only enterprise adapter for compliance.

    Queries the `enterprises` table (owned by identity/) directly.
    This is acceptable in a modular monolith where all bounded contexts
    share the same database. The query is read-only and uses only fields
    needed by compliance (PAN, GSTIN, state code).

    context.md §7: Cross-domain data access via shared read-only protocol,
    NOT via identity domain import.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_snapshot(self, enterprise_id: uuid.UUID) -> EnterpriseSnapshot | None:
        """
        Fetch enterprise compliance data from DB.

        Returns None if enterprise not yet created (graceful degradation:
        compliance records use placeholder PAN/GSTIN and can be updated later).
        """
        result = await self._session.execute(
            sa.text(
                "SELECT id, name, pan, gstin "
                "FROM enterprises "
                "WHERE id = :enterprise_id"
            ),
            {"enterprise_id": enterprise_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None

        pan: str = row.get("pan") or "AAAAA0000A"
        gstin: str = row.get("gstin") or "27AAAAA0000A1Z5"

        # Derive state_code from GSTIN prefix (first 2 digits)
        state_code = gstin[:2] if len(gstin) >= 2 else "00"

        return EnterpriseSnapshot(
            enterprise_id=uuid.UUID(str(row["id"])),
            name=str(row["name"]),
            pan=pan,
            gstin=gstin,
            state_code=state_code,
        )
