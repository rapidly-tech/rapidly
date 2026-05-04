"""Tests for ``rapidly/integrations/aws/s3/types.py``.

Two load-bearing surfaces had no coverage:

1. ``sanitize_filename`` — the module docstring advertises
   "filename sanitisation to prevent path traversal attacks". It
   feeds every ``S3FileCreate.name`` via a mode=before field
   validator. A regression here is a path-traversal surface into
   the S3 bucket.

2. ``S3FileUploadCompleted.generate_base64_multipart_checksum`` —
   S3 multipart uploads use a COMPOSITE checksum (hash of the
   concatenated per-part digests, NOT the hash of the whole file).
   Getting this wrong corrupts upload verification silently:
   boto3 accepts the upload, the checksum mismatch surfaces only
   later when a reader validates.
"""

from __future__ import annotations

import base64
import hashlib

import pytest

from rapidly.integrations.aws.s3.types import (
    S3FileCreate,
    S3FileUploadCompleted,
    get_downloadable_content_disposition,
    sanitize_filename,
)


class TestSanitizeFilename:
    def test_strips_dotdot_path_traversal(self) -> None:
        # The documented attack: ``../etc/passwd`` must not survive
        # past the sanitiser. The ``while ".." in cleaned`` loop
        # handles nested ``....//`` sequences too.
        assert ".." not in sanitize_filename("../../etc/passwd")

    def test_collapses_nested_dotdot_sequences(self) -> None:
        # ``....//`` — after a single replace this leaves ``../``,
        # so the loop must iterate until no ``..`` remains.
        assert ".." not in sanitize_filename("..../report.pdf")
        assert ".." not in sanitize_filename("...../a")

    @pytest.mark.parametrize(
        "dangerous",
        [
            "a/b.pdf",  # forward slash
            "a\\b.pdf",  # backslash (Windows path)
            "a:b.pdf",  # drive letter
            "a*b.pdf",  # glob
            "a?b.pdf",  # query
            'a"b.pdf',  # quote
            "a<b.pdf",  # html
            "a>b.pdf",
            "a|b.pdf",
        ],
    )
    def test_strips_dangerous_shell_and_path_chars(self, dangerous: str) -> None:
        result = sanitize_filename(dangerous)
        for c in '/\\:*?"<>|':
            assert c not in result

    def test_strips_control_characters(self) -> None:
        # NUL byte + other C0 controls are a known smuggling
        # vector on some filesystems / presigned-URL parsers.
        assert sanitize_filename("a\x00b\x01c\x7fd") == "abcd"

    def test_strips_surrounding_whitespace(self) -> None:
        assert sanitize_filename("   report.pdf   ") == "report.pdf"

    def test_truncates_to_255_chars(self) -> None:
        # S3 key segments + OS filename limits are ~255 bytes.
        # Truncation happens AFTER the other sanitisation steps.
        result = sanitize_filename("a" * 500)
        assert len(result) == 255

    def test_empty_name_becomes_unnamed_file(self) -> None:
        # The documented fallback — a caller submitting only
        # sanitisable content (``"///"``) still gets a valid name.
        assert sanitize_filename("") == "unnamed_file"
        assert sanitize_filename("///") == "unnamed_file"
        assert sanitize_filename("    ") == "unnamed_file"


class TestS3FileCreateWiring:
    def _body(self, name: str) -> dict[str, object]:
        return {
            "name": name,
            "mime_type": "application/pdf",
            "size": 1,
            "upload": {"parts": [{"number": 1, "chunk_start": 0, "chunk_end": 1}]},
        }

    def test_name_is_sanitised_at_validation(self) -> None:
        # Wired via ``@field_validator("name", mode="before")`` —
        # the sanitised value must reach the model, not the raw one.
        obj = S3FileCreate.model_validate(self._body("../../../etc/passwd"))
        assert ".." not in obj.name
        assert "/" not in obj.name


class TestContentDispositionEscaping:
    def test_escapes_embedded_quote(self) -> None:
        # A filename containing ``"`` would otherwise break out of
        # the ``filename="..."`` parameter in the Content-Disposition
        # header and let the caller inject arbitrary header params.
        # The escape rule: every inner ``"`` becomes ``\"``; the
        # outer quotes around the whole filename remain.
        header = get_downloadable_content_disposition('ab"cd')
        assert header == r'attachment; filename="ab\"cd"'

    def test_escapes_multiple_embedded_quotes(self) -> None:
        header = get_downloadable_content_disposition('a"b"c')
        assert header == r'attachment; filename="a\"b\"c"'

    def test_wraps_in_attachment_filename(self) -> None:
        assert (
            get_downloadable_content_disposition("report.pdf")
            == 'attachment; filename="report.pdf"'
        )


class TestCompositeMultipartChecksum:
    def test_matches_spec_formula(self) -> None:
        # S3 multipart checksum = sha256(digest_1 || digest_2 || ...)
        # base64-encoded. Reimplementing the reference formula here
        # catches any refactor that silently changes the algorithm
        # (e.g. hashing the hex-strings instead of the raw bytes).
        d1 = hashlib.sha256(b"part-one").digest()
        d2 = hashlib.sha256(b"part-two").digest()

        got = S3FileUploadCompleted.generate_base64_multipart_checksum([d1, d2])
        expected = base64.b64encode(hashlib.sha256(d1 + d2).digest()).decode()
        assert got == expected

    def test_single_part_returns_hash_of_that_part_digest(self) -> None:
        # Edge case: even with one part, the S3 composite checksum
        # hashes the digest, NOT the part bytes.
        d1 = hashlib.sha256(b"only-part").digest()
        got = S3FileUploadCompleted.generate_base64_multipart_checksum([d1])
        expected = base64.b64encode(hashlib.sha256(d1).digest()).decode()
        assert got == expected

    def test_empty_list_hashes_empty_bytes(self) -> None:
        # No-parts edge case — defensive: must not raise. The
        # upstream caller gates on ``digest_accumulator`` to avoid
        # this path in practice, but the helper itself must remain
        # total.
        got = S3FileUploadCompleted.generate_base64_multipart_checksum([])
        expected = base64.b64encode(hashlib.sha256(b"").digest()).decode()
        assert got == expected
