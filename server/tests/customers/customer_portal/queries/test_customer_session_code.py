"""Tests for ``rapidly/customers/customer_portal/queries/customer_session_code.py``.

Customer-portal session-code lookup. Three load-bearing surfaces:

- The base query filters to ``expires_at > now()`` — a session
  code that has expired MUST NOT authenticate. Drift would let
  expired bearer tokens grant portal access (catastrophic
  trust escalation if any code was ever leaked).
- The lookup matches the SUPPLIED ``code_hash`` literally — drift
  to LIKE / substring would let an attacker brute-force one
  character at a time.
- The query eager-loads ``customer.workspace`` (drift to lazy
  load would N+1 every single portal request — the customer
  AND the workspace are read on every single hit).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from rapidly.customers.customer_portal.queries.customer_session_code import (
    CustomerSessionCodeRepository,
)


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestValidByCodeHashStatement:
    def test_filters_expired_codes(self) -> None:
        # Pin: expired codes do NOT authenticate. Drift would let
        # leaked / stale codes grant portal access forever.
        from datetime import UTC, datetime

        repo = CustomerSessionCodeRepository(session=MagicMock())
        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            stmt = repo.get_valid_by_code_hash_statement("abc")

        sql = _compile(stmt).lower()
        # The expiry comparison appears with a literal-bound now().
        assert "expires_at >" in sql
        assert "2026-04-25" in sql

    def test_matches_code_hash_literally(self) -> None:
        # Pin: the SQL is an exact equality match. Drift to LIKE
        # / substring would let an attacker brute-force one
        # character at a time.
        repo = CustomerSessionCodeRepository(session=MagicMock())
        stmt = repo.get_valid_by_code_hash_statement("abc_hash")
        sql = _compile(stmt).lower()
        assert "customer_session_codes.code = 'abc_hash'" in sql
        # No LIKE.
        assert "like" not in sql

    def test_eager_loads_customer_and_workspace(self) -> None:
        # Pin: ``joinedload(customer).joinedload(workspace)`` —
        # the portal handler reads BOTH on every request. Drift
        # to lazy-load would N+1 every portal page.
        repo = CustomerSessionCodeRepository(session=MagicMock())
        stmt = repo.get_valid_by_code_hash_statement("abc")
        # The joinedload chain emits LEFT OUTER JOINs to both
        # tables in the rendered SQL. We assert on the table
        # names because ``stmt._with_options`` doesn't expose
        # a stable repr of the loader chain.
        sql = _compile(stmt).lower()
        assert "left outer join customers" in sql
        assert "left outer join workspaces" in sql


@pytest.mark.asyncio
class TestGetValidByCodeHash:
    async def test_returns_row_when_match(self) -> None:
        repo = CustomerSessionCodeRepository(session=MagicMock())
        result = MagicMock()
        target = MagicMock()
        result.scalar_one_or_none.return_value = target
        repo.session.execute = AsyncMock(return_value=result)  # type: ignore[method-assign]

        out = await repo.get_valid_by_code_hash("abc")
        assert out is target

    async def test_returns_none_when_no_match(self) -> None:
        # Pin: missing / expired codes return None (NOT raise).
        # Drift to raise would 500 on every wrong-code login
        # attempt.
        repo = CustomerSessionCodeRepository(session=MagicMock())
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        repo.session.execute = AsyncMock(return_value=result)  # type: ignore[method-assign]

        out = await repo.get_valid_by_code_hash("ghost")
        assert out is None

    async def test_passes_supplied_hash_to_statement(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the helper forwards the caller's hash unmodified.
        # Drift to re-hash or normalise would let valid codes
        # mismatch their own DB row.
        repo = CustomerSessionCodeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalar_one_or_none.return_value = None
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        await repo.get_valid_by_code_hash("specific_hash_xyz")

        sql = _compile(captured["stmt"]).lower()
        assert "specific_hash_xyz" in sql
