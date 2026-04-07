# Phase 3 refactor: MerkleService relocated to src/shared/infrastructure/merkle_service.py.
# This module re-exports MerkleService for backward compatibility.
# New code should import from src.shared.infrastructure.merkle_service directly.

from src.shared.infrastructure.merkle_service import MerkleService  # noqa: F401

__all__ = ["MerkleService"]
