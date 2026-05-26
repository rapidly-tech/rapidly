"""Tests for the RAG chunker."""

from __future__ import annotations

import pytest

from rapidly.agents.rag.chunkers import (
    DEFAULT_MAX_CHARS,
    UnsupportedMimeError,
    chunk_for_mime,
    chunk_text,
)


class TestChunkText:
    def test_empty_input_returns_empty_list(self) -> None:
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert chunk_text("   \n\n  \n") == []

    def test_short_text_returns_single_chunk(self) -> None:
        out = chunk_text("hello world")
        assert out == ["hello world"]

    def test_paragraphs_grouped_until_cap(self) -> None:
        # Three paragraphs that fit together stay one chunk.
        text = "para one.\n\npara two.\n\npara three."
        out = chunk_text(text, max_chars=100, overlap=10)
        assert out == ["para one.\n\npara two.\n\npara three."]

    def test_paragraphs_split_at_cap(self) -> None:
        # Two paragraphs that don't fit together get split.
        text = ("a" * 80) + "\n\n" + ("b" * 80)
        out = chunk_text(text, max_chars=100, overlap=10)
        assert len(out) == 2
        assert out[0] == "a" * 80
        assert out[1] == "b" * 80

    def test_long_paragraph_gets_char_split_with_overlap(self) -> None:
        # A single oversize paragraph gets character-level split
        # with overlap repeated.
        text = "x" * 250
        out = chunk_text(text, max_chars=100, overlap=20)
        # Step is 80; positions 0, 80, 160 → 3 chunks.
        assert len(out) == 3
        assert out[0] == "x" * 100
        assert out[1] == "x" * 100
        # Last chunk is the tail.
        assert out[2] == "x" * 90

    def test_rejects_negative_overlap(self) -> None:
        with pytest.raises(ValueError, match="overlap must be >= 0"):
            chunk_text("hi there", overlap=-1)

    def test_rejects_overlap_at_or_above_cap(self) -> None:
        with pytest.raises(ValueError, match="overlap must be < max_chars"):
            chunk_text("hi there", max_chars=10, overlap=10)

    def test_rejects_zero_max_chars(self) -> None:
        with pytest.raises(ValueError, match="max_chars must be >= 1"):
            chunk_text("hi there", max_chars=0)

    def test_default_max_chars_is_documented_constant(self) -> None:
        # Lock in the default — calibrated against embedding model
        # context limits. Changing it shifts indexed shape for
        # every collection so the change should be deliberate.
        assert DEFAULT_MAX_CHARS == 1500


class TestChunkForMime:
    def test_text_plain_dispatches_to_chunk_text(self) -> None:
        out = chunk_for_mime("text/plain", b"hello")
        assert out == ["hello"]

    def test_text_markdown_is_supported(self) -> None:
        out = chunk_for_mime("text/markdown", b"# Header\n\nBody.")
        assert out == ["# Header\n\nBody."]

    def test_application_json_is_supported(self) -> None:
        out = chunk_for_mime("application/json", b'{"a": 1}')
        assert out == ['{"a": 1}']

    def test_rejects_pdf(self) -> None:
        with pytest.raises(UnsupportedMimeError, match="application/pdf"):
            chunk_for_mime("application/pdf", b"%PDF-1.4 ...")

    def test_rejects_binary_decode_failure(self) -> None:
        with pytest.raises(UnsupportedMimeError, match="non-utf-8"):
            chunk_for_mime("text/plain", b"\xff\xfe\x00\x00")
