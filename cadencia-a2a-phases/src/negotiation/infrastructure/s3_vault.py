# S3 Tenant Vault — Multi-tenant document storage for enterprise onboarding.
# context.md §14: Data residency ap-south-1. AES256 server-side encryption.
# Bucket pattern: cadencia-agents-{tenant_prefix}
# Key layout: raw/{tenant_id}/{filename}
#
# Implements IS3Vault protocol (ports.py).
# Uses boto3 — infrastructure layer only, never imported by domain.

from __future__ import annotations

import os
import uuid

import structlog

log = structlog.get_logger(__name__)

_DEFAULT_ENDPOINT = os.getenv("AWS_S3_ENDPOINT", "")
_DEFAULT_REGION = os.getenv("DATA_RESIDENCY_REGION", "ap-south-1")
_BUCKET_TEMPLATE = "cadencia-agents-{tenant_prefix}"


class S3Vault:
    """
    Tenant-isolated S3 storage for enterprise documents.

    Each tenant gets a logically isolated prefix within a shared bucket
    (or a dedicated bucket if configured). All objects encrypted AES256.

    Supports MinIO for local development via AWS_S3_ENDPOINT env var.
    """

    def __init__(
        self,
        s3_client: object | None = None,
        bucket_template: str = _BUCKET_TEMPLATE,
        region: str = _DEFAULT_REGION,
    ) -> None:
        if s3_client is not None:
            self._s3 = s3_client
        else:
            self._s3 = self._create_client(region)
        self._bucket_template = bucket_template
        self._region = region

    @staticmethod
    def _create_client(region: str) -> object:
        """Create boto3 S3 client with optional MinIO endpoint."""
        import boto3  # Infrastructure-only import

        kwargs: dict = {
            "service_name": "s3",
            "region_name": region,
        }
        endpoint = _DEFAULT_ENDPOINT
        if endpoint:
            kwargs["endpoint_url"] = (
                endpoint if endpoint.startswith("http") else f"http://{endpoint}"
            )
            # MinIO typically needs path-style access
            from botocore.config import Config

            kwargs["config"] = Config(s3={"addressing_style": "path"})
        return boto3.client(**kwargs)

    def _bucket_name(self, tenant_id: uuid.UUID) -> str:
        """Derive bucket name from tenant_id (first 8 hex chars)."""
        return self._bucket_template.format(tenant_prefix=tenant_id.hex[:8])

    def _ensure_bucket(self, bucket: str) -> None:
        """Create bucket if it doesn't exist (idempotent)."""
        try:
            self._s3.head_bucket(Bucket=bucket)  # type: ignore[union-attr]
        except Exception:
            try:
                self._s3.create_bucket(  # type: ignore[union-attr]
                    Bucket=bucket,
                    CreateBucketConfiguration={
                        "LocationConstraint": self._region,
                    },
                )
                log.info("s3_bucket_created", bucket=bucket, region=self._region)
            except Exception as e:
                # Bucket may have been created by another process
                if "BucketAlreadyOwnedByYou" not in str(e):
                    log.warning("s3_bucket_create_failed", bucket=bucket, error=str(e))

    # ── IS3Vault Protocol Methods ─────────────────────────────────────────────

    async def store_document(
        self,
        tenant_id: uuid.UUID,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
    ) -> str:
        """
        Store a raw document in the tenant's S3 bucket.

        Returns the S3 key where the document was stored.
        All objects encrypted with AES256 server-side encryption.
        """
        bucket = self._bucket_name(tenant_id)
        self._ensure_bucket(bucket)

        key = f"raw/{tenant_id.hex}/{filename}"

        self._s3.put_object(  # type: ignore[union-attr]
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=mime_type,
            ServerSideEncryption="AES256",
            Metadata={
                "tenant_id": str(tenant_id),
                "original_filename": filename,
            },
        )

        log.info(
            "s3_document_stored",
            tenant_id=str(tenant_id),
            key=key,
            size_bytes=len(content),
            mime_type=mime_type,
        )
        return key

    async def get_document(
        self, tenant_id: uuid.UUID, key: str
    ) -> bytes:
        """Download a document from the tenant's S3 bucket."""
        bucket = self._bucket_name(tenant_id)

        response = self._s3.get_object(Bucket=bucket, Key=key)  # type: ignore[union-attr]
        content = response["Body"].read()

        log.info(
            "s3_document_retrieved",
            tenant_id=str(tenant_id),
            key=key,
            size_bytes=len(content),
        )
        return content

    async def list_documents(
        self, tenant_id: uuid.UUID
    ) -> list[str]:
        """List all raw document keys for a tenant."""
        bucket = self._bucket_name(tenant_id)
        prefix = f"raw/{tenant_id.hex}/"

        try:
            response = self._s3.list_objects_v2(  # type: ignore[union-attr]
                Bucket=bucket, Prefix=prefix
            )
            keys = [obj["Key"] for obj in response.get("Contents", [])]
            log.info(
                "s3_documents_listed",
                tenant_id=str(tenant_id),
                count=len(keys),
            )
            return keys
        except Exception:
            log.warning("s3_list_failed", tenant_id=str(tenant_id))
            return []

    async def delete_document(
        self, tenant_id: uuid.UUID, key: str
    ) -> None:
        """Delete a document from the tenant's S3 bucket."""
        bucket = self._bucket_name(tenant_id)
        self._s3.delete_object(Bucket=bucket, Key=key)  # type: ignore[union-attr]
        log.info("s3_document_deleted", tenant_id=str(tenant_id), key=key)


class StubS3Vault:
    """
    In-memory stub for development and testing.

    Stores documents in a dict keyed by (tenant_id_prefix, key).
    No AWS credentials needed.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def _key(self, tenant_id: uuid.UUID, filename: str) -> str:
        return f"{tenant_id.hex[:8]}/raw/{tenant_id.hex}/{filename}"

    async def store_document(
        self,
        tenant_id: uuid.UUID,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
    ) -> str:
        key = f"raw/{tenant_id.hex}/{filename}"
        storage_key = self._key(tenant_id, filename)
        self._store[storage_key] = content
        return key

    async def get_document(
        self, tenant_id: uuid.UUID, key: str
    ) -> bytes:
        # Extract filename from key
        parts = key.split("/")
        filename = parts[-1] if parts else key
        storage_key = self._key(tenant_id, filename)
        if storage_key not in self._store:
            raise FileNotFoundError(f"Document not found: {key}")
        return self._store[storage_key]

    async def list_documents(
        self, tenant_id: uuid.UUID
    ) -> list[str]:
        prefix = f"{tenant_id.hex[:8]}/raw/{tenant_id.hex}/"
        return [
            k.replace(f"{tenant_id.hex[:8]}/", "", 1)
            for k in self._store
            if k.startswith(prefix)
        ]

    async def delete_document(
        self, tenant_id: uuid.UUID, key: str
    ) -> None:
        parts = key.split("/")
        filename = parts[-1] if parts else key
        storage_key = self._key(tenant_id, filename)
        self._store.pop(storage_key, None)
