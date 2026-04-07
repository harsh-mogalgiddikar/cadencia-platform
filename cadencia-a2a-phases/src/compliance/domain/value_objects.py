# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.
# Pure Python value objects for the compliance bounded context.

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from src.shared.domain.base_value_object import BaseValueObject
from src.shared.domain.exceptions import ValidationError

# ── Constants ─────────────────────────────────────────────────────────────────

GENESIS_HASH: str = "0" * 64  # prev_hash for the first audit entry in a chain

# ── Value Objects ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HashValue(BaseValueObject):
    """
    64-character hex SHA-256 hash.

    Used for audit chain prev_hash and entry_hash fields.
    """

    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.value):
            raise ValidationError(
                f"HashValue must be a 64-char lowercase hex string, got: {self.value!r}",
                field="value",
            )


@dataclass(frozen=True)
class SequenceNumber(BaseValueObject):
    """
    Non-negative monotonically increasing audit entry sequence number per escrow.
    """

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValidationError(
                f"SequenceNumber must be >= 0, got {self.value}.",
                field="value",
            )


@dataclass(frozen=True)
class PANNumber(BaseValueObject):
    """
    Indian Permanent Account Number — exactly 10 alphanumeric uppercase chars.
    Format: AAAAA9999A (5 letters, 4 digits, 1 letter).
    """

    value: str

    _PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

    def __post_init__(self) -> None:
        cleaned = self.value.strip().upper()
        object.__setattr__(self, "value", cleaned)
        if not self._PATTERN.match(cleaned):
            raise ValidationError(
                f"Invalid PAN format: {self.value!r}. Expected AAAAA9999A.",
                field="value",
            )


@dataclass(frozen=True)
class GSTIN(BaseValueObject):
    """
    Indian GST Identification Number — 15-char alphanumeric.
    Format: 2-digit state + 10-char PAN + 1 entity + 1 Z + 1 check.
    Example: 27AABCP1234C1Z5
    """

    value: str

    _PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][0-9A-Z]$")

    def __post_init__(self) -> None:
        cleaned = self.value.strip().upper()
        object.__setattr__(self, "value", cleaned)
        if not self._PATTERN.match(cleaned):
            raise ValidationError(
                f"Invalid GSTIN format: {self.value!r}. Expected 15-char GSTIN.",
                field="value",
            )

    @property
    def state_code(self) -> str:
        """First two digits of GSTIN = GST state code."""
        return self.value[:2]


@dataclass(frozen=True)
class HSNCode(BaseValueObject):
    """
    Harmonised System Nomenclature code — 4 to 8 digits.
    Used in GST records for product classification.
    """

    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip()
        object.__setattr__(self, "value", cleaned)
        if not re.fullmatch(r"\d{4,8}", cleaned):
            raise ValidationError(
                f"HSN code must be 4-8 digits, got: {self.value!r}.",
                field="value",
            )


@dataclass(frozen=True)
class INRAmount(BaseValueObject):
    """
    Indian Rupee amount as a Decimal (supports paise-level precision).
    Must be non-negative.
    """

    value: Decimal

    def __post_init__(self) -> None:
        if self.value < Decimal("0"):
            raise ValidationError(
                f"INRAmount must be >= 0, got {self.value}.",
                field="value",
            )


@dataclass(frozen=True)
class PurposeCode(BaseValueObject):
    """
    RBI LRS (Liberalised Remittance Scheme) purpose code.
    Format: P + 4 digits (e.g., P0108 = MSME goods import).
    """

    value: str

    DEFAULT = "P0108"  # RBI LRS purpose code for MSME goods import

    def __post_init__(self) -> None:
        cleaned = self.value.strip().upper()
        object.__setattr__(self, "value", cleaned)
        if not re.fullmatch(r"P\d{4}", cleaned):
            raise ValidationError(
                f"PurposeCode must be P + 4 digits, got: {self.value!r}.",
                field="value",
            )
