"""
Pagination models for API responses.

context.md §10: Pagination: cursor-based (CursorPage[T] with next_cursor, has_more).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    """
    Cursor-based pagination result.

    Used for large, append-dominant collections (audit log, offers, matches).
    `next_cursor` is an opaque base64-encoded string encoding the last item's
    sort key. Pass it back as `?cursor=` to retrieve the next page.
    """

    items: list[T]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page. None if this is the last page.",
    )
    has_more: bool = Field(
        description="True if there are more items beyond this page.",
    )
    total_count: int | None = Field(
        default=None,
        description="Total item count, if computable without extra query.",
    )


class OffsetPage(BaseModel, Generic[T]):
    """
    Offset-based pagination result.

    Used for small, sortable collections where random access is needed
    (e.g. enterprise listings, compliance records).
    """

    items: list[T]
    total: int = Field(description="Total number of items matching the query.")
    page: int = Field(description="Current page number (1-indexed).")
    page_size: int = Field(description="Number of items per page.")

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1
