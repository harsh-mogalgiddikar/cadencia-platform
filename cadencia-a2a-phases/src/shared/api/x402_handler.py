# context.md §3: x402 HTTP 402 payment flow handler.
# Phase 3: rejects SIM- prefixed tokens; builds 402 response with payment headers.
# X402_SIMULATION_MODE=false is strictly enforced — no silent fallback.

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

from src.shared.domain.exceptions import PolicyViolation, ValidationError
from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)


# ── SIM- Token Enforcement ────────────────────────────────────────────────────


def _is_simulation_mode_allowed() -> bool:
    """
    Check X402_SIMULATION_MODE env var.

    Returns True ONLY if explicitly set to "true" (case-insensitive).
    Defaults to False — simulation mode is NEVER silently enabled.
    """
    return os.environ.get("X402_SIMULATION_MODE", "false").lower() == "true"


def reject_sim_tokens(token_or_id: str, field_name: str = "token") -> None:
    """
    Reject any value prefixed with 'SIM-' unless X402_SIMULATION_MODE=true.

    Called on ALL transaction IDs, payment tokens, and API keys before
    they are processed by any service layer.

    Raises PolicyViolation if a SIM- prefixed value is found in production mode.
    """
    if not token_or_id:
        return

    if token_or_id.startswith("SIM-"):
        if _is_simulation_mode_allowed():
            log.warning(
                "sim_token_accepted_simulation_mode",
                field=field_name,
                token_prefix=token_or_id[:8],
            )
            return

        raise PolicyViolation(
            f"Simulated {field_name} rejected: '{token_or_id[:12]}…' — "
            "X402_SIMULATION_MODE=false. All tokens must be live. "
            "Set X402_SIMULATION_MODE=true only in development."
        )


def enforce_no_simulation_mode_at_startup() -> None:
    """
    Called at application startup to warn/reject simulation mode.

    In production (APP_ENV=production), raises RuntimeError if
    X402_SIMULATION_MODE=true — simulation mode is PROHIBITED in production.
    """
    sim_mode = _is_simulation_mode_allowed()
    app_env = os.environ.get("APP_ENV", "development")

    if sim_mode and app_env == "production":
        raise RuntimeError(
            "X402_SIMULATION_MODE=true is PROHIBITED in production. "
            "All payment flows must use real tokens. "
            "Remove X402_SIMULATION_MODE=true from environment."
        )

    if sim_mode:
        log.warning(
            "x402_simulation_mode_enabled",
            env=app_env,
            message="SIM- prefixed tokens will be accepted. "
            "This MUST NOT be used in production.",
        )
    else:
        log.info("x402_simulation_mode_disabled", env=app_env)


# ── HTTP 402 Payment Required Response Builder ────────────────────────────────


@dataclass(frozen=True)
class PaymentRequirement:
    """
    Describes what payment is needed before the resource can be accessed.

    Used to build the HTTP 402 response with custom payment headers.
    """

    amount_microalgo: int
    recipient_address: str  # Algorand address to pay
    session_id: str  # Tie payment to a session
    description: str = "Payment required to access this resource"
    currency: str = "ALGO"
    network: str = "algorand-testnet"
    expiry_seconds: int = 300  # 5 minutes


def build_402_response_headers(requirement: PaymentRequirement) -> dict[str, str]:
    """
    Build HTTP headers for a 402 Payment Required response.

    Headers follow the x402 protocol convention:
      X-Payment-Required:     "true"
      X-Payment-Amount:       amount in microAlgo
      X-Payment-Currency:     "ALGO"
      X-Payment-Network:      "algorand-testnet"
      X-Payment-Recipient:    Algorand address
      X-Payment-Session:      session ID for correlation
      X-Payment-Description:  human-readable description
      X-Payment-Expires:      unix timestamp of payment deadline
    """
    expiry_ts = int(time.time()) + requirement.expiry_seconds

    return {
        "X-Payment-Required": "true",
        "X-Payment-Amount": str(requirement.amount_microalgo),
        "X-Payment-Currency": requirement.currency,
        "X-Payment-Network": requirement.network,
        "X-Payment-Recipient": requirement.recipient_address,
        "X-Payment-Session": requirement.session_id,
        "X-Payment-Description": requirement.description,
        "X-Payment-Expires": str(expiry_ts),
    }


def build_402_response_body(requirement: PaymentRequirement) -> dict:
    """
    Build JSON body for a 402 Payment Required response.

    Follows the standard ApiResponse error envelope.
    """
    return {
        "success": False,
        "data": None,
        "meta": {
            "payment_required": True,
            "amount": requirement.amount_microalgo,
            "currency": requirement.currency,
            "network": requirement.network,
            "recipient": requirement.recipient_address,
            "session_id": requirement.session_id,
            "expires_in_seconds": requirement.expiry_seconds,
        },
        "error": {
            "code": "PAYMENT_REQUIRED",
            "message": requirement.description,
        },
    }


# ── Payment Header Verification ──────────────────────────────────────────────


def verify_payment_header(
    payment_header: str | None,
    expected_session_id: str,
    expected_amount_microalgo: int,
) -> dict:
    """
    Verify an incoming X-Payment-Proof header.

    The header should contain a pipe-separated string:
      tx_id|session_id|amount|timestamp|signature

    Returns parsed payment proof dict if valid.
    Raises ValidationError if malformed or expired.
    Raises PolicyViolation if SIM- token detected.
    """
    if not payment_header:
        raise ValidationError(
            "X-Payment-Proof header is required.",
            field="X-Payment-Proof",
        )

    parts = payment_header.split("|")
    if len(parts) != 5:
        raise ValidationError(
            "X-Payment-Proof must contain exactly 5 pipe-separated fields: "
            "tx_id|session_id|amount|timestamp|signature",
            field="X-Payment-Proof",
        )

    tx_id, session_id, amount_str, timestamp_str, signature = parts

    # Reject SIM- prefixed transaction IDs
    reject_sim_tokens(tx_id, field_name="payment_tx_id")

    # Validate session_id matches
    if session_id != expected_session_id:
        raise ValidationError(
            f"Payment session_id mismatch: expected '{expected_session_id}', "
            f"got '{session_id}'.",
            field="session_id",
        )

    # Validate amount
    try:
        amount = int(amount_str)
    except ValueError:
        raise ValidationError(
            f"Payment amount must be an integer, got: {amount_str!r}.",
            field="amount",
        )

    if amount < expected_amount_microalgo:
        raise PolicyViolation(
            f"Payment amount insufficient: expected {expected_amount_microalgo}, "
            f"got {amount}."
        )

    # Validate timestamp (not expired — 5-minute window)
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise ValidationError(
            f"Payment timestamp must be an integer, got: {timestamp_str!r}.",
            field="timestamp",
        )

    now = int(time.time())
    if timestamp < now - 300:
        raise ValidationError(
            "Payment proof has expired (>5 minutes old).",
            field="timestamp",
        )

    # Verify HMAC signature (if secret configured)
    payment_secret = os.environ.get("X402_PAYMENT_SECRET", "")
    if payment_secret:
        expected_sig = hmac.new(
            payment_secret.encode(),
            f"{tx_id}|{session_id}|{amount_str}|{timestamp_str}".encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise ValidationError(
                "Payment proof signature is invalid.",
                field="signature",
            )

    log.info(
        "payment_proof_verified",
        tx_id=tx_id,
        session_id=session_id,
        amount=amount,
    )

    return {
        "tx_id": tx_id,
        "session_id": session_id,
        "amount": amount,
        "timestamp": timestamp,
    }
