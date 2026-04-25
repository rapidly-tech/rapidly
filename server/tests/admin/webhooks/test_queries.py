"""Tests for ``rapidly/admin/webhooks/queries.py``.

Four load-bearing surfaces:

- The base statement always JOINs Workspace and applies
  ``contains_eager`` so the endpoint's workspace is hydrated in
  the list view (drift to lazy-load would N+1 every list page).
- A UUID-shaped query matches BOTH ``endpoint.id`` AND
  ``endpoint.workspace_id``. Admins paste either a webhook id or
  a workspace id; drift to single-column match would force them
  to know which.
- A non-UUID query falls back to ILIKE-OR across THREE columns
  (``endpoint.url`` / ``workspace.slug`` / ``workspace.name``)
  with ``escape_like`` applied. Drift to AND zero-results every
  search; drift to drop ``escape_like`` lets ``%`` match every
  row.
- Default ordering is ``created_at DESC`` — the newest endpoint
  is at the top. Drift to ASC would bury fresh signups.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.admin.webhooks.queries import AdminWebhookRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestBaseStatementHasWorkspaceJoin:
    def test_unfiltered_includes_workspace_join(self) -> None:
        # Pin: every list query joins workspaces table for the
        # eager-load. Drift to lazy-load would N+1 every list
        # page render.
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "join workspaces" in sql

    def test_no_query_no_where_clause(self) -> None:
        # Pin: only filter active when ``query`` is set. The only
        # WHERE-equivalent clause is the JOIN's ON.
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "where" not in sql.split("from")[1]

    def test_empty_string_query_treated_as_falsy(self) -> None:
        # Pin: ``if query:`` (truthy check) — an empty string
        # MUST NOT add a filter. Drift to ``if query is not
        # None`` would let `?q=` empty searches narrow to UUID-
        # parse-failure-then-ILIKE-of-empty (matching everything
        # with redundant work).
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="")).lower()
        assert "where" not in sql.split("from")[1]


class TestUuidQueryMatchesBothColumns:
    def test_uuid_query_matches_endpoint_or_workspace_id(self) -> None:
        # Pin: admin pastes EITHER an endpoint id OR a workspace
        # id — the query matches both. Drift to single-column
        # match would force admins to know which they had.
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(
            repo.get_list_statement(query="11111111-1111-1111-1111-111111111111")
        ).lower()
        assert "webhook_endpoints.id" in sql
        assert "webhook_endpoints.workspace_id" in sql
        assert " or " in sql


class TestTextQuerySearchesThreeColumns:
    def test_non_uuid_query_searches_documented_three_columns(self) -> None:
        # Pin: 3-column ILIKE-OR search.
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="example.com")).lower()
        assert "webhook_endpoints.url" in sql
        assert "workspaces.slug" in sql
        assert "workspaces.name" in sql
        assert " or " in sql

    def test_escape_like_applied(self) -> None:
        # Pin: user-supplied ``%`` is escaped (drift would let
        # ``%`` match every row).
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="50%off"))
        assert r"50\%off" in sql


class TestOrdering:
    def test_default_orders_by_created_at_desc(self) -> None:
        # Pin: most-recent-first list. Drift to ASC would bury
        # fresh endpoints at the bottom of the admin list.
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "order by webhook_endpoints.created_at desc" in sql

    def test_ordering_preserved_when_query_filters_applied(self) -> None:
        # Pin: filtering does NOT drop the ORDER BY — it's applied
        # to the base statement before the WHERE is layered on.
        repo = AdminWebhookRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="alice")).lower()
        assert "order by webhook_endpoints.created_at desc" in sql
