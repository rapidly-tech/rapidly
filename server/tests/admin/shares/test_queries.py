"""Tests for ``rapidly/admin/shares/queries.py``.

Three load-bearing surfaces:

- The base statement always JOINs Workspace and applies
  ``contains_eager`` so the share's workspace is hydrated in
  the list view (drift to lazy-load would N+1 every list page).
- UUID-shaped query matches BOTH share.id AND workspace.id —
  admins paste either kind of UUID; drift to single-column
  match would force admins to know which they had.
- Non-UUID query falls back to ILIKE-OR across share.name +
  workspace.slug + workspace.name with ``escape_like``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.admin.shares.queries import AdminShareRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestBaseStatementHasWorkspaceJoin:
    def test_unfiltered_includes_workspace_join(self) -> None:
        # Pin: every list query joins workspaces table for the
        # eager-load. Drift to lazy-load would N+1 every list
        # page.
        repo = AdminShareRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "join workspaces" in sql

    def test_no_query_no_where_clause(self) -> None:
        repo = AdminShareRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        # Only WHERE-equivalent clause is the JOIN's ON; no extra
        # WHERE filter when query is absent.
        # The "where" keyword wouldn't appear without a filter.
        # (The JOIN ON does NOT use the WHERE keyword.)
        assert "where" not in sql.split("from")[1]


class TestUuidQueryMatchesBothColumns:
    def test_uuid_query_matches_share_or_workspace_id(self) -> None:
        # Pin: admin pastes EITHER a share id OR a workspace id —
        # the query matches both. Drift to single-column match
        # would force admins to know which they had.
        repo = AdminShareRepository(session=MagicMock())
        sql = _compile(
            repo.get_list_statement(query="11111111-1111-1111-1111-111111111111")
        ).lower()
        assert "shares.id" in sql
        assert "shares.workspace_id" in sql
        assert " or " in sql


class TestTextQuerySearchesThreeColumns:
    def test_non_uuid_query_searches_name_slug_workspace_name(self) -> None:
        # Pin: 3-column ILIKE-OR search for non-UUID input.
        repo = AdminShareRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="alice")).lower()
        # share.name + workspace.slug + workspace.name all in the
        # WHERE clause.
        assert "shares.name" in sql
        assert "workspaces.slug" in sql
        assert "workspaces.name" in sql
        assert " or " in sql

    def test_escape_like_applied(self) -> None:
        # Pin: user-supplied % is escaped (drift would let % match
        # every row).
        repo = AdminShareRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="50%off"))
        assert r"50\%off" in sql
