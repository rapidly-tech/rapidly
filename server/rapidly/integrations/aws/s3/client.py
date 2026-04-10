"""Low-level S3 client wrapper for bucket operations.

Creates a boto3 S3 client configured from application settings
(endpoint, credentials, region, signature version).  A module-level
singleton is provided for convenience.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from rapidly.config import settings

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client


def get_client(*, signature_version: str = settings.AWS_SIGNATURE_VERSION) -> S3Client:
    """Build a new boto3 S3 client using the app's configured credentials."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(
            region_name=settings.AWS_REGION,
            signature_version=signature_version,
        ),
    )


#: Module-level singleton — prefer injecting ``get_client()`` in tests.
client: S3Client = get_client()

__all__: tuple[str, ...] = ("client", "get_client")
