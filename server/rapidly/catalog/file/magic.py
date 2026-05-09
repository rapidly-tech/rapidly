"""Magic byte validation for file uploads.

This module validates that file content matches the declared MIME type by checking
magic bytes (file signatures). This prevents attackers from uploading malicious files
with spoofed extensions.

Usage:
    from rapidly.catalog.file.magic import validate_magic_bytes, MimeTypeMismatchError

    try:
        validate_magic_bytes(file_data, declared_mime_type="image/png")
    except MimeTypeMismatchError as e:
        # Handle mismatch - file content doesn't match declared type
        pass
"""

from dataclasses import dataclass

import structlog

_log = structlog.get_logger()


# ── Exceptions ──


class MimeTypeMismatchError(Exception):
    """Raised when file content doesn't match declared MIME type."""

    def __init__(
        self, declared_type: str, detected_type: str | None, message: str | None = None
    ) -> None:
        self.declared_type = declared_type
        self.detected_type = detected_type
        msg = message or (
            f"File content mismatch: declared as '{declared_type}', "
            f"detected as '{detected_type or 'unknown'}'"
        )
        super().__init__(msg)


# ── File Type Constants ──


@dataclass
class MagicSignature:
    """Magic byte signature for file type detection."""

    mime_type: str
    signatures: list[bytes]  # Multiple possible signatures
    offset: int = 0  # Offset from start of file


