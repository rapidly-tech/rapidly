"""Background tasks for ClamAV file scanning.

Files are scanned asynchronously after upload to avoid blocking the upload
request. Infected files are quarantined and disabled from download.
"""

import time
from typing import Any
from uuid import UUID

import structlog

from rapidly.catalog.file.magic import MimeTypeMismatchError, validate_magic_bytes
from rapidly.catalog.file.queries import FileRepository
from rapidly.catalog.file.s3 import S3_SERVICES
from rapidly.config import settings
from rapidly.core.utils import now_utc
from rapidly.models.file import FileScanStatus
from rapidly.observability.security_metrics import (
    record_file_scan,
    record_malware_detection,
    record_mime_mismatch,
    record_quarantine,
)
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor, dispatch_task

from . import actions as clamav_service
from .exceptions import ClamAVConnectionError, ClamAVScanError

_log = structlog.get_logger()


# ── Scanning ──


def _handle_infected_file(
    file: Any,
    file_id: UUID,
    threat_name: str | None,
    s3_service: Any,
    scan_duration: float,
) -> None:
    """Update file status and quarantine an infected file."""
    file.scan_status = FileScanStatus.infected
    file.scan_result = threat_name
    file.is_enabled = False

    _log.warning(
        "file.scan.infected",
        file_id=str(file_id),
        file_name=file.name,
        threat=threat_name,
    )

    if settings.CLAMAV_QUARANTINE_BUCKET:
        quarantined = s3_service.quarantine_file(
            path=file.path,
            quarantine_bucket=settings.CLAMAV_QUARANTINE_BUCKET,
            reason="malware",
            metadata={
                "threat-name": threat_name or "unknown",
                "file-id": str(file.id),
                "file-name": file.name,
                "workspace-id": str(file.workspace_id),
            },
        )
        if quarantined:
            _log.info(
                "file.scan.quarantined",
                file_id=str(file_id),
                quarantine_bucket=settings.CLAMAV_QUARANTINE_BUCKET,
            )
            record_quarantine(reason="malware", success=True)
        else:
            _log.error(
                "file.scan.quarantine_failed",
                file_id=str(file_id),
            )
            record_quarantine(reason="malware", success=False)

    record_file_scan(
        status="infected",
        file_size=file.size,
        duration_seconds=scan_duration,
    )
    record_malware_detection(threat_name or "unknown")


def _handle_clean_file(
    file: Any, file_id: UUID, file_data: bytes, s3_service: Any, scan_duration: float
) -> None:
    """Validate magic bytes on a ClamAV-clean file and handle MIME mismatches."""
    try:
        validate_magic_bytes(file_data, file.mime_type, strict=True)
        file.scan_status = FileScanStatus.clean
        file.scan_result = None
        _log.info(
            "file.scan.clean",
            file_id=str(file_id),
            file_name=file.name,
        )
        record_file_scan(
            status="clean",
            file_size=file.size,
            duration_seconds=scan_duration,
        )
    except MimeTypeMismatchError as e:
        file.scan_status = FileScanStatus.mime_mismatch
        file.scan_result = (
            f"MIME mismatch: declared {e.declared_type}, "
            f"detected {e.detected_type or 'unknown'}"
        )
        file.is_enabled = False

        _log.warning(
            "file.scan.mime_mismatch",
            file_id=str(file_id),
            file_name=file.name,
            declared_type=e.declared_type,
            detected_type=e.detected_type,
        )

        if settings.CLAMAV_QUARANTINE_BUCKET:
            quarantined = s3_service.quarantine_file(
                path=file.path,
                quarantine_bucket=settings.CLAMAV_QUARANTINE_BUCKET,
                reason="mime_mismatch",
                metadata={
                    "declared-type": e.declared_type,
                    "detected-type": e.detected_type or "unknown",
                    "file-id": str(file.id),
                    "file-name": file.name,
                    "workspace-id": str(file.workspace_id),
                },
            )
            if quarantined:
                _log.info(
                    "file.scan.quarantined",
                    file_id=str(file_id),
                    reason="mime_mismatch",
                )
                record_quarantine(reason="mime_mismatch", success=True)
            else:
                record_quarantine(reason="mime_mismatch", success=False)

        record_file_scan(
            status="mime_mismatch",
            file_size=file.size,
            duration_seconds=scan_duration,
        )
        record_mime_mismatch(e.declared_type, e.detected_type)


