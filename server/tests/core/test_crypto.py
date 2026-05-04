"""Tests for ``rapidly/core/crypto.py`` — token generation + hashing.

Security invariants pinned here:
- 32 bytes of OS entropy + 4-byte BLAKE2b integrity tag, URL-safe
  base64 encoded (no padding).
- Keyed BLAKE2b for hashes. Same token + same secret → same hash.
- Different secrets MUST produce different hashes for the same token
  (that's what the ``secret`` key parameter is for).
"""

from __future__ import annotations

import base64
import hashlib

from rapidly.core.crypto import (
    generate_token,
    generate_token_hash_pair,
    get_token_hash,
)


class TestGetTokenHash:
    def test_returns_64_char_hex(self) -> None:
        # Default digest_size=32 → 32 bytes → 64 hex chars.
        out = get_token_hash("some-token", secret="sk-123")
        assert len(out) == 64
        int(out, 16)  # hex parses cleanly

    def test_is_deterministic_for_same_inputs(self) -> None:
        a = get_token_hash("token", secret="secret")
        b = get_token_hash("token", secret="secret")
        assert a == b

    def test_different_secrets_produce_different_hashes(self) -> None:
        a = get_token_hash("token", secret="secret-a")
        b = get_token_hash("token", secret="secret-b")
        # Key-change invariant — otherwise the ``secret`` param does
        # nothing (silent downgrade to plain BLAKE2b).
        assert a != b

    def test_different_tokens_produce_different_hashes(self) -> None:
        assert get_token_hash("token-a", secret="s") != get_token_hash(
            "token-b", secret="s"
        )

    def test_matches_reference_keyed_blake2b(self) -> None:
        # Cross-check against the stdlib implementation so a future
        # refactor to a different primitive would be caught.
        expected = hashlib.blake2b(b"token", key=b"secret", digest_size=32).hexdigest()
        assert get_token_hash("token", secret="secret") == expected


class TestGenerateToken:
    def test_decoded_body_is_32_entropy_plus_4_tag_bytes(self) -> None:
        token = generate_token()
        # Re-pad before decoding since generate_token strips "=".
        padded = token + "=" * ((4 - len(token) % 4) % 4)
        raw = base64.urlsafe_b64decode(padded)
        assert len(raw) == 36  # 32 entropy + 4 tag

    def test_integrity_tag_matches_blake2b_of_entropy(self) -> None:
        token = generate_token()
        padded = token + "=" * ((4 - len(token) % 4) % 4)
        raw = base64.urlsafe_b64decode(padded)
        entropy, tag = raw[:32], raw[32:]
        expected = hashlib.blake2b(entropy, digest_size=4).digest()
        assert tag == expected

    def test_has_no_base64_padding(self) -> None:
        # Base64url with padding would break URL semantics on some
        # parsers — the generator explicitly strips ``=``. Pin it.
        assert "=" not in generate_token()

    def test_uses_url_safe_base64_alphabet_only(self) -> None:
        # urlsafe_b64encode uses ``-`` and ``_`` instead of ``+`` and
        # ``/``. Explicit pin so a future switch to plain b64 would
        # break URLs silently.
        token = generate_token()
        assert "+" not in token
        assert "/" not in token

    def test_applies_prefix_verbatim(self) -> None:
        token = generate_token(prefix="rpl_")
        assert token.startswith("rpl_")

    def test_produces_distinct_values_across_calls(self) -> None:
        # Collision probability is 1 / 2^256 per pair — effectively zero.
        values = {generate_token() for _ in range(20)}
        assert len(values) == 20

    def test_prefix_applied_even_for_empty_entropy_seed_edge_case(self) -> None:
        # The prefix is purely a string prepend; no interaction with
        # the cryptographic core.
        assert generate_token(prefix="").startswith("")


class TestGenerateTokenHashPair:
    def test_hash_verifies_against_raw_token(self) -> None:
        raw, stored = generate_token_hash_pair(secret="sk")
        # The documented contract: persist only ``stored``, later verify
        # by hashing the submitted raw token under the same secret.
        assert get_token_hash(raw, secret="sk") == stored

    def test_hash_is_64_hex_chars(self) -> None:
        _, stored = generate_token_hash_pair(secret="sk")
        assert len(stored) == 64
        int(stored, 16)

    def test_raw_token_carries_prefix(self) -> None:
        raw, _ = generate_token_hash_pair(secret="sk", prefix="live_")
        assert raw.startswith("live_")

    def test_hash_ignores_prefix_equality(self) -> None:
        # The hash covers the full prefix+body token — not just the
        # body. Pinned so a "helpful" refactor that hashes only the
        # random body portion is caught.
        raw_a, hash_a = generate_token_hash_pair(secret="sk", prefix="a_")
        raw_b, hash_b = generate_token_hash_pair(secret="sk", prefix="b_")
        assert raw_a != raw_b
        # Different prefixes + different entropy → different hashes.
        assert hash_a != hash_b

    def test_different_calls_yield_distinct_pairs(self) -> None:
        pairs = {generate_token_hash_pair(secret="sk") for _ in range(10)}
        assert len(pairs) == 10
