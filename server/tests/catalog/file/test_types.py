"""Tests for ``rapidly/catalog/file/types.py``.

The file-create types carry two load-bearing security invariants:

1. **MIME allow-lists** — the downloadable pattern explicitly
   excludes ``javascript`` and ``html`` (see the inline comment);
   image-only types (product media, workspace avatar) are
   restricted to the image regex. A regression widening either
   would turn the upload API into an arbitrary-content vector that
   browsers could then load as script.

2. **Size caps** — downloadable ≤ 5 GB, product_media ≤ 10 MB,
   workspace_avatar ≤ 1 MB. Silently relaxing the avatar cap (for
   example) would turn the dashboard avatar surface into a cheap
   disk-fill / CDN-cache-eviction DoS.

Also pins the ``FileCreate`` discriminated union on ``service`` —
the service discriminator is what routes the upload to the right
validation bucket.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.catalog.file.types import (
    DownloadableFileCreate,
    FileCreate,
    ShareMediaFileCreate,
    WorkspaceAvatarFileCreate,
)
from rapidly.models.file import FileServiceTypes


def _minimal_upload() -> dict[str, object]:
    # ``S3FileCreate`` requires a multipart upload descriptor; supply
    # the minimal single-part shape so tests focus on the subclass's
    # own constraints.
    return {"parts": [{"number": 1, "chunk_start": 0, "chunk_end": 1}]}


def _base_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "file.bin",
        "upload": _minimal_upload(),
    }
    body.update(overrides)
    return body


class TestDownloadableMimeAllowList:
    @pytest.mark.parametrize(
        "mime",
        [
            # Documents
            "application/pdf",
            "application/msword",
            # Archives
            "application/zip",
            "application/x-tar",
            # Data
            "application/json",
            "application/octet-stream",
            # Images
            "image/jpeg",
            "image/png",
            # Audio / video
            "audio/mpeg",
            "video/mp4",
            # Text (safe subset)
            "text/plain",
            "text/csv",
            "text/markdown",
            # Fonts
            "font/woff2",
        ],
    )
    def test_accepts_common_safe_mimes(self, mime: str) -> None:
        body = _base_body(
            service=FileServiceTypes.downloadable.value,
            mime_type=mime,
            size=1000,
        )
        parsed = DownloadableFileCreate.model_validate(body)
        assert parsed.mime_type == mime

    @pytest.mark.parametrize(
        "hostile",
        [
            # Script types — explicit exclusion in the module comment.
            "text/html",
            "application/javascript",
            "text/javascript",
            "application/x-sh",
            "application/x-msdownload",
            # Random nonsense
            "not/a-type",
            "",
        ],
    )
    def test_rejects_hostile_or_unrecognised_mimes(self, hostile: str) -> None:
        body = _base_body(
            service=FileServiceTypes.downloadable.value,
            mime_type=hostile,
            size=1000,
        )
        with pytest.raises(ValidationError):
            DownloadableFileCreate.model_validate(body)


class TestDownloadableSizeCap:
    def test_accepts_size_up_to_5gb(self) -> None:
        body = _base_body(
            service=FileServiceTypes.downloadable.value,
            mime_type="application/pdf",
            size=5 * 1024 * 1024 * 1024,
        )
        parsed = DownloadableFileCreate.model_validate(body)
        assert parsed.size == 5 * 1024 * 1024 * 1024

    def test_rejects_size_over_5gb(self) -> None:
        body = _base_body(
            service=FileServiceTypes.downloadable.value,
            mime_type="application/pdf",
            size=5 * 1024 * 1024 * 1024 + 1,
        )
        with pytest.raises(ValidationError):
            DownloadableFileCreate.model_validate(body)


class TestImageOnlyTypes:
    @pytest.mark.parametrize(
        "mime", ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"]
    )
    def test_product_media_accepts_images(self, mime: str) -> None:
        body = _base_body(
            service=FileServiceTypes.product_media.value,
            mime_type=mime,
            size=1000,
        )
        ShareMediaFileCreate.model_validate(body)

    @pytest.mark.parametrize(
        "non_image",
        ["application/pdf", "text/plain", "video/mp4", "application/javascript"],
    )
    def test_product_media_rejects_non_images(self, non_image: str) -> None:
        # Product-media images must stay images — the storefront
        # renders these via ``<img>``. Accepting PDF or script types
        # would either misrender or execute as HTML via MIME sniffing.
        body = _base_body(
            service=FileServiceTypes.product_media.value,
            mime_type=non_image,
            size=1000,
        )
        with pytest.raises(ValidationError):
            ShareMediaFileCreate.model_validate(body)

    def test_workspace_avatar_accepts_images(self) -> None:
        body = _base_body(
            service=FileServiceTypes.workspace_avatar.value,
            mime_type="image/png",
            size=1000,
        )
        WorkspaceAvatarFileCreate.model_validate(body)

    def test_workspace_avatar_rejects_non_images(self) -> None:
        body = _base_body(
            service=FileServiceTypes.workspace_avatar.value,
            mime_type="application/pdf",
            size=1000,
        )
        with pytest.raises(ValidationError):
            WorkspaceAvatarFileCreate.model_validate(body)


class TestImageSizeCaps:
    def test_product_media_accepts_up_to_10mb(self) -> None:
        body = _base_body(
            service=FileServiceTypes.product_media.value,
            mime_type="image/png",
            size=10 * 1024 * 1024,
        )
        ShareMediaFileCreate.model_validate(body)

    def test_product_media_rejects_over_10mb(self) -> None:
        body = _base_body(
            service=FileServiceTypes.product_media.value,
            mime_type="image/png",
            size=10 * 1024 * 1024 + 1,
        )
        with pytest.raises(ValidationError):
            ShareMediaFileCreate.model_validate(body)

    def test_workspace_avatar_accepts_up_to_1mb(self) -> None:
        body = _base_body(
            service=FileServiceTypes.workspace_avatar.value,
            mime_type="image/png",
            size=1 * 1024 * 1024,
        )
        WorkspaceAvatarFileCreate.model_validate(body)

    def test_workspace_avatar_rejects_over_1mb(self) -> None:
        # A 10 MB avatar uploaded 10 000 times would silently fill
        # 100 GB of CDN cache. The 1 MB cap is the load-bearing
        # defence against that.
        body = _base_body(
            service=FileServiceTypes.workspace_avatar.value,
            mime_type="image/png",
            size=1 * 1024 * 1024 + 1,
        )
        with pytest.raises(ValidationError):
            WorkspaceAvatarFileCreate.model_validate(body)


class TestFileCreateDiscriminator:
    def test_dispatches_on_service_field(self) -> None:
        from pydantic import TypeAdapter

        adapter: TypeAdapter[FileCreate] = TypeAdapter(FileCreate)
        body = _base_body(
            service=FileServiceTypes.downloadable.value,
            mime_type="application/pdf",
            size=1000,
        )
        parsed = adapter.validate_python(body)
        assert isinstance(parsed, DownloadableFileCreate)

    def test_unknown_service_is_rejected(self) -> None:
        from pydantic import TypeAdapter

        adapter: TypeAdapter[FileCreate] = TypeAdapter(FileCreate)
        body = _base_body(
            service="not_a_service",
            mime_type="application/pdf",
            size=1000,
        )
        with pytest.raises(ValidationError):
            adapter.validate_python(body)
