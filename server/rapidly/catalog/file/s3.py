"""S3 service registry for file storage operations.

Maps each ``FileServiceTypes`` member to a lazily-constructed
``S3Service`` configured with the appropriate bucket and presign TTL.
"""

from __future__ import annotations

from rapidly.config import settings
from rapidly.integrations.aws.s3 import S3Service
from rapidly.models.file import FileServiceTypes


def _build_s3_service(bucket_name: str) -> S3Service:
    """Construct an S3Service for the given bucket."""
    return S3Service(
        bucket=bucket_name,
        presign_ttl=settings.S3_FILES_PRESIGN_TTL,
    )


#: Maps each file service type to its pre-configured S3 backend.
S3_SERVICES: dict[FileServiceTypes, S3Service] = {
    FileServiceTypes.downloadable: _build_s3_service(settings.S3_FILES_BUCKET_NAME),
    FileServiceTypes.product_media: _build_s3_service(
        settings.S3_FILES_PUBLIC_BUCKET_NAME
    ),
    FileServiceTypes.workspace_avatar: _build_s3_service(
        settings.S3_FILES_PUBLIC_BUCKET_NAME
    ),
}
