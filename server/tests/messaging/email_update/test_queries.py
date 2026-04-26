"""Tests for ``rapidly/messaging/email_update/queries.py``.

Email-change verification token repository. Four load-bearing
surfaces:

- ``get_by_token_hash`` matches on BOTH ``token_hash`` (exact
  equality, no LIKE) AND ``expires_at > now()``. Drift to drop
  the expiry check would let a stale verification token still
  change the user's email forever; drift to LIKE would let an
  attacker brute-force one character at a time.
- ``get_by_token_hash`` eager-loads ``user`` via ``joinedload``
  so the post-redemption email-change handler doesn't N+1 fetch
  the user row.
- ``get_by_token_hash`` returns None for misses so wrong-token
  attempts return a clean 401 instead of 500.
- ``delete_expired`` HARD-deletes via ``expires_at < now()``.
  Drift to ``>`` would catastrophically delete every active
  pending verification on every cron tick (mass email-change
  abort).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from rapidly.messaging.email_update.queries import EmailVerificationRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByTokenHash:
    async def test_filters_on_hash_AND_expiry(self) -> None:
        # Pin: BOTH predicates required. Drift to drop expiry
        # would let stale tokens change the user's email forever.
        repo = EmailVerificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "email_verification.token_hash = 'hash_abc'" in sql
        assert "email_verification.expires_at >" in sql
        assert "2026-04-25" in sql

    async def test_uses_exact_equality_no_like(self) -> None:
        # Pin: no LIKE/ILIKE. Drift would let an attacker brute-
        # force one character at a time.
        repo = EmailVerificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert " like " not in sql
        assert " ilike " not in sql

    async def test_eager_loads_user(self) -> None:
        # Pin: drift to lazy-load would extra-query the user on
        # every email-change redemption.
        repo = EmailVerificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "left outer join users" in sql

    async def test_returns_none_for_misses(self) -> None:
        # Pin: misses return None so wrong-token attempts get a
        # clean 401, not a 500.
        repo = EmailVerificationRepository(session=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)  # type: ignore[method-assign]
        out = await repo.get_by_token_hash("ghost")
        assert out is None


@pytest.mark.asyncio
class TestDeleteExpired:
    async def test_hard_delete_correct_direction(self) -> None:
        # Pin: ``expires_at < now()``. Drift to ``>`` would
        # delete every ACTIVE pending verification on every
        # cron tick (mass email-change abort).
        repo = EmailVerificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        repo.session.flush = AsyncMock()  # type: ignore[method-assign]

        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.delete_expired()

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("delete from email_verification")
        assert "expires_at <" in sql
        assert "2026-04-25" in sql

    async def test_flushes_after_delete(self) -> None:
        # Pin: explicit flush after the bulk DELETE so the cron
        # commits the cleanup before returning. Drift would let
        # the next worker invocation see the same expired rows.
        repo = EmailVerificationRepository(session=MagicMock())
        repo.session.execute = AsyncMock()  # type: ignore[method-assign]
        repo.session.flush = AsyncMock()  # type: ignore[method-assign]

        await repo.delete_expired()

        repo.session.flush.assert_called_once()
