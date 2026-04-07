# context.md §3 — Hexagonal Architecture: domain layer MUST NOT import
# FastAPI, SQLAlchemy, algosdk, or any infrastructure library.
# Pure Python frozen dataclasses extending BaseValueObject.

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from src.shared.domain.base_value_object import BaseValueObject
from src.shared.domain.exceptions import ValidationError

# ── AlgoAppId ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AlgoAppId(BaseValueObject):
    """Algorand application ID (positive uint64)."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(
                f"AlgoAppId must be a positive integer; got {self.value}.",
                field="algo_app_id",
            )


# ── AlgoAppAddress ────────────────────────────────────────────────────────────

_ALGO_ADDR_RE = re.compile(r"^[A-Z2-7]{58}$")


@dataclass(frozen=True)
class AlgoAppAddress(BaseValueObject):
    """
    Algorand account/contract address — 58-char uppercase base32 string.
    Validation is format-only (length + charset).
    """

    value: str

    def __post_init__(self) -> None:
        if not _ALGO_ADDR_RE.match(self.value):
            raise ValidationError(
                "Invalid Algorand app address: must be 58 uppercase base32 characters "
                "(A-Z, 2-7).",
                field="algo_app_address",
            )


# ── MicroAlgo ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MicroAlgo(BaseValueObject):
    """
    Amount expressed in microALGO (1 ALGO = 1_000_000 microALGO).
    Zero is valid (placeholder / 0-value payment for Note anchoring).
    Negative values are rejected.
    """

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValidationError(
                f"MicroAlgo must be non-negative; got {self.value}.",
                field="amount_microalgo",
            )

    @classmethod
    def from_algo(cls, algo: Decimal) -> "MicroAlgo":
        """Convert ALGO (Decimal) to MicroAlgo."""
        return cls(value=int(algo * Decimal("1000000")))

    @property
    def as_algo(self) -> Decimal:
        """Return ALGO value as Decimal."""
        return Decimal(self.value) / Decimal("1000000")


# ── MerkleRoot ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MerkleRoot(BaseValueObject):
    """SHA-256 Merkle root — exactly 64 lowercase hex characters."""

    value: str

    def __post_init__(self) -> None:
        if len(self.value) != 64:
            raise ValidationError(
                f"MerkleRoot must be exactly 64 hex characters; got {len(self.value)}.",
                field="merkle_root",
            )
        try:
            int(self.value, 16)
        except ValueError as exc:
            raise ValidationError(
                "MerkleRoot must be a valid hexadecimal string.",
                field="merkle_root",
            ) from exc


# ── TxId ──────────────────────────────────────────────────────────────────────

_TXID_RE = re.compile(r"^[A-Z2-7]{52}$")


@dataclass(frozen=True)
class TxId(BaseValueObject):
    """
    Algorand transaction ID — 52-char uppercase base32 string.
    Algorand TxIDs are 32 raw bytes, base32-encoded without padding → 52 chars.
    """

    value: str

    def __post_init__(self) -> None:
        if not _TXID_RE.match(self.value):
            raise ValidationError(
                "Invalid Algorand TxId: must be exactly 52 uppercase base32 characters "
                "(A-Z, 2-7).",
                field="tx_id",
            )


# ── EscrowAmount ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EscrowAmount(BaseValueObject):
    """
    Non-zero escrow amount in microALGO.
    Wrapper around MicroAlgo that enforces non-zero at escrow creation.
    """

    value: MicroAlgo

    def __post_init__(self) -> None:
        if self.value.value == 0:
            raise ValidationError(
                "EscrowAmount must be greater than zero.",
                field="amount",
            )
