"""Tests for ``rapidly/integrations/aws/s3/client.py``.

Thin boto3 wrapper. The module pulls AWS credentials + endpoint +
signature version from ``settings`` and builds an S3 client; a
module-level ``client`` singleton caches one at import.

Pins:
- ``get_client`` threads the documented settings into ``boto3.client``
  (endpoint_url, credentials, region, signature_version)
- ``signature_version`` defaults to ``settings.AWS_SIGNATURE_VERSION``
  but accepts an override — a presigned-URL caller can drop down to
  ``s3v2`` for specific legacy buckets without mutating the global
- Module-level ``client`` singleton is a real S3 client instance
- ``__all__`` exports ``client`` + ``get_client``
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from rapidly.config import settings
from rapidly.integrations.aws.s3 import client as M
from rapidly.integrations.aws.s3.client import get_client


class TestGetClient:
    def _captured(self) -> tuple[MagicMock, dict[str, Any]]:
        captured: dict[str, Any] = {}

        def fake_boto3_client(service: str, **kwargs: Any) -> MagicMock:
            captured["service"] = service
            captured.update(kwargs)
            return MagicMock(name="S3Client")

        return MagicMock(side_effect=fake_boto3_client), captured

    def test_builds_s3_client_with_configured_credentials(self) -> None:
        fake, captured = self._captured()
        with patch("rapidly.integrations.aws.s3.client.boto3.client", fake):
            get_client()
        assert captured["service"] == "s3"
        assert captured["endpoint_url"] == settings.S3_ENDPOINT_URL
        assert captured["aws_access_key_id"] == settings.AWS_ACCESS_KEY_ID
        assert captured["aws_secret_access_key"] == settings.AWS_SECRET_ACCESS_KEY

    def test_signature_version_defaults_to_settings(self) -> None:
        fake, captured = self._captured()
        with patch("rapidly.integrations.aws.s3.client.boto3.client", fake):
            get_client()
        cfg = captured["config"]
        assert cfg.signature_version == settings.AWS_SIGNATURE_VERSION

    def test_region_from_settings(self) -> None:
        fake, captured = self._captured()
        with patch("rapidly.integrations.aws.s3.client.boto3.client", fake):
            get_client()
        cfg = captured["config"]
        assert cfg.region_name == settings.AWS_REGION

    def test_signature_version_override_is_honoured(self) -> None:
        # A caller generating presigned URLs for a legacy bucket
        # can drop to ``s3v2`` without mutating the global singleton.
        fake, captured = self._captured()
        with patch("rapidly.integrations.aws.s3.client.boto3.client", fake):
            get_client(signature_version="s3v2")
        cfg = captured["config"]
        assert cfg.signature_version == "s3v2"


class TestSingleton:
    def test_module_level_client_is_built_at_import(self) -> None:
        # ``client`` is the convenience singleton; pinning prevents a
        # regression that lazy-builds it and stalls the first request.
        assert M.client is not None


class TestExports:
    def test_all_declared(self) -> None:
        assert M.__all__ == ("client", "get_client")
