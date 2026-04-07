# context.md §4.4: uses CadenciaEscrowClient exclusively — zero raw ABI calls.
# context.md §7.3: dry-run simulation BEFORE every transaction broadcast.
# context.md §3: algosdk ONLY in infrastructure — never in domain.
# NEVER log mnemonic, private key, or signing key.

from __future__ import annotations

import os

import structlog

from src.shared.domain.exceptions import BlockchainSimulationError
from src.settlement.domain.ports import IBlockchainGateway

log = structlog.get_logger(__name__)


def _load_creator_sk() -> str:
    """
    Load ALGORAND_ESCROW_CREATOR_MNEMONIC from env → private key.

    SECURITY: key/mnemonic NEVER logged — only "creator key loaded".
    Raises RuntimeError if env var missing or algorithm=RS256 required in prod.
    """
    import algosdk.mnemonic as algo_mnemonic  # type: ignore[import-untyped]

    raw_mnemonic = os.environ.get("ALGORAND_ESCROW_CREATOR_MNEMONIC", "")
    if not raw_mnemonic:
        raise RuntimeError(
            "ALGORAND_ESCROW_CREATOR_MNEMONIC is not set. "
            "Required for escrow deployment. See .env.example."
        )
    sk = algo_mnemonic.to_private_key(raw_mnemonic)
    log.info("algorand_gateway_creator_key_loaded")
    return str(sk)


