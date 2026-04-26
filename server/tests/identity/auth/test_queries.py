"""Tests for ``rapidly/identity/auth/queries.py``.

Browser-session repository. Six load-bearing surfaces:

- ``get_by_token`` HASHES the raw cookie before lookup via
  ``get_token_hash`` with the configured secret. Drift to
  compare raw cookie to stored hash would break EVERY browser
  session (no cookie would match its own DB row).
- ``get_by_token`` defaults to filtering ``expires_at > now()``;
  ``include_expired=True`` drops the lifetime gate (admin/audit
  override).
- ``count_active_for_user`` counts only non-expired rows
  (drift would inflate the count and trip the per-user session
  cap prematurely).
- ``delete_expired`` HARD-deletes via ``expires_at < now()``.
  Drift to ``>`` would catastrophically delete every ACTIVE
  session on every cron tick.
- ``evict_oldest_for_user`` keeps the ``keep`` MOST RECENT
  active sessions and HARD-deletes the rest. The "keep" subquery
  orders by ``created_at DESC`` (drift to ASC would evict the
  newest sessions instead). Both the outer DELETE and the
  inner sub-query gate on ``expires_at > now()`` so expired
  rows are NOT counted toward the keep budget AND not
  spuriously deleted by the outer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from freezegun import freeze_time

from rapidly.identity.auth.queries import UserSessionRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByToken:
    async def test_hashes_raw_cookie_before_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def _fake_hash(token: str, *, secret: str) -> str:
            captured["raw"] = token
            return f"hashed:{token}"

        monkeypatch.setattr("rapidly.identity.auth.queries.get_token_hash", _fake_hash)

        repo = UserSessionRepository(session=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)  # type: ignore[method-assign]
        await repo.get_by_token("rapidly_session_xyz")

        assert captured["raw"] == "rapidly_session_xyz"

    async def test_default_excludes_expired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.identity.auth.queries.get_token_hash",
            lambda t, *, secret: "h",
        )

        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.get_by_token("xyz")

        sql = _compile(captured["stmt"]).lower()
        assert "user_sessions.expires_at >" in sql
        assert "2026-04-25" in sql

    async def test_include_expired_drops_lifetime_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.identity.auth.queries.get_token_hash",
            lambda t, *, secret: "h",
        )

        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token("xyz", include_expired=True)

        sql = _compile(captured["stmt"]).lower()
        assert "user_sessions.expires_at >" not in sql


@pytest.mark.asyncio
class TestCountActiveForUser:
    async def test_filters_non_expired_only(self) -> None:
        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalar_one.return_value = 0
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.count_active_for_user(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "count(" in sql
        assert "user_sessions.expires_at >" in sql

    async def test_scopes_by_user_id(self) -> None:
        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalar_one.return_value = 0
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        target = uuid4()
        await repo.count_active_for_user(target)

        sql = _compile(captured["stmt"]).replace("-", "")
        assert target.hex in sql


@pytest.mark.asyncio
class TestDeleteExpired:
    async def test_hard_delete_with_correct_direction(self) -> None:
        # Pin: ``expires_at < now()``. Drift to ``>`` would
        # delete every ACTIVE session on every cron tick.
        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.delete_expired()

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("delete from user_sessions")
        assert "expires_at <" in sql
        assert "2026-04-25" in sql


@pytest.mark.asyncio
class TestEvictOldestForUser:
    async def test_keep_subquery_orders_by_created_at_desc(self) -> None:
        # Pin: drift to ASC would evict the user's NEWEST
        # sessions instead of the oldest (the opposite of what
        # the helper name claims).
        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.evict_oldest_for_user(uuid4(), keep=5)

        sql = _compile(captured["stmt"]).lower()
        assert "order by user_sessions.created_at desc" in sql
        assert "limit 5" in sql

    async def test_outer_and_inner_filter_active_sessions(self) -> None:
        # Pin: BOTH the keep-subquery AND the outer DELETE
        # filter ``expires_at > now()`` so expired rows are
        # NOT counted in the keep budget AND not double-touched
        # by the cron / evict.
        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.evict_oldest_for_user(uuid4(), keep=3)

        sql = _compile(captured["stmt"]).lower()
        # The expiry comparison appears at least twice (outer +
        # inner subquery).
        assert sql.count("expires_at >") >= 2

    async def test_uses_not_in_for_keep_subquery(self) -> None:
        # Pin: outer WHERE uses ``id NOT IN (keep_ids)`` —
        # drift to ``IN`` would delete the keepers and preserve
        # the oldest (catastrophic).
        repo = UserSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.evict_oldest_for_user(uuid4(), keep=3)

        sql = _compile(captured["stmt"]).lower()
        assert "not in" in sql
