# context.md §3 — Puya-First Contracts: ALL Algorand smart contracts MUST be written in
# Algorand Python (Puya/PuyaPy). PyTeal is EXPLICITLY PROHIBITED.
# context.md §3 — Offline Contract Compilation: compiled via
#   algokit compile py contracts/escrow_contract.py --out-dir artifacts/
# Runtime compilation in production is PROHIBITED.
#
# Compile command:
#   algokit compile py contracts/escrow_contract.py --out-dir artifacts/
#
# ABI Standard: ARC-4 + ARC-56
# Global state:
#   buyer      (Account)  — Algorand address of buyer enterprise
#   seller     (Account)  — Algorand address of seller enterprise
#   amount     (UInt64)   — Escrow amount in microALGO
#   session_id (Bytes)    — Cadencia negotiation session UUID
#   status     (UInt64)   — 0=DEPLOYED, 1=FUNDED, 2=RELEASED, 3=REFUNDED
#   frozen     (UInt64)   — 0=normal, 1=frozen (blocks all state transitions)

from algopy import (
    Account,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
)


class CadenciaEscrow(arc4.ARC4Contract):
    """
    Cadencia B2B Trade Escrow Contract.

    ARC-4 + ARC-56 compliant smart contract for MSME trade settlement on Algorand.

    Status codes:
        0 = DEPLOYED   — contract created, awaiting funding
        1 = FUNDED     — buyer has funded the escrow
        2 = RELEASED   — seller has received funds
        3 = REFUNDED   — buyer has received refund

    Frozen flag:
        0 = normal     — all transitions permitted
        1 = frozen     — fund() and release() blocked (dispute mode)

    Safety rules (context.md §12):
        SRS-SC-001: All calls preceded by algod.dryrun() in AlgorandGateway adapter
        SRS-SC-002: fund() verifies payment.amount == self.amount atomically
        SRS-SC-003: release() asserts frozen==0; refund() asserts frozen==0
        SRS-SC-004: Only creator may call release(), refund(), unfreeze()
    """

    def __init__(self) -> None:
        # Declare global state slots — values set in initialize() on-chain
        self.buyer = GlobalState(Account, key=b"buyer")
        self.seller = GlobalState(Account, key=b"seller")
        self.amount = GlobalState(UInt64, key=b"amount")
        self.session_id = GlobalState(Bytes, key=b"session_id")
        self.status = GlobalState(UInt64, key=b"status")
        self.frozen = GlobalState(UInt64, key=b"frozen")

    @arc4.abimethod(create="require")
    def initialize(
        self,
        buyer: arc4.Address,
        seller: arc4.Address,
        amount: arc4.UInt64,
        session_id: arc4.String,
    ) -> None:
        """
        Initialize escrow on contract creation. Creator only.

        Pre-condition:  This is the CREATE transaction.
        Post-condition: status=DEPLOYED(0), frozen=0, all state vars set.
        """
        # SRS-SC-004: Only creator can initialize (enforced by create="require" +
        # sender check as defence-in-depth)
        assert Txn.sender == Global.creator_address, "Only creator can initialize"
        self.buyer.value = buyer.native
        self.seller.value = seller.native
        self.amount.value = amount.native
        # Store ARC-4 encoded bytes of session UUID (2-byte length prefix + UTF-8)
        self.session_id.value = session_id.bytes
        self.status.value = UInt64(0)   # DEPLOYED
        self.frozen.value = UInt64(0)   # unfrozen

    @arc4.abimethod
    def fund(self, payment: gtxn.PaymentTransaction) -> None:
        """
        Fund the escrow with an atomic payment.

        Pre-condition:  status==DEPLOYED(0), frozen==0.
                        payment.receiver == contract address.
                        payment.amount == self.amount (SRS-SC-002).
        Post-condition: status=FUNDED(1).
        """
        # Status guard
        assert self.status.value == UInt64(0), "Escrow must be DEPLOYED to fund"
        # SRS-SC-003 (freeze guard on fund)
        assert self.frozen.value == UInt64(0), "Escrow is frozen — cannot fund"
        # SRS-SC-002: payment must go to this contract
        assert (
            payment.receiver == Global.current_application_address
        ), "Payment receiver must be this escrow contract"
        # SRS-SC-002: exact amount enforced atomically in transaction group
        assert payment.amount == self.amount.value, "Payment amount must equal escrow amount"
        self.status.value = UInt64(1)   # FUNDED

    @arc4.abimethod
    def release(self, merkle_root: arc4.String) -> None:
        """
        Release funds to seller. Anchors Merkle root in transaction note field.

        Pre-condition:  status==FUNDED(1), frozen==0, sender==creator.
        Post-condition: status=RELEASED(2); inner PaymentTxn to seller.

        merkle_root: SHA-256 Merkle root of all session audit events (anchored
                     on-chain per context.md §8 end-to-end flow).
        """
        # SRS-SC-004: creator only
        assert Txn.sender == Global.creator_address, "Only creator can release escrow"
        # Status guard
        assert self.status.value == UInt64(1), "Escrow must be FUNDED to release"
        # SRS-SC-003: freeze guard
        assert self.frozen.value == UInt64(0), "Escrow is frozen — cannot release"
        # Inner payment to seller (fee pooled from outer transaction)
        itxn.Payment(
            receiver=self.seller.value,
            amount=self.amount.value,
            fee=0,
            note=merkle_root.bytes,   # Merkle root anchored on-chain
        ).submit()
        self.status.value = UInt64(2)   # RELEASED

    @arc4.abimethod
    def refund(self, reason: arc4.String) -> None:
        """
        Refund buyer. Used when trade fails or dispute resolved in buyer's favour.

        Pre-condition:  status==FUNDED(1), frozen==0, sender==creator.
        Post-condition: status=REFUNDED(3); inner PaymentTxn to buyer.

        SRS-SC-003 applies: frozen check enforced here as defence-in-depth.
        """
        # SRS-SC-004: creator only
        assert Txn.sender == Global.creator_address, "Only creator can refund"
        # Status guard
        assert self.status.value == UInt64(1), "Escrow must be FUNDED to refund"
        # SRS-SC-003: freeze guard (additional safety — blocks refund during active dispute)
        assert self.frozen.value == UInt64(0), "Escrow is frozen — resolve dispute first"
        # Inner payment to buyer
        itxn.Payment(
            receiver=self.buyer.value,
            amount=self.amount.value,
            fee=0,
            note=reason.bytes,
        ).submit()
        self.status.value = UInt64(3)   # REFUNDED

    @arc4.abimethod
    def freeze(self) -> None:
        """
        Freeze escrow to halt all state transitions (dispute mode).

        Access: buyer OR seller OR creator.
        Pre-condition:  Any status.
        Post-condition: frozen=1.
        """
        assert (
            Txn.sender == self.buyer.value
            or Txn.sender == self.seller.value
            or Txn.sender == Global.creator_address
        ), "Only buyer, seller, or creator can freeze"
        self.frozen.value = UInt64(1)

    @arc4.abimethod
    def unfreeze(self) -> None:
        """
        Unfreeze escrow after dispute resolution.

        Access: creator only (SRS-SC-004).
        Pre-condition:  frozen==1.
        Post-condition: frozen=0.
        """
        # SRS-SC-004: creator only
        assert Txn.sender == Global.creator_address, "Only creator can unfreeze"
        assert self.frozen.value == UInt64(1), "Escrow is not frozen"
        self.frozen.value = UInt64(0)
