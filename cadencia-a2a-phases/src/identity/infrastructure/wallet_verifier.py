"""
Wallet challenge-response verifier for Pera Wallet integration.

context.md §14: Wallet ownership verified via challenge-response.
context.md §12 SRS-SC-001: backend NEVER stores private keys.

Flow:
1. Backend generates random nonce → stores in Redis with 5-min TTL
2. Frontend signs nonce with wallet private key via Pera Wallet
3. Backend verifies signature using algosdk.encoding.verify_bytes()

Security:
- Challenge nonces expire after 5 minutes (Redis TTL)
- Wallet address validated against Algorand checksum before linking
- All wallet operations logged to structured audit trail
"""

from __future__ import annotations

import base64
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import algosdk
from algosdk import encoding

from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)

_CHALLENGE_TTL = 300  # 5 minutes
_CHALLENGE_PREFIX = "wallet_challenge:"


@dataclass(frozen=True)
class WalletChallenge:
    """Issued challenge for wallet ownership verification."""

    challenge_id: str
    nonce: str
    message_to_sign: str
    expires_at: datetime


class WalletVerifier:
    """
    Cryptographic wallet ownership verification using Algorand signatures.

    Uses Redis for challenge storage with automatic TTL expiration.
    Backend NEVER handles or stores private keys (context.md §12).
    """

    def __init__(self, redis: object) -> None:
        """
        Args:
            redis: Redis async client for challenge storage.
        """
        self._redis = redis

    async def create_challenge(self, enterprise_id: uuid.UUID) -> WalletChallenge:
        """
        Generate a new wallet ownership challenge.

        Creates a random nonce and stores it in Redis with 5-minute TTL.
        The frontend should prompt the user to sign the message via Pera Wallet.
        """
        challenge_id = f"wc-{uuid.uuid4().hex[:16]}"
        nonce = secrets.token_hex(32)
        message = f"Cadencia wallet verification: {nonce}"
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=_CHALLENGE_TTL)

        # Store in Redis
        redis_key = f"{_CHALLENGE_PREFIX}{challenge_id}"
        await self._redis.setex(
            redis_key,
            _CHALLENGE_TTL,
            f"{nonce}|{enterprise_id}",
        )

        log.info(
            "wallet_challenge_created",
            challenge_id=challenge_id,
            enterprise_id=str(enterprise_id),
            expires_at=expires_at.isoformat(),
        )

        return WalletChallenge(
            challenge_id=challenge_id,
            nonce=nonce,
            message_to_sign=message,
            expires_at=expires_at,
        )

    async def verify_challenge(
        self,
        challenge_id: str,
        algorand_address: str,
        signature_b64: str,
    ) -> bool:
        """
        Verify that the wallet owner signed the challenge nonce.

        Args:
            challenge_id: ID of the challenge issued by create_challenge.
            algorand_address: 58-char Algorand address claiming ownership.
            signature_b64: Base64-encoded Ed25519 signature of the message.

        Returns:
            True if the signature is valid, False otherwise.
        """
        # 1. Validate Algorand address checksum
        if not self._is_valid_algorand_address(algorand_address):
            log.warning(
                "wallet_verify_invalid_address",
                challenge_id=challenge_id,
                address=algorand_address[:8] + "...",
            )
            return False

        # 2. Retrieve challenge from Redis
        redis_key = f"{_CHALLENGE_PREFIX}{challenge_id}"
        stored = await self._redis.get(redis_key)
        if stored is None:
            log.warning(
                "wallet_verify_challenge_expired_or_missing",
                challenge_id=challenge_id,
            )
            return False

        stored_str = stored.decode() if isinstance(stored, bytes) else stored
        parts = stored_str.split("|", 1)
        if len(parts) != 2:
            return False
        nonce, _ = parts

        # 3. Reconstruct the message that should have been signed
        message = f"Cadencia wallet verification: {nonce}"
        message_bytes = message.encode("utf-8")

        # 4. Verify Ed25519 signature
        try:
            signature_bytes = base64.b64decode(signature_b64)
            # algosdk verify_bytes expects: message, signature, address
            is_valid = encoding.verify_bytes(
                message_bytes, signature_bytes, algorand_address
            )
        except Exception as exc:
            log.warning(
                "wallet_verify_signature_error",
                challenge_id=challenge_id,
                error=str(exc),
            )
            return False

        # 5. Delete challenge (one-time use)
        await self._redis.delete(redis_key)

        if is_valid:
            log.info(
                "wallet_ownership_verified",
                challenge_id=challenge_id,
                address=algorand_address[:8] + "...",
            )
        else:
            log.warning(
                "wallet_verify_signature_invalid",
                challenge_id=challenge_id,
                address=algorand_address[:8] + "...",
            )

        return is_valid

    @staticmethod
    def _is_valid_algorand_address(address: str) -> bool:
        """Validate Algorand address format and checksum."""
        try:
            algosdk.encoding.decode_address(address)
            return True
        except Exception:
            return False
