"""
Unit tests for shared/domain/exceptions.py and shared/api/error_handler.py.

Tests:
    test_not_found_error_is_domain_error
    test_policy_violation_carries_message
    test_error_handler_maps_not_found_to_404
    test_error_handler_maps_policy_violation_to_422
    test_error_response_envelope_structure
"""

from __future__ import annotations

import uuid

import pytest

from src.shared.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BlockchainSimulationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PolicyViolation,
    RateLimitError,
    ValidationError,
)


# ── Exception hierarchy ───────────────────────────────────────────────────────

def test_not_found_error_is_domain_error() -> None:
    exc = NotFoundError("Enterprise", "123")
    assert isinstance(exc, DomainError)
    assert isinstance(exc, Exception)
    assert exc.error_code == "NOT_FOUND"
    assert "Enterprise" in exc.message
    assert "123" in exc.message


def test_policy_violation_carries_message() -> None:
    msg = "Offer exceeds budget ceiling"
    exc = PolicyViolation(msg)
    assert exc.message == msg
    assert exc.error_code == "POLICY_VIOLATION"
    assert str(exc) == msg


def test_validation_error_carries_field() -> None:
    exc = ValidationError("Invalid PAN format", field="pan")
    assert exc.error_code == "VALIDATION_ERROR"
    assert exc.field == "pan"
    assert "PAN" in exc.message


def test_validation_error_without_field() -> None:
    exc = ValidationError("Bad input")
    assert exc.field is None


def test_conflict_error_is_domain_error() -> None:
    exc = ConflictError("Enterprise already registered")
    assert isinstance(exc, DomainError)
    assert exc.error_code == "CONFLICT"


def test_rate_limit_error() -> None:
    exc = RateLimitError("Too many requests")
    assert exc.error_code == "RATE_LIMIT_EXCEEDED"


def test_blockchain_simulation_error() -> None:
    exc = BlockchainSimulationError("dryrun failed: logic eval error")
    assert exc.error_code == "BLOCKCHAIN_DRY_RUN_FAILED"
    assert isinstance(exc, DomainError)


def test_authentication_error() -> None:
    exc = AuthenticationError("Token expired")
    assert exc.error_code == "UNAUTHORIZED"


def test_authorization_error() -> None:
    exc = AuthorizationError("Insufficient role")
    assert exc.error_code == "FORBIDDEN"


def test_domain_error_custom_code() -> None:
    exc = DomainError("Custom error", error_code="CUSTOM_CODE")
    assert exc.error_code == "CUSTOM_CODE"


def test_exception_hierarchy_all_are_domain_error() -> None:
    """All domain exceptions must be catchable as DomainError."""
    exceptions = [
        NotFoundError("X", "1"),
        PolicyViolation("p"),
        ValidationError("v"),
        ConflictError("c"),
        RateLimitError("r"),
        BlockchainSimulationError("b"),
        AuthenticationError("a"),
        AuthorizationError("az"),
    ]
    for exc in exceptions:
        assert isinstance(exc, DomainError), f"{type(exc).__name__} not a DomainError"


# ── Error handler status code mapping ─────────────────────────────────────────

def test_error_handler_maps_not_found_to_404() -> None:
    """_resolve_status must return 404 for NotFoundError."""
    from src.shared.api.error_handler import _resolve_status

    exc = NotFoundError("Enterprise", "abc")
    assert _resolve_status(exc) == 404


def test_error_handler_maps_policy_violation_to_422() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = PolicyViolation("Budget ceiling exceeded")
    assert _resolve_status(exc) == 422


def test_error_handler_maps_validation_error_to_400() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = ValidationError("Bad input")
    assert _resolve_status(exc) == 400


def test_error_handler_maps_conflict_to_409() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = ConflictError("Already exists")
    assert _resolve_status(exc) == 409


def test_error_handler_maps_rate_limit_to_429() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = RateLimitError("Slow down")
    assert _resolve_status(exc) == 429


def test_error_handler_maps_blockchain_error_to_502() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = BlockchainSimulationError("Dry-run failed")
    assert _resolve_status(exc) == 502


def test_error_handler_maps_auth_to_401() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = AuthenticationError("Bad token")
    assert _resolve_status(exc) == 401


def test_error_handler_maps_authz_to_403() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = AuthorizationError("No permission")
    assert _resolve_status(exc) == 403


def test_error_handler_maps_base_domain_error_to_500() -> None:
    from src.shared.api.error_handler import _resolve_status

    exc = DomainError("Unknown internal error")
    assert _resolve_status(exc) == 500


# ── Error response envelope ───────────────────────────────────────────────────

def test_error_response_envelope_structure() -> None:
    from src.shared.api.responses import error_response

    request_id = uuid.uuid4()
    response = error_response(
        code="NOT_FOUND",
        message="Resource not found",
        request_id=request_id,
        field="enterprise_id",
    )

    assert response.success is False
    assert response.data is None
    assert response.error is not None
    assert response.error.code == "NOT_FOUND"
    assert response.error.message == "Resource not found"
    assert response.error.field == "enterprise_id"
    assert response.meta.request_id == str(request_id)
