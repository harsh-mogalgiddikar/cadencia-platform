"""
Compliance domain unit tests — hash-chain integrity, FEMA, GST, exporter.

Tests:
  - AuditEntry creation and hash computation
  - AuditChainVerifier (valid chain, broken chain, tampered entry)
  - AuditHasher verify/compute roundtrip
  - FEMARecord.generate (form type switch at INR 5L, PAN formatting)
  - GSTRecord.generate (interstate IGST vs intrastate CGST+SGST, tax math)
  - Value object validation (HashValue, SequenceNumber, PANNumber, GSTIN, HSNCode, INRAmount, PurposeCode)
  - FEMAGSTExporter PDF/CSV output format
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from decimal import Decimal

import pytest

from src.compliance.domain.audit_log import (
    AuditChainVerifier,
    AuditEntry,
    AuditHasher,
)
from src.compliance.domain.fema_record import FEMARecord
from src.compliance.domain.gst_record import GSTRecord
from src.compliance.domain.value_objects import (
    GENESIS_HASH,
    GSTIN,
    HSNCode,
    HashValue,
    INRAmount,
    PANNumber,
    PurposeCode,
    SequenceNumber,
)
from src.shared.domain.exceptions import ValidationError


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Hash Chain Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditHasher:
    """SHA-256 hash computation and verification."""

    def test_compute_deterministic(self):
        """Same inputs always produce the same hash."""
        h1 = AuditHasher.compute(GENESIS_HASH, "EscrowFunded", '{"amount":100}')
        h2 = AuditHasher.compute(GENESIS_HASH, "EscrowFunded", '{"amount":100}')
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_compute_different_inputs_different_hash(self):
        """Changing any input changes the hash."""
        base = AuditHasher.compute(GENESIS_HASH, "EscrowFunded", '{"amount":100}')
        changed_type = AuditHasher.compute(GENESIS_HASH, "EscrowReleased", '{"amount":100}')
        changed_payload = AuditHasher.compute(GENESIS_HASH, "EscrowFunded", '{"amount":200}')
        changed_prev = AuditHasher.compute("a" * 64, "EscrowFunded", '{"amount":100}')

        assert base != changed_type
        assert base != changed_payload
        assert base != changed_prev

    def test_verify_valid_entry(self):
        """Verify returns True for a correctly computed entry."""
        entry = AuditEntry.create(
            escrow_id=uuid.uuid4(),
            sequence_no=0,
            event_type="EscrowFunded",
            payload={"amount": 100},
            prev_hash=GENESIS_HASH,
        )
        assert AuditHasher.verify(entry) is True

    def test_verify_tampered_payload(self):
        """Verify returns False if payload was modified after creation."""
        entry = AuditEntry.create(
            escrow_id=uuid.uuid4(),
            sequence_no=0,
            event_type="EscrowFunded",
            payload={"amount": 100},
            prev_hash=GENESIS_HASH,
        )
        # Tamper with the payload
        object.__setattr__(entry, "payload_json", '{"amount":999}')
        assert AuditHasher.verify(entry) is False


class TestAuditEntry:
    """AuditEntry creation and hash chain linkage."""

    def test_create_first_entry_uses_genesis_hash(self):
        """First entry in chain has prev_hash = GENESIS_HASH."""
        escrow_id = uuid.uuid4()
        entry = AuditEntry.create(
            escrow_id=escrow_id,
            sequence_no=0,
            event_type="EscrowDeployed",
            payload={"status": "deployed"},
            prev_hash=GENESIS_HASH,
        )
        assert entry.prev_hash.value == GENESIS_HASH
        assert entry.sequence_no.value == 0
        assert entry.event_type == "EscrowDeployed"
        assert entry.escrow_id == escrow_id

    def test_create_chained_entry(self):
        """Second entry links to first entry's hash."""
        escrow_id = uuid.uuid4()
        e1 = AuditEntry.create(
            escrow_id=escrow_id,
            sequence_no=0,
            event_type="EscrowDeployed",
            payload={"status": "deployed"},
            prev_hash=GENESIS_HASH,
        )
        e2 = AuditEntry.create(
            escrow_id=escrow_id,
            sequence_no=1,
            event_type="EscrowFunded",
            payload={"amount": 1000000},
            prev_hash=e1.entry_hash.value,
        )
        assert e2.prev_hash.value == e1.entry_hash.value
        assert e2.sequence_no.value == 1

    def test_payload_serialized_deterministically(self):
        """Payload dict is serialized with sorted keys and no whitespace."""
        entry = AuditEntry.create(
            escrow_id=uuid.uuid4(),
            sequence_no=0,
            event_type="Test",
            payload={"z_key": 1, "a_key": 2},
            prev_hash=GENESIS_HASH,
        )
        parsed = json.loads(entry.payload_json)
        assert parsed == {"a_key": 2, "z_key": 1}
        # No whitespace in compact serialization
        assert " " not in entry.payload_json

    def test_emit_appended_event(self):
        """emit_appended() returns correct domain event."""
        entry = AuditEntry.create(
            escrow_id=uuid.uuid4(),
            sequence_no=3,
            event_type="EscrowReleased",
            payload={"merkle": "abc"},
            prev_hash=GENESIS_HASH,
        )
        event = entry.emit_appended()
        assert event.sequence_no == 3
        assert event.audit_event_type == "EscrowReleased"
        assert event.entry_hash == entry.entry_hash.value


