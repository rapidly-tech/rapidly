"""Tests for ``FileShareSessionSortProperty`` — the sort-column enum
declared in ``pg_repository.py`` and re-exported through
``ordering.py``. This is the only ordering enum in the codebase that
lives in a non-standard location (next to the SQLAlchemy repository
that consumes it).
"""

from __future__ import annotations

from rapidly.sharing.file_sharing.pg_repository import (
    FileShareSessionSortProperty,
)


class TestFileShareSessionSortProperty:
    def test_exposes_documented_columns(self) -> None:
        # created_at / status / download_count — the three columns
        # the dashboard + API paginated list surfaces allow sorting
        # by. Silent additions would need matching match-case
        # coverage in the repository's ``_sort_column`` handler.
        assert {e.value for e in FileShareSessionSortProperty} == {
            "created_at",
            "status",
            "download_count",
        }

    def test_is_str_enum(self) -> None:
        assert str(FileShareSessionSortProperty.created_at) == "created_at"
        assert str(FileShareSessionSortProperty.download_count) == "download_count"

    def test_values_are_snake_case_matching_db_columns(self) -> None:
        # DB columns are snake_case; StrEnum values must match for
        # raw ORDER BY clauses.
        for e in FileShareSessionSortProperty:
            assert e.value == e.value.lower()
            assert " " not in e.value
