"""Tests for ``rapidly/health/api.py``.

Liveness + readiness probes. Three load-bearing surfaces:

- ``healthz`` returns 200 only when BOTH the DB AND Redis are
  reachable. Either failing returns 503 — orchestrators (k8s,
  Render) recycle the pod on 503; a regression that swallowed
  one of the failures would leave dead pods in service
- DB is checked FIRST (the cheaper SELECT 1 fails faster than a
  Redis network round-trip in a typical outage)
- ``healthz_security`` reports ``ok`` when ClamAV is available,
  ``degraded`` when not — and does NOT expose version / signature
  details (the docstring calls this out as security-by-design)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from redis import RedisError
from sqlalchemy.exc import SQLAlchemyError

from rapidly.health.api import healthz, healthz_security


def _ok_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


def _ok_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.mark.asyncio
class TestHealthz:
    async def test_returns_ok_when_both_available(self) -> None:
        result = await healthz(_ok_session(), _ok_redis())
        assert result == {"status": "ok"}

    async def test_503_when_database_unavailable(self) -> None:
        # Load-bearing pin. SQLAlchemyError → 503 means orchestrator
        # recycles the pod. A regression that swallowed the error
        # would leave dead pods in service.
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=SQLAlchemyError("boom"))
        with pytest.raises(HTTPException) as exc:
            await healthz(session, _ok_redis())
        assert exc.value.status_code == 503
        assert "Database" in exc.value.detail

    async def test_503_when_redis_unavailable(self) -> None:
        redis = AsyncMock()
        redis.ping = AsyncMock(side_effect=RedisError("conn lost"))
        with pytest.raises(HTTPException) as exc:
            await healthz(_ok_session(), redis)
        assert exc.value.status_code == 503
        assert "Redis" in exc.value.detail

    async def test_database_checked_before_redis(self) -> None:
        # DB check runs first; if DB fails, Redis is never pinged.
        # Pin the order so a refactor doesn't reverse it (Redis
        # check would then mask DB failures during simultaneous
        # outages).
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=SQLAlchemyError("boom"))
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        with pytest.raises(HTTPException):
            await healthz(session, redis)
        redis.ping.assert_not_awaited()


@pytest.mark.asyncio
class TestHealthzSecurity:
    async def test_returns_ok_when_clamav_available(self) -> None:
        with patch(
            "rapidly.health.api.clamav_service.get_status",
            new=AsyncMock(return_value={"enabled": True, "available": True}),
        ):
            result = await healthz_security()
        assert result["status"] == "ok"
        assert result["services"]["clamav"]["available"] is True

    async def test_returns_degraded_when_clamav_unavailable(self) -> None:
        # Documented "degraded" tier — Rapidly continues running
        # but file uploads can't be virus-scanned. Pin the literal
        # so dashboards keep filtering correctly.
        with patch(
            "rapidly.health.api.clamav_service.get_status",
            new=AsyncMock(return_value={"enabled": True, "available": False}),
        ):
            result = await healthz_security()
        assert result["status"] == "degraded"

    async def test_does_not_expose_version_or_signatures(self) -> None:
        # Security pin (docstring calls this out): the response
        # MUST NOT include version or signature-DB details that
        # would aid an attacker timing AV evasion.
        with patch(
            "rapidly.health.api.clamav_service.get_status",
            new=AsyncMock(
                return_value={
                    "enabled": True,
                    "available": True,
                    "version": "ClamAV 1.0.0",
                    "signatures": "daily-26000",
                }
            ),
        ):
            result = await healthz_security()
        # Top-level shape doesn't bleed extra keys.
        assert "version" not in result
        assert "signatures" not in result
        # ClamAV nested entry has only ``enabled`` and ``available``.
        assert set(result["services"]["clamav"].keys()) == {
            "enabled",
            "available",
        }

    async def test_handles_missing_keys_in_status_dict(self) -> None:
        # If ``get_status`` returns a partial dict (e.g. on its
        # own degraded path), the helper falls back to False
        # rather than KeyError — orchestrator probes must always
        # get a parseable JSON response.
        with patch(
            "rapidly.health.api.clamav_service.get_status",
            new=AsyncMock(return_value={}),
        ):
            result = await healthz_security()
        assert result["status"] == "degraded"
        assert result["services"]["clamav"]["enabled"] is False
        assert result["services"]["clamav"]["available"] is False