class TestAuditChainVerifier:
    """Full chain integrity verification."""

    def _build_chain(self, escrow_id: uuid.UUID, count: int) -> list[AuditEntry]:
        """Helper: build a valid chain of N entries."""
        entries = []
        prev = GENESIS_HASH
        for i in range(count):
            entry = AuditEntry.create(
                escrow_id=escrow_id,
                sequence_no=i,
                event_type=f"Event{i}",
                payload={"seq": i},
                prev_hash=prev,
            )
            entries.append(entry)
            prev = entry.entry_hash.value
        return entries

    def test_empty_chain_is_valid(self):
        """Empty chain is considered valid."""
        is_valid, bad_seq = AuditChainVerifier.verify([])
        assert is_valid is True
        assert bad_seq is None

    def test_single_entry_chain(self):
        """Single entry chain is valid if hash is correct."""
        chain = self._build_chain(uuid.uuid4(), 1)
        is_valid, bad_seq = AuditChainVerifier.verify(chain)
        assert is_valid is True
        assert bad_seq is None

    def test_valid_chain_three_entries(self):
        """Three-entry chain verifies correctly."""
        chain = self._build_chain(uuid.uuid4(), 3)
        is_valid, bad_seq = AuditChainVerifier.verify(chain)
        assert is_valid is True
        assert bad_seq is None

    def test_tampered_entry_detected(self):
        """Modifying a payload invalidates the chain."""
        chain = self._build_chain(uuid.uuid4(), 3)
        # Tamper with second entry's payload
        object.__setattr__(chain[1], "payload_json", '{"tampered":true}')
        is_valid, bad_seq = AuditChainVerifier.verify(chain)
        assert is_valid is False
        assert bad_seq == 1

    def test_broken_prev_hash_linkage(self):
        """Replacing an entry breaks chain linkage for subsequent entries."""
        chain = self._build_chain(uuid.uuid4(), 3)
        # Replace second entry's prev_hash with garbage
        object.__setattr__(chain[1], "prev_hash", HashValue(value="a" * 64))
        is_valid, bad_seq = AuditChainVerifier.verify(chain)
        assert is_valid is False
        assert bad_seq == 1

    def test_out_of_order_entries_verified_correctly(self):
        """Verifier sorts by sequence_no, so order doesn't matter."""
        chain = self._build_chain(uuid.uuid4(), 3)
        shuffled = [chain[2], chain[0], chain[1]]
        is_valid, bad_seq = AuditChainVerifier.verify(shuffled)
        assert is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# FEMA Record Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFEMARecord:
    """FEMA (Foreign Exchange Management Act) record generation."""

    def test_generate_form_15ca_below_threshold(self):
        """Amount below INR 5L → Form 15CA."""
        record = FEMARecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_pan="ABCDE1234F",
            seller_pan="GHIJK5678L",
            amount_microalgo=1_000_000,  # 1 ALGO
            fx_rate_inr_per_algo=Decimal("250.00"),  # 1 ALGO = 250 INR → 250 INR total
            merkle_root="a" * 64,
        )
        assert record.form_type == "15CA"
        assert record.amount_inr.value == Decimal("250.00")
        assert record.amount_algo == Decimal("1")
        assert record.buyer_pan.value == "ABCDE1234F"
        assert record.seller_pan.value == "GHIJK5678L"

    def test_generate_form_15cb_above_threshold(self):
        """Amount >= INR 5L → Form 15CB required."""
        record = FEMARecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_pan="ABCDE1234F",
            seller_pan="GHIJK5678L",
            amount_microalgo=10_000_000_000,  # 10,000 ALGO
            fx_rate_inr_per_algo=Decimal("250.00"),  # 10,000 * 250 = 2,500,000 INR
            merkle_root="b" * 64,
        )
        assert record.form_type == "15CB"
        assert record.amount_inr.value == Decimal("2500000.00")

    def test_generate_exact_threshold_uses_15cb(self):
        """Exactly INR 5,00,000 → 15CB (>= check)."""
        # 500_000 INR / 250 = 2000 ALGO = 2_000_000_000 microALGO
        record = FEMARecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_pan="ABCDE1234F",
            seller_pan="GHIJK5678L",
            amount_microalgo=2_000_000_000,
            fx_rate_inr_per_algo=Decimal("250.00"),
            merkle_root="c" * 64,
        )
        assert record.form_type == "15CB"
        assert record.amount_inr.value == Decimal("500000.00")

    def test_default_purpose_code(self):
        """Default purpose code is P0108 (MSME goods import)."""
        record = FEMARecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_pan="ABCDE1234F",
            seller_pan="GHIJK5678L",
            amount_microalgo=1_000_000,
            fx_rate_inr_per_algo=Decimal("100.00"),
            merkle_root="d" * 64,
        )
        assert record.purpose_code.value == "P0108"

    def test_custom_purpose_code(self):
        """Custom purpose code is preserved."""
        record = FEMARecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_pan="ABCDE1234F",
            seller_pan="GHIJK5678L",
            amount_microalgo=1_000_000,
            fx_rate_inr_per_algo=Decimal("100.00"),
            merkle_root="e" * 64,
            purpose_code="P0201",
        )
        assert record.purpose_code.value == "P0201"


