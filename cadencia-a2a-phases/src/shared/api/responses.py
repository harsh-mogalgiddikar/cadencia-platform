"""
Unified API response envelope.

Frontend contract (non-negotiable):
  Success: { "status": "success", "data": <payload> }
  Error:   { "status": "error",   "detail": "..." }

The frontend Axios client destructures every response as `response.data.data`.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    Unified response envelope for all Cadencia API endpoints.

    The frontend destructures `response.data.data` — this envelope must be:
        { "status": "success", "data": <T> }
    """

    status: str = "success"
    data: T | None = None

    model_config = {"arbitrary_types_allowed": True}


class ApiErrorResponse(BaseModel):
    """
    Error response envelope.

    The frontend expects:
        { "status": "error", "detail": "Human-readable message" }
    """

    status: str = "error"
    detail: str


def success_response(data: T) -> ApiResponse[T]:
    """Factory for successful responses."""
    return ApiResponse(status="success", data=data)


def error_dict(detail: str) -> dict[str, Any]:
    """Return the canonical error envelope as a plain dict (for JSONResponse)."""
    return {"status": "error", "detail": detail}
