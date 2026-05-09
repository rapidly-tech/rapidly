"""Tests for ``rapidly/catalog/file/magic.py``.

Magic-byte validation — defence against MIME-type spoofing attacks.
This is the security companion to ClamAV: ClamAV catches known
malware, magic-byte validation catches content-type spoofs that
would let an attacker upload an executable disguised as a PNG.

Six load-bearing surfaces:

- Common-format signatures (PNG, JPEG, PDF, ZIP) — drift in any
  of these silently misclassifies legitimate uploads as spoofs
  (false-positive quarantine).
- RIFF-format disambiguation: WebP / WAV / AVI all start with
  ``RIFF`` but differ at offset 8. A regression to plain
  prefix-match would let any RIFF file pass as any of the three.
- MP4/QuickTime/M4A ``ftyp`` atom check at offset 4 — without
  the offset, a regression would mis-validate or never match.
- TAR signature lives at offset 257 (NOT at the start). Drift
  would make every TAR upload register as a spoof.
- ``SKIP_VALIDATION_MIMES`` — text/* + JSON + SVG + octet-stream
  always pass. A regression that skipped this set would crash
  every text upload because there are no magic bytes for them.
- ``strict=True`` raises ``MimeTypeMismatchError`` carrying both
  declared + detected types so the SOC can triage; ``strict=False``
  returns ``(False, detected)`` for non-blocking inspection.
"""

from __future__ import annotations

import pytest

from rapidly.catalog.file.magic import (
    MAGIC_SIGNATURES,
    SKIP_VALIDATION_MIMES,
    TEXT_BASED_MIMES,
    MagicSignature,
    MimeTypeMismatchError,
    _check_signature,
    _detect_mime_type,
    _is_avi,
    _is_mp4_compatible,
    _is_wav,
    _is_webp,
    validate_magic_bytes,
)

# Real magic-byte prefixes used as test fixtures.
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF"
GIF87A = b"GIF87a"
GIF89A = b"GIF89a"
PDF_HEADER = b"%PDF-1.5\n"
ZIP_HEADER = b"PK\x03\x04"
GZIP_HEADER = b"\x1f\x8b\x08"
RIFF_PREFIX = b"RIFF\x00\x00\x00\x00"
WEBP_FILE = RIFF_PREFIX + b"WEBP" + b"\x00" * 16
WAV_FILE = RIFF_PREFIX + b"WAVE" + b"\x00" * 16
AVI_FILE = RIFF_PREFIX + b"AVI " + b"\x00" * 16
MP4_FILE = b"\x00\x00\x00\x18ftyp" + b"isom" + b"\x00" * 16


class TestSkipValidationMimes:
    def test_text_based_mimes_subset_pinned(self) -> None:
        # Pin: the documented text-based set. Adding a binary
        # type here would silently disable magic-byte checking
        # for it — opens the spoof vector this module guards.
        assert "text/plain" in TEXT_BASED_MIMES
        assert "text/csv" in TEXT_BASED_MIMES
        assert "application/json" in TEXT_BASED_MIMES
        assert "image/svg+xml" in TEXT_BASED_MIMES

    def test_skip_set_includes_octet_stream(self) -> None:
        # Pin: ``application/octet-stream`` is the generic-binary
        # default; we can't validate it (no specific signature).
        assert "application/octet-stream" in SKIP_VALIDATION_MIMES

    def test_skip_validation_returns_clean(self) -> None:
        # Pin: every MIME in the skip set passes validation
        # without inspecting bytes — preserves text-upload UX.
        for mime in SKIP_VALIDATION_MIMES:
            ok, detected = validate_magic_bytes(b"", mime, strict=True)
            assert ok is True
            assert detected == mime


class TestPngSignature:
    def test_valid_png_passes(self) -> None:
        ok, detected = validate_magic_bytes(PNG_HEADER + b"x" * 100, "image/png")
        assert ok is True
        assert detected == "image/png"

    def test_jpeg_bytes_declared_as_png_raises(self) -> None:
        # The classic spoof: declare PNG, send JPEG (or worse, EXE).
        # Pin the strict-raise path AND the captured types.
        with pytest.raises(MimeTypeMismatchError) as exc:
            validate_magic_bytes(JPEG_HEADER, "image/png")
        assert exc.value.declared_type == "image/png"
        assert exc.value.detected_type == "image/jpeg"

    def test_truncated_data_raises(self) -> None:
        # Pin: bytes shorter than the signature don't crash on
        # index — they fail validation cleanly.
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(b"\x89P", "image/png")


