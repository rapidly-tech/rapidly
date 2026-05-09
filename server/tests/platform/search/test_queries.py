"""Tests for ``rapidly/platform/search/queries.py``.

The unified cross-entity search. Six load-bearing surfaces:

- ``search`` returns ``[]`` early when NEITHER scope flag
  (``has_shares_scope`` / ``has_customers_scope``) is set. Drift
  to fall through would emit a ``UNION ALL ()`` SQL that
  Postgres rejects.
- The workspace membership subquery scopes by
  ``workspace_id`` AND ``user_id`` AND ``deleted_at IS NULL``.
  This is the multi-tenant privacy guard — drift to drop the
  user_id check would let any workspace member search any
  other workspace's data.
- Products use the ``"english"`` tsvector config (stemming
  matters for product names); customers use ``"simple"``
  (stemming a customer's name like "Anderson" → "anders" would
  drop legitimate matches).
- UUID-shaped query path matches exactly on ``id`` and SKIPS
  the text-search predicate. Drift to AND-combine would zero-
  result every UUID paste.
- Customer search ALSO ILIKEs against ``email`` (with
  ``escape_like``). Drift to drop the email branch would miss
  email-as-search-key results — a common admin use case.
- Final UNION orders by ``rank DESC`` and applies ``LIMIT``
  caller-supplied (default 20). Drift to ASC would put noise
  at the top; drift to drop LIMIT could OOM the search bar.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.platform.search.queries import SearchRepository


def _compile(stmt: object) -> str:
    """Compile to a Postgres-dialect SQL string. We don't pass
    ``literal_binds=True`` because tsquery's REGCONFIG type
    doesn't have a literal-value renderer; substring assertions
    pick out the columns/operators of interest from the template.
    """
    from sqlalchemy.dialects import postgresql

    compiled = stmt.compile(  # type: ignore[attr-defined]
        dialect=postgresql.dialect(),
    )
    # Inline the Python-side bind params so substring checks pick
    # up UUID hexes etc. The REGCONFIG bind for tsquery is
    # stringified verbatim into the template (``'english'``).
    rendered = str(compiled)
    for key, value in compiled.params.items():
        rendered = rendered.replace(f"%({key})s", repr(value))
    return rendered


@pytest.mark.asyncio
async def _captured_sql(
    *,
    workspace_id: Any = None,
    user_id: Any = None,
    query: str = "alice",
    query_uuid: Any = None,
    has_shares_scope: bool = True,
    has_customers_scope: bool = True,
    limit: int = 20,
) -> str:
    repo = SearchRepository(session=MagicMock())
    captured: dict[str, object] = {}

    async def _exec(stmt: object) -> object:
        captured["stmt"] = stmt
        result = MagicMock()
        result.all.return_value = []
        return result

    repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
    await repo.search(
        workspace_id=workspace_id or uuid4(),
        user_id=user_id or uuid4(),
        query=query,
        query_uuid=query_uuid,
        has_shares_scope=has_shares_scope,
        has_customers_scope=has_customers_scope,
        limit=limit,
    )
    return _compile(captured["stmt"]).lower()


@pytest.mark.asyncio
class TestEarlyReturnNoScopes:
    async def test_no_scope_returns_empty(self) -> None:
        # Pin: short-circuit when caller picks neither scope.
        # Drift to fall through would emit a UNION ALL () SQL
        # that Postgres rejects.
        repo = SearchRepository(session=MagicMock())
        repo.session.execute = AsyncMock()  # type: ignore[method-assign]

        result = await repo.search(
            workspace_id=uuid4(),
            user_id=uuid4(),
            query="x",
            query_uuid=None,
            has_shares_scope=False,
            has_customers_scope=False,
        )

        assert result == []
        # No SQL was executed.
        repo.session.execute.assert_not_called()


@pytest.mark.asyncio
class TestWorkspaceMembershipPrivacyGuard:
    async def test_workspace_id_user_id_and_deleted_at_filters(self) -> None:
        # Pin: the workspace subquery scopes by all three. Drift
        # to drop ``user_id`` would let any user search any
        # workspace's data they could name.
        workspace_id = uuid4()
        user_id = uuid4()
        sql = await _captured_sql(workspace_id=workspace_id, user_id=user_id)

        # The bound UUID literals appear in the rendered SQL.
        assert workspace_id.hex in sql.replace("-", "")
        assert user_id.hex in sql.replace("-", "")
        # Soft-delete filter on the membership row.
        assert "workspace_memberships.deleted_at is null" in sql


@pytest.mark.asyncio
class TestTextSearchConfigSplit:
    async def test_products_use_english_tsvector(self) -> None:
        # Pin: products get English stemming so "running" matches
        # "ran". Drift to "simple" would lose stemming on product
        # names.
        sql = await _captured_sql(has_shares_scope=True, has_customers_scope=False)
        assert "websearch_to_tsquery('english'" in sql

    async def test_customers_use_simple_tsvector(self) -> None:
        # Pin: customers use the simple config — stemming a name
        # like "Anderson" → "anders" would drop legitimate
        # matches.
        sql = await _captured_sql(has_shares_scope=False, has_customers_scope=True)
        assert "websearch_to_tsquery('simple'" in sql


@pytest.mark.asyncio
class TestUuidQueryShortCircuit:
    async def test_uuid_query_uses_exact_id_match(self) -> None:
        # Pin: UUID-shaped query matches on ``id`` and SKIPS
        # the text-search predicate. Drift to AND-combine would
        # zero-result every UUID paste.
        target = uuid4()
        sql = await _captured_sql(query="ignored", query_uuid=target)

        # The UUID literal appears at least once.
        assert target.hex in sql.replace("-", "")
        # The full-text-search ``@@`` operator does NOT appear in
        # the WHERE for UUID queries (text-search is skipped).
        # We assert an UPPER bound — there's no ``@@`` paired with
        # the customer/share search_vector when query_uuid is set.
        # Note: the ``websearch_to_tsquery`` literal still appears
        # as part of the SELECT projection's rank computation,
        # but that's OK; the predicate is the gate we care about.
        assert "@@" not in sql


@pytest.mark.asyncio
class TestCustomerEmailSearch:
    async def test_email_ilike_predicate_for_text_query(self) -> None:
        # Pin: customer search ILIKEs against ``email`` for
        # email-as-search-key admin use cases. Drift to drop the
        # email branch would miss every admin who pastes an
        # email into the search bar.
        sql = await _captured_sql(
            query="alice@example.com",
            has_shares_scope=False,
            has_customers_scope=True,
        )
        assert "customers.email" in sql
        assert "ilike" in sql or "like" in sql

    async def test_escape_like_applied_to_ilike_term(self) -> None:
        # Pin: user-supplied ``%`` is escaped (drift would let an
        # admin's typo'd ``%`` match every customer).
        sql = await _captured_sql(
            query="50%off",
            has_shares_scope=False,
            has_customers_scope=True,
        )
        # Backslash-escape on the percent sign before the bound
        # literal.
        assert r"50\%off" in sql or r"50\\%off" in sql


@pytest.mark.asyncio
class TestRankOrderingAndLimit:
    async def test_orders_by_rank_desc(self) -> None:
        # Pin: most-relevant-first ordering on the UNION result.
        # Drift to ASC would put noise at the top of the search
        # bar.
        sql = await _captured_sql()
        assert "order by" in sql
        assert "rank desc" in sql

    async def test_limit_propagated_from_caller(self) -> None:
        # Pin: caller-supplied LIMIT applies to the final UNION
        # query (drift to drop would let a global "search" OOM
        # the search bar; drift to hardcode would ignore caller
        # tuning).
        sql = await _captured_sql(limit=5)
        assert "limit 5" in sql


@pytest.mark.asyncio
class TestSoftDeleteFilters:
    async def test_share_subquery_excludes_deleted_shares(self) -> None:
        # Pin: deleted shares don't surface in search.
        sql = await _captured_sql(has_shares_scope=True, has_customers_scope=False)
        assert "shares.deleted_at is null" in sql

    async def test_customer_subquery_excludes_deleted_customers(self) -> None:
        sql = await _captured_sql(has_shares_scope=False, has_customers_scope=True)
        assert "customers.deleted_at is null" in sql