# ═══════════════════════════════════════════════════════════════════════════════
# GST Record Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestGSTRecord:
    """GST (Goods and Services Tax) record generation."""

    def test_interstate_igst(self):
        """Different state codes → IGST @ 18%."""
        record = GSTRecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_gstin="27AAAAA0000A1Z5",   # State 27 (Maharashtra)
            seller_gstin="29BBBBB0000B1Z5",  # State 29 (Karnataka)
            hsn_code="8471",
            taxable_amount_inr=Decimal("100000"),
        )
        assert record.tax_type == "IGST"
        assert record.igst_amount.value == Decimal("18000.00")
        assert record.cgst_amount.value == Decimal("0")
        assert record.sgst_amount.value == Decimal("0")
        assert record.total_tax == Decimal("18000.00")

    def test_intrastate_cgst_sgst(self):
        """Same state codes → CGST 9% + SGST 9%."""
        record = GSTRecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_gstin="27AAAAA0000A1Z5",   # State 27
            seller_gstin="27CCCCC0000C1Z5",  # State 27 (same)
            hsn_code="8471",
            taxable_amount_inr=Decimal("100000"),
        )
        assert record.tax_type == "CGST_SGST"
        assert record.igst_amount.value == Decimal("0")
        assert record.cgst_amount.value == Decimal("9000.00")
        assert record.sgst_amount.value == Decimal("9000.00")
        assert record.total_tax == Decimal("18000.00")

    def test_total_tax_same_for_both_types(self):
        """Total tax is 18% regardless of interstate/intrastate."""
        base_amount = Decimal("50000")

        interstate = GSTRecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_gstin="27AAAAA0000A1Z5",
            seller_gstin="29BBBBB0000B1Z5",
            hsn_code="8471",
            taxable_amount_inr=base_amount,
        )
        intrastate = GSTRecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_gstin="27AAAAA0000A1Z5",
            seller_gstin="27CCCCC0000C1Z5",
            hsn_code="8471",
            taxable_amount_inr=base_amount,
        )
        assert interstate.total_tax == intrastate.total_tax

    def test_hsn_code_preserved(self):
        """HSN code is stored correctly."""
        record = GSTRecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_gstin="27AAAAA0000A1Z5",
            seller_gstin="29BBBBB0000B1Z5",
            hsn_code="84713010",
            taxable_amount_inr=Decimal("1000"),
        )
        assert record.hsn_code.value == "84713010"

    def test_small_amount_precision(self):
        """Paise-level precision is maintained for small amounts."""
        record = GSTRecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_gstin="27AAAAA0000A1Z5",
            seller_gstin="29BBBBB0000B1Z5",
            hsn_code="8471",
            taxable_amount_inr=Decimal("1.50"),
        )
        assert record.igst_amount.value == Decimal("0.27")
        assert record.taxable_amount.value == Decimal("1.50")


