"""Tests for ``rapidly/sharing/file_sharing/slugs.py`` — slug + secret
generators that back channel identification and ownership. The entropy
documented in the module's comments is a security invariant: pinning
the output shape prevents a silent regression that'd weaken channel
guessability."""

from __future__ import annotations

import re
import uuid

from rapidly.sharing.file_sharing.slugs import (
    LONG_SLUG_NUM_WORDS,
    generate_long_slug,
    generate_secret,
    generate_short_slug,
)
from rapidly.sharing.file_sharing.wordlist import TOPPINGS


class TestGenerateShortSlug:
    def test_returns_a_valid_uuid_string(self) -> None:
        slug = generate_short_slug()
        # UUID constructor raises on malformed input, so a successful
        # parse is the strongest assertion available.
        uuid.UUID(slug)

    def test_returns_the_canonical_36_char_form_with_four_hyphens(
        self,
    ) -> None:
        slug = generate_short_slug()
        assert len(slug) == 36
        assert slug.count("-") == 4

    def test_produces_distinct_values_across_calls(self) -> None:
        values = {generate_short_slug() for _ in range(10)}
        assert len(values) == 10


class TestGenerateLongSlug:
    def test_contains_the_documented_number_of_slash_separated_words(
        self,
    ) -> None:
        slug = generate_long_slug()
        parts = slug.split("/")
        assert len(parts) == LONG_SLUG_NUM_WORDS == 7

    def test_every_word_comes_from_the_TOPPINGS_wordlist(self) -> None:
        # Pinning this invariant catches "fix" regressions where someone
        # accidentally adds non-wordlist sources (e.g. adjectives) that
        # would either break parsing or widen the keyspace by an
        # off-by-one amount.
        toppings = set(TOPPINGS)
        for _ in range(20):
            for word in generate_long_slug().split("/"):
                assert word in toppings

    def test_generates_different_slugs_across_calls(self) -> None:
        # Collision probability is 1 / 128^7 per pair — effectively zero
        # across 20 samples.
        values = {generate_long_slug() for _ in range(20)}
        assert len(values) == 20


class TestGenerateSecret:
    _HEX_64 = re.compile(r"^[0-9a-f]{64}$")

    def test_returns_a_64_char_lowercase_hex_string(self) -> None:
        secret = generate_secret()
        assert self._HEX_64.match(secret), secret

    def test_produces_distinct_values_across_calls(self) -> None:
        values = {generate_secret() for _ in range(20)}
        assert len(values) == 20

    def test_encodes_256_bits_of_entropy(self) -> None:
        # 64 hex chars × 4 bits each = 256 bits. Documentation invariant
        # — changing ``token_hex(32)`` to ``token_hex(16)`` would drop
        # entropy by half without any other signal.
        secret = generate_secret()
        assert len(secret) * 4 == 256
