"""Tests for ``rapidly/integrations/clamav/actions.py``.

ClamAV antivirus integration. Five load-bearing surfaces:

- ``CLAMAV_ENABLED=False`` short-circuits — ``scan_bytes`` returns
  ``(True, None)`` (clean) and ``is_available`` returns ``False``.
  Drift in the disabled-path semantics would either block uploads
  in dev (false-positive infected) or silently skip scans in prod
  (false-negative clean).
- ``scan_bytes`` raises ``ClamAVConnectionError`` when the client
  is unavailable (NOT a generic Exception). The worker retries on
  this specific exception type.
- ``scan_bytes`` parses three pyclamd result formats:
  - ``None`` → clean ``(True, None)``
  - ``{"stream": ("FOUND", "name")}`` → infected ``(False, "name")``
  - other → ``ClamAVScanError``
- ``get_status`` parses the version string by ``/`` delimiter into
  engine_version, signature_version, signature_date — drift would
  blank out the admin AV-status panel.
- ``get_status`` returns the disabled-stub dict (with all fields
  ``None`` / ``False``) when the integration is disabled.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.config import settings as settings_obj
from rapidly.integrations.clamav import actions as M
from rapidly.integrations.clamav.actions import (
    get_status,
    get_version,
    is_available,
    scan_bytes,
)
from rapidly.integrations.clamav.exceptions import (
    ClamAVConnectionError,
    ClamAVScanError,
)


@pytest.fixture(autouse=True)
def _reset_client() -> Any:
    """Reset the module-level ``_client`` singleton around every test."""
    original = M._client
    M._client = None
    yield
    M._client = original


@pytest.mark.asyncio
class TestIsAvailable:
    async def test_returns_false_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", False)
        assert await is_available() is False

    async def test_returns_false_when_client_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: when ``_get_client`` returns None (e.g., pyclamd not
        # installed), ``is_available`` returns False rather than
        # raising. Otherwise the health endpoint would 500 in
        # environments without the AV daemon.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        monkeypatch.setattr(M, "_get_client", lambda: None)
        assert await is_available() is False

    async def test_returns_true_when_ping_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.ping = MagicMock(return_value=True)
        monkeypatch.setattr(M, "_get_client", lambda: client)
        assert await is_available() is True

    async def test_returns_false_when_ping_returns_non_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``ping`` returning anything other than the literal
        # ``True`` (e.g., None on transient failure) yields
        # unavailable. Drift to a truthy check would let a stale
        # client's "PONG" string pass.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.ping = MagicMock(return_value="PONG")
        monkeypatch.setattr(M, "_get_client", lambda: client)
        assert await is_available() is False

    async def test_returns_false_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ping exceptions are swallowed → unavailable. Without
        # this, a transient socket error would crash health checks.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.ping = MagicMock(side_effect=ConnectionRefusedError("nope"))
        monkeypatch.setattr(M, "_get_client", lambda: client)
        assert await is_available() is False


@pytest.mark.asyncio
class TestScanBytesDisabled:
    async def test_returns_clean_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the disabled mode treats every file as clean rather
        # than rejecting uploads. This is the documented dev-mode
        # behaviour. Drift to (False, ...) would block uploads in
        # any environment without the AV daemon.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", False)
        clean, threat = await scan_bytes(b"any-payload")
        assert clean is True
        assert threat is None


@pytest.mark.asyncio
class TestScanBytesEnabled:
    async def test_raises_connection_error_when_client_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ConnectionError (NOT generic Exception) so the
        # worker's retry middleware treats it as transient.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        monkeypatch.setattr(M, "_get_client", lambda: None)
        with pytest.raises(ClamAVConnectionError, match="not available"):
            await scan_bytes(b"x")

    async def test_clean_result_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # pyclamd returns None for clean files.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.scan_stream = MagicMock(return_value=None)
        monkeypatch.setattr(M, "_get_client", lambda: client)
        clean, threat = await scan_bytes(b"clean-data")
        assert clean is True
        assert threat is None

    async def test_infected_result_extracts_threat_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``{"stream": ("FOUND", "Threat.Name")}`` → infected
        # with the second tuple element as the threat name.
        # Quarantine + alerts read this string; drift would blank
        # out incident attribution.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.scan_stream = MagicMock(
            return_value={"stream": ("FOUND", "Trojan.Generic.12345")}
        )
        monkeypatch.setattr(M, "_get_client", lambda: client)
        clean, threat = await scan_bytes(b"infected")
        assert clean is False
        assert threat == "Trojan.Generic.12345"

    async def test_infected_without_name_falls_back_to_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: ``("FOUND",)`` (length 1, missing name) must
        # NOT crash on tuple-index. Pin the ``"Unknown"`` fallback.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.scan_stream = MagicMock(return_value={"stream": ("FOUND",)})
        monkeypatch.setattr(M, "_get_client", lambda: client)
        clean, threat = await scan_bytes(b"x")
        assert clean is False
        assert threat == "Unknown"

    async def test_unexpected_result_raises_scan_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: unexpected result shapes raise ScanError (terminal),
        # NOT ConnectionError (transient). Otherwise the worker
        # would infinitely retry on protocol-level corruption.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.scan_stream = MagicMock(return_value={"stream": ("WUT", "?")})
        monkeypatch.setattr(M, "_get_client", lambda: client)
        with pytest.raises(ClamAVScanError):
            await scan_bytes(b"x")

    async def test_arbitrary_exception_wrapped_as_scan_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a generic exception from pyclamd (e.g. socket.timeout
        # mid-scan) wraps to ``ClamAVScanError`` with the original
        # cause attached via ``raise … from``.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.scan_stream = MagicMock(side_effect=RuntimeError("socket bad"))
        monkeypatch.setattr(M, "_get_client", lambda: client)
        with pytest.raises(ClamAVScanError, match="Scan failed"):
            await scan_bytes(b"x")

    async def test_connection_error_passes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: an explicit ``ClamAVConnectionError`` raised by
        # downstream code re-raises (NOT wrapped as scan error).
        # The worker's transient-retry handler depends on the
        # type being preserved.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.scan_stream = MagicMock(side_effect=ClamAVConnectionError("dropped"))
        monkeypatch.setattr(M, "_get_client", lambda: client)
        with pytest.raises(ClamAVConnectionError):
            await scan_bytes(b"x")


@pytest.mark.asyncio
class TestGetVersion:
    async def test_returns_none_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", False)
        assert await get_version() is None

    async def test_returns_none_when_client_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        monkeypatch.setattr(M, "_get_client", lambda: None)
        assert await get_version() is None

    async def test_returns_version_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.version = MagicMock(return_value="ClamAV 1.0.0/26867/Wed Feb 5")
        monkeypatch.setattr(M, "_get_client", lambda: client)
        assert await get_version() == "ClamAV 1.0.0/26867/Wed Feb 5"

    async def test_returns_none_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: a transient daemon failure during version
        # query must NOT crash the admin page.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        client = MagicMock()
        client.version = MagicMock(side_effect=ConnectionError("dropped"))
        monkeypatch.setattr(M, "_get_client", lambda: client)
        assert await get_version() is None


@pytest.mark.asyncio
class TestGetStatus:
    async def test_disabled_stub_when_setting_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the disabled stub has ``enabled=False`` and every
        # other field is the documented null. The admin page
        # renders this verbatim.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", False)
        status = await get_status()
        assert status == {
            "enabled": False,
            "available": False,
            "version": None,
            "engine_version": None,
            "signature_version": None,
            "signature_date": None,
        }

    async def test_unavailable_returns_partial_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: when ClamAV is enabled but the daemon is down, the
        # call still returns a dict (not an exception) so the admin
        # page can render the unavailable state.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        monkeypatch.setattr(M, "is_available", AsyncMock(return_value=False))
        status = await get_status()
        assert status["enabled"] is True
        assert status["available"] is False
        assert status["version"] is None

    async def test_parses_version_string_into_three_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the version-string parsing. ClamAV emits
        # ``ClamAV X.Y.Z/<sigver>/<sigdate>`` separated by ``/``.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        monkeypatch.setattr(M, "is_available", AsyncMock(return_value=True))
        monkeypatch.setattr(
            M,
            "get_version",
            AsyncMock(return_value="ClamAV 1.0.0/26867/Wed Feb 5 10:00:00 2026"),
        )
        status = await get_status()
        assert status["engine_version"] == "ClamAV 1.0.0"
        assert status["signature_version"] == "26867"
        assert status["signature_date"] == "Wed Feb 5 10:00:00 2026"

    async def test_handles_truncated_version_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: an old daemon emitting only ``ClamAV 1.0.0``
        # (no slashes) must NOT crash. Pin the partial-parse
        # behaviour: engine_version populated, others left None.
        monkeypatch.setattr(settings_obj, "CLAMAV_ENABLED", True)
        monkeypatch.setattr(M, "is_available", AsyncMock(return_value=True))
        monkeypatch.setattr(M, "get_version", AsyncMock(return_value="ClamAV 1.0.0"))
        status = await get_status()
        assert status["engine_version"] == "ClamAV 1.0.0"
        assert status["signature_version"] is None
        assert status["signature_date"] is None
