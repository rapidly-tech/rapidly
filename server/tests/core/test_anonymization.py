"""Tests for ``rapidly/core/anonymization.py`` — PII anonymisation
before hard deletion. Two invariants matter:
  - Hashes are deterministic (same PII in → same anonymised form out),
    so the irreversible transform can still be verified idempotent.
  - Anonymised emails go to a non-routable domain (``redacted.invalid``)
    so no anonymised record can accidentally receive mail.
"""

from __future__ import annotations

import hashlib

import pytest

from rapidly.core.anonymization import (
    ANONYMIZED_EMAIL_DOMAIN,
    anonymize_email_for_deletion,
    anonymize_for_deletion,
    sha256_digest,
)


class TestSha256Digest:
    def test_hex_length_is_64(self) -> None:
        assert len(sha256_digest("hello")) == 64

    def test_is_deterministic_for_the_same_input(self) -> None:
        assert sha256_digest("user@example.com") == sha256_digest("user@example.com")

    def test_different_inputs_produce_different_hashes(self) -> None:
        assert sha256_digest("a") != sha256_digest("b")

    def test_matches_the_stdlib_reference(self) -> None:
        ref = hashlib.sha256(b"probe").hexdigest()
        assert sha256_digest("probe") == ref

    def test_handles_unicode_input(self) -> None:
        # UTF-8 encoding is explicit in the implementation — non-ASCII
        # inputs must not raise.
        assert len(sha256_digest("café")) == 64
        assert len(sha256_digest("🔒")) == 64


class TestAnonymizeForDeletion:
    def test_is_an_alias_for_sha256_digest(self) -> None:
        # Pinning the alias ensures legacy callers importing the old name
        # keep working.
        assert anonymize_for_deletion is sha256_digest


class TestAnonymizeEmailForDeletion:
    def test_returns_hash_at_redacted_invalid_domain(self) -> None:
        out = anonymize_email_for_deletion("alice@example.com")
        local, _, domain = out.partition("@")
        assert len(local) == 64  # SHA-256 hex
        assert domain == ANONYMIZED_EMAIL_DOMAIN == "redacted.invalid"

    def test_is_deterministic_for_the_same_email(self) -> None:
        assert anonymize_email_for_deletion(
            "alice@example.com"
        ) == anonymize_email_for_deletion("alice@example.com")

    def test_different_emails_produce_different_anonymised_addresses(
        self,
    ) -> None:
        a = anonymize_email_for_deletion("alice@example.com")
        b = anonymize_email_for_deletion("bob@example.com")
        assert a != b

    def test_asserts_on_input_without_at_sign(self) -> None:
        with pytest.raises(AssertionError):
            anonymize_email_for_deletion("no-at-sign")

    def test_preserves_full_local_part_when_hashing(self) -> None:
        # The hash covers the ENTIRE email (local + domain), not just
        # the local part — this pinning prevents a refactor where
        # someone "optimises" by hashing only one side.
        full = anonymize_email_for_deletion("alice@example.com")
        local, _, _ = full.partition("@")
        assert local == sha256_digest("alice@example.com")
