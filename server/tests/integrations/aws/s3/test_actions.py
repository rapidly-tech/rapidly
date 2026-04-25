"""Tests for ``rapidly/integrations/aws/s3/actions.py``.

Six load-bearing surfaces of ``S3Service``:

- ``upload`` only sends ``ChecksumAlgorithm=SHA256`` +
  ``ChecksumSHA256=...`` when the caller supplies a checksum.
  Drift to always-add would force every upload to recompute the
  SHA-256 server-side; drift to never-add would skip integrity
  validation when the caller wanted it.
- ``create_multipart_upload`` constructs the upload path as
  ``{namespace}/{workspace_id}/{file_uuid}/{name}``. The
  workspace UUID prefix is the multi-tenant isolation guard —
  drift to drop it would cause collisions across workspaces and
  silently overwrite each other's files.
- ``create_multipart_upload`` raises ``S3FileError`` when
  ``workspace_id`` is missing. Drift would let the path collapse
  to ``//{file_uuid}/{name}`` and cross-tenant on retrieval.
- ``quarantine_file`` copies to ``{reason}/{path}`` in the
  quarantine bucket, applies the documented metadata, and
  deletes the source AFTER copy succeeds. Drift to delete-
  before-copy would lose data on copy failure.
- ``quarantine_file`` swallows ClientError into a False return.
  Drift to propagate would crash the malware-cleanup worker on
  transient S3 hiccups, leaving infected files in the live bucket.
- ``generate_presigned_download_url`` uses ``presign_ttl`` for
  both the ``ExpiresIn`` argument AND the returned ``expires_at``
  datetime. Drift would let the client cache a URL that fails
  before the documented expiry.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from freezegun import freeze_time

from rapidly.integrations.aws.s3.actions import S3Service
from rapidly.integrations.aws.s3.exceptions import S3FileError
from rapidly.integrations.aws.s3.types import (
    S3FileCreate,
    S3FileCreateMultipart,
)


def _make_service(client: Any | None = None, bucket: str = "test-bucket") -> S3Service:
    return S3Service(bucket=bucket, presign_ttl=600, client=client or MagicMock())


class TestUploadChecksumGate:
    def test_no_checksum_omits_algorithm_field(self) -> None:
        # Pin: when caller omits the checksum, we don't tell S3
        # to validate one. Drift to always-add would cause S3 to
        # recompute SHA-256 server-side on every upload.
        client = MagicMock()
        service = _make_service(client=client)

        service.upload(b"data", "path/to/file", "text/plain")

        kwargs = client.put_object.call_args.kwargs
        assert "ChecksumAlgorithm" not in kwargs
        assert "ChecksumSHA256" not in kwargs

    def test_with_checksum_adds_both_fields(self) -> None:
        # Pin: caller-supplied checksum surfaces both
        # ``ChecksumAlgorithm`` and ``ChecksumSHA256`` so S3
        # rejects mismatched bodies.
        client = MagicMock()
        service = _make_service(client=client)

        service.upload(b"data", "path/to/file", "text/plain", "abc=")

        kwargs = client.put_object.call_args.kwargs
        assert kwargs["ChecksumAlgorithm"] == "SHA256"
        assert kwargs["ChecksumSHA256"] == "abc="


class TestCreateMultipartUploadPath:
    def test_path_includes_workspace_id_isolation_prefix(self) -> None:
        # Pin: ``{namespace}/{workspace_id}/{file_uuid}/{name}``.
        # The workspace UUID prefix is the multi-tenant isolation
        # guard — drift would cause collisions across workspaces.
        from uuid import uuid4

        client = MagicMock()
        client.create_multipart_upload.return_value = {"UploadId": "u1"}
        client.generate_presigned_url.return_value = "https://signed/"
        service = _make_service(client=client)

        workspace_id = uuid4()
        data = S3FileCreate(
            workspace_id=workspace_id,
            name="report.pdf",
            mime_type="application/pdf",
            size=1234,
            upload=S3FileCreateMultipart(parts=[]),
        )
        result = service.create_multipart_upload(data, namespace="files")

        # The upload path includes namespace + workspace id +
        # the per-file uuid + the original filename.
        assert result.upload.path.startswith(f"files/{workspace_id}/")
        assert result.upload.path.endswith("/report.pdf")
        # And it's exactly four slash-separated parts.
        assert result.upload.path.count("/") == 3

    def test_missing_workspace_id_raises(self) -> None:
        # Pin: workspace_id is required. Drift would let the path
        # collapse to ``//{file_uuid}/{name}`` and cross-tenant on
        # retrieval.
        client = MagicMock()
        service = _make_service(client=client)

        data = S3FileCreate(
            workspace_id=None,
            name="report.pdf",
            mime_type="application/pdf",
            size=1234,
            upload=S3FileCreateMultipart(parts=[]),
        )
        with pytest.raises(S3FileError, match="Workspace ID"):
            service.create_multipart_upload(data)

    def test_missing_upload_id_raises(self) -> None:
        # Pin: an S3 response without ``UploadId`` is treated as
        # a hard error. Drift to silently fall through would
        # produce an S3FileUpload with an empty upload id → every
        # subsequent UploadPart call would 400.
        from uuid import uuid4

        client = MagicMock()
        client.create_multipart_upload.return_value = {}  # no UploadId
        service = _make_service(client=client)

        data = S3FileCreate(
            workspace_id=uuid4(),
            name="report.pdf",
            mime_type="application/pdf",
            size=1234,
            upload=S3FileCreateMultipart(parts=[]),
        )
        with pytest.raises(S3FileError, match="upload ID"):
            service.create_multipart_upload(data)


class TestQuarantineFile:
    def test_copies_to_reason_prefixed_path(self) -> None:
        # Pin: quarantine path is ``{reason}/{path}`` in the
        # quarantine bucket. Drift would lose the audit trail
        # that distinguishes malware from policy-violation
        # quarantine moves.
        client = MagicMock()
        service = _make_service(client=client, bucket="live")

        ok = service.quarantine_file(
            "tenant1/abc/file.pdf",
            quarantine_bucket="quarantine",
            reason="malware",
        )

        assert ok is True
        copy_kwargs = client.copy_object.call_args.kwargs
        assert copy_kwargs["Bucket"] == "quarantine"
        assert copy_kwargs["Key"] == "malware/tenant1/abc/file.pdf"
        # Source is the live bucket + original key.
        assert copy_kwargs["CopySource"] == {
            "Bucket": "live",
            "Key": "tenant1/abc/file.pdf",
        }

    def test_metadata_carries_audit_trail(self) -> None:
        # Pin: documented metadata keys (``quarantine-reason``,
        # ``quarantine-timestamp``, ``original-bucket``,
        # ``original-path``). Drift to drop a key would lose the
        # forensic context for incident-response.
        client = MagicMock()
        service = _make_service(client=client, bucket="live")

        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            service.quarantine_file(
                "p.pdf",
                quarantine_bucket="quarantine",
                reason="malware",
            )

        meta = client.copy_object.call_args.kwargs["Metadata"]
        assert meta["quarantine-reason"] == "malware"
        assert meta["original-bucket"] == "live"
        assert meta["original-path"] == "p.pdf"
        assert meta["quarantine-timestamp"].startswith("2026-04-25")

    def test_metadata_directive_is_replace(self) -> None:
        # Pin: ``MetadataDirective=REPLACE`` so the quarantine
        # metadata wins over whatever was on the source object.
        # Drift to ``COPY`` would carry over the source's
        # metadata (potentially overwriting our forensic keys).
        client = MagicMock()
        service = _make_service(client=client, bucket="live")
        service.quarantine_file("p.pdf", quarantine_bucket="quarantine")
        assert client.copy_object.call_args.kwargs["MetadataDirective"] == "REPLACE"

    def test_deletes_source_after_successful_copy(self) -> None:
        # Pin: COPY then DELETE (NOT delete-then-copy). Drift to
        # delete-first would lose data on a copy failure.
        client = MagicMock()
        service = _make_service(client=client, bucket="live")

        service.quarantine_file(
            "tenant1/abc/file.pdf",
            quarantine_bucket="quarantine",
        )

        # The source delete uses the live bucket.
        delete_kwargs = client.delete_object.call_args.kwargs
        assert delete_kwargs["Bucket"] == "live"
        assert delete_kwargs["Key"] == "tenant1/abc/file.pdf"

        # And copy was called BEFORE delete (call ordering pin).
        method_names = [call_obj[0] for call_obj in client.method_calls if call_obj[0]]
        assert method_names.index("copy_object") < method_names.index("delete_object")

    def test_client_error_returns_false(self) -> None:
        # Pin: transient S3 hiccups MUST NOT crash the malware-
        # cleanup worker (which would leave infected files in
        # the live bucket). Drift to raise would re-add the file
        # to the worker queue, but our worker sees False as
        # "skip; admin will retry manually".
        client = MagicMock()
        client.copy_object.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceUnavailable"}},
            operation_name="CopyObject",
        )
        service = _make_service(client=client, bucket="live")

        ok = service.quarantine_file(
            "p.pdf",
            quarantine_bucket="quarantine",
        )

        assert ok is False
        # Source NOT deleted on copy failure.
        client.delete_object.assert_not_called()


class TestPresignedDownloadUrlExpiry:
    def test_expires_at_matches_presign_ttl(self) -> None:
        # Pin: returned ``expires_at`` equals "now + ttl". Drift
        # would let the client cache a URL that fails before our
        # documented expiry — surface as broken-download UX.
        from datetime import timedelta

        client = MagicMock()
        client.generate_presigned_url.return_value = "https://signed/"
        service = _make_service(client=client)
        service.presign_ttl = 600

        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            url, expires = service.generate_presigned_download_url(
                path="p.pdf", filename="report.pdf", mime_type="application/pdf"
            )

        assert url == "https://signed/"
        assert expires == datetime(2026, 4, 25, 14, 30, tzinfo=UTC) + timedelta(
            seconds=600
        )

    def test_expires_in_argument_matches_ttl(self) -> None:
        # Pin: ExpiresIn passed to S3 == presign_ttl. Drift
        # would mismatch our returned ``expires_at`` with the
        # actual S3 expiry.
        client = MagicMock()
        client.generate_presigned_url.return_value = "u"
        service = _make_service(client=client)
        service.presign_ttl = 900

        service.generate_presigned_download_url(
            path="p.pdf", filename="r.pdf", mime_type="application/pdf"
        )

        kwargs = client.generate_presigned_url.call_args.kwargs
        assert kwargs["ExpiresIn"] == 900

    def test_content_disposition_is_attachment(self) -> None:
        # Pin: download URL forces ``Content-Disposition:
        # attachment``. Drift to ``inline`` would let HTML files
        # render in the browser — XSS hazard for any
        # user-uploaded content.
        client = MagicMock()
        client.generate_presigned_url.return_value = "u"
        service = _make_service(client=client)

        service.generate_presigned_download_url(
            path="p.html", filename="payload.html", mime_type="text/html"
        )

        params = client.generate_presigned_url.call_args.kwargs["Params"]
        assert params["ResponseContentDisposition"].startswith("attachment;")
