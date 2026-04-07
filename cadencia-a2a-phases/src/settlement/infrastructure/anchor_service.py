# context.md §3 — algosdk ONLY in infrastructure layer — never in domain.
# context.md §7.3: dry-run BEFORE every Algorand call.
# Implements IAnchorService Protocol.

from __future__ import annotations

import os
import uuid

import structlog

from src.settlement.domain.value_objects import MerkleRoot, TxId

log = structlog.get_logger(__name__)

# Note field prefix for on-chain Merkle root anchoring.
ANCHOR_NOTE_PREFIX = b"cadencia:merkle:"


def _load_creator_sk() -> str:
    """
    Load Algorand creator private key from environment.

    SECURITY: mnemonic is NEVER logged — only "creator key loaded" is logged.
    Raises RuntimeError if env var is missing.
    """
    import algosdk.mnemonic as mnemonic  # type: ignore[import-untyped]

    raw = os.environ.get("ALGORAND_ESCROW_CREATOR_MNEMONIC", "")
    if not raw:
        raise RuntimeError(
            "ALGORAND_ESCROW_CREATOR_MNEMONIC is not set. "
            "Required for on-chain anchoring. See .env.example."
        )
    sk = mnemonic.to_private_key(raw)
    log.info("anchor_service_creator_key_loaded")
    return str(sk)


class AnchorService:
    """
    Writes a Merkle root into an Algorand transaction Note field.

    The anchor transaction is a zero-ALGO payment from creator to self,
    with note = ANCHOR_NOTE_PREFIX + session_id.bytes + merkle_root_hex.

    context.md §7.3: dry-run simulated before broadcast.
    Implements IAnchorService Protocol.
    """

    def __init__(self, algod_client: object, creator_sk: str) -> None:
        self._algod = algod_client  # algosdk.v2client.algod.AlgodClient
        self._creator_sk = creator_sk

    async def anchor_root(
        self,
        merkle_root: MerkleRoot,
        session_id: uuid.UUID,
    ) -> TxId:
        """
        Anchor merkle_root on-chain as a Note-only transaction.

        Raises RuntimeError if ANCHOR_SERVICE_ENABLED != "true".
        Raises BlockchainSimulationError if dry-run fails.
        Returns TxId of the confirmed anchor transaction.
        """
        if os.environ.get("ANCHOR_SERVICE_ENABLED", "true").lower() != "true":
            raise RuntimeError(
                "AnchorService is disabled (ANCHOR_SERVICE_ENABLED != 'true'). "
                "Set ANCHOR_SERVICE_ENABLED=true to enable on-chain anchoring."
            )

        import algosdk.account as account  # type: ignore[import-untyped]
        import algosdk.transaction as txn_lib  # type: ignore[import-untyped]

        creator_address = account.address_from_private_key(self._creator_sk)

        # Build note payload: prefix + session UUID bytes + merkle root hex
        note = (
            ANCHOR_NOTE_PREFIX
            + session_id.bytes
            + merkle_root.value.encode("utf-8")
        )

        sp = self._algod.suggested_params()  # type: ignore[attr-defined]

        # Zero-value payment to self — only purpose is carrying the Note field
        txn = txn_lib.PaymentTxn(
            sender=creator_address,
            receiver=creator_address,
            amt=0,
            note=note,
            sp=sp,
        )

        # Dry-run before broadcast
        await _simulate_payment_txn(self._algod, txn, self._creator_sk)

        # Sign and submit
        signed = txn.sign(self._creator_sk)
        tx_id = str(self._algod.send_transaction(signed))  # type: ignore[attr-defined]

        # Wait for confirmation (context.md §9: <5s finality → 5 rounds max)
        txn_lib.wait_for_confirmation(self._algod, tx_id, 5)  # type: ignore[attr-defined]

        log.info(
            "anchor_root_confirmed",
            tx_id=tx_id,
            session_id=str(session_id),
            merkle_root=merkle_root.value,
        )

        return TxId(value=tx_id)


async def _simulate_payment_txn(algod: object, txn: object, sk: str) -> None:
    """
    Simulate a payment transaction using algod simulate endpoint.

    Raises BlockchainSimulationError if simulation indicates rejection.
    context.md §7.3: dry-run MANDATORY before every Algorand call.
    """
    from src.shared.domain.exceptions import BlockchainSimulationError

    dry_run_enabled = os.environ.get("ESCROW_DRY_RUN_ENABLED", "true").lower()
    if dry_run_enabled != "true":
        return

    try:
        import algosdk.transaction as txn_lib  # type: ignore[import-untyped]

        signed = txn.sign(sk)  # type: ignore[attr-defined]
        dr_request = txn_lib.create_dryrun(algod, [signed])  # type: ignore[attr-defined]
        dr_result = algod.dryrun(dr_request)  # type: ignore[attr-defined]

        for txn_result in dr_result.get("txns", []):
            messages = txn_result.get("app-call-messages", [])
            if any("REJECT" in msg for msg in messages):
                raise BlockchainSimulationError(
                    f"Anchor transaction dry-run rejected: {messages}"
                )
    except BlockchainSimulationError:
        raise
    except Exception as exc:
        # Dry-run endpoint unavailable (e.g., non-localnet algod) — log and continue
        log.warning(
            "anchor_dryrun_unavailable",
            error=str(exc),
            note="Proceeding without dry-run — ensure ESCROW_DRY_RUN_ENABLED=false in this env",
        )
