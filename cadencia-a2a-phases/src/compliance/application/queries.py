# context.md §3 — Hexagonal Architecture: queries are pure Python dataclasses.

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetAuditLogQuery:
    """
    Cursor-based paginated fetch of audit entries for an escrow.

    cursor: ISO-8601 datetime string (base64-encoded at API boundary).
            Pass None to start from the beginning.
    limit:  Max entries to return (1–100).
    """

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID
    cursor: datetime | None = None
    limit: int = 50


@dataclass(frozen=True)
class VerifyAuditChainQuery:
    """Verify the full hash chain for all entries of an escrow."""

    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class GetFEMARecordQuery:
    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class GetGSTRecordQuery:
    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class ExportFEMAPDFQuery:
    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class ExportGSTCSVQuery:
    escrow_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID


@dataclass(frozen=True)
class GetExportJobQuery:
    job_id: uuid.UUID
    requesting_enterprise_id: uuid.UUID
