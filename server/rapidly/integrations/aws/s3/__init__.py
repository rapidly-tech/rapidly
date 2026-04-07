"""AWS S3 integration: re-exports S3Service and S3FileError."""

from .actions import S3Service
from .exceptions import S3FileError

__all__ = ("S3FileError", "S3Service")
