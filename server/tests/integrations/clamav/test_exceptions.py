"""Tests for ``rapidly/integrations/clamav/exceptions.py``.

ClamAV exception hierarchy. Load-bearing because callers in
``actions.py`` and the worker pipeline catch on the BASE class
(``ClamAVError``) when escalating to quarantine, but distinguish
``ClamAVConnectionError`` (transient — retry) from
``ClamAVScanError`` (terminal — quarantine + alert).

Drift in the inheritance chain would either swallow connection
errors as scan errors (and falsely quarantine clean files) or
re-raise scan errors as connection errors (and infinitely retry
malware-detection failures).
"""

from __future__ import annotations

import pytest

from rapidly.integrations.clamav.exceptions import (
    ClamAVConnectionError,
    ClamAVError,
    ClamAVScanError,
)


class TestExceptionHierarchy:
    def test_connection_error_inherits_from_clamav_error(self) -> None:
        # Pin: ``except ClamAVError`` catches both subtypes — the
        # quarantine-escalation path relies on this.
        assert issubclass(ClamAVConnectionError, ClamAVError)

    def test_scan_error_inherits_from_clamav_error(self) -> None:
        assert issubclass(ClamAVScanError, ClamAVError)

    def test_clamav_error_inherits_from_exception(self) -> None:
        # Pin: top-level base extends the standard Exception
        # hierarchy so callers can use ``except Exception`` as a
        # last-ditch fallback.
        assert issubclass(ClamAVError, Exception)

    def test_subtypes_are_distinct(self) -> None:
        # Pin: connection error and scan error are NOT subclasses
        # of each other. ``except ClamAVConnectionError`` must NOT
        # catch ``ClamAVScanError`` (otherwise transient retries
        # would loop on terminal failures).
        assert not issubclass(ClamAVConnectionError, ClamAVScanError)
        assert not issubclass(ClamAVScanError, ClamAVConnectionError)

    def test_can_be_raised_and_caught_via_base_class(self) -> None:
        # End-to-end: every exception type can be caught via the
        # base class. ``pytest.raises(ClamAVError)`` succeeds for
        # all three.
        for cls in (ClamAVError, ClamAVConnectionError, ClamAVScanError):
            with pytest.raises(ClamAVError, match="test") as excinfo:
                raise cls("test")
            assert isinstance(excinfo.value, cls)
