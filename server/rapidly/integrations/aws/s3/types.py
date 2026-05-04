"""S3 file lifecycle Pydantic models: create, upload, download, and checksums.

Defines the request/response shapes for pre-signed upload URLs, multipart
upload completion, download URL generation, and SHA-256 checksum handling.
Includes filename sanitisation to prevent path traversal attacks.
"""

import base64
import hashlib
import re
from datetime import datetime
from typing import Any, Self

from pydantic import UUID4, computed_field, field_validator

from rapidly.core.types import IdentifiableSchema, Schema
from rapidly.core.utils import human_readable_size
from rapidly.platform.workspace.types import WorkspaceID

# ---------------------------------------------------------------------------
# Filename sanitisation
# ---------------------------------------------------------------------------


_DANGEROUS_CHARS_RE = re.compile(r'[/\\:*?"<>|]')
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_filename(name: str) -> str:
    """Strip path traversal sequences and dangerous characters from a filename."""
    cleaned = name
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "")
    cleaned = _DANGEROUS_CHARS_RE.sub("", cleaned)
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)
    cleaned = cleaned.strip()[:255]
    return cleaned if cleaned else "unnamed_file"


def get_downloadable_content_disposition(filename: str) -> str:
    safe = filename.replace('"', '\\"')
    return f'attachment; filename="{safe}"'


# ---------------------------------------------------------------------------
# Upload part definitions
# ---------------------------------------------------------------------------


class S3FileCreatePart(Schema):
    number: int
    chunk_start: int
    chunk_end: int

    checksum_sha256_base64: str | None = None

    def get_boto3_arguments(self) -> dict[str, Any]:
        if not self.checksum_sha256_base64:
            return dict(PartNumber=self.number)

        return dict(
            PartNumber=self.number,
            ChecksumAlgorithm="SHA256",
            ChecksumSHA256=self.checksum_sha256_base64,
        )


class S3FileCreateMultipart(Schema):
    parts: list[S3FileCreatePart]


# ---------------------------------------------------------------------------
# Create payload
# ---------------------------------------------------------------------------


class S3FileCreate(Schema):
    workspace_id: WorkspaceID | None = None
    name: str
    mime_type: str
    size: int

    checksum_sha256_base64: str | None = None

    upload: S3FileCreateMultipart

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_sanitize_name(cls, v: str) -> str:
        """Sanitize filename to prevent path traversal attacks."""
        return sanitize_filename(v)


# ---------------------------------------------------------------------------
# File read model
# ---------------------------------------------------------------------------


class S3File(IdentifiableSchema, validate_assignment=True):
    workspace_id: UUID4

    name: str
    path: str
    mime_type: str
    size: int

    storage_version: str | None
    checksum_etag: str | None

    checksum_sha256_base64: str | None
    checksum_sha256_hex: str | None

    last_modified_at: datetime | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def size_readable(self) -> str:
        return human_readable_size(self.size)

    def to_metadata(self) -> dict[str, str]:
        md = {
            "rapidly-id": str(self.id),
            "rapidly-workspace-id": str(self.workspace_id),
            "rapidly-name": self.name.encode("ascii", "ignore").decode("ascii"),
            "rapidly-size": str(self.size),
        }
        if self.checksum_sha256_base64:
            md["rapidly-techa256-base64"] = self.checksum_sha256_base64
        if self.checksum_sha256_hex:
            md["rapidly-techa256-hex"] = self.checksum_sha256_hex
        return md

    @classmethod
    def from_head(cls, path: str, head: dict[str, Any]) -> Self:
        md = head.get("Metadata", {})

        return cls(
            id=md.get("rapidly-id"),
            workspace_id=md.get("rapidly-workspace-id"),
            name=md.get("rapidly-name"),
            path=path,
            mime_type=head["ContentType"],
            size=md.get("rapidly-size"),
            storage_version=head.get("VersionId", None),
            checksum_etag=head.get("ETag", None),
            checksum_sha256_base64=md.get("rapidly-techa256-base64"),
            checksum_sha256_hex=md.get("rapidly-techa256-hex"),
            last_modified_at=head.get("LastModified", None),
        )


# ---------------------------------------------------------------------------
# Upload response models
# ---------------------------------------------------------------------------


class S3FileUploadPart(S3FileCreatePart):
    url: str
    expires_at: datetime

    headers: dict[str, str] = {}

    @classmethod
    def generate_headers(cls, sha256_base64: str | None) -> dict[str, str]:
        if not sha256_base64:
            return {}

        return {
            "x-amz-checksum-sha256": sha256_base64,
            "x-amz-sdk-checksum-algorithm": "SHA256",
        }


class S3FileUploadMultipart(Schema):
    id: str
    path: str
    parts: list[S3FileUploadPart]


class S3FileUpload(S3File):
    upload: S3FileUploadMultipart


# ---------------------------------------------------------------------------
# Multipart completion
# ---------------------------------------------------------------------------


class S3FileUploadCompletedPart(Schema):
    number: int
    checksum_etag: str
    checksum_sha256_base64: str | None


class S3FileUploadCompleted(Schema):
    id: str
    path: str
    parts: list[S3FileUploadCompletedPart]

    @staticmethod
    def generate_base64_multipart_checksum(checksum_digests: list[bytes]) -> str:
        """Compute the S3-specific composite SHA-256 checksum for multipart uploads.

        S3 multipart checksums are NOT the hash of the whole file; they are
        the hash of the concatenated per-part digest bytes.
        """
        concatenated = b"".join(checksum_digests)
        composite_digest = hashlib.sha256(concatenated).digest()
        return base64.b64encode(composite_digest).decode("utf-8")

    def get_boto3_arguments(self) -> dict[str, Any]:
        part_list = []
        digest_accumulator: list[bytes] = []
        for part in self.parts:
            entry = dict(
                ETag=part.checksum_etag,
                PartNumber=part.number,
            )
            if part.checksum_sha256_base64:
                entry["ChecksumSHA256"] = part.checksum_sha256_base64
                digest_accumulator.append(base64.b64decode(part.checksum_sha256_base64))

            part_list.append(entry)

        result = dict(
            UploadId=self.id,
            MultipartUpload=dict(Parts=part_list),
        )
        if not digest_accumulator:
            return result

        result["ChecksumSHA256"] = self.generate_base64_multipart_checksum(
            digest_accumulator
        )
        return result


# ---------------------------------------------------------------------------
# Download models
# ---------------------------------------------------------------------------


class S3DownloadURL(Schema):
    url: str
    headers: dict[str, str] = {}
    expires_at: datetime


class S3FileDownload(S3File):
    download: S3DownloadURL
