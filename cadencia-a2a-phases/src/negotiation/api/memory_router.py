# Agent Memory API — Document upload, ingestion, and retrieval endpoints.
# context.md §4: API prefix /v1/*, API-first modular monolith.

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from src.identity.api.dependencies import get_current_user
from src.shared.api.responses import success_response

router = APIRouter(prefix="/v1/agent-memory", tags=["agent-memory"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    tenant_id: uuid.UUID
    role: str = Field(default="buyer", pattern="^(buyer|seller)$")


class IngestResponse(BaseModel):
    tenant_id: str
    role: str
    docs_processed: int
    chunks_stored: int
    errors: list[str]


class RetrieveRequest(BaseModel):
    tenant_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class MemoryChunkResponse(BaseModel):
    id: str
    content: str
    metadata: dict
    similarity: float


class MemoryStatsResponse(BaseModel):
    tenant_id: str
    total_chunks: int
    total_docs: int


# ── Dependency injection ──────────────────────────────────────────────────────


async def get_personalization_service():
    """Construct PersonalizationService with S3Vault and DB session."""
    import os
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import Depends
    from src.shared.infrastructure.db.session import get_db_session
    from src.negotiation.application.personalization_service import PersonalizationService
    from src.negotiation.infrastructure.s3_vault import S3Vault

    s3 = S3Vault(
        bucket_prefix=os.environ.get("S3_AGENT_BUCKET_PREFIX", "cadencia-agents"),
        region=os.environ.get("AWS_REGION", "ap-south-1"),
    )
    return PersonalizationService(s3_vault=s3)


async def get_s3_vault():
    """Construct S3Vault from environment configuration."""
    import os
    from src.negotiation.infrastructure.s3_vault import S3Vault

    return S3Vault(
        bucket_prefix=os.environ.get("S3_AGENT_BUCKET_PREFIX", "cadencia-agents"),
        region=os.environ.get("AWS_REGION", "ap-south-1"),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/upload", status_code=201)
async def upload_document(
    tenant_id: Annotated[str, Form()],
    role: Annotated[str, Form()] = "buyer",
    file: UploadFile = File(...),
    _user: object = Depends(get_current_user),
    s3_vault: object = Depends(get_s3_vault),
) -> dict:
    """
    POST /v1/agent-memory/upload — Upload document to tenant S3 vault.

    Accepts multipart file upload. Stores in tenant-isolated S3 bucket.
    Call /ingest after uploading to process into agent memory.
    """
    tid = uuid.UUID(tenant_id)
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    filename = file.filename or f"upload_{uuid.uuid4().hex[:8]}"

    key = await s3_vault.store_document(  # type: ignore[union-attr]
        tenant_id=tid,
        filename=filename,
        content=content,
        mime_type=mime_type,
    )

    return success_response(
        data={
            "key": key,
            "filename": filename,
            "size_bytes": len(content),
            "mime_type": mime_type,
            "tenant_id": str(tid),
        },
        status_code=201,
    )


@router.post("/ingest")
async def ingest_documents(
    body: IngestRequest,
    _user: object = Depends(get_current_user),
    svc: object = Depends(get_personalization_service),
) -> dict:
    """
    POST /v1/agent-memory/ingest — Full pipeline: S3 → chunk → embed → pgvector.

    Processes all documents in tenant's S3 vault into searchable agent memory.
    """
    from src.negotiation.application.commands import IngestMemoryCommand

    cmd = IngestMemoryCommand(
        tenant_id=body.tenant_id,
        role=body.role,
    )
    result = await svc.ingest_enterprise_memory(cmd)  # type: ignore[union-attr]
    return success_response(data=result)


@router.post("/retrieve")
async def retrieve_similar(
    body: RetrieveRequest,
    _user: object = Depends(get_current_user),
    svc: object = Depends(get_personalization_service),
) -> dict:
    """
    POST /v1/agent-memory/retrieve — Cosine similarity Top-N retrieval.

    Returns most relevant document chunks for a given query.
    Used by Layer 3 LLM advisory for RAG-augmented negotiation.
    """
    from src.negotiation.application.commands import RetrieveMemoryCommand

    cmd = RetrieveMemoryCommand(
        tenant_id=body.tenant_id,
        query=body.query,
        limit=body.limit,
    )
    results = await svc.retrieve_similar(cmd)  # type: ignore[union-attr]
    return success_response(data=results)


@router.get("/{tenant_id}/stats")
async def get_memory_stats(
    tenant_id: uuid.UUID,
    _user: object = Depends(get_current_user),
    svc: object = Depends(get_personalization_service),
) -> dict:
    """
    GET /v1/agent-memory/{tenant_id}/stats — Memory statistics.

    Returns count of stored chunks and documents for a tenant.
    """
    stats = await svc.get_memory_stats(tenant_id)  # type: ignore[union-attr]
    return success_response(data=stats)


@router.delete("/{tenant_id}")
async def clear_memory(
    tenant_id: uuid.UUID,
    _user: object = Depends(get_current_user),
    svc: object = Depends(get_personalization_service),
) -> dict:
    """
    DELETE /v1/agent-memory/{tenant_id} — Clear all memory for re-ingestion.
    """
    deleted = await svc.clear_memory(tenant_id)  # type: ignore[union-attr]
    return success_response(data={"deleted": deleted, "tenant_id": str(tenant_id)})
