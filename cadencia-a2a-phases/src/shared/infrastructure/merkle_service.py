# context.md §1.2: stdlib only — no external Merkle libraries.
# Relocated from settlement/infrastructure/ to shared/infrastructure/ (Phase 3).
# Implements IMerkleService Protocol from shared/domain/protocols.py.
# SHA-256 binary Merkle tree with deterministic pair ordering.

from __future__ import annotations

import hashlib

from src.shared.domain.exceptions import ValidationError


def _sha256(data: str) -> str:
    """SHA-256 hex digest of UTF-8 encoded data."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    """
    Deterministic pair hash: sort before combining to prevent reorder attacks.
    SHA-256(min(left, right) + max(left, right))
    """
    combined = min(left, right) + max(left, right)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


class MerkleService:
    """
    SHA-256 binary Merkle tree.

    Leaves:          SHA-256 hash of each entry string.
    Internal nodes:  SHA-256(sorted(left_hash, right_hash))
    Odd leaves:      last leaf duplicated at each level.

    Implements IMerkleService Protocol (returns str, not domain value objects).
    Callers in settlement/ wrap the returned str in MerkleRoot(value=...).
    """

    def compute_root(self, entries: list[str]) -> str:
        """
        Compute the Merkle root of a list of string entries.

        Raises ValidationError if entries is empty.
        Returns 64-char hex string.
        """
        if not entries:
            raise ValidationError(
                "Cannot compute Merkle root of empty entry list.",
                field="entries",
            )

        layer = [_sha256(entry) for entry in entries]

        while len(layer) > 1:
            next_layer: list[str] = []
            if len(layer) % 2 == 1:
                layer.append(layer[-1])
            for i in range(0, len(layer), 2):
                next_layer.append(_hash_pair(layer[i], layer[i + 1]))
            layer = next_layer

        return layer[0]

    def generate_proof(self, entries: list[str], index: int) -> list[str]:
        """
        Generate a Merkle inclusion proof for entries[index].

        Returns list of sibling hashes prefixed "L:" or "R:".
        """
        if not entries:
            raise ValidationError("Cannot generate proof for empty entries.", field="entries")
        if not (0 <= index < len(entries)):
            raise ValidationError(
                f"Index {index} out of range for {len(entries)} entries.",
                field="index",
            )

        layer = [_sha256(entry) for entry in entries]
        proof: list[str] = []
        pos = index

        while len(layer) > 1:
            if len(layer) % 2 == 1:
                layer.append(layer[-1])
            sibling_pos = pos ^ 1
            if sibling_pos > pos:
                proof.append(f"R:{layer[sibling_pos]}")
            else:
                proof.append(f"L:{layer[sibling_pos]}")
            next_layer: list[str] = []
            for i in range(0, len(layer), 2):
                next_layer.append(_hash_pair(layer[i], layer[i + 1]))
            layer = next_layer
            pos = pos // 2

        return proof

    def verify_proof(
        self, root: str, entry: str, proof: list[str], index: int
    ) -> bool:
        """
        Verify a Merkle inclusion proof.

        Returns True if the recomputed root matches root.
        """
        current = _sha256(entry)
        pos = index

        for step in proof:
            if step.startswith("R:"):
                sibling = step[2:]
                current = _hash_pair(current, sibling)
            elif step.startswith("L:"):
                sibling = step[2:]
                current = _hash_pair(sibling, current)
            else:
                return False
            pos = pos // 2

        return current == root
