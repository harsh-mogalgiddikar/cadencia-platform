"""
Short-form wallet router — /v1/wallet/* endpoints.

These proxy to the existing enterprise-scoped wallet logic in the identity module,
resolving enterprise_id from the JWT's claims automatically. The frontend's
WalletContext.tsx calls these short-form paths exclusively.

Existing enterprise-scoped routes remain untouched at /v1/enterprises/{id}/wallet/*.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.api.responses import ApiResponse, success_response
from src.shared.infrastructure.db.session import get_db_session
from src.shared.infrastructure.logging import get_logger
from src.identity.api.dependencies import (
    get_current_user,
    get_identity_service,
)
from src.identity.domain.user import User
from src.identity.application.commands import LinkWalletCommand, UnlinkWalletCommand
from src.identity.application.queries import GetEnterpriseQuery
from src.identity.infrastructure.models import EnterpriseModel
from src.settlement.infrastructure.models import EscrowContractModel

from src.wallet.schemas import (
    OptedInApp,
    WalletBalanceResponse,
    WalletChallengeResponse,
    WalletLinkRequest,
    WalletLinkResponse,
    WalletUnlinkResponse,
)

log = get_logger(__name__)

router = APIRouter(
    prefix="/v1/wallet",
    tags=["wallet"],
    dependencies=[Depends(get_current_user)],
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _require_enterprise(user: User) -> uuid.UUID:
    """Extract enterprise_id from JWT-authenticated user. 400 if missing."""
    if not user.enterprise_id:
        raise HTTPException(
            status_code=400,
            detail="No enterprise associated with this account",
        )
    return user.enterprise_id


# ── 1. GET /v1/wallet/challenge ───────────────────────────────────────────────


@router.get(
    "/challenge",
    response_model=ApiResponse[WalletChallengeResponse],
    summary="Generate wallet ownership challenge for Pera Wallet signing",
)
async def get_wallet_challenge(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WalletChallengeResponse]:
    """
    Initiates the wallet linking flow. Returns a unique nonce that the user
    must sign with their Algorand private key via Pera Wallet.
    """
    enterprise_id = _require_enterprise(current_user)

    from src.shared.infrastructure.cache.redis_client import get_redis_instance
    from src.identity.infrastructure.wallet_verifier import WalletVerifier

    redis = await get_redis_instance()
    verifier = WalletVerifier(redis=redis)

    # Invalidate any prior unused challenge for this enterprise
    # (Redis key pattern: wallet_challenge:wc-*)
    # The verifier's create_challenge generates a new unique key each time;
    # old keys expire via TTL. For strict single-active-challenge, delete prior ones.
    pattern = f"wallet_challenge:*"
    try:
        async for key in redis.scan_iter(match=pattern):
            stored = await redis.get(key)
            if stored:
                stored_str = stored.decode() if isinstance(stored, bytes) else stored
                parts = stored_str.split("|", 1)
                if len(parts) == 2 and parts[1] == str(enterprise_id):
                    await redis.delete(key)
    except Exception:
        pass  # Best-effort cleanup — Redis scan failures are non-fatal

    challenge = await verifier.create_challenge(enterprise_id)

    return success_response(
        WalletChallengeResponse(
            challenge=challenge.challenge_id,
            enterprise_id=str(enterprise_id),
            expires_at=challenge.expires_at.isoformat(),
        )
    )


# ── 2. POST /v1/wallet/link ──────────────────────────────────────────────────


@router.post(
    "/link",
    response_model=ApiResponse[WalletLinkResponse],
    summary="Link Algorand wallet after verifying signed challenge",
)
async def link_wallet(
    body: WalletLinkRequest,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_identity_service),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[WalletLinkResponse]:
    """
    Completes the wallet linking flow. Verifies the Ed25519 signature of the
    challenge nonce, then stores the wallet address on the enterprise record.
    """
    enterprise_id = _require_enterprise(current_user)

    # Check if address is already linked to a different enterprise
    existing = await db.execute(
        select(EnterpriseModel).where(
            and_(
                EnterpriseModel.algorand_wallet == body.address,
                EnterpriseModel.id != enterprise_id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="This wallet address is already linked to another enterprise",
        )

    # Retrieve the active challenge and verify the signature
    from src.shared.infrastructure.cache.redis_client import get_redis_instance
    from src.identity.infrastructure.wallet_verifier import WalletVerifier

    redis = await get_redis_instance()
    verifier = WalletVerifier(redis=redis)

    # Find the active challenge for this enterprise
    challenge_id = None
    try:
        async for key in redis.scan_iter(match="wallet_challenge:*"):
            stored = await redis.get(key)
            if stored:
                stored_str = stored.decode() if isinstance(stored, bytes) else stored
                parts = stored_str.split("|", 1)
                if len(parts) == 2 and parts[1] == str(enterprise_id):
                    # Extract challenge_id from the redis key
                    key_str = key.decode() if isinstance(key, bytes) else key
                    challenge_id = key_str.replace("wallet_challenge:", "")
                    break
    except Exception:
        pass

    if challenge_id is None:
        raise HTTPException(
            status_code=400,
            detail="Challenge not found or expired. Please request a new challenge.",
        )

    # Verify the signature
    is_valid = await verifier.verify_challenge(
        challenge_id=challenge_id,
        algorand_address=body.address,
        signature_b64=body.signature,
    )
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Signature verification failed. Ensure you signed the correct challenge.",
        )

    # Link wallet via the existing identity service
    enterprise = await svc.link_wallet(
        LinkWalletCommand(
            enterprise_id=enterprise_id,
            requesting_user_id=current_user.id,
            algorand_address=body.address,
        )
    )

    log.info(
        "wallet_linked_shortform",
        enterprise_id=str(enterprise_id),
        address=body.address[:8] + "...",
    )

    return success_response(
        WalletLinkResponse(
            algorand_address=body.address,
            message="Wallet linked successfully",
        )
    )


# ── 3. DELETE /v1/wallet/link ─────────────────────────────────────────────────


@router.delete(
    "/link",
    response_model=ApiResponse[WalletUnlinkResponse],
    summary="Unlink Algorand wallet from enterprise",
)
async def unlink_wallet(
    current_user: User = Depends(get_current_user),
    svc=Depends(get_identity_service),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[WalletUnlinkResponse]:
    """
    Unlinks the Algorand wallet from the enterprise. Blocks if there are
    active or funded escrow contracts.
    """
    enterprise_id = _require_enterprise(current_user)

    # Check if enterprise has a wallet linked
    result = await db.execute(
        select(EnterpriseModel.algorand_wallet).where(
            EnterpriseModel.id == enterprise_id
        )
    )
    wallet_address = result.scalar_one_or_none()
    if not wallet_address:
        raise HTTPException(
            status_code=400,
            detail="No wallet is currently linked to this enterprise",
        )

    # Block unlink if there are active/funded escrows
    active_escrow_statuses = ("DEPLOYED", "FUNDED")
    escrow_result = await db.execute(
        select(EscrowContractModel.id).where(
            and_(
                EscrowContractModel.buyer_algorand_address == wallet_address,
                EscrowContractModel.status.in_(active_escrow_statuses),
            )
        ).limit(1)
    )
    # Also check seller side
    if escrow_result.scalar_one_or_none() is None:
        escrow_result = await db.execute(
            select(EscrowContractModel.id).where(
                and_(
                    EscrowContractModel.seller_algorand_address == wallet_address,
                    EscrowContractModel.status.in_(active_escrow_statuses),
                )
            ).limit(1)
        )
    if escrow_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot unlink wallet while active escrow contracts exist",
        )

    # Unlink via the identity service
    await svc.unlink_wallet(
        UnlinkWalletCommand(
            enterprise_id=enterprise_id,
            requesting_user_id=current_user.id,
        )
    )

    # Invalidate any active challenges for this enterprise
    try:
        from src.shared.infrastructure.cache.redis_client import get_redis_instance

        redis = await get_redis_instance()
        async for key in redis.scan_iter(match="wallet_challenge:*"):
            stored = await redis.get(key)
            if stored:
                stored_str = stored.decode() if isinstance(stored, bytes) else stored
                parts = stored_str.split("|", 1)
                if len(parts) == 2 and parts[1] == str(enterprise_id):
                    await redis.delete(key)
    except Exception:
        pass  # Best-effort

    log.info("wallet_unlinked_shortform", enterprise_id=str(enterprise_id))

    return success_response(
        WalletUnlinkResponse(message="Wallet unlinked successfully")
    )


# ── 4. GET /v1/wallet/balance ─────────────────────────────────────────────────


@router.get(
    "/balance",
    response_model=ApiResponse[WalletBalanceResponse],
    summary="Query on-chain ALGO balance and opted-in apps",
)
async def get_wallet_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[WalletBalanceResponse]:
    """
    Fetches the current ALGO balance and opted-in app state for the
    enterprise's linked Algorand wallet from the live blockchain.
    """
    enterprise_id = _require_enterprise(current_user)

    # Get the enterprise's wallet address
    result = await db.execute(
        select(EnterpriseModel.algorand_wallet).where(
            EnterpriseModel.id == enterprise_id
        )
    )
    wallet_address = result.scalar_one_or_none()
    if not wallet_address:
        raise HTTPException(
            status_code=404,
            detail="No wallet linked to this enterprise",
        )

    # Query the Algorand node
    try:
        from algosdk.v2client.algod import AlgodClient

        algod_address = os.environ.get(
            "ALGORAND_ALGOD_ADDRESS", "http://localhost:4001"
        )
        algod_token = os.environ.get(
            "ALGORAND_ALGOD_TOKEN", "a" * 64
        )
        client = AlgodClient(algod_token, algod_address)
        info = client.account_info(wallet_address)

        balance_microalgo = info.get("amount", 0)
        min_balance = info.get("min-balance", 100000)
        available = balance_microalgo - min_balance  # Can be negative — raw value

        # Build opted-in apps list, cross-referencing escrow table for names
        apps = []
        for app in info.get("apps-local-state", []):
            app_id = app["id"]
            app_name = None

            try:
                escrow = await db.execute(
                    select(EscrowContractModel.id).where(
                        EscrowContractModel.algo_app_id == app_id
                    )
                )
                if escrow.scalar_one_or_none() is not None:
                    app_name = "Cadencia Escrow"
            except Exception:
                pass

            apps.append(OptedInApp(app_id=app_id, app_name=app_name))

        return success_response(
            WalletBalanceResponse(
                algorand_address=wallet_address,
                algo_balance_microalgo=balance_microalgo,
                algo_balance_algo=str(balance_microalgo / 1_000_000),
                min_balance=min_balance,
                available_balance=available,
                opted_in_apps=apps,
            )
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.warning(
            "wallet_balance_query_failed",
            address=wallet_address[:8] + "...",
            error=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to reach Algorand network. Please try again.",
        )
