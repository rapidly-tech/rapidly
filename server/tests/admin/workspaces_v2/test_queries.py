"""Tests for ``rapidly/admin/workspaces_v2/queries.py``.

The admin moderation list-statement builder. Five load-bearing
surfaces:

- **Default status filter EXCLUDES ``DENIED``.** Drift to include
  it would dump rejected workspaces back into the moderator's
  queue every time they open the list.
- **Risk-level thresholds**: ``high`` is ``risk_score >= 75``,
  ``medium`` is ``50 <= risk_score < 75``, ``low`` is ``< 50``,
  ``unscored`` matches rows with NO review row (LEFT JOIN +
  ``WorkspaceReview.id IS NULL``). Drift to wrong boundaries
  would mis-bucket workspaces in the moderation queue.
- **``days_in_status`` filter** combines
  ``status_updated_at <= threshold`` OR ``(status_updated_at IS
  NULL AND created_at <= threshold)``. Drift to drop the NULL
  fallback would NEVER surface workspaces that have not had a
  status update yet (e.g. CREATED rows).
- **Pagination fetches ``limit + 1``** so the caller can detect
  ``has_more`` without an extra COUNT query. Drift to fetch
  exactly ``limit`` would always render ``has_more = False``.
- **Default sort ``priority``** is
  ``(status DESC, status_updated_at ASC NULLSFIRST)`` — moderators
  see the oldest pending-status workspaces first. Drift would
  bury aging cases at the bottom of the queue.

Plus the ``append_internal_note`` UTC-timestamp prefix (drift to
local time would be timezone-dependent and hard to reason about
across moderators in different regions).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from rapidly.admin.workspaces_v2.queries import AdminWorkspaceRepository
from rapidly.models.workspace import WorkspaceStatus


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestDefaultStatusFilter:
    def test_default_excludes_denied(self) -> None:
        # Pin: an unfiltered list MUST exclude DENIED. Drift
        # would dump rejected workspaces back into the
        # moderator's queue on every refresh.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement()).lower()
        assert "denied" in sql
        assert "!=" in sql or "<>" in sql

    def test_explicit_status_filter_uses_equality(self) -> None:
        # Pin: when the moderator picks a specific status
        # (e.g., INITIAL_REVIEW), the SQL is an equality match.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(
            repo.build_list_statement(status_filter=WorkspaceStatus.INITIAL_REVIEW)
        ).lower()
        # An equality clause to ``initial_review`` appears.
        assert "= 'initial_review'" in sql
        # The default-DENIED-exclusion is REPLACED, not added.
        # ``denied`` must not appear in the WHERE.
        assert " 'denied'" not in sql


class TestRiskLevelThresholds:
    def test_high_threshold_is_75(self) -> None:
        # Pin: ``risk_score >= 75`` is "high". Drift to a
        # different cutoff would mis-bucket cases.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(risk_level="high")).lower()
        assert "risk_score" in sql
        assert ">= 75" in sql

    def test_medium_threshold_is_50_to_74(self) -> None:
        # Pin: ``50 <= risk_score < 75`` is "medium". Both
        # bounds appear in the rendered SQL.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(risk_level="medium")).lower()
        assert ">= 50" in sql
        assert "< 75" in sql

    def test_low_threshold_is_below_50(self) -> None:
        # Pin: ``risk_score < 50`` is "low".
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(risk_level="low")).lower()
        assert "< 50" in sql

    def test_unscored_uses_left_outer_join_with_null_review(self) -> None:
        # Pin: ``unscored`` returns rows with NO review row.
        # Drift would either skip workspaces that need scoring
        # (inner join) or surface the wrong rows.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(risk_level="unscored")).lower()
        assert "left outer join" in sql or "outerjoin" in sql or "left join" in sql
        # The ``WorkspaceReview.id IS NULL`` predicate.
        assert "is null" in sql


class TestDaysInStatusFilter:
    def test_includes_status_updated_at_or_created_at_fallback(self) -> None:
        # Pin: rows where ``status_updated_at`` is NULL fall back
        # to ``created_at`` against the same threshold. Drift to
        # drop the OR branch would never surface freshly-CREATED
        # workspaces in the moderation queue.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(days_in_status_int=7)).lower()
        assert "status_updated_at" in sql
        assert "created_at" in sql
        assert " or " in sql
        # The NULL fallback path uses IS NULL on status_updated_at.
        assert "is null" in sql


class TestPaginationFetchesLimitPlusOne:
    def test_limit_one_extra_for_has_more_detection(self) -> None:
        # Pin: ``LIMIT N+1`` to detect a next page without an
        # extra COUNT query. Drift to fetch exactly ``limit``
        # would always render the "next" button as disabled.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(limit=50)).lower()
        # Effective LIMIT is 51 (50 + 1).
        assert "limit 51" in sql

    def test_offset_uses_zero_indexed_page_math(self) -> None:
        # Pin: page 1 → offset 0; page 2 → offset = limit. Drift
        # to ``page * limit`` would skip the first page entirely.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(page=2, limit=10)).lower()
        assert "offset 10" in sql


class TestPrioritySortDefault:
    def test_priority_orders_by_status_desc_then_status_updated_asc(self) -> None:
        # Pin: default sort surfaces aging cases first.
        # ``status DESC`` then ``status_updated_at ASC NULLSFIRST``.
        # Drift would bury old cases at the bottom of the queue.
        repo = AdminWorkspaceRepository(session=MagicMock())
        sql = _compile(repo.build_list_statement(sort="priority")).lower()
        # Both ordering keys appear in order.
        idx_status = sql.find("workspaces.status desc")
        idx_updated = sql.find("workspaces.status_updated_at asc")
        assert idx_status != -1
        assert idx_updated != -1
        assert idx_status < idx_updated


class TestAppendInternalNote:
    @pytest.mark.asyncio
    async def test_prepends_utc_timestamp(self) -> None:
        # Pin: the timestamp prefix uses UTC and the documented
        # ``%Y-%m-%d %H:%M UTC`` format. Drift to local time
        # would be timezone-dependent across moderators in
        # different regions.
        repo = AdminWorkspaceRepository(session=MagicMock())

        async def _fake_update(obj: object, update_dict: dict[str, object]) -> object:
            return obj

        repo.update = _fake_update  # type: ignore[method-assign,assignment]

        workspace = MagicMock()
        workspace.internal_notes = None

        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.append_internal_note(workspace, "Reviewed by alice")

        assert workspace.internal_notes == "[2026-04-25 14:30 UTC] Reviewed by alice"

    @pytest.mark.asyncio
    async def test_appends_with_blank_line_when_existing_notes_present(self) -> None:
        # Pin: existing notes preserved + separated by a blank
        # line. Drift to overwrite would lose moderation history;
        # drift to no separator would jam notes together.
        repo = AdminWorkspaceRepository(session=MagicMock())

        async def _fake_update(obj: object, update_dict: dict[str, object]) -> object:
            return obj

        repo.update = _fake_update  # type: ignore[method-assign,assignment]

        workspace = MagicMock()
        workspace.internal_notes = "[2026-04-24 10:00 UTC] First review"

        with freeze_time(datetime(2026, 4, 25, 14, 30, tzinfo=UTC)):
            await repo.append_internal_note(workspace, "Second review")

        assert workspace.internal_notes == (
            "[2026-04-24 10:00 UTC] First review\n\n"
            "[2026-04-25 14:30 UTC] Second review"
        )