# Common magic byte signatures
# Reference: https://en.wikipedia.org/wiki/List_of_file_signatures
MAGIC_SIGNATURES: list[MagicSignature] = [
    # Images
    MagicSignature(
        mime_type="image/jpeg",
        signatures=[b"\xff\xd8\xff"],
    ),
    MagicSignature(
        mime_type="image/png",
        signatures=[b"\x89PNG\r\n\x1a\n"],
    ),
    MagicSignature(
        mime_type="image/gif",
        signatures=[b"GIF87a", b"GIF89a"],
    ),
    MagicSignature(
        mime_type="image/webp",
        signatures=[b"RIFF"],  # Full check: RIFF....WEBP
    ),
    MagicSignature(
        mime_type="image/bmp",
        signatures=[b"BM"],
    ),
    MagicSignature(
        mime_type="image/tiff",
        signatures=[b"II*\x00", b"MM\x00*"],  # Little/big endian
    ),
    MagicSignature(
        mime_type="image/x-icon",
        signatures=[b"\x00\x00\x01\x00"],  # ICO
    ),
    # Documents
    MagicSignature(
        mime_type="application/pdf",
        signatures=[b"%PDF"],
    ),
    MagicSignature(
        mime_type="application/rtf",
        signatures=[b"{\\rtf"],
    ),
    # Archives
    MagicSignature(
        mime_type="application/zip",
        signatures=[b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ),
    MagicSignature(
        mime_type="application/x-zip-compressed",
        signatures=[b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ),
    MagicSignature(
        mime_type="application/x-rar-compressed",
        signatures=[b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00"],
    ),
    MagicSignature(
        mime_type="application/x-7z-compressed",
        signatures=[b"7z\xbc\xaf'\x1c"],
    ),
    MagicSignature(
        mime_type="application/gzip",
        signatures=[b"\x1f\x8b"],
    ),
    MagicSignature(
        mime_type="application/x-bzip2",
        signatures=[b"BZh"],
    ),
    MagicSignature(
        mime_type="application/x-tar",
        signatures=[b"ustar"],
        offset=257,  # TAR magic at offset 257
    ),
    # Audio
    MagicSignature(
        mime_type="audio/mpeg",
        signatures=[b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    ),
    MagicSignature(
        mime_type="audio/wav",
        signatures=[b"RIFF"],  # Full check: RIFF....WAVE
    ),
    MagicSignature(
        mime_type="audio/ogg",
        signatures=[b"OggS"],
    ),
    MagicSignature(
        mime_type="audio/flac",
        signatures=[b"fLaC"],
    ),
    MagicSignature(
        mime_type="audio/aac",
        signatures=[b"\xff\xf1", b"\xff\xf9"],  # ADTS
    ),
    MagicSignature(
        mime_type="audio/x-m4a",
        signatures=[b"\x00\x00\x00"],  # Check for ftyp atom
    ),
    # Video
    MagicSignature(
        mime_type="video/mp4",
        signatures=[b"\x00\x00\x00"],  # Check for ftyp atom
    ),
    MagicSignature(
        mime_type="video/webm",
        signatures=[b"\x1aE\xdf\xa3"],  # EBML header
    ),
    MagicSignature(
        mime_type="video/ogg",
        signatures=[b"OggS"],
    ),
    MagicSignature(
        mime_type="video/quicktime",
        signatures=[b"\x00\x00\x00"],  # Check for ftyp/moov atom
    ),
    MagicSignature(
        mime_type="video/x-msvideo",
        signatures=[b"RIFF"],  # Full check: RIFF....AVI
    ),
    MagicSignature(
        mime_type="video/x-matroska",
        signatures=[b"\x1aE\xdf\xa3"],  # EBML header
    ),
    # Office documents (OpenXML - all are ZIP-based)
    MagicSignature(
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        signatures=[b"PK\x03\x04"],
    ),
    MagicSignature(
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        signatures=[b"PK\x03\x04"],
    ),
    MagicSignature(
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        signatures=[b"PK\x03\x04"],
    ),
    # Legacy Office documents
    MagicSignature(
        mime_type="application/msword",
        signatures=[b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],  # OLE2
    ),
    # OpenDocument formats (also ZIP-based)
    MagicSignature(
        mime_type="application/vnd.oasis.opendocument.text",
        signatures=[b"PK\x03\x04"],
    ),
    MagicSignature(
        mime_type="application/vnd.oasis.opendocument.spreadsheet",
        signatures=[b"PK\x03\x04"],
    ),
    MagicSignature(
        mime_type="application/vnd.oasis.opendocument.presentation",
        signatures=[b"PK\x03\x04"],
    ),
    # Ebook
    MagicSignature(
        mime_type="application/epub+zip",
        signatures=[b"PK\x03\x04"],  # EPUB is a ZIP file
    ),
    # Fonts
    MagicSignature(
        mime_type="font/ttf",
        signatures=[b"\x00\x01\x00\x00"],
    ),
    MagicSignature(
        mime_type="font/otf",
        signatures=[b"OTTO"],
    ),
    MagicSignature(
        mime_type="font/woff",
        signatures=[b"wOFF"],
    ),
    MagicSignature(
        mime_type="font/woff2",
        signatures=[b"wOF2"],
    ),
]

# ── Lookup Tables ──

# Build a lookup table by MIME type
_SIGNATURES_BY_MIME: dict[str, MagicSignature] = {
    sig.mime_type: sig for sig in MAGIC_SIGNATURES
}

# MIME types that are text-based and don't have magic bytes
TEXT_BASED_MIMES: set[str] = {
    "text/plain",
    "text/csv",
    "text/markdown",
    "text/x-python",
    "text/x-java",
    "text/x-c",
    "text/x-c++",
    "text/x-ruby",
    "application/json",
    "application/xml",
    "image/svg+xml",  # SVG is XML-based
}

# MIME types where we can't reliably validate with magic bytes
SKIP_VALIDATION_MIMES: set[str] = TEXT_BASED_MIMES | {
    "application/octet-stream",  # Generic binary - no specific signature
}


# ── MIME Detection ──


def _check_signature(data: bytes, signature: MagicSignature) -> bool:
    """Check if data matches a magic signature."""
    for sig in signature.signatures:
        offset = signature.offset
        if len(data) >= offset + len(sig):
            if data[offset : offset + len(sig)] == sig:
                return True
    return False


def _detect_mime_type(data: bytes) -> str | None:
    """Attempt to detect MIME type from magic bytes."""
    for signature in MAGIC_SIGNATURES:
        if _check_signature(data, signature):
            return signature.mime_type
    return None


def _is_webp(data: bytes) -> bool:
    """Check if data is a WebP file (RIFF....WEBP)."""
    if len(data) >= 12:
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _is_wav(data: bytes) -> bool:
    """Check if data is a WAV file (RIFF....WAVE)."""
    if len(data) >= 12:
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    return False


def _is_avi(data: bytes) -> bool:
    """Check if data is an AVI file (RIFF....AVI )."""
    if len(data) >= 12:
        return data[:4] == b"RIFF" and data[8:12] == b"AVI "
    return False


def _is_mp4_compatible(data: bytes) -> bool:
    """Check if data is MP4/M4A/MOV compatible (ftyp atom)."""
    if len(data) >= 12:
        # Look for ftyp atom
        # First 4 bytes are size, next 4 should be 'ftyp'
        return data[4:8] == b"ftyp"
    return False


# ── Validation ──


def validate_magic_bytes(
    data: bytes,
    declared_mime_type: str,
    *,
    strict: bool = True,
) -> tuple[bool, str | None]:
    """Validate that file content matches declared MIME type.

    Args:
        data: File content bytes (at least first 512 bytes recommended)
        declared_mime_type: The MIME type declared by the uploader
        strict: If True, raise exception on mismatch. If False, return result.

    Returns:
        Tuple of (is_valid, detected_type)

    Raises:
        MimeTypeMismatchError: If strict=True and content doesn't match declared type
    """
    # Skip validation for text-based and generic types
    if declared_mime_type in SKIP_VALIDATION_MIMES:
        _log.debug(
            "magic.validation.skipped",
            declared_type=declared_mime_type,
            reason="text-based or generic type",
        )
        return True, declared_mime_type

    # Special handling for RIFF-based formats
    if declared_mime_type == "image/webp":
        if _is_webp(data):
            return True, "image/webp"
        detected = _detect_mime_type(data)
        if strict:
            raise MimeTypeMismatchError(declared_mime_type, detected)
        return False, detected

    if declared_mime_type == "audio/wav":
        if _is_wav(data):
            return True, "audio/wav"
        detected = _detect_mime_type(data)
        if strict:
            raise MimeTypeMismatchError(declared_mime_type, detected)
        return False, detected

    if declared_mime_type == "video/x-msvideo":
        if _is_avi(data):
            return True, "video/x-msvideo"
        detected = _detect_mime_type(data)
        if strict:
            raise MimeTypeMismatchError(declared_mime_type, detected)
        return False, detected

    # Special handling for MP4/M4A/MOV containers
    if declared_mime_type in ("video/mp4", "video/quicktime", "audio/x-m4a"):
        if _is_mp4_compatible(data):
            return True, declared_mime_type
        detected = _detect_mime_type(data)
        if strict:
            raise MimeTypeMismatchError(declared_mime_type, detected)
        return False, detected

    # Get signature for declared type
    signature = _SIGNATURES_BY_MIME.get(declared_mime_type)

    # If we don't have a signature for this type, skip validation
    if signature is None:
        _log.debug(
            "magic.validation.no_signature",
            declared_type=declared_mime_type,
        )
        return True, declared_mime_type

    # Check if data matches expected signature
    if _check_signature(data, signature):
        _log.debug(
            "magic.validation.passed",
            declared_type=declared_mime_type,
        )
        return True, declared_mime_type

    # Mismatch - try to detect actual type
    detected = _detect_mime_type(data)

    _log.warning(
        "magic.validation.mismatch",
        declared_type=declared_mime_type,
        detected_type=detected,
    )

    if strict:
        raise MimeTypeMismatchError(declared_mime_type, detected)

    return False, detected
