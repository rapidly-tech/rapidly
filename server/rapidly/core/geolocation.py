"""IP geolocation lookup using an IPInfo Country+ASN MMDB database.

Provides country, continent, and ASN data for any IP address via the
local database file.  Falls back gracefully when the database is absent
(e.g. local development without a token).

Usage::

    from rapidly.core.geolocation import geolocate, get_request_geo

    # Direct lookup
    info = geolocate("8.8.8.8")
    # GeoInfo(country="US", continent="NA", asn="AS15169", as_name="GOOGLE")

    # From a FastAPI request (set by middleware)
    @router.get("/")
    async def endpoint(request: Request):
        geo = get_request_geo(request)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from rapidly.config import settings

if TYPE_CHECKING:
    from fastapi import Request

_log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GeoInfo:
    """Geolocation result for a single IP address."""

    country: str  # ISO 3166-1 alpha-2 (e.g. "US", "DE")
    continent: str  # Two-letter continent code (e.g. "NA", "EU")
    asn: str  # AS number with prefix (e.g. "AS15169")
    as_name: str  # AS organisation name (e.g. "GOOGLE")


UNKNOWN = GeoInfo(country="", continent="", asn="", as_name="")

# ---------------------------------------------------------------------------
# Database singleton
# ---------------------------------------------------------------------------

_reader: Any | None = None
_initialised = False


def _get_reader() -> Any | None:
    """Lazily open the MMDB reader, returning None if the DB is absent."""
    global _reader, _initialised
    if _initialised:
        return _reader

    _initialised = True
    db_path = os.path.join(
        settings.IP_GEOLOCATION_DATABASE_DIRECTORY_PATH,
        settings.IP_GEOLOCATION_DATABASE_NAME,
    )
    if not os.path.isfile(db_path):
        _log.info("Geolocation database not found, lookups disabled", path=db_path)
        return None

    try:
        import maxminddb

        _reader = maxminddb.open_database(db_path)
        _log.info("Geolocation database loaded", path=db_path)
    except Exception:
        _log.warning("Failed to open geolocation database", path=db_path, exc_info=True)

    return _reader


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def geolocate(ip: str) -> GeoInfo:
    """Look up geolocation data for *ip*, returning ``UNKNOWN`` on failure."""
    reader = _get_reader()
    if reader is None:
        return UNKNOWN

    try:
        data = reader.get(ip)
    except Exception:
        return UNKNOWN

    if data is None:
        return UNKNOWN

    return GeoInfo(
        country=data.get("country", ""),
        continent=data.get("continent", ""),
        asn=f"AS{data['asn']}" if "asn" in data else "",
        as_name=data.get("as_name", ""),
    )


def get_request_geo(request: Request) -> GeoInfo:
    """Retrieve geolocation data attached to *request* by the middleware."""
    return request.scope.get("geo") or UNKNOWN