class TestJpegSignature:
    def test_valid_jpeg_passes(self) -> None:
        ok, detected = validate_magic_bytes(JPEG_HEADER, "image/jpeg")
        assert ok is True
        assert detected == "image/jpeg"


class TestGifSignature:
    def test_gif87a_passes(self) -> None:
        ok, _ = validate_magic_bytes(GIF87A + b"\x00" * 50, "image/gif")
        assert ok is True

    def test_gif89a_passes(self) -> None:
        # Pin: BOTH GIF89a and GIF87a are valid GIF magic. Drift
        # to only one variant breaks ~half of legitimate GIFs.
        ok, _ = validate_magic_bytes(GIF89A + b"\x00" * 50, "image/gif")
        assert ok is True


class TestPdfSignature:
    def test_valid_pdf_passes(self) -> None:
        ok, _ = validate_magic_bytes(PDF_HEADER + b"\xff" * 100, "application/pdf")
        assert ok is True

    def test_html_disguised_as_pdf_raises(self) -> None:
        # Common XSS-via-PDF-upload vector: HTML uploaded with
        # PDF content-type. Browsers can render HTML even with
        # PDF MIME — magic-byte check is the only defence.
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(b"<html>", "application/pdf")


class TestZipSignature:
    def test_valid_zip_passes(self) -> None:
        ok, _ = validate_magic_bytes(ZIP_HEADER + b"\x00" * 100, "application/zip")
        assert ok is True

    def test_office_xml_declared_as_zip_passes(self) -> None:
        # OpenXML / OpenDocument formats are ZIPs internally —
        # their declared MIME types share the ZIP signature.
        # Pin: a docx file (PK header) declared as docx passes.
        ok, _ = validate_magic_bytes(
            ZIP_HEADER + b"\x00" * 100,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert ok is True


class TestRiffDisambiguation:
    def test_webp_must_have_webp_marker(self) -> None:
        # Pin: ``_is_webp`` requires both RIFF prefix AND ``WEBP``
        # at offset 8. A regression to bare RIFF would let WAV
        # / AVI files masquerade as WebP.
        assert _is_webp(WEBP_FILE) is True
        assert _is_webp(WAV_FILE) is False
        assert _is_webp(AVI_FILE) is False

    def test_wav_must_have_wave_marker(self) -> None:
        assert _is_wav(WAV_FILE) is True
        assert _is_wav(WEBP_FILE) is False

    def test_avi_must_have_avi_marker(self) -> None:
        # Note the trailing space in ``AVI `` — common drift
        # point. Pin it.
        assert _is_avi(AVI_FILE) is True
        assert _is_avi(b"RIFF" + b"\x00\x00\x00\x00" + b"AVIX") is False

    def test_riff_too_short_does_not_match(self) -> None:
        # Defensive: < 12 bytes can't carry a RIFF format
        # marker. Pin the early-return so a truncated upload
        # doesn't crash on slice.
        assert _is_webp(b"RIFF") is False
        assert _is_wav(b"RIFF") is False
        assert _is_avi(b"RIFF") is False

    def test_wav_declared_as_webp_raises(self) -> None:
        # Cross-format spoof inside the RIFF family. Pin: the
        # declared type's specific marker is required.
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(WAV_FILE, "image/webp")


class TestMp4Compatibility:
    def test_ftyp_atom_at_offset_four(self) -> None:
        # Pin: ftyp lives at offset 4 (NOT 0). A regression to
        # offset 0 would never match a real MP4.
        assert _is_mp4_compatible(MP4_FILE) is True
        # Same bytes shifted to offset 0 must NOT match.
        wrong = b"ftyp" + MP4_FILE[8:]
        assert _is_mp4_compatible(wrong) is False

    def test_mp4_too_short_does_not_match(self) -> None:
        assert _is_mp4_compatible(b"\x00") is False

    @pytest.mark.parametrize("mime", ["video/mp4", "video/quicktime", "audio/x-m4a"])
    def test_mp4_compatible_types_all_pass(self, mime: str) -> None:
        ok, _ = validate_magic_bytes(MP4_FILE, mime)
        assert ok is True

    def test_non_mp4_data_declared_as_mp4_raises(self) -> None:
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(b"not-an-mp4-file" + b"\x00" * 100, "video/mp4")


class TestTarOffset:
    def test_tar_signature_at_offset_257(self) -> None:
        # Pin: TAR magic ``ustar`` lives at offset 257 (POSIX
        # spec). Drift to a different offset breaks every TAR
        # upload.
        sig = next(s for s in MAGIC_SIGNATURES if s.mime_type == "application/x-tar")
        assert sig.offset == 257
        assert b"ustar" in sig.signatures

    def test_tar_validates_at_offset_257(self) -> None:
        # Construct: 257 bytes of zeros + "ustar" = real TAR header.
        tar_data = b"\x00" * 257 + b"ustar" + b"\x00" * 250
        ok, _ = validate_magic_bytes(tar_data, "application/x-tar")
        assert ok is True


class TestNonStrictMode:
    def test_returns_false_with_detected_on_mismatch(self) -> None:
        # Pin: ``strict=False`` returns the result instead of
        # raising — used by inspection / preview pipelines that
        # want to log without blocking.
        ok, detected = validate_magic_bytes(JPEG_HEADER, "image/png", strict=False)
        assert ok is False
        assert detected == "image/jpeg"

    def test_no_detected_on_unknown_bytes(self) -> None:
        # Defensive: unknown magic bytes return (False, None) so
        # the caller can render "unknown" in the SOC dashboard.
        ok, detected = validate_magic_bytes(
            b"\x99\x99\x99\x99" * 10, "image/png", strict=False
        )
        assert ok is False
        assert detected is None


class TestUnsignedDeclaredType:
    def test_unknown_declared_type_passes_silently(self) -> None:
        # Pin: a declared MIME we have no signature for passes
        # (with the declared type echoed). Drift to "raise" would
        # block every upload of an unusual-but-legitimate format.
        ok, detected = validate_magic_bytes(
            b"any-bytes" * 10, "application/x-custom-format"
        )
        assert ok is True
        assert detected == "application/x-custom-format"


class TestMimeTypeMismatchError:
    def test_carries_declared_and_detected_attributes(self) -> None:
        # Pin: the exception is the SOC-attribution payload —
        # ``declared_type`` + ``detected_type`` MUST be readable
        # attributes (not just stringified into the message).
        err = MimeTypeMismatchError(
            declared_type="image/png", detected_type="application/x-msdownload"
        )
        assert err.declared_type == "image/png"
        assert err.detected_type == "application/x-msdownload"

    def test_default_message_includes_both_types(self) -> None:
        err = MimeTypeMismatchError(
            declared_type="image/png", detected_type="application/x-msdownload"
        )
        s = str(err)
        assert "image/png" in s
        assert "application/x-msdownload" in s

    def test_none_detected_renders_as_unknown(self) -> None:
        # Pin: ``detected_type=None`` renders as "unknown" in the
        # default message so the SOC dashboard never shows
        # literal None.
        err = MimeTypeMismatchError(declared_type="image/png", detected_type=None)
        assert "unknown" in str(err)


class TestDetectMimeType:
    def test_returns_none_for_unknown(self) -> None:
        assert _detect_mime_type(b"random-bytes" * 5) is None

    def test_detects_png(self) -> None:
        assert _detect_mime_type(PNG_HEADER) == "image/png"

    def test_detects_jpeg(self) -> None:
        assert _detect_mime_type(JPEG_HEADER) == "image/jpeg"

    def test_detects_pdf(self) -> None:
        assert _detect_mime_type(PDF_HEADER) == "application/pdf"

    def test_detects_gzip(self) -> None:
        assert _detect_mime_type(GZIP_HEADER + b"\x00" * 10) == "application/gzip"


class TestCheckSignature:
    def test_truncated_data_returns_false(self) -> None:
        # Defensive: data shorter than offset+sig must NOT crash
        # on slice — return False cleanly.
        sig = MagicSignature(
            mime_type="application/x-tar", signatures=[b"ustar"], offset=257
        )
        assert _check_signature(b"abc", sig) is False

    def test_matches_at_zero_offset(self) -> None:
        sig = MagicSignature(mime_type="image/png", signatures=[PNG_HEADER])
        assert _check_signature(PNG_HEADER + b"x" * 50, sig) is True

    def test_multi_signature_returns_true_on_any(self) -> None:
        # Pin: any single signature matching is enough. A regression
        # to "all signatures must match" would reject every GIF
        # (which is GIF87a OR GIF89a, never both).
        sig = MagicSignature(mime_type="image/gif", signatures=[b"GIF87a", b"GIF89a"])
        assert _check_signature(GIF87A + b"\x00" * 5, sig) is True
        assert _check_signature(GIF89A + b"\x00" * 5, sig) is True
