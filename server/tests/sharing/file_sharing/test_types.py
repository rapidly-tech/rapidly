"""Tests for file sharing Pydantic types (checksum schemas)."""

import pytest
from pydantic import ValidationError

from rapidly.sharing.file_sharing.types import (
    ChecksumFetchResponse,
    ChecksumUploadRequest,
    ChecksumUploadResponse,
)


class TestChecksumUploadRequest:
    def test_valid_request(self) -> None:
        req = ChecksumUploadRequest(
            secret="test-secret",
            checksums={"file.txt": "a" * 64},
        )
        assert req.secret == "test-secret"
        assert req.checksums == {"file.txt": "a" * 64}

    def test_multiple_files(self) -> None:
        req = ChecksumUploadRequest(
            secret="s",
            checksums={
                "file1.txt": "a" * 64,
                "file2.txt": "b" * 64,
            },
        )
        assert len(req.checksums) == 2

    def test_rejects_invalid_hex_digest(self) -> None:
        with pytest.raises(ValidationError):
            ChecksumUploadRequest(
                secret="s",
                checksums={"file.txt": "not-a-hex-digest"},
            )

    def test_rejects_wrong_length_digest(self) -> None:
        with pytest.raises(ValidationError):
            ChecksumUploadRequest(
                secret="s",
                checksums={"file.txt": "a" * 32},  # too short
            )

    def test_rejects_uppercase_hex(self) -> None:
        with pytest.raises(ValidationError):
            ChecksumUploadRequest(
                secret="s",
                checksums={"file.txt": "A" * 64},
            )

    def test_rejects_empty_secret(self) -> None:
        with pytest.raises(ValidationError):
            ChecksumUploadRequest(
                secret="",
                checksums={"file.txt": "a" * 64},
            )

    def test_rejects_too_long_filename(self) -> None:
        with pytest.raises(ValidationError):
            ChecksumUploadRequest(
                secret="s",
                checksums={"x" * 5000: "a" * 64},
            )


class TestChecksumUploadResponse:
    def test_success(self) -> None:
        resp = ChecksumUploadResponse(success=True)
        assert resp.success is True

    def test_failure(self) -> None:
        resp = ChecksumUploadResponse(success=False)
        assert resp.success is False


class TestChecksumFetchResponse:
    def test_with_checksums(self) -> None:
        resp = ChecksumFetchResponse(
            checksums={"file.txt": "a" * 64, "img.png": "b" * 64}
        )
        assert len(resp.checksums) == 2
        assert resp.checksums["file.txt"] == "a" * 64
