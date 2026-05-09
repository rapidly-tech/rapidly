"""Tests for ``rapidly/identity/member_session/queries.py``.

Member-portal session lookup. Five load-bearing surfaces:

- ``get_by_token_hash`` filters out soft-deleted SESSIONS
  (``MemberSession.deleted_at IS NULL``). Drift would let an
  admin-revoked session continue to authenticate.
- ``get_by_token_hash`` filters out soft-deleted MEMBERS
  (``Member.deleted_at IS NULL``). Drift would let a session
  for a deleted member still authenticate (entitlement leak
  after member-deletion).
- ``get_by_token_hash`` defaults to excluding EXPIRED sessions
  (``expires_at > now()``); ``expired=True`` admin/audit
  override drops only that filter.
- The lookup uses EXACT equality on the hash (no LIKE) — drift
  would let an attacker brute-force one character at a time.
- ``delete_expired`` HARD-deletes via ``expires_at < now()``.
  Drift to ``>`` would catastrophically delete every ACTIVE
  session on every cron tick.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from rapidly.identity.member_session.queries import MemberSessionRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByTokenHash:
    async def _captured(self, *, expired: bool = False) -> str:
        repo = MemberSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.unique.return_value.scalar_one_or_none.return_value = None
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.get_by_token_hash("hash_abc", expired=expired)
        return _compile(captured["stmt"]).lower()

    async def test_filters_soft_deleted_sessions(self) -> None:
        # Pin: admin-revoked sessions don't authenticate.
        sql = await self._captured()
        assert "member_sessions.deleted_at is null" in sql

    async def test_filters_soft_deleted_members(self) -> None:
        # Pin: a session whose owning Member is soft-deleted
        # MUST NOT authenticate (entitlement leak after member
        # deletion).
        sql = await self._captured()
        assert "members.deleted_at is null" in sql

    async def test_default_excludes_expired(self) -> None:
        # Pin: ``expires_at > now()`` is the lifetime gate.
        # Drift would let expired sessions still authenticate.
        sql = await self._captured()
        assert "member_sessions.expires_at >" in sql
        assert "2026-04-25" in sql

    async def test_expired_flag_drops_lifetime_filter(self) -> None:
        # Pin: admin-audit override path. Drift to always-filter
        # would 404 admin session-detail pages on expired rows.
        sql = await self._captured(expired=True)
        assert "member_sessions.expires_at >" not in sql

    async def test_uses_exact_equality_on_hash(self) -> None:
        # Pin: equality, no LIKE/ILIKE. Drift would let an
        # attacker brute-force one character at a time.
        sql = await self._captured()
        assert "member_sessions.token = 'hash_abc'" in sql
        assert " like " not in sql


@pytest.mark.asyncio
class TestDeleteExpired:
    async def test_uses_hard_delete(self) -> None:
        # Pin: HARD delete (no soft delete on the cleanup cron).
        # Drift to soft-delete would bloat the table forever.
        repo = MemberSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.delete_expired()

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("delete from member_sessions")

    async def test_filters_to_expired_rows_only(self) -> None:
        # Pin: ``expires_at < now()``. Drift to ``>`` would
        # catastrophically delete every ACTIVE session on every
        # cron tick (mass-logout footgun).
        repo = MemberSessionRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.delete_expired()

        sql = _compile(captured["stmt"]).lower()
        assert "expires_at <" in sql
        assert "2026-04-25" in sql
