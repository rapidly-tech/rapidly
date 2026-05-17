"""Tests for ``rapidly.projects.work_item.actions``.

Surfaces that would break the security or invariant contract if
they drifted:

- ``create`` requires the parent project to be readable (404 if not).
- ``create`` then requires the caller's project role to be at least
  ``member`` before touching uniqueness / state lookups.
- ``state_id`` MUST belong to the same project — a workspace member
  could otherwise assign a work item to a state from a different
  project they read.
- ``parent_id`` MUST belong to the same project.
- ``label_ids`` MUST all belong to the same project.
- ``assignee_ids`` MUST all be members of the project's workspace.
- ``update`` rejects ``parent_id == work_item.id`` (no self-parent).
- ``next_sequence_number`` always returns ``max + 1`` (1 on empty).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import BadRequest, NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectMemberRole, User, WorkItem, WorkItemPriority
from rapidly.projects.work_item import actions as work_item_actions
from rapidly.projects.work_item.types import WorkItemCreate, WorkItemUpdate


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _work_item(project_id: UUID | None = None, id: UUID | None = None) -> WorkItem:
    return WorkItem(
        id=id or uuid4(),
        project_id=project_id or uuid4(),
        sequence_number=1,
        name="thing",
        state_id=uuid4(),
        priority=WorkItemPriority.none,
        sort_order=65535.0,
        is_draft=False,
    )


def _create_payload(**overrides: Any) -> WorkItemCreate:
    base: dict[str, Any] = {
        "project_id": uuid4(),
        "name": "Build the thing",
        "state_id": uuid4(),
    }
    base.update(overrides)
    return WorkItemCreate(**base)


def _project_repo_returning(project: Any) -> MagicMock:
    project_repo = MagicMock()
    project_repo.get_one_or_none = AsyncMock(return_value=project)
    project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
    project_repo.model = MagicMock()
    return project_repo


@pytest.mark.asyncio
class TestCreate:
    async def test_unknown_project_404(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        project_repo = _project_repo_returning(None)

        with patch(
            "rapidly.projects.work_item.actions.ProjectRepository.from_session",
            return_value=project_repo,
        ):
            with pytest.raises(ResourceNotFound):
                await work_item_actions.create(session, principal, _create_payload())

    async def test_role_gate_invoked_before_state_check(self) -> None:
        # Pin: role enforcement runs BEFORE state / label / assignee
        # validation so a non-member never gets to probe other-project
        # state IDs via 4xx-vs-200 oracles.
        principal = _user_principal()
        session = MagicMock()
        project_repo = _project_repo_returning(MagicMock(id=uuid4()))

        with (
            patch(
                "rapidly.projects.work_item.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
            patch(
                "rapidly.projects.work_item.actions._verify_state",
                new_callable=AsyncMock,
            ) as verify_state,
        ):
            with pytest.raises(NotPermitted):
                await work_item_actions.create(session, principal, _create_payload())
            gate.assert_awaited_once()
            verify_state.assert_not_called()
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member

    async def test_state_in_other_project_rejected(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        project_repo = _project_repo_returning(
            MagicMock(id=uuid4(), workspace_id=uuid4())
        )

        with (
            patch(
                "rapidly.projects.work_item.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.require_role",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(BadRequest):
                await work_item_actions.create(session, principal, _create_payload())


@pytest.mark.asyncio
class TestUpdate:
    async def test_self_parent_rejected(self) -> None:
        # Pin: a work item cannot be its own parent — would create an
        # infinite cycle in the sub-item tree.
        principal = _user_principal()
        work_item = _work_item()
        session = MagicMock()

        with (
            patch(
                "rapidly.projects.work_item.actions._ensure_member",
                new_callable=AsyncMock,
                return_value=MagicMock(id=work_item.project_id, workspace_id=uuid4()),
            ),
        ):
            with pytest.raises(BadRequest):
                await work_item_actions.update(
                    session,
                    principal,
                    work_item,
                    WorkItemUpdate(parent_id=work_item.id),
                )

    async def test_update_requires_member(self) -> None:
        principal = _user_principal()
        work_item = _work_item()
        session = MagicMock()
        project_repo = _project_repo_returning(MagicMock(id=work_item.project_id))

        with (
            patch(
                "rapidly.projects.work_item.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await work_item_actions.update(
                    session, principal, work_item, WorkItemUpdate(name="x")
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member


@pytest.mark.asyncio
class TestNextSequenceNumber:
    async def test_returns_one_on_empty_project(self) -> None:
        from rapidly.projects.work_item.queries import WorkItemRepository

        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        repo = WorkItemRepository(session)
        assert await repo.next_sequence_number(uuid4()) == 1

    async def test_increments_from_max(self) -> None:
        # Pin: sequence numbering is monotonic per project.  Reset to
        # 1 after deletion would create duplicate human-readable IDs.
        from rapidly.projects.work_item.queries import WorkItemRepository

        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=42))
        )

        repo = WorkItemRepository(session)
        assert await repo.next_sequence_number(uuid4()) == 43


@pytest.mark.asyncio
class TestDelete:
    async def test_delete_requires_member(self) -> None:
        principal = _user_principal()
        work_item = _work_item()
        session = MagicMock()
        project_repo = _project_repo_returning(MagicMock(id=work_item.project_id))

        with (
            patch(
                "rapidly.projects.work_item.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await work_item_actions.delete(session, principal, work_item)
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member


# ── List filter tests ──────────────────────────────────────────────────
#
# These pin the *count* of ``.where`` calls added by each filter — we
# can't compare the ``ilike`` / EXISTS expressions by value through a
# MagicMock chain, so per server/CLAUDE.md "Substring search filter"
# we assert structure instead of SQL text.


def _list_repo_returning_empty() -> tuple[MagicMock, MagicMock]:
    """Mocked WorkItemRepository + the inner Select-like statement."""
    statement = MagicMock(name="initial_statement")
    statement.where = MagicMock(return_value=statement)
    repo = MagicMock()
    repo.get_readable_statement = MagicMock(return_value=statement)
    repo.apply_sorting = MagicMock(return_value=statement)
    return repo, statement


@pytest.mark.asyncio
class TestListItems:
    async def test_no_filters_no_extra_wheres(self) -> None:
        # Baseline: only the two implicit filters (archived, drafts) run.
        principal = _user_principal()
        session = MagicMock()
        repo, statement = _list_repo_returning_empty()
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.work_item.actions.WorkItemRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await work_item_actions.list_items(
                session, principal, pagination=pagination, sorting=()
            )
        # archived + drafts → 2 .where calls.
        assert statement.where.call_count == 2

    async def test_priority_filter_adds_where(self) -> None:
        from rapidly.models import WorkItemPriority

        principal = _user_principal()
        session = MagicMock()
        repo, statement = _list_repo_returning_empty()
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.work_item.actions.WorkItemRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await work_item_actions.list_items(
                session,
                principal,
                priority=[WorkItemPriority.high, WorkItemPriority.urgent],
                pagination=pagination,
                sorting=(),
            )
        # 1 (priority) + 2 (implicit) = 3.
        assert statement.where.call_count == 3

    async def test_label_filter_adds_where(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        repo, statement = _list_repo_returning_empty()
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.work_item.actions.WorkItemRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await work_item_actions.list_items(
                session,
                principal,
                label_id=[uuid4()],
                pagination=pagination,
                sorting=(),
            )
        assert statement.where.call_count == 3

    async def test_name_filter_adds_where(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        repo, statement = _list_repo_returning_empty()
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.work_item.actions.WorkItemRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await work_item_actions.list_items(
                session,
                principal,
                name="login bug",
                pagination=pagination,
                sorting=(),
            )
        assert statement.where.call_count == 3

    async def test_blank_name_skipped(self) -> None:
        # ``"   "`` must not bypass into a "match everything" ilike.
        principal = _user_principal()
        session = MagicMock()
        repo, statement = _list_repo_returning_empty()
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.work_item.actions.WorkItemRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await work_item_actions.list_items(
                session,
                principal,
                name="   ",
                pagination=pagination,
                sorting=(),
            )
        # Only the two implicit filters.
        assert statement.where.call_count == 2

    async def test_combined_filters_compose(self) -> None:
        from rapidly.models import WorkItemPriority

        principal = _user_principal()
        session = MagicMock()
        repo, statement = _list_repo_returning_empty()
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.work_item.actions.WorkItemRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.work_item.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await work_item_actions.list_items(
                session,
                principal,
                priority=[WorkItemPriority.high],
                label_id=[uuid4()],
                name="checkout",
                pagination=pagination,
                sorting=(),
            )
        # 3 explicit + 2 implicit.
        assert statement.where.call_count == 5
