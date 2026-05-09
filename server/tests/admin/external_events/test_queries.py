"""Tests for ``rapidly/admin/external_events/queries.py``.

Three load-bearing surfaces:

- UUID-shaped query goes to exact-id match; non-UUID query
  triggers the partial-text fallback. Drift would either reject
  legitimate text searches or fail to match by id.
- Partial-text search uses ``escape_like`` BEFORE ILIKE — so
  user-supplied ``%`` and ``_`` aren't interpreted as wildcards.
  Drift would let an attacker (or a user with a literal ``%``
  in their search) accidentally match every row.
- ``is_handled=None`` skips the filter; ``True``/``False`` add
  a ``WHERE is_handled = ...`` clause. Drift would either always
  filter (silent zero results) or never filter (broken UI).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.admin.external_events.queries import (
    AdminExternalEventRepository,
)


def _compile(stmt: object) -> str:
    """Compile a SQLAlchemy statement to its parameter-bound SQL string."""
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestUuidExactMatch:
    def test_uuid_query_uses_id_filter(self) -> None:
        # Pin: when the query parses as UUID, we filter by exact id.
        repo = AdminExternalEventRepository(session=MagicMock())
        stmt = repo.get_list_statement(query="11111111-1111-1111-1111-111111111111")
        sql = _compile(stmt).lower()
        # Expect ``id = '...'`` clause. Postgres literal-bind
        # strips dashes from UUID rendering — match the dashless
        # form.
        assert "external_events.id" in sql
        assert "11111111111111111111111111111111" in sql

    def test_non_uuid_query_uses_text_search(self) -> None:
        # Pin: non-UUID query falls back to case-insensitive
        # match on external_id / task_name (SQLAlchemy compiles
        # ``ilike()`` to ``LOWER(...) LIKE LOWER(...)`` for
        # cross-dialect compatibility).
        repo = AdminExternalEventRepository(session=MagicMock())
        stmt = repo.get_list_statement(query="alice")
        sql = _compile(stmt).lower()
        # ``ilike`` or ``lower(...) like`` indicates case-insensitive.
        assert "lower(" in sql or "ilike" in sql
        assert "external_id" in sql
        assert "task_name" in sql

    def test_text_search_uses_or(self) -> None:
        # Pin: external_id OR task_name (NOT AND — drift to AND
        # would silently zero-result every search since most
        # events match only one column).
        repo = AdminExternalEventRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="x")).lower()
        assert " or " in sql


class TestEscapeLikeApplied:
    def test_percent_in_query_does_not_become_wildcard(self) -> None:
        # Pin: user-supplied ``%`` is escaped via escape_like
        # BEFORE the ILIKE pattern is built. Drift would let
        # ``%`` match every row.
        repo = AdminExternalEventRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="50%off"))
        # The escaped form has the % preceded by a backslash;
        # the literal-bind form will show ``50\%off`` somewhere.
        assert r"50\%off" in sql


class TestHandledFilter:
    def test_none_omits_filter(self) -> None:
        # Pin: handled=None → no handled_at clause in WHERE.
        repo = AdminExternalEventRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(handled=None)).lower()
        # No WHERE clause at all when both filters are None.
        assert "where" not in sql

    def test_true_adds_filter(self) -> None:
        # Pin: ``is_handled`` is a hybrid property backed by
        # ``handled_at IS NOT NULL`` — at SQL level it's a
        # column expression on handled_at.
        repo = AdminExternalEventRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(handled=True)).lower()
        # The WHERE clause references handled_at (the underlying
        # column) AND a true literal.
        assert "handled_at" in sql
        assert "where" in sql

    def test_false_adds_filter(self) -> None:
        # Pin: explicit False is honoured (NOT conflated with
        # None). Used by the "show only unhandled" filter.
        repo = AdminExternalEventRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(handled=False)).lower()
        assert "handled_at" in sql
        assert "where" in sql

    def test_handled_none_vs_handled_set_differ(self) -> None:
        # Pin: True and False produce DIFFERENT SQL (drift to a
        # collapsed condition would silently make True === False).
        repo = AdminExternalEventRepository(session=MagicMock())
        sql_true = _compile(repo.get_list_statement(handled=True))
        sql_false = _compile(repo.get_list_statement(handled=False))
        assert sql_true != sql_false


class TestNoFiltersBaseStatement:
    def test_empty_args_returns_base_statement(self) -> None:
        # Pin: with no query and no handled filter, the
        # statement is the unfiltered base SELECT.
        repo = AdminExternalEventRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "external_events" in sql
        # No WHERE clause.
        assert "where" not in sql
