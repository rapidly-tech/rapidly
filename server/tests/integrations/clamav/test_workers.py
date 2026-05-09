"""Tests for ``rapidly/integrations/clamav/workers.py``.

ClamAV scan-result handlers. Three load-bearing surfaces:

- ``_handle_infected_file`` MUST set ``is_enabled=False`` so the
  download endpoint refuses to serve malware. Drift here would
  let an infected file remain downloadable post-scan even though
  the status reads ``infected`` (silent serving of malware).
- Quarantine flow only runs when ``CLAMAV_QUARANTINE_BUCKET`` is
  configured. Without it we still mark the file as infected but
  skip the S3 copy. Pin: status update happens regardless of
  quarantine outcome (so the file is disabled even if S3 is down).
- ``_handle_clean_file`` runs ``validate_magic_bytes`` on the
  ClamAV-clean payload. A MIME mismatch (e.g. PNG declared, EXE
  bytes) flips the status to ``mime_mismatch``, sets
  ``is_enabled=False``, AND optionally quarantines — same
  defence-in-depth pattern as infected files.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.catalog.file.magic import MimeTypeMismatchError
from rapidly.config import settings as settings_obj
from rapidly.integrations.clamav.workers import (
    _handle_clean_file,
    _handle_infected_file,
)
from rapidly.models.file import FileScanStatus


def _make_file(**overrides: Any) -> Any:
    """Build a mock file ORM object with the attrs the handlers touch."""
    file = MagicMock()
    file.id = uuid4()
    file.name = "report.pdf"
    file.size = 1024
    file.path = "files/report.pdf"
    file.workspace_id = uuid4()
    file.mime_type = "application/pdf"
    file.is_enabled = True
    for k, v in overrides.items():
        setattr(file, k, v)
    return file


class TestHandleInfectedFile:
    def test_disables_file_and_marks_infected(self) -> None:
        # Pin: is_enabled=False is the load-bearing safety: the
        # download endpoint refuses to serve when this flag is False.
        # Drift would silently leave malware downloadable after scan.
        file = _make_file()
        s3 = MagicMock()
        _handle_infected_file(
            file=file,
            file_id=file.id,
            threat_name="Trojan.X",
            s3_service=s3,
            scan_duration=0.5,
        )
        assert file.is_enabled is False
        assert file.scan_status == FileScanStatus.infected
        assert file.scan_result == "Trojan.X"

    def test_quarantines_when_bucket_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the quarantine call shape: reason="malware",
        # threat-name in metadata. Drift in the metadata keys
        # would break SOC retrieval workflows.
        monkeypatch.setattr(
            settings_obj, "CLAMAV_QUARANTINE_BUCKET", "rapidly-quarantine"
        )
        file = _make_file()
        s3 = MagicMock()
        s3.quarantine_file = MagicMock(return_value=True)
        _handle_infected_file(
            file=file,
            file_id=file.id,
            threat_name="Eicar",
            s3_service=s3,
            scan_duration=0.5,
        )
        s3.quarantine_file.assert_called_once()
        kwargs = s3.quarantine_file.call_args.kwargs
        assert kwargs["quarantine_bucket"] == "rapidly-quarantine"
        assert kwargs["reason"] == "malware"
        assert kwargs["metadata"]["threat-name"] == "Eicar"
        assert kwargs["metadata"]["file-id"] == str(file.id)

    def test_skips_quarantine_when_no_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: dev environments don't configure a quarantine
        # bucket. Pin: status still flips to infected, the S3 call
        # is skipped, no exception.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "")
        file = _make_file()
        s3 = MagicMock()
        _handle_infected_file(
            file=file,
            file_id=file.id,
            threat_name="X",
            s3_service=s3,
            scan_duration=0.1,
        )
        s3.quarantine_file.assert_not_called()
        assert file.scan_status == FileScanStatus.infected
        assert file.is_enabled is False

    def test_handles_none_threat_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Defensive: pyclamd occasionally returns FOUND with no
        # threat name; the bridge passes None. Pin the
        # ``"unknown"`` fallback in metadata so the SOC dashboard
        # doesn't see a literal ``None`` string.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "qb")
        file = _make_file()
        s3 = MagicMock()
        s3.quarantine_file = MagicMock(return_value=True)
        _handle_infected_file(
            file=file,
            file_id=file.id,
            threat_name=None,
            s3_service=s3,
            scan_duration=0.1,
        )
        kwargs = s3.quarantine_file.call_args.kwargs
        assert kwargs["metadata"]["threat-name"] == "unknown"

    def test_records_metrics(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: file_scan + malware_detection metrics are recorded
        # even when no quarantine bucket is configured. Otherwise
        # ops would lose detection visibility in dev / unconfigured
        # environments.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "")
        with (
            patch("rapidly.integrations.clamav.workers.record_file_scan") as rec_scan,
            patch(
                "rapidly.integrations.clamav.workers.record_malware_detection"
            ) as rec_mal,
        ):
            file = _make_file(size=2048)
            s3 = MagicMock()
            _handle_infected_file(
                file=file,
                file_id=file.id,
                threat_name="T",
                s3_service=s3,
                scan_duration=0.42,
            )
            rec_scan.assert_called_once_with(
                status="infected", file_size=2048, duration_seconds=0.42
            )
            rec_mal.assert_called_once_with("T")

    def test_records_quarantine_failure_metric(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: when S3 quarantine_file returns False (S3 outage,
        # IAM denial), the metric is emitted with success=False
        # so alerting can fire. Without this pin, a silent S3
        # failure during malware quarantine would go undetected.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "qb")
        with patch("rapidly.integrations.clamav.workers.record_quarantine") as rec_q:
            file = _make_file()
            s3 = MagicMock()
            s3.quarantine_file = MagicMock(return_value=False)
            _handle_infected_file(
                file=file,
                file_id=file.id,
                threat_name="T",
                s3_service=s3,
                scan_duration=0.1,
            )
            rec_q.assert_called_once_with(reason="malware", success=False)


class TestHandleCleanFile:
    def test_marks_clean_when_magic_bytes_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a clean ClamAV result + matching magic bytes flips
        # the status to clean and clears scan_result. The download
        # endpoint reads scan_status to gate access.
        with patch(
            "rapidly.integrations.clamav.workers.validate_magic_bytes",
            return_value=None,
        ):
            file = _make_file(size=512)
            s3 = MagicMock()
            _handle_clean_file(
                file=file,
                file_id=file.id,
                file_data=b"any",
                s3_service=s3,
                scan_duration=0.05,
            )
            assert file.scan_status == FileScanStatus.clean
            assert file.scan_result is None
            # is_enabled untouched (still True from fixture default).
            assert file.is_enabled is True

    def test_mime_mismatch_disables_and_quarantines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: MIME mismatch is treated like infected — status flips,
        # is_enabled flag flips, quarantine fires (when configured).
        # This is the defence-in-depth for content-type spoofing.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "qb")
        err = MimeTypeMismatchError(
            declared_type="image/png", detected_type="application/x-msdownload"
        )
        with patch(
            "rapidly.integrations.clamav.workers.validate_magic_bytes",
            side_effect=err,
        ):
            file = _make_file()
            s3 = MagicMock()
            s3.quarantine_file = MagicMock(return_value=True)
            _handle_clean_file(
                file=file,
                file_id=file.id,
                file_data=b"MZ",
                s3_service=s3,
                scan_duration=0.05,
            )
            assert file.scan_status == FileScanStatus.mime_mismatch
            assert file.is_enabled is False
            # scan_result captures both declared + detected types
            # so the SOC can triage the spoof.
            assert "image/png" in (file.scan_result or "")
            assert "application/x-msdownload" in (file.scan_result or "")
            s3.quarantine_file.assert_called_once()
            kwargs = s3.quarantine_file.call_args.kwargs
            assert kwargs["reason"] == "mime_mismatch"
            assert kwargs["metadata"]["declared-type"] == "image/png"
            assert kwargs["metadata"]["detected-type"] == "application/x-msdownload"

    def test_mime_mismatch_handles_none_detected_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: ``detected_type=None`` means magic bytes were
        # unreadable. Pin the ``"unknown"`` fallback in scan_result
        # text and quarantine metadata so the SOC dashboard doesn't
        # render literal ``None``.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "qb")
        err = MimeTypeMismatchError(declared_type="image/png", detected_type=None)
        with patch(
            "rapidly.integrations.clamav.workers.validate_magic_bytes",
            side_effect=err,
        ):
            file = _make_file()
            s3 = MagicMock()
            s3.quarantine_file = MagicMock(return_value=True)
            _handle_clean_file(
                file=file,
                file_id=file.id,
                file_data=b"x",
                s3_service=s3,
                scan_duration=0.01,
            )
            assert "unknown" in (file.scan_result or "")
            kwargs = s3.quarantine_file.call_args.kwargs
            assert kwargs["metadata"]["detected-type"] == "unknown"

    def test_mime_mismatch_skips_quarantine_when_no_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Same defensive pin as for malware: dev environments
        # without a quarantine bucket still flip the status +
        # is_enabled, but skip the S3 call.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "")
        err = MimeTypeMismatchError(
            declared_type="image/png", detected_type="application/x-msdownload"
        )
        with patch(
            "rapidly.integrations.clamav.workers.validate_magic_bytes",
            side_effect=err,
        ):
            file = _make_file()
            s3 = MagicMock()
            _handle_clean_file(
                file=file,
                file_id=file.id,
                file_data=b"MZ",
                s3_service=s3,
                scan_duration=0.01,
            )
            assert file.scan_status == FileScanStatus.mime_mismatch
            assert file.is_enabled is False
            s3.quarantine_file.assert_not_called()

    def test_mime_mismatch_records_metrics(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the metric tuple: file_scan(mime_mismatch) +
        # mime_mismatch(declared, detected). Drift would lose the
        # cross-tabulation of which declared types attackers favour.
        monkeypatch.setattr(settings_obj, "CLAMAV_QUARANTINE_BUCKET", "")
        err = MimeTypeMismatchError(
            declared_type="application/pdf", detected_type="text/plain"
        )
        with (
            patch(
                "rapidly.integrations.clamav.workers.validate_magic_bytes",
                side_effect=err,
            ),
            patch("rapidly.integrations.clamav.workers.record_file_scan") as rec_scan,
            patch("rapidly.integrations.clamav.workers.record_mime_mismatch") as rec_mm,
        ):
            file = _make_file(size=1024)
            s3 = MagicMock()
            _handle_clean_file(
                file=file,
                file_id=file.id,
                file_data=b"x",
                s3_service=s3,
                scan_duration=0.05,
            )
            rec_scan.assert_called_once_with(
                status="mime_mismatch", file_size=1024, duration_seconds=0.05
            )
            rec_mm.assert_called_once_with("application/pdf", "text/plain")
