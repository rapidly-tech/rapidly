"""Tests for ``rapidly/identity/login_code/queries.py``.

One-time login-code lookup. Four load-bearing surfaces:

- The lookup matches on ALL THREE fields: ``code_hash`` (hash
  equality), ``email`` (the address the code was sent to), AND
  ``expires_at > now()``. Drift to drop the email check would
  let an attacker who intercepted ANYONE'S code redeem it
  against THEIR account; drift to drop the expiry would let
  stale codes log a user in forever.
- Hash + email use EXACT equality (no LIKE / case-folding) —
  drift to LIKE would let an attacker brute-force one
  character at a time.
- ``user`` is eager-loaded via ``joinedload`` so the post-
  redemption flow can issue a session without a follow-up
  fetch (drift to lazy-load would N+1 every login).
- ``get_one_or_none`` returns None for misses (no raise) so
  wrong-code attempts return a clean 401 instead of 500.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from rapidly.identity.login_code.queries import LoginCodeRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetValidByHashAndEmail:
    async def test_filters_on_hash_email_and_expiry(self) -> None:
        # Pin: ALL three predicates required. Drift to drop email
        # would let a code intercepted from one user be redeemed
        # against an attacker's account.
        repo = LoginCodeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.get_valid_by_hash_and_email("hash_abc", "alice@example.com")

        sql = _compile(captured["stmt"]).lower()
        assert "login_codes.code_hash = 'hash_abc'" in sql
        assert "login_codes.email = 'alice@example.com'" in sql
        assert "login_codes.expires_at >" in sql
        # The frozen now() literal appears in the expiry comparison.
        assert "2026-04-25" in sql

    async def test_uses_exact_equality_no_like(self) -> None:
        # Pin: equality, not LIKE. Drift to LIKE would let an
        # attacker brute-force one character at a time.
        repo = LoginCodeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_valid_by_hash_and_email("hash_abc", "alice@example.com")

        sql = _compile(captured["stmt"]).lower()
        assert " like " not in sql
        assert " ilike " not in sql

    async def test_eager_loads_user(self) -> None:
        # Pin: ``joinedload(LoginCode.user)`` so the post-
        # redemption session-creation path doesn't N+1 fetch
        # the user. Drift to lazy-load would extra-query every
        # login.
        repo = LoginCodeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_valid_by_hash_and_email("hash_abc", "alice@example.com")

        sql = _compile(captured["stmt"]).lower()
        # joinedload emits a LEFT OUTER JOIN to the users table.
        assert "left outer join users" in sql

    async def test_returns_none_for_misses(self) -> None:
        # Pin: misses return None (caller maps to 401), NOT
        # raise (which would 500 wrong-code attempts).
        repo = LoginCodeRepository(session=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)  # type: ignore[method-assign]
        out = await repo.get_valid_by_hash_and_email("ghost", "alice@example.com")
        assert out is None

    async def test_returns_row_when_match(self) -> None:
        # Pin: clean path returns the row.
        repo = LoginCodeRepository(session=MagicMock())
        target = MagicMock()
        repo.get_one_or_none = AsyncMock(return_value=target)  # type: ignore[method-assign]
        out = await repo.get_valid_by_hash_and_email("hash_abc", "alice@example.com")
        assert out is target
