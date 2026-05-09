"""File upload, download, and patch Pydantic models.

Covers creation payloads for every ``FileServiceTypes`` variant
(downloadable, share media, workspace avatar), upload/download URL
responses, and the discriminated-union ``FileRead`` type used in list
endpoints.
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import Discriminator, Field, TypeAdapter, computed_field

from rapidly.core.types import ClassName, MergeJSONSchema, Schema, SetSchemaReference
from rapidly.integrations.aws.s3.types import (
    S3DownloadURL,
    S3File,
    S3FileCreate,
    S3FileDownload,
    S3FileUpload,
    S3FileUploadCompleted,
)
from rapidly.models.file import File, FileServiceTypes

from .s3 import S3_SERVICES

# ---------------------------------------------------------------------------
# Shared MIME patterns
# ---------------------------------------------------------------------------

_IMAGE_MIME_PATTERN = r"^image\/(jpeg|png|gif|webp|svg\+xml)$"

_DOWNLOADABLE_MIME_PATTERN = (
    r"^("
    # Documents
    r"application/(pdf|msword|vnd\.openxmlformats-officedocument\..+|"
    r"vnd\.oasis\.opendocument\..+|rtf|epub\+zip)|"
    # Archives
    r"application/(zip|x-zip-compressed|x-rar-compressed|x-7z-compressed|"
    r"x-tar|gzip|x-bzip2)|"
    # Data formats
    r"application/(json|xml|octet-stream)|"
    # Images
    r"image/(jpeg|png|gif|webp|svg\+xml|bmp|tiff|x-icon)|"
    # Audio
    r"audio/(mpeg|wav|ogg|flac|aac|x-m4a)|"
    # Video
    r"video/(mp4|webm|ogg|quicktime|x-msvideo|x-matroska)|"
    # Text (excluding javascript/html which could be malicious)
    r"text/(plain|csv|markdown|x-python|x-java|x-c|x-c\+\+|x-ruby)|"
    # Fonts
    r"font/(ttf|otf|woff|woff2)"
    r")$"
)


# ---------------------------------------------------------------------------
# Create payloads (per service type)
# ---------------------------------------------------------------------------


class FileCreateBase(S3FileCreate):
    service: FileServiceTypes
    version: str | None = None


class DownloadableFileCreate(FileCreateBase):
    """Upload a downloadable file (max 5 GB)."""

    service: Literal[FileServiceTypes.downloadable]
    mime_type: str = Field(
        description=(
            "MIME type of the file. Executables and potentially dangerous "
            "script types are not allowed for security reasons."
        ),
        pattern=_DOWNLOADABLE_MIME_PATTERN,
    )
    size: int = Field(
        description=(
            "Size of the file. A maximum of 5 GB is allowed for downloadable files."
        ),
        le=5 * 1024 * 1024 * 1024,
    )


class ShareMediaFileCreate(FileCreateBase):
    """Upload a share media image (max 10 MB)."""

    service: Literal[FileServiceTypes.product_media]
    mime_type: str = Field(
        description=(
            "MIME type of the file. Only images are supported for this type of file."
        ),
        pattern=_IMAGE_MIME_PATTERN,
    )
    size: int = Field(
        description=(
            "Size of the file. A maximum of 10 MB is allowed for this type of file."
        ),
        le=10 * 1024 * 1024,
    )


class WorkspaceAvatarFileCreate(FileCreateBase):
    """Upload a workspace avatar image (max 1 MB)."""

    service: Literal[FileServiceTypes.workspace_avatar]
    mime_type: str = Field(
        description=(
            "MIME type of the file. Only images are supported for this type of file."
        ),
        pattern=_IMAGE_MIME_PATTERN,
    )
    size: int = Field(
        description=(
            "Size of the file. A maximum of 1 MB is allowed for this type of file."
        ),
        le=1 * 1024 * 1024,
    )


FileCreate = Annotated[
    DownloadableFileCreate | ShareMediaFileCreate | WorkspaceAvatarFileCreate,
    Discriminator("service"),
    SetSchemaReference("FileCreate"),
]


# ---------------------------------------------------------------------------
# Read models (per service type)
# ---------------------------------------------------------------------------


class FileReadBase(S3File):
    version: str | None
    service: FileServiceTypes
    is_uploaded: bool
    created_at: datetime


class DownloadableFileRead(FileReadBase):
    """A downloadable file."""

    service: Literal[FileServiceTypes.downloadable]


class PublicFileReadBase(FileReadBase):
    @computed_field  # type: ignore[prop-decorator]
    @property
    def public_url(self) -> str:
        return S3_SERVICES[self.service].get_public_url(self.path)


class ShareMediaFileRead(PublicFileReadBase):
    """File to be used as a share media file."""

    service: Literal[FileServiceTypes.product_media]


class WorkspaceAvatarFileRead(PublicFileReadBase):
    """File to be used as an workspace avatar."""

    service: Literal[FileServiceTypes.workspace_avatar]


FileRead = Annotated[
    DownloadableFileRead | ShareMediaFileRead | WorkspaceAvatarFileRead,
    Discriminator("service"),
    MergeJSONSchema({"title": "FileRead"}),
    ClassName("FileRead"),
]

FileReadAdapter: TypeAdapter[FileRead] = TypeAdapter[FileRead](FileRead)


# ---------------------------------------------------------------------------
# Upload / download helpers
# ---------------------------------------------------------------------------


class FileUpload(S3FileUpload):
    version: str | None
    is_uploaded: bool = False
    service: FileServiceTypes


class FileUploadCompleted(S3FileUploadCompleted): ...


class FileDownload(S3FileDownload):
    version: str | None
    is_uploaded: bool
    service: FileServiceTypes

    @classmethod
    def from_presigned(cls, file: File, url: str, expires_at: datetime) -> Self:
        attrs: dict[str, Any] = dict(
            id=file.id,
            workspace_id=file.workspace_id,
            name=file.name,
            path=file.path,
            mime_type=file.mime_type,
            size=file.size,
            version=file.version,
            service=file.service,
            checksum_etag=file.checksum_etag,
            last_modified_at=file.last_modified_at,
            storage_version=file.storage_version,
            is_uploaded=file.is_uploaded,
            created_at=file.created_at,
            checksum_sha256_base64=file.checksum_sha256_base64,
            checksum_sha256_hex=file.checksum_sha256_hex,
        )

        return cls(
            **attrs,
            download=S3DownloadURL(
                url=url,
                expires_at=expires_at,
            ),
        )


# ---------------------------------------------------------------------------
# Mutation payloads
# ---------------------------------------------------------------------------


class FilePatch(Schema):
    name: str | None = None
    version: str | None = None
