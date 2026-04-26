"""Tests for ``rapidly/core/geolocation.py``.

The geolocation helper loads a MaxMind MMDB on first use and is
documented to fail gracefully when the database is absent (local dev
without a token). The ``UNKNOWN`` fallback matters: every call site
expects a real ``GeoInfo`` back, never ``None`` — returning None would
break ``request.scope["geo"]`` readers that do attribute access.
"""

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.core import geolocation as G
from rapidly.core.geolocation import UNKNOWN, GeoInfo, geolocate, get_request_geo


class TestGeoInfoIsFrozenSlots:
    def test_is_frozen(self) -> None:
        # A frozen result means downstream callers can safely cache
        # or share GeoInfo without worrying about mutation surprises.
        info = GeoInfo(country="US", continent="NA", asn="AS1", as_name="X")
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.country = "DE"  # type: ignore[misc]


class TestUnknownSentinel:
    def test_is_all_empty_strings(self) -> None:
        # UNKNOWN is the documented fallback — every field empty-string
        # (not None). Consumers like ``get_request_geo`` rely on the
        # shape never changing.
        assert UNKNOWN.country == ""
        assert UNKNOWN.continent == ""
        assert UNKNOWN.asn == ""
        assert UNKNOWN.as_name == ""

    def test_is_a_geoinfo_instance(self) -> None:
        assert isinstance(UNKNOWN, GeoInfo)


class TestGeolocateWithNoReader:
    def test_returns_unknown_when_reader_is_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Local-dev path: no database file, no reader — must NOT raise.
        monkeypatch.setattr(G, "_get_reader", lambda: None)
        assert geolocate("8.8.8.8") is UNKNOWN


class TestGeolocateWithReader:
    def _install_reader(
        self, monkeypatch: pytest.MonkeyPatch, reader_data: Any
    ) -> MagicMock:
        reader = MagicMock()
        reader.get = MagicMock(return_value=reader_data)
        monkeypatch.setattr(G, "_get_reader", lambda: reader)
        return reader

    def test_builds_geoinfo_from_reader_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_reader(
            monkeypatch,
            {"country": "US", "continent": "NA", "asn": 15169, "as_name": "GOOGLE"},
        )
        info = geolocate("8.8.8.8")
        assert info == GeoInfo(
            country="US", continent="NA", asn="AS15169", as_name="GOOGLE"
        )

    def test_asn_is_prefixed_with_AS(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # ``AS15169`` not ``15169`` — downstream callers (audit logs,
        # webhook payloads) rely on the standard ``AS<n>`` form.
        self._install_reader(monkeypatch, {"asn": 15169})
        assert geolocate("8.8.8.8").asn == "AS15169"

    def test_missing_asn_yields_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Some IPs have no ASN in the DB — must not KeyError. A
        # regression using ``data["asn"]`` unconditionally would crash
        # every request from those IPs.
        self._install_reader(monkeypatch, {"country": "US"})
        info = geolocate("8.8.8.8")
        assert info.asn == ""
        assert info.country == "US"

    def test_missing_fields_default_to_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_reader(monkeypatch, {})
        info = geolocate("8.8.8.8")
        assert info == GeoInfo(country="", continent="", asn="", as_name="")

    def test_reader_returning_none_yields_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # MaxMind returns None for IPs not in the DB (e.g. private
        # ranges). Must NOT dereference.
        self._install_reader(monkeypatch, None)
        assert geolocate("192.168.0.1") is UNKNOWN

    def test_reader_exception_yields_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A malformed IP string or a corrupt DB entry must not
        # propagate — callers are request handlers; an uncaught
        # exception here would 500 the whole response.
        reader = MagicMock()
        reader.get = MagicMock(side_effect=ValueError("bad IP"))
        monkeypatch.setattr(G, "_get_reader", lambda: reader)
        assert geolocate("not-an-ip") is UNKNOWN


class TestGetRequestGeo:
    def test_returns_scope_geo_when_present(self) -> None:
        # Middleware-populated ``scope["geo"]`` is used as-is.
        info = GeoInfo(country="DE", continent="EU", asn="AS1", as_name="X")
        request = MagicMock()
        request.scope = {"geo": info}
        assert get_request_geo(request) is info

    def test_returns_unknown_when_scope_has_no_geo(self) -> None:
        request = MagicMock()
        request.scope = {}
        assert get_request_geo(request) is UNKNOWN

    def test_returns_unknown_when_scope_geo_is_none(self) -> None:
        # The middleware may set ``scope["geo"] = None`` explicitly;
        # the ``or UNKNOWN`` branch must still hand back a GeoInfo.
        request = MagicMock()
        request.scope = {"geo": None}
        assert get_request_geo(request) is UNKNOWN
