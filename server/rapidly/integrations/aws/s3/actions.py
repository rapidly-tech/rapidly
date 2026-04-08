"""S3-compatible object storage service (AWS / MinIO).

Wraps ``boto3`` for pre-signed upload and download URLs, multipart upload
lifecycle management, integrity verification via SHA-256 checksums,
file quarantine, and existence checks.  Works transparently against both
AWS S3 and a local MinIO instance.
"""

import base64
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import botocore
import structlog
from botocore.client import ClientError

from rapidly.core.utils import create_uuid, now_utc

from .client import client, get_client
from .exceptions import S3FileError
from .types import (
    S3File,
    S3FileCreate,
    S3FileCreatePart,
    S3FileUpload,
    S3FileUploadCompleted,
    S3FileUploadMultipart,
    S3FileUploadPart,
    get_downloadable_content_disposition,
)

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_s3.type_defs import PutObjectRequestTypeDef

_log = structlog.get_logger()


class S3Service:
    """Pre-signed URL generation, multipart uploads, and integrity checks."""

    def __init__(
        self,
        bucket: str,
        presign_ttl: int = 600,
        client: "S3Client" = client,
    ):
        self.bucket = bucket
        self.presign_ttl = presign_ttl
        self.client = client

    # ------------------------------------------------------------------
    # Direct upload (backend-generated files)
    # ------------------------------------------------------------------

    def upload(
        self,
        data: bytes,
        path: str,
        mime_type: str,
        checksum_sha256_base64: str | None = None,
    ) -> str:
        """Upload a file directly to S3 (for server-generated artifacts)."""
        req: PutObjectRequestTypeDef = {
            "Bucket": self.bucket,
            "Key": path,
            "Body": data,
            "ContentType": mime_type,
        }
        if checksum_sha256_base64 is not None:
            req["ChecksumAlgorithm"] = "SHA256"
            req["ChecksumSHA256"] = checksum_sha256_base64

        self.client.put_object(**req)
        return path

    # ------------------------------------------------------------------
    # Multipart upload lifecycle
    # ------------------------------------------------------------------

    def create_multipart_upload(
        self, data: S3FileCreate, namespace: str = ""
    ) -> S3FileUpload:
        if not data.workspace_id:
            raise S3FileError("Workspace ID is required")

        file_uuid = create_uuid()
        upload_path = f"{namespace}/{data.workspace_id}/{file_uuid}/{data.name}"

        s3_file = S3File(
            id=file_uuid,
            workspace_id=data.workspace_id,
            name=data.name,
            path=upload_path,
            mime_type=data.mime_type,
            size=data.size,
            storage_version=None,
            checksum_etag=None,
            checksum_sha256_base64=None,
            checksum_sha256_hex=None,
            last_modified_at=None,
        )

        if data.checksum_sha256_base64:
            b64_checksum = data.checksum_sha256_base64
            s3_file.checksum_sha256_base64 = b64_checksum
            s3_file.checksum_sha256_hex = base64.b64decode(b64_checksum).hex()

        mp_response = self.client.create_multipart_upload(
            Bucket=self.bucket,
            Key=s3_file.path,
            ContentType=s3_file.mime_type,
            ChecksumAlgorithm="SHA256",
            Metadata=s3_file.to_metadata(),
        )
        upload_id = mp_response.get("UploadId")
        if not upload_id:
            _log.error(
                "aws.s3",
                workspace_id=s3_file.workspace_id,
                filename=s3_file.name,
                mime_type=s3_file.mime_type,
                size=s3_file.size,
                error="No upload ID returned from S3",
            )
            raise S3FileError("No upload ID returned from S3")

        signed_parts = self._sign_upload_parts(
            path=s3_file.path,
            parts=data.upload.parts,
            upload_id=upload_id,
        )

        return S3FileUpload(
            upload=S3FileUploadMultipart(
                id=upload_id,
                path=s3_file.path,
                parts=signed_parts,
            ),
            **s3_file.model_dump(),
        )

    def _sign_upload_parts(
        self,
        *,
        path: str,
        parts: list[S3FileCreatePart],
        upload_id: str,
    ) -> list[S3FileUploadPart]:
        ttl = self.presign_ttl
        signed: list[S3FileUploadPart] = []
        for part in parts:
            url = self.client.generate_presigned_url(
                "upload_part",
                Params=dict(
                    UploadId=upload_id,
                    Bucket=self.bucket,
                    Key=path,
                    **part.get_boto3_arguments(),
                ),
                ExpiresIn=ttl,
            )
            expires = now_utc() + timedelta(seconds=ttl)
            hdrs = S3FileUploadPart.generate_headers(part.checksum_sha256_base64)
            signed.append(
                S3FileUploadPart(
                    number=part.number,
                    chunk_start=part.chunk_start,
                    chunk_end=part.chunk_end,
                    checksum_sha256_base64=part.checksum_sha256_base64,
                    url=url,
                    expires_at=expires,
                    headers=hdrs,
                )
            )
        return signed

    # Kept for backward compat with callers using the old name
    generate_presigned_upload_parts = _sign_upload_parts

    def complete_multipart_upload(self, data: S3FileUploadCompleted) -> S3File:
        boto_args = data.get_boto3_arguments()
        resp = self.client.complete_multipart_upload(
            Bucket=self.bucket, Key=data.path, **boto_args
        )
        if not resp:
            raise S3FileError("No response from S3")

        version = resp.get("VersionId", "")
        head = self.get_head_or_raise(data.path, s3_version_id=version)
        return S3File.from_head(data.path, head)

    # ------------------------------------------------------------------
    # Object queries
    # ------------------------------------------------------------------

    def get_object_or_raise(self, path: str, s3_version_id: str = "") -> dict[str, Any]:
        try:
            obj = self.client.get_object(
                Bucket=self.bucket,
                Key=path,
                VersionId=s3_version_id,
                ChecksumMode="ENABLED",
            )
        except ClientError:
            raise S3FileError("No object on S3")

        return cast(dict[str, Any], obj)

    def get_head_or_raise(self, path: str, s3_version_id: str = "") -> dict[str, Any]:
        try:
            head = self.client.head_object(
                Bucket=self.bucket, Key=path, VersionId=s3_version_id
            )
        except ClientError:
            raise S3FileError("No metadata from S3")

        return cast(dict[str, Any], head)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def generate_presigned_download_url(
        self,
        *,
        path: str,
        filename: str,
        mime_type: str,
    ) -> tuple[str, datetime]:
        ttl = self.presign_ttl
        start = now_utc()
        url = self.client.generate_presigned_url(
            "get_object",
            Params=dict(
                Bucket=self.bucket,
                Key=path,
                ResponseContentDisposition=get_downloadable_content_disposition(
                    filename
                ),
                ResponseContentType=mime_type,
            ),
            ExpiresIn=ttl,
        )

        return (url, start + timedelta(seconds=ttl))

    def get_public_url(self, path: str) -> str:
        unsigned = get_client(signature_version=botocore.UNSIGNED)
        return unsigned.generate_presigned_url(
            "get_object", ExpiresIn=0, Params=dict(Bucket=self.bucket, Key=path)
        )

    # ------------------------------------------------------------------
    # Deletion & quarantine
    # ------------------------------------------------------------------

    def delete_file(self, path: str) -> bool:
        result = self.client.delete_object(Bucket=self.bucket, Key=path)
        return result.get("DeleteMarker", False)

    def quarantine_file(
        self,
        path: str,
        quarantine_bucket: str,
        reason: str = "malware",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        """Copy a file to quarantine storage, then delete the original.

        Returns True on success, False if the operation fails.
        """
        try:
            q_meta = {
                "quarantine-reason": reason,
                "quarantine-timestamp": now_utc().isoformat(),
                "original-bucket": self.bucket,
                "original-path": path,
            }
            if metadata:
                q_meta.update(metadata)

            q_path = f"{reason}/{path}"
            self.client.copy_object(
                Bucket=quarantine_bucket,
                Key=q_path,
                CopySource={"Bucket": self.bucket, "Key": path},
                Metadata=q_meta,
                MetadataDirective="REPLACE",
            )

            _log.info(
                "s3.quarantine.copied",
                source_bucket=self.bucket,
                source_path=path,
                quarantine_bucket=quarantine_bucket,
                quarantine_path=q_path,
                reason=reason,
            )

            self.delete_file(path)

            _log.info(
                "s3.quarantine.complete",
                original_path=path,
                quarantine_path=q_path,
            )

            return True

        except ClientError as exc:
            _log.error("s3.quarantine.error", path=path, error=str(exc))
            return False
