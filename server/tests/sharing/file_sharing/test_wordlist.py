"""Tests for ``rapidly/sharing/file_sharing/wordlist.py``.

The wordlist size is a hard **security invariant** — the module
docstring claims 128 words × 7-word slugs ≈ 49 bits of entropy. Any
change to the count silently alters the brute-force hardness of every
long-slug channel. Pin it.
"""

from __future__ import annotations

import re

from rapidly.sharing.file_sharing.wordlist import TOPPINGS


class TestToppings:
    def test_contains_exactly_128_words(self) -> None:
        # 128 is load-bearing: the docstring derives slug entropy from
        # it; slug generators hard-code the 7-word count against it.
        # Any drift must be a conscious + auditable change.
        assert len(TOPPINGS) == 128

    def test_every_entry_is_a_non_empty_string(self) -> None:
        for word in TOPPINGS:
            assert isinstance(word, str)
            assert word, f"empty entry in TOPPINGS: {word!r}"

    def test_words_are_lowercase(self) -> None:
        # URL-safe property: slugs are built via "/".join(TOPPINGS) and
        # end up in hash URLs. Uppercase would cause the ``SAFE_SLUG``
        # regex (lowercase-only) on the frontend to reject legit links.
        for word in TOPPINGS:
            assert word == word.lower(), word

    def test_words_are_url_safe_alphanumeric_only(self) -> None:
        # No hyphens / underscores / dots — slugs use ``/`` as separator
        # and SAFE_SLUG on the frontend accepts only a-z 0-9 - and /.
        url_safe = re.compile(r"^[a-z0-9]+$")
        for word in TOPPINGS:
            assert url_safe.match(word), word

    def test_no_duplicates(self) -> None:
        # Duplicates would effectively shrink the keyspace below the
        # documented 128-word size.
        assert len(set(TOPPINGS)) == len(TOPPINGS)

    def test_list_is_a_plain_list_type(self) -> None:
        # ``secrets.choice`` works on any sequence, but downstream code
        # may rely on list semantics (indexing, len) so pin the type.
        assert isinstance(TOPPINGS, list)