@actor(actor_name="file.scan", priority=TaskPriority.HIGH)
async def scan_file(file_id: UUID) -> None:
    """Scan a file for malware after upload.

    This task:
    1. Downloads the file from S3
    2. Scans it with ClamAV
    3. Updates the file's scan status
    4. If infected, disables the file
    """
    async with AsyncSessionMaker() as session:
        repository = FileRepository.from_session(session)
        file = await repository.get_by_id(file_id)

        if file is None:
            _log.error("file.scan.not_found", file_id=str(file_id))
            return

        # Skip if already scanned (idempotency)
        if file.scan_status not in (FileScanStatus.pending, FileScanStatus.error):
            _log.info(
                "file.scan.already_scanned",
                file_id=str(file_id),
                status=file.scan_status,
            )
            return

        # Skip if ClamAV is disabled
        if not settings.CLAMAV_ENABLED:
            _log.info(
                "file.scan.skipped",
                file_id=str(file_id),
                reason="ClamAV disabled",
            )
            await repository.update(
                file,
                update_dict={
                    "scan_status": FileScanStatus.skipped,
                    "scanned_at": now_utc(),
                },
            )
            record_file_scan(status="skipped", file_size=file.size)
            return

        # Mark as scanning
        await repository.update(
            file, update_dict={"scan_status": FileScanStatus.scanning}
        )
        await session.flush()

        try:
            # Download file from S3 with size limit to prevent OOM
            s3_service = S3_SERVICES[file.service]
            if file.size and file.size > settings.CLAMAV_MAX_SCAN_SIZE_BYTES:
                _log.warning(
                    "file.scan.too_large",
                    file_id=str(file_id),
                    file_size=file.size,
                    max_size=settings.CLAMAV_MAX_SCAN_SIZE_BYTES,
                )
                file.scan_status = FileScanStatus.skipped
                file.scan_result = "File exceeds maximum scan size"
                record_file_scan(status="skipped", file_size=file.size)
                return
            s3_object = s3_service.get_object_or_raise(file.path)
            file_data = s3_object["Body"].read()

            _log.info(
                "file.scan.started",
                file_id=str(file_id),
                file_name=file.name,
                file_size=file.size,
            )

            # Scan with ClamAV (with timing)
            scan_start = time.perf_counter()
            is_clean, threat_name = await clamav_service.scan_bytes(file_data)
            scan_duration = time.perf_counter() - scan_start

            if not is_clean:
                _handle_infected_file(
                    file, file_id, threat_name, s3_service, scan_duration
                )
            else:
                _handle_clean_file(file, file_id, file_data, s3_service, scan_duration)

        except ClamAVConnectionError as e:
            _log.error(
                "file.scan.connection_error",
                file_id=str(file_id),
                error=str(e),
            )
            file.scan_status = FileScanStatus.error
            file.scan_result = f"Connection error: {str(e)}"
            record_file_scan(status="error", file_size=file.size)

        except ClamAVScanError as e:
            _log.error(
                "file.scan.error",
                file_id=str(file_id),
                error=str(e),
            )
            file.scan_status = FileScanStatus.error
            file.scan_result = f"Scan error: {str(e)}"
            record_file_scan(status="error", file_size=file.size)

        except Exception as e:
            _log.exception(
                "file.scan.unexpected_error",
                file_id=str(file_id),
                error=str(e),
            )
            file.scan_status = FileScanStatus.error
            file.scan_result = f"Unexpected error: {type(e).__name__}"
            record_file_scan(status="error", file_size=file.size)

        finally:
            file.scanned_at = now_utc()
            session.add(file)


# ── Cleanup ──


@actor(actor_name="file.scan_all_pending", priority=TaskPriority.LOW)
async def scan_all_pending_files() -> None:
    """Scan all files that are pending scan.

    This can be used as a catch-up job if some scans were missed.
    """
    if not settings.CLAMAV_ENABLED:
        _log.info("file.scan_all_pending.skipped", reason="ClamAV disabled")
        return

    async with AsyncSessionMaker() as session:
        repository = FileRepository.from_session(session)
        pending_files = await repository.get_pending_scan()

        _log.info(
            "file.scan_all_pending.starting",
            count=len(pending_files),
        )

        for file in pending_files:
            # Enqueue individual scan jobs
            dispatch_task("file.scan", file_id=file.id)

        _log.info(
            "file.scan_all_pending.complete",
            enqueued=len(pending_files),
        )
