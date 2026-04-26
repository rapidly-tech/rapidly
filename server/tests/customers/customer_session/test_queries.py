"""Tests for ``rapidly/customers/customer_session/queries.py``.

Five load-bearing surfaces:

- ``get_by_token_hash`` requires the customer's
  ``can_authenticate`` (deleted_at IS NULL on Customer) — drift
  would let sessions for soft-deleted customers still
  authenticate (entitlement leak after account-deletion).
- ``get_by_token_hash`` filters out soft-deleted sessions
  (``CustomerSession.deleted_at IS NULL``). Drift would let an
  admin-revoked session continue to authenticate.
- ``get_by_token_hash`` defaults to excluding EXPIRED sessions
  (``expires_at > now()``); ``expired=True`` admin/audit
  override drops only that filter.
- ``get_by_token_hash`` looks up by exact token hash equality
  (no LIKE / substring) — drift would let an attacker brute-
  force one character at a time.
- ``delete_expired`` HARD deletes sessions whose ``expires_at``
  is in the past (cleanup cron). Drift to soft-delete would
  bloat the table indefinitely; drift to wrong comparison
  (``>`` instead of ``<``) would delete every active session.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from rapidly.customers.customer_session.queries import CustomerSessionRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByTokenHash:
    async def test_default_excludes_expired_sessions(self) -> None:
        # Pin: ``expires_at > now()`` is the default lifetime
        # gate. Drift would let expired sessions still
        # authenticate.
        repo = CustomerSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "expires_at >" in sql
        assert "2026-04-25" in sql

    async def test_expired_flag_drops_lifetime_filter(self) -> None:
        # Pin: admin / audit can opt into expired sessions.
        # Drift to always-filter would 404 every admin session-
        # detail page.
        repo = CustomerSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc", expired=True)

        sql = _compile(captured["stmt"]).lower()
        # The expiry comparison is absent.
        assert "expires_at >" not in sql

    async def test_filters_soft_deleted_sessions(self) -> None:
        # Pin: an admin-revoked session has ``deleted_at IS NOT
        # NULL`` and MUST NOT authenticate.
        repo = CustomerSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "customer_sessions.deleted_at is null" in sql

    async def test_filters_by_customer_can_authenticate(self) -> None:
        # Pin: ``Customer.can_authenticate`` resolves to
        # ``customers.deleted_at IS NULL``. Drift would let
        # sessions for soft-deleted customers still
        # authenticate (entitlement leak after deletion).
        repo = CustomerSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "customers.deleted_at is null" in sql

    async def test_token_hash_matches_literally(self) -> None:
        # Pin: equality match — drift to LIKE/substring would
        # let an attacker brute-force one character at a time.
        repo = CustomerSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("specific_hash_xyz")

        sql = _compile(captured["stmt"]).lower()
        assert "customer_sessions.token = 'specific_hash_xyz'" in sql
        # No LIKE.
        assert " like " not in sql


@pytest.mark.asyncio
class TestDeleteExpired:
    async def test_uses_hard_delete(self) -> None:
        # Pin: cleanup cron HARD-deletes (no soft delete). Drift
        # to soft delete would bloat the table indefinitely.
        repo = CustomerSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.delete_expired()

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("delete from customer_sessions")

    async def test_filters_to_expired_rows_only(self) -> None:
        # Pin: ``expires_at < now()`` — drift to ``>`` would
        # DELETE every ACTIVE session (catastrophic). Drift to
        # ``<=`` would race on the cron's tick boundary.
        repo = CustomerSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.delete_expired()

        sql = _compile(captured["stmt"]).lower()
        # The expiry comparison is strictly LESS THAN.
        assert "expires_at <" in sql
        # And the cutoff timestamp is the frozen now() literal.
        assert "2026-04-25" in sql