# ═══════════════════════════════════════════════════════════════════════════════
# Value Object Validation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestValueObjects:
    """Compliance domain value object validation."""

    # ── HashValue ──────────────────────────────────────────────────────────────

    def test_hash_value_valid(self):
        assert HashValue(value="a" * 64).value == "a" * 64

    def test_hash_value_invalid_length(self):
        with pytest.raises(ValidationError):
            HashValue(value="abc")

    def test_hash_value_invalid_chars(self):
        with pytest.raises(ValidationError):
            HashValue(value="G" * 64)  # uppercase not allowed

    # ── SequenceNumber ────────────────────────────────────────────────────────

    def test_sequence_number_valid(self):
        assert SequenceNumber(value=0).value == 0
        assert SequenceNumber(value=100).value == 100

    def test_sequence_number_negative_fails(self):
        with pytest.raises(ValidationError):
            SequenceNumber(value=-1)

    # ── PANNumber ─────────────────────────────────────────────────────────────

    def test_pan_valid(self):
        assert PANNumber(value="ABCDE1234F").value == "ABCDE1234F"

    def test_pan_lowercase_normalized(self):
        assert PANNumber(value="abcde1234f").value == "ABCDE1234F"

    def test_pan_invalid_format(self):
        with pytest.raises(ValidationError):
            PANNumber(value="12345ABCDE")

    def test_pan_wrong_length(self):
        with pytest.raises(ValidationError):
            PANNumber(value="ABC")

    # ── GSTIN ─────────────────────────────────────────────────────────────────

    def test_gstin_valid(self):
        g = GSTIN(value="27AAAAA0000A1Z5")
        assert g.value == "27AAAAA0000A1Z5"
        assert g.state_code == "27"

    def test_gstin_invalid_format(self):
        with pytest.raises(ValidationError):
            GSTIN(value="INVALID_GSTIN")

    def test_gstin_state_code_extraction(self):
        g = GSTIN(value="29BBBBB0000B1Z5")
        assert g.state_code == "29"

    # ── HSNCode ───────────────────────────────────────────────────────────────

    def test_hsn_4_digit(self):
        assert HSNCode(value="8471").value == "8471"

    def test_hsn_8_digit(self):
        assert HSNCode(value="84713010").value == "84713010"

    def test_hsn_3_digit_fails(self):
        with pytest.raises(ValidationError):
            HSNCode(value="847")

    def test_hsn_9_digit_fails(self):
        with pytest.raises(ValidationError):
            HSNCode(value="847130101")

    def test_hsn_non_numeric_fails(self):
        with pytest.raises(ValidationError):
            HSNCode(value="84AB")

    # ── INRAmount ─────────────────────────────────────────────────────────────

    def test_inr_amount_valid(self):
        assert INRAmount(value=Decimal("100.50")).value == Decimal("100.50")

    def test_inr_amount_zero(self):
        assert INRAmount(value=Decimal("0")).value == Decimal("0")

    def test_inr_amount_negative_fails(self):
        with pytest.raises(ValidationError):
            INRAmount(value=Decimal("-1"))

    # ── PurposeCode ───────────────────────────────────────────────────────────

    def test_purpose_code_valid(self):
        assert PurposeCode(value="P0108").value == "P0108"

    def test_purpose_code_lowercase_normalized(self):
        assert PurposeCode(value="p0108").value == "P0108"

    def test_purpose_code_invalid_format(self):
        with pytest.raises(ValidationError):
            PurposeCode(value="X1234")

    def test_purpose_code_default_constant(self):
        assert PurposeCode.DEFAULT == "P0108"


