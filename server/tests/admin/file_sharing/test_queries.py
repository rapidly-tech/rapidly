"""Tests for ``rapidly/admin/file_sharing/queries.py``.

Three load-bearing surfaces:

- ``query`` triggers ILIKE on three columns
  (``short_slug`` / ``long_slug`` / ``file_name``) joined by OR.
  Drift to AND would zero-result every search (each row only
  matches one column).
- ``escape_like`` is applied BEFORE ILIKE so user-supplied
  ``%`` / ``_`` don't act as wildcards.
- Invalid status string is SILENTLY ignored (no WHERE clause).
  Drift to raise would crash the admin page on a typo'd URL
  parameter; drift to keep the bad string in the WHERE would
  return zero rows for any existing status.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.admin.file_sharing.queries import (
    AdminFileShareSessionRepository,
)


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestQueryFilter:
    def test_no_query_no_where(self) -> None:
        repo = AdminFileShareSessionRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement()).lower()
        assert "where" not in sql

    def test_query_searches_three_columns(self) -> None:
        # Pin: the documented 3-column search set
        # (short_slug / long_slug / file_name) joined by OR.
        repo = AdminFileShareSessionRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="abc")).lower()
        assert "short_slug" in sql
        assert "long_slug" in sql
        assert "file_name" in sql
        assert " or " in sql

    def test_query_uses_ilike_with_percent_wrapping(self) -> None:
        # Pin: ILIKE pattern is ``%<query>%`` (substring match).
        repo = AdminFileShareSessionRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="abc"))
        # Pattern is bound as ``%abc%``.
        assert "%abc%" in sql

    def test_escape_like_applied(self) -> None:
        # Pin: user-supplied ``%`` is escaped (via escape_like).
        # Drift would let an attacker / user matchanything.
        repo = AdminFileShareSessionRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(query="50%off"))
        assert r"50\%off" in sql


class TestStatusFilter:
    def test_valid_status_adds_filter(self) -> None:
        # Pin: a recognised FileShareSessionStatus value adds a
        # WHERE clause.
        from rapidly.models.file_share_session import (
            FileShareSessionStatus,
        )

        repo = AdminFileShareSessionRepository(session=MagicMock())
        valid_status = next(iter(FileShareSessionStatus)).value
        sql = _compile(repo.get_list_statement(status=valid_status)).lower()
        assert "status" in sql

    def test_invalid_status_silently_ignored(self) -> None:
        # Pin (load-bearing UX): a typo'd status URL parameter
        # does NOT crash the page (no raise) and does NOT add a
        # garbage WHERE clause. Drift to raise would 500 on any
        # bookmarked admin URL with a stale status; drift to
        # include the bad string would return zero rows.
        repo = AdminFileShareSessionRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(status="not-a-real-status"))
        # No status WHERE clause appears.
        assert "not-a-real-status" not in sql

    def test_none_status_no_filter(self) -> None:
        repo = AdminFileShareSessionRepository(session=MagicMock())
        sql = _compile(repo.get_list_statement(status=None)).lower()
        # Filter only applied when query/status is set; no other
        # filter active here.
        assert "where" not in sql
