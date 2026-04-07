"""
Unit tests for identity domain value objects.

context.md §19: TC validation coverage for PAN, GSTIN, AlgorandAddress.
context.md §15: domain/ ≥ 90% line coverage.
"""

import pytest

from src.identity.domain.value_objects import (
    AlgorandAddress,
    Email,
    GSTIN,
    HashedAPIKey,
    HashedPassword,
    PAN,
)
from src.shared.domain.exceptions import ValidationError


# ── PAN ───────────────────────────────────────────────────────────────────────


class TestPAN:
    def test_valid_pan(self):
        pan = PAN(value="ABCDE1234F")
        assert pan.value == "ABCDE1234F"

    def test_pan_rejects_lowercase(self):
        with pytest.raises(ValidationError, match="Invalid PAN format"):
            PAN(value="abcde1234f")

    def test_pan_rejects_short_string(self):
        with pytest.raises(ValidationError, match="Invalid PAN format"):
            PAN(value="ABC12")

    def test_pan_rejects_wrong_format(self):
        with pytest.raises(ValidationError, match="Invalid PAN format"):
            PAN(value="12345ABCDE")

    def test_pan_rejects_empty(self):
        with pytest.raises(ValidationError, match="Invalid PAN format"):
            PAN(value="")

    def test_pan_equality(self):
        assert PAN(value="ABCDE1234F") == PAN(value="ABCDE1234F")


# ── GSTIN ─────────────────────────────────────────────────────────────────────


class TestGSTIN:
    def test_valid_gstin(self):
        gstin = GSTIN(value="27ABCDE1234F1Z5")
        assert gstin.value == "27ABCDE1234F1Z5"

    def test_gstin_rejects_invalid_format(self):
        with pytest.raises(ValidationError, match="Invalid GSTIN format"):
            GSTIN(value="INVALIDGSTIN")

    def test_gstin_rejects_short(self):
        with pytest.raises(ValidationError, match="Invalid GSTIN format"):
            GSTIN(value="27ABCDE")

    def test_gstin_rejects_no_state_code(self):
        with pytest.raises(ValidationError, match="Invalid GSTIN format"):
            GSTIN(value="XXABCDE1234F1Z5")

    def test_gstin_equality(self):
        assert GSTIN(value="27ABCDE1234F1Z5") == GSTIN(value="27ABCDE1234F1Z5")


# ── AlgorandAddress ───────────────────────────────────────────────────────────


class TestAlgorandAddress:
    def test_valid_address(self):
        addr = "A" * 58
        result = AlgorandAddress(value=addr)
        assert result.value == addr

    def test_rejects_lowercase(self):
        with pytest.raises(ValidationError, match="Invalid Algorand address"):
            AlgorandAddress(value="a" * 58)

    def test_rejects_short(self):
        with pytest.raises(ValidationError, match="Invalid Algorand address"):
            AlgorandAddress(value="ABCD2345")

    def test_rejects_invalid_chars(self):
        # Algorand base32 uses A-Z and 2-7 only; 0, 1, 8, 9 are invalid
        with pytest.raises(ValidationError, match="Invalid Algorand address"):
            AlgorandAddress(value="0" * 58)

    def test_valid_base32_chars(self):
        # A-Z2-7 are all valid
        addr = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        result = AlgorandAddress(value=addr)
        assert len(result.value) == 58


# ── Email ─────────────────────────────────────────────────────────────────────


class TestEmail:
    def test_valid_email(self):
        email = Email(value="user@example.com")
        assert email.value == "user@example.com"

    def test_normalises_to_lowercase(self):
        email = Email(value="User@Example.COM")
        assert email.value == "user@example.com"

    def test_strips_whitespace(self):
        email = Email(value="  user@example.com  ")
        assert email.value == "user@example.com"

    def test_rejects_no_at(self):
        with pytest.raises(ValidationError, match="Invalid email"):
            Email(value="userexample.com")


# ── HashedPassword ────────────────────────────────────────────────────────────


class TestHashedPassword:
    def test_hash_and_verify(self):
        hp = HashedPassword.from_plaintext("SecurePass123!")
        assert hp.verify("SecurePass123!")
        assert not hp.verify("WrongPassword")

    def test_hash_is_not_plaintext(self):
        hp = HashedPassword.from_plaintext("MySecret")
        assert hp.value != "MySecret"
        assert hp.value.startswith("$2b$")


# ── HashedAPIKey ──────────────────────────────────────────────────────────────


class TestHashedAPIKey:
    def test_hash_and_verify(self):
        raw = "cad_live_api_key_12345"
        secret = "test-secret"
        hk = HashedAPIKey.from_raw(raw, secret)
        assert hk.verify(raw, secret)
        assert not hk.verify("wrong_key", secret)

    def test_different_secrets_produce_different_hashes(self):
        raw = "same_key"
        h1 = HashedAPIKey.from_raw(raw, "secret1")
        h2 = HashedAPIKey.from_raw(raw, "secret2")
        assert h1.value != h2.value