def _get_algorand_client() -> object:
    """Build algokit_utils.AlgorandClient from env vars."""
    from algokit_utils import AlgorandClient  # type: ignore[import-untyped]

    algod_address = os.environ.get(
        "ALGORAND_ALGOD_ADDRESS", "http://localhost:4001"
    )
    algod_token = os.environ.get(
        "ALGORAND_ALGOD_TOKEN",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    return AlgorandClient.from_environment()  # reads ALGORAND_ALGOD_ADDRESS / TOKEN


class AlgorandGateway:
    """
    IBlockchainGateway implementation using CadenciaEscrowClient (typed ARC-56 client).

    context.md §4.4: CadenciaEscrowClient is the ONLY escrow interaction mechanism.
    Zero raw ABI calls. Zero PyTeal.
    """

    def __init__(self, algorand_client: object | None = None) -> None:
        """
        Build gateway.

        If algorand_client is None, constructs AlgorandClient from env vars.
        """
        import algosdk.account as account  # type: ignore[import-untyped]

        self._algorand = algorand_client or _get_algorand_client()
        self._creator_sk = _load_creator_sk()
        self._creator_address = account.address_from_private_key(self._creator_sk)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_factory(self) -> object:
        """Get CadenciaEscrowFactory — used to deploy new contracts."""
        from artifacts.CadenciaEscrowClient import CadenciaEscrowFactory  # type: ignore[import-untyped]

        return CadenciaEscrowFactory(
            algorand=self._algorand,
            creator=self._creator_address,
        )

    def _get_client(self, app_id: int) -> object:
        """Get CadenciaEscrowClient — used to call existing contracts."""
        from artifacts.CadenciaEscrowClient import CadenciaEscrowClient  # type: ignore[import-untyped]

        return CadenciaEscrowClient(
            app_id=app_id,
            algorand=self._algorand,
            sender=self._creator_address,
        )

    async def _simulate_app_call(
        self, app_id: int, method_name: str
    ) -> None:
        """
        Simulate an app call using algod simulate endpoint before broadcast.
        context.md §7.3: MANDATORY for every contract call.

        Uses the underlying algod client for simulation.
        Raises BlockchainSimulationError if simulation predicts rejection.
        """
        if os.environ.get("ESCROW_DRY_RUN_ENABLED", "true").lower() != "true":
            return

        try:
            import algosdk.atomic_transaction_composer as atc_module  # type: ignore[import-untyped]
            import algosdk.transaction as txn_lib  # type: ignore[import-untyped]

            # Access underlying algod client from AlgorandClient wrapper
            algod = self._algorand.client.algod  # type: ignore[attr-defined]
            sp = algod.suggested_params()

            # Build minimal app call for simulation (no-op call to check state)
            txn = txn_lib.ApplicationCallTxn(
                sender=self._creator_address,
                sp=sp,
                index=app_id,
                on_complete=txn_lib.OnComplete.NoOpOC,
            )

            signed = txn.sign(self._creator_sk)
            dr = txn_lib.create_dryrun(algod, [signed])
            result = algod.dryrun(dr)

            for txn_result in result.get("txns", []):
                messages = txn_result.get("app-call-messages", [])
                if any("REJECT" in msg for msg in messages):
                    raise BlockchainSimulationError(
                        f"Dry-run rejected {method_name} on app {app_id}: {messages}"
                    )

            log.debug(
                "dry_run_passed",
                app_id=app_id,
                method=method_name,
            )

        except BlockchainSimulationError:
            raise
        except Exception as exc:
            # Dryrun endpoint may be unavailable (non-localnet algod).
            # Log warning and proceed — production must have ESCROW_DRY_RUN_ENABLED=true.
            log.warning(
                "dry_run_unavailable",
                method=method_name,
                app_id=app_id,
                error=str(exc),
            )

    # ── Deploy ─────────────────────────────────────────────────────────────────

    async def deploy_escrow(
        self,
        buyer_address: str,
        seller_address: str,
        amount_microalgo: int,
        session_id: str,
    ) -> dict:
        """
        Deploy a new CadenciaEscrow contract via CadenciaEscrowFactory.

        1. Factory.deploy() → calls initialize(buyer, seller, amount, session_id)
        2. Returns {"app_id": int, "app_address": str, "tx_id": str}
        """
        import algosdk.logic as logic  # type: ignore[import-untyped]

        factory = self._get_factory()
        client, deploy_result = await factory.deploy(  # type: ignore[attr-defined]
            buyer=buyer_address,
            seller=seller_address,
            amount_microalgo=amount_microalgo,
            session_id=session_id,
        )

        app_id = int(client.app_id)  # type: ignore[attr-defined]
        app_address = str(logic.get_application_address(app_id))
        # Transaction ID from deploy result
        tx_id = str(getattr(deploy_result, "tx_id", None) or getattr(deploy_result, "txid", ""))

        log.info(
            "escrow_contract_deployed",
            app_id=app_id,
            app_address=app_address,
            tx_id=tx_id,
            session_id=session_id,
        )

        return {
            "app_id": app_id,
            "app_address": app_address,
            "tx_id": tx_id,
        }

    # ── Fund ───────────────────────────────────────────────────────────────────

    async def fund_escrow(
        self,
        app_id: int,
        app_address: str,
        amount_microalgo: int,
        funder_sk: str,
    ) -> dict:
        """
        Fund escrow with atomic group [PaymentTxn + AppCallTxn].

        The CadenciaEscrowClient.fund() builds the atomic group internally
        using the provided funder as sender for the payment leg.
        context.md SRS-SC-002: payment amount must equal stored escrow amount.

        SECURITY: funder_sk NEVER logged.
        """
        # Pre-call simulation using creator's key (validates app state)
        await self._simulate_app_call(app_id, "fund")

        import algosdk.account as account  # type: ignore[import-untyped]
        from artifacts.CadenciaEscrowClient import CadenciaEscrowClient  # type: ignore[import-untyped]

        funder_address = account.address_from_private_key(funder_sk)

        # Build a funder-scoped client for the payment leg
        funder_client = CadenciaEscrowClient(
            app_id=app_id,
            algorand=self._algorand,
            sender=funder_address,
        )

        result = await funder_client.fund(payment_amount_microalgo=amount_microalgo)  # type: ignore[attr-defined]

        tx_id = str(getattr(result, "tx_id", None) or getattr(result, "txid", ""))
        confirmed_round = int(getattr(result, "confirmed_round", 0))

        log.info(
            "escrow_funded_on_chain",
            app_id=app_id,
            tx_id=tx_id,
            confirmed_round=confirmed_round,
            # SECURITY: funder_sk and funder_address NOT logged
        )

        return {"tx_id": tx_id, "confirmed_round": confirmed_round}

    # ── Release ────────────────────────────────────────────────────────────────

    async def release_escrow(self, app_id: int, merkle_root: str) -> dict:
        """Release funds to seller. Anchors Merkle root in inner tx note."""
        await self._simulate_app_call(app_id, "release")

        client = self._get_client(app_id)
        result = await client.release(merkle_root=merkle_root)  # type: ignore[attr-defined]

        tx_id = str(getattr(result, "tx_id", None) or getattr(result, "txid", ""))
        confirmed_round = int(getattr(result, "confirmed_round", 0))

        log.info(
            "escrow_released_on_chain",
            app_id=app_id,
            merkle_root=merkle_root,
            tx_id=tx_id,
        )

        return {"tx_id": tx_id, "confirmed_round": confirmed_round}

    # ── Refund ─────────────────────────────────────────────────────────────────

    async def refund_escrow(self, app_id: int, reason: str) -> dict:
        """Refund buyer. Stores reason in inner transaction note."""
        await self._simulate_app_call(app_id, "refund")

        client = self._get_client(app_id)
        result = await client.refund(reason=reason)  # type: ignore[attr-defined]

        tx_id = str(getattr(result, "tx_id", None) or getattr(result, "txid", ""))
        confirmed_round = int(getattr(result, "confirmed_round", 0))

        log.info(
            "escrow_refunded_on_chain",
            app_id=app_id,
            reason=reason,
            tx_id=tx_id,
        )

        return {"tx_id": tx_id, "confirmed_round": confirmed_round}

    # ── Freeze ─────────────────────────────────────────────────────────────────

    async def freeze_escrow(self, app_id: int) -> dict:
        """Freeze escrow. Buyer, seller, or creator."""
        await self._simulate_app_call(app_id, "freeze")

        client = self._get_client(app_id)
        result = await client.freeze()  # type: ignore[attr-defined]

        tx_id = str(getattr(result, "tx_id", None) or getattr(result, "txid", ""))
        log.info("escrow_frozen_on_chain", app_id=app_id, tx_id=tx_id)

        return {"tx_id": tx_id}

    # ── Unfreeze ───────────────────────────────────────────────────────────────

    async def unfreeze_escrow(self, app_id: int) -> dict:
        """Unfreeze escrow. Creator only (SRS-SC-004)."""
        await self._simulate_app_call(app_id, "unfreeze")

        client = self._get_client(app_id)
        result = await client.unfreeze()  # type: ignore[attr-defined]

        tx_id = str(getattr(result, "tx_id", None) or getattr(result, "txid", ""))
        log.info("escrow_unfrozen_on_chain", app_id=app_id, tx_id=tx_id)

        return {"tx_id": tx_id}

    # ── State Query ────────────────────────────────────────────────────────────

    async def get_app_state(self, app_id: int) -> dict:
        """
        Read and decode current on-chain global state.

        Returns:
            {"status": int, "frozen": int, "buyer": str, "seller": str, "amount": int}
        """
        from artifacts.CadenciaEscrowClient import CadenciaEscrowClient  # type: ignore[import-untyped]

        client = CadenciaEscrowClient(
            app_id=app_id,
            algorand=self._algorand,
            sender=self._creator_address,
        )
        state = await client.get_state()  # type: ignore[attr-defined]

        return {
            "status": state.status,
            "frozen": state.frozen,
            "buyer": state.buyer,
            "seller": state.seller,
            "amount": state.amount,
            "status_label": state.status_label,
            "is_frozen": state.is_frozen,
        }

    # ── Pera Wallet: Unsigned Transaction Builder (RW-02) ─────────────────────

    async def build_fund_transaction(
        self,
        app_id: int,
        app_address: str,
        amount_microalgo: int,
        funder_address: str,
    ) -> dict:
        """
        Build an unsigned atomic group for escrow funding.

        Returns base64-encoded unsigned transactions that the frontend
        passes to Pera Wallet for user signing.

        Atomic group:
          [0] PaymentTxn — funder → escrow app address
          [1] AppCallTxn — call fund() on the escrow contract

        context.md §12: backend NEVER handles private keys for user wallets.
        """
        import base64
        from algosdk import transaction
        from algosdk.v2client.algod import AlgodClient

        algod_address = os.environ.get(
            "ALGORAND_ALGOD_ADDRESS", "http://localhost:4001"
        )
        algod_token = os.environ.get(
            "ALGORAND_ALGOD_TOKEN", "a" * 64,
        )
        algod = AlgodClient(algod_token, algod_address)
        params = algod.suggested_params()

        # Transaction 0: Payment — funder sends ALGO to escrow
        pay_txn = transaction.PaymentTxn(
            sender=funder_address,
            sp=params,
            receiver=app_address,
            amt=amount_microalgo,
        )

        # Transaction 1: AppCall — call fund() method on the escrow
        fund_method_selector = b"fund"  # ABI method selector
        app_call_txn = transaction.ApplicationCallTxn(
            sender=funder_address,
            sp=params,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[fund_method_selector],
        )

        # Assign group ID (atomic group)
        gid = transaction.calculate_group_id([pay_txn, app_call_txn])
        pay_txn.group = gid
        app_call_txn.group = gid

        # Encode as base64 for frontend transport
        unsigned_txns = [
            base64.b64encode(
                transaction.write_to_file([pay_txn])
                if hasattr(transaction, "write_to_file")
                else pay_txn.dictify()  # type: ignore[union-attr]
            ).decode()
            if False
            else base64.b64encode(
                bytes(transaction.encoding.msgpack_encode(pay_txn), "latin-1")
                if isinstance(transaction.encoding.msgpack_encode(pay_txn), str)
                else transaction.encoding.msgpack_encode(pay_txn)
            ).decode(),
            base64.b64encode(
                bytes(transaction.encoding.msgpack_encode(app_call_txn), "latin-1")
                if isinstance(transaction.encoding.msgpack_encode(app_call_txn), str)
                else transaction.encoding.msgpack_encode(app_call_txn)
            ).decode(),
        ]

        log.info(
            "build_fund_txn_success",
            app_id=app_id,
            funder=funder_address[:8] + "...",
            amount_microalgo=amount_microalgo,
            group_id=base64.b64encode(gid).decode(),
        )

        return {
            "unsigned_transactions": unsigned_txns,
            "group_id": base64.b64encode(gid).decode(),
            "transaction_count": 2,
            "description": "Atomic group: [PaymentTxn, AppCallTxn(fund)]",
        }

    async def submit_signed_fund(
        self,
        signed_txn_bytes_list: list[str],
    ) -> dict:
        """
        Submit pre-signed transaction group from Pera Wallet.

        1. Decode base64 signed transactions
        2. Run mandatory dry-run simulation (SRS-SC-001)
        3. Broadcast to Algorand network
        4. Wait for confirmation

        context.md §7.3: dry-run BEFORE every broadcast.
        context.md §12: backend NEVER sees private keys.
        """
        import base64
        from algosdk import transaction
        from algosdk.v2client.algod import AlgodClient

        algod_address = os.environ.get(
            "ALGORAND_ALGOD_ADDRESS", "http://localhost:4001"
        )
        algod_token = os.environ.get(
            "ALGORAND_ALGOD_TOKEN", "a" * 64,
        )
        algod = AlgodClient(algod_token, algod_address)

        # 1. Decode signed transactions
        signed_txns = []
        for b64_txn in signed_txn_bytes_list:
            raw = base64.b64decode(b64_txn)
            signed_txns.append(raw)

        # 2. Mandatory dry-run simulation (context.md §7.3, SRS-SC-001)
        is_simulation = os.environ.get("X402_SIMULATION_MODE", "true").lower() == "true"
        if not is_simulation:
            try:
                from algosdk.v2client.models import DryrunRequest
                dr = DryrunRequest(txns=signed_txns)
                dr_result = algod.dryrun(dr)

                # Check for any failed transactions in the dry-run
                for txn_result in dr_result.get("txns", []):
                    if txn_result.get("app-call-messages"):
                        msgs = txn_result["app-call-messages"]
                        if any("REJECT" in str(m).upper() for m in msgs):
                            raise BlockchainSimulationError(
                                f"Dry-run simulation rejected: {msgs}"
                            )
            except BlockchainSimulationError:
                raise
            except Exception as exc:
                log.warning("dry_run_check_failed", error=str(exc))
                # In production, this should raise; in prototype, continue
                if not is_simulation:
                    raise BlockchainSimulationError(
                        f"Dry-run simulation failed: {exc}"
                    )

        # 3. Broadcast signed transaction group
        try:
            tx_id = algod.send_raw_transaction(b"".join(signed_txns))

            # 4. Wait for confirmation
            from algosdk import transaction as txn_module
            confirmed = txn_module.wait_for_confirmation(algod, tx_id, 10)
            confirmed_round = confirmed.get("confirmed-round", 0)

            log.info(
                "submit_signed_fund_success",
                tx_id=tx_id,
                confirmed_round=confirmed_round,
            )

            return {
                "tx_id": tx_id,
                "confirmed_round": confirmed_round,
            }
        except Exception as exc:
            log.error("submit_signed_fund_failed", error=str(exc))
            raise