# ═══════════════════════════════════════════════════════════════════════════════
# Exporter Tests (PDF / CSV / ZIP)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFEMAGSTExporter:
    """FEMA PDF and GST CSV export tests."""

    def test_export_fema_pdf_returns_bytes(self):
        """PDF export returns non-empty bytes."""
        from src.compliance.infrastructure.fema_gst_exporter import FEMAGSTExporter

        exporter = FEMAGSTExporter()
        record = FEMARecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_pan="ABCDE1234F",
            seller_pan="GHIJK5678L",
            amount_microalgo=1_000_000,
            fx_rate_inr_per_algo=Decimal("100.00"),
            merkle_root="a" * 64,
        )
        pdf_bytes = exporter.export_fema_pdf(record)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # Should start with %PDF header (if reportlab available) or our fallback
        assert pdf_bytes[:5] in (b"%PDF-", b"%PDF-")

    def test_export_gst_csv_format(self):
        """CSV export has correct headers and data rows."""
        from src.compliance.infrastructure.fema_gst_exporter import FEMAGSTExporter

        exporter = FEMAGSTExporter()
        record = GSTRecord.generate(
            escrow_id=uuid.uuid4(),
            buyer_gstin="27AAAAA0000A1Z5",
            seller_gstin="29BBBBB0000B1Z5",
            hsn_code="8471",
            taxable_amount_inr=Decimal("100000"),
        )
        csv_bytes = exporter.export_gst_csv([record])
        assert isinstance(csv_bytes, bytes)

        # Strip BOM and parse
        csv_text = csv_bytes.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Header row + 1 data row
        assert len(rows) == 2
        assert "Escrow ID" in rows[0][0]
        assert rows[1][4] == "IGST"  # Tax Type column
        assert rows[1][6] == "18000.00"  # IGST Amount

    def test_export_gst_csv_multiple_records(self):
        """CSV export handles multiple records."""
        from src.compliance.infrastructure.fema_gst_exporter import FEMAGSTExporter

        exporter = FEMAGSTExporter()
        records = [
            GSTRecord.generate(
                escrow_id=uuid.uuid4(),
                buyer_gstin="27AAAAA0000A1Z5",
                seller_gstin="29BBBBB0000B1Z5",
                hsn_code="8471",
                taxable_amount_inr=Decimal("1000"),
            )
            for _ in range(5)
        ]
        csv_bytes = exporter.export_gst_csv(records)
        csv_text = csv_bytes.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(csv_text)))
        assert len(rows) == 6  # header + 5 data rows

    def test_build_zip_contains_manifest(self):
        """ZIP export contains manifest.json with correct structure."""
        import zipfile

        from src.compliance.infrastructure.fema_gst_exporter import FEMAGSTExporter

        exporter = FEMAGSTExporter()
        escrow_id = uuid.uuid4()

        fema = FEMARecord.generate(
            escrow_id=escrow_id,
            buyer_pan="ABCDE1234F",
            seller_pan="GHIJK5678L",
            amount_microalgo=1_000_000,
            fx_rate_inr_per_algo=Decimal("100.00"),
            merkle_root="a" * 64,
        )
        gst = GSTRecord.generate(
            escrow_id=escrow_id,
            buyer_gstin="27AAAAA0000A1Z5",
            seller_gstin="29BBBBB0000B1Z5",
            hsn_code="8471",
            taxable_amount_inr=Decimal("10000"),
        )

        zip_bytes = exporter.build_zip([fema], [gst])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert f"fema/{escrow_id}.pdf" in names
            assert "gst/gst_records.csv" in names
            assert f"audit/{escrow_id}.json" in names

            manifest = json.loads(zf.read("manifest.json"))
            assert manifest["escrow_count"] == 1
            assert str(escrow_id) in manifest["escrow_ids"]


# ═══════════════════════════════════════════════════════════════════════════════
# GENESIS_HASH Constant Test
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenesisHash:
    def test_genesis_hash_format(self):
        """GENESIS_HASH is exactly 64 zero characters."""
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64
