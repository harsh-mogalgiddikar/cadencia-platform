# context.md §6: KYC Provider integration type — HTTP REST, mocked in Phase One.
# context.md §4 OCP: New KYC provider = new adapter. Zero modification to IdentityService.

from __future__ import annotations

import os
import uuid

from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)


class MockKYCAdapter:
    """
    Mock KYC adapter for Phase One development and testing.

    context.md §4 OCP: satisfies IKYCAdapter Protocol.
    Production adapter wired in via same interface.

    Behaviour:
      submit() — always returns submitted status with reference ID.
      verify() — returns True in development/test; False in production.
                 Returns False if KYC_MOCK_FAIL=true env var set (failure path testing).
    """

    async def submit(
        self,
        enterprise_id: uuid.UUID,
        documents: dict,
    ) -> dict:
        """Simulate KYC document submission."""
        log.info(
            "kyc_mock_submit",
            enterprise_id=str(enterprise_id),
            document_keys=list(documents.keys()),
        )
        return {
            "status": "submitted",
            "reference_id": str(uuid.uuid4()),
            "provider": "mock",
        }

    async def verify(self, enterprise_id: uuid.UUID) -> bool:
        """
        Simulate KYC verification result.

        context.md §14: NEVER auto-verifies in production.
        Returns False if APP_ENV=production or KYC_MOCK_FAIL=true.
        """
        app_env = os.environ.get("APP_ENV", "development")
        if app_env == "production":
            log.warning(
                "kyc_mock_called_in_production",
                enterprise_id=str(enterprise_id),
            )
            return False

        if os.environ.get("KYC_MOCK_FAIL", "false").lower() == "true":
            log.info("kyc_mock_fail_triggered", enterprise_id=str(enterprise_id))
            return False

        log.info("kyc_mock_verified", enterprise_id=str(enterprise_id))
        return True
