"""Tests for ``rapidly/admin/customers/queries.py``.

Four load-bearing surfaces:

- The base statement always JOINs Workspace and applies
  ``contains_eager`` so the customer's workspace is hydrated in
  the list view (drift to lazy-load would N+1 every list page).
- A UUID-shaped query matches BOTH ``customer.id`` AND
  ``workspace.id``. Admins paste either kind of UUID; drift to
  single-column match would force them to know which they had.
- A non-UUID query falls back to ILIKE-OR across FIVE columns
  (``customer.email`` / ``customer.name`` / ``customer.external_id``
  / ``workspace.slug`` / ``workspace.name``) with ``escape_like``
  applied. Drift to AND would zero-result every search; drift to
  drop ``escape_like`` would let user-supplied ``%`` match every
  row.
- Results are ordered by ``created_at DESC`` so the most-recent
  customer is at the top of the list. Drift to ASC would bury
  fresh signups.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.admin.customers.queries import AdminCustomerRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestBaseStatementHasWorkspaceJoin:
    def test_unfiltered_includes_workspace_join(self) -> None:
        # Pin: every list query joins workspaces table for the
        # eager-load. Drift to lazy-load would N+1 every list
        # page render.
        repo = AdminCustomerRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "join workspaces" in sql

    def test_no_query_no_where_clause(self) -> None:
        # Pin: only filter active when ``query`` is set. The
        # only WHERE-equivalent clause is the JOIN's ON.
        repo = AdminCustomerRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        # The WHERE keyword should not appear after FROM.
        assert "where" not in sql.split("from")[1]


class TestUuidQueryMatchesBothColumns:
    def test_uuid_query_matches_customer_or_workspace_id(self) -> None:
        # Pin: admin pastes EITHER a customer id OR a workspace
        # id — the query matches both. Drift to single-column
        # match would force admins to know which they had.
        repo = AdminCustomerRepository(session=MagicMock())
        sql = _compile(
            repo.get_list_statement(query="11111111-1111-1111-1111-111111111111")
        ).lower()
        assert "customers.id" in sql
        assert "customers.workspace_id" in sql or "workspaces.id" in sql
        assert " or " in sql


class TestTextQuerySearchesFiveColumns:
    def test_non_uuid_query_searches_documented_five_columns(self) -> None:
        # Pin: 5-column ILIKE-OR search.
        repo = AdminCustomerRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="alice")).lower()
        assert "customers.email" in sql
        assert "customers.name" in sql
        assert "customers.external_id" in sql
        assert "workspaces.slug" in sql
        assert "workspaces.name" in sql
        assert " or " in sql

    def test_text_query_is_lowercased(self) -> None:
        # Pin: ``escape_like(query.lower())`` — the search is
        # case-insensitive via ``func.lower()`` on both sides.
        # Drift to compare raw cases would miss results that
        # differ only in case.
        repo = AdminCustomerRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="Alice"))
        # The bound pattern is the lowercased form.
        assert "alice" in sql
        # ``func.lower(...)`` appears on the column side.
        assert "lower(" in sql.lower()

    def test_escape_like_applied(self) -> None:
        # Pin: user-supplied ``%`` is escaped (drift would let
        # ``%`` match every row).
        repo = AdminCustomerRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="50%off"))
        assert r"50\%off" in sql


class TestOrdering:
    def test_default_orders_by_created_at_desc(self) -> None:
        # Pin: most-recent-first list. Drift to ASC would bury
        # fresh signups at the bottom of the admin list.
        repo = AdminCustomerRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "order by customers.created_at desc" in sql
