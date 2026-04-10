"""ClamAV service for malware scanning.

This service provides integration with ClamAV antivirus daemon for scanning
uploaded files. It supports both Unix socket and TCP connections.

Usage:
    from rapidly.integrations.clamav import clamav_service

    # Scan bytes directly
    is_clean, threat = await clamav_service.scan_bytes(file_data)

    # Check if ClamAV is available
    if await clamav_service.is_available():
        ...
"""

import asyncio
from io import BytesIO
from typing import Any

import structlog

from rapidly.config import settings

from .exceptions import ClamAVConnectionError, ClamAVScanError

_log = structlog.get_logger()


# ── Initialization ──


_client: Any = None


def _get_client() -> Any:
    """Lazily initialize ClamAV client."""
    global _client
    if _client is None:
        try:
            import pyclamd

            if settings.CLAMAV_SOCKET_PATH:
                _client = pyclamd.ClamdUnixSocket(filename=settings.CLAMAV_SOCKET_PATH)
            else:
                _client = pyclamd.ClamdNetworkSocket(
                    host=settings.CLAMAV_HOST,
                    port=settings.CLAMAV_PORT,
                )
        except ImportError:
            _log.warning(
                "clamav.client_not_installed",
                message="pyclamd not installed, scanning disabled",
            )
            return None
        except Exception as e:
            _log.error("clamav.connection_error", error=str(e))
            return None
    return _client


# ── Scanning ──


async def is_available() -> bool:
    """Check if ClamAV daemon is available and responding."""
    if not settings.CLAMAV_ENABLED:
        return False

    try:
        client = _get_client()
        if client is None:
            return False

        # Run ping in executor to avoid blocking
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, client.ping)
        # pyclamd returns True/False for ping
        return result is True
    except Exception as e:
        _log.warning("clamav.ping_failed", error=str(e))
        return False


async def scan_bytes(data: bytes) -> tuple[bool, str | None]:
    """Scan file bytes for malware.

    Args:
        data: The file content as bytes

    Returns:
        Tuple of (is_clean, threat_name)
        - (True, None) if file is clean
        - (False, "Trojan.Generic") if infected

    Raises:
        ClamAVConnectionError: If cannot connect to ClamAV
        ClamAVScanError: If scan fails for other reasons
    """
    if not settings.CLAMAV_ENABLED:
        _log.debug("clamav.disabled", size=len(data))
        return True, None

    client = _get_client()
    if client is None:
        raise ClamAVConnectionError("ClamAV client not available")

    try:
        loop = asyncio.get_running_loop()

        # Run scan in executor to avoid blocking
        def do_scan() -> dict[str, tuple[str, str]] | None:
            stream = BytesIO(data)
            return client.scan_stream(stream)

        result = await loop.run_in_executor(None, do_scan)

        # pyclamd result format:
        # - None for clean files
        # - {"stream": ("FOUND", "ThreatName")} for infected files
        if result is None:
            _log.info(
                "clamav.scan.clean",
                size=len(data),
                size_mb=round(len(data) / 1024 / 1024, 2),
            )
            return True, None

        # Check for infection
        stream_result = result.get("stream")
        if stream_result and stream_result[0] == "FOUND":
            threat_name = stream_result[1] if len(stream_result) > 1 else "Unknown"
            _log.warning(
                "clamav.scan.infected",
                size=len(data),
                threat=threat_name,
            )
            return False, threat_name

        # Unexpected result
        _log.error("clamav.scan.error", result=result)
        raise ClamAVScanError(f"Unexpected scan result: {result}")

    except ClamAVConnectionError:
        raise
    except ClamAVScanError:
        raise
    except Exception as e:
        _log.error("clamav.scan.exception", error=str(e), error_type=type(e).__name__)
        raise ClamAVScanError(f"Scan failed: {str(e)}") from e


# ── Status ──


async def get_version() -> str | None:
    """Get ClamAV version string."""
    if not settings.CLAMAV_ENABLED:
        return None

    client = _get_client()
    if client is None:
        return None

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, client.version)
    except Exception:
        _log.debug("ClamAV version check failed", exc_info=True)
        return None


async def get_status() -> dict[str, Any]:
    """Get comprehensive ClamAV status.

    Returns:
        Dictionary with status information:
        - enabled: Whether ClamAV is enabled in settings
        - available: Whether ClamAV daemon is responding
        - version: Full version string including signature info
        - engine_version: ClamAV engine version
        - signature_version: Virus signature database version
        - signature_date: Date of signature database
    """
    status: dict[str, Any] = {
        "enabled": settings.CLAMAV_ENABLED,
        "available": False,
        "version": None,
        "engine_version": None,
        "signature_version": None,
        "signature_date": None,
    }

    if not settings.CLAMAV_ENABLED:
        return status

    # Check availability
    status["available"] = await is_available()

    if not status["available"]:
        return status

    # Get version info
    version = await get_version()
    status["version"] = version

    if version:
        # Parse version string: "ClamAV 1.0.0/26867/Wed Feb 5 10:00:00 2026"
        parts = version.split("/")
        if len(parts) >= 1:
            status["engine_version"] = parts[0].strip()
        if len(parts) >= 2:
            status["signature_version"] = parts[1].strip()
        if len(parts) >= 3:
            status["signature_date"] = parts[2].strip()

    return status


# Singleton instance
