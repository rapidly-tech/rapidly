"""Tests for ``rapidly.projects.link.actions``.

Invariants pinned:

- ``create`` rejects self-link (``work_item_id == related_id``).
- ``create`` rejects cross-project relations (both sides must share
  the same parent project).
- ``create`` rejects duplicate edges of the same ``relation_type``.
- ``create`` requires ``member`` role on the parent project.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import (
    BadRequest,
    NotPermitted,
    ResourceAlreadyExists,
    ResourceNotFound,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    ProjectMemberRole,
    User,
    WorkItem,
    WorkItemPriority,
    WorkItemRelation,
    WorkItemRelationType,
)
from rapidly.projects.link import actions as link_actions
from rapidly.projects.link.types import WorkItemRelationCreate


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
        name="x",
        state_id=uuid4(),
        priority=WorkItemPriority.none,
        sort_order=65535.0,
        is_draft=False,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_self_link_rejected(self) -> None:
        principal = _user_principal()
        same = uuid4()
        session = MagicMock()

        with pytest.raises(BadRequest):
            await link_actions.create(
                session,
                principal,
                WorkItemRelationCreate(
                    work_item_id=same,
                    related_id=same,
                    relation_type=WorkItemRelationType.blocks,
                ),
            )

    async def test_cross_project_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        source = _work_item(project_id=uuid4())
        target = _work_item(project_id=uuid4())  # different project

        async def _readable(session: Any, auth: Any, work_item_id: UUID) -> WorkItem:
            return source if work_item_id == source.id else target

        monkeypatch.setattr(
            "rapidly.projects.link.actions._readable_work_item", _readable
        )

        session = MagicMock()
        with pytest.raises(BadRequest):
            await link_actions.create(
                session,
                principal,
                WorkItemRelationCreate(
                    work_item_id=source.id,
                    related_id=target.id,
                    relation_type=WorkItemRelationType.blocks,
                ),
            )

    async def test_duplicate_relation_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        project_id = uuid4()
        source = _work_item(project_id=project_id)
        target = _work_item(project_id=project_id)

        async def _readable(session: Any, auth: Any, work_item_id: UUID) -> WorkItem:
            return source if work_item_id == source.id else target

        monkeypatch.setattr(
            "rapidly.projects.link.actions._readable_work_item", _readable
        )

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(
            return_value=MagicMock(id=project_id, workspace_id=uuid4())
        )
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        repo = MagicMock()
        repo.get_base_statement = MagicMock(return_value=MagicMock())
        repo.get_one_or_none = AsyncMock(
            return_value=WorkItemRelation(
                id=uuid4(),
                work_item_id=source.id,
                related_id=target.id,
                relation_type=WorkItemRelationType.blocks,
            )
        )

        session = MagicMock()
        with (
            patch(
                "rapidly.projects.link.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.link.actions.WorkItemRelationRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.link.actions.require_role",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ResourceAlreadyExists):
                await link_actions.create(
                    session,
                    principal,
                    WorkItemRelationCreate(
                        work_item_id=source.id,
                        related_id=target.id,
                        relation_type=WorkItemRelationType.blocks,
                    ),
                )

    async def test_role_gate_member_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        project_id = uuid4()
        source = _work_item(project_id=project_id)
        target = _work_item(project_id=project_id)

        async def _readable(session: Any, auth: Any, work_item_id: UUID) -> WorkItem:
            return source if work_item_id == source.id else target

        monkeypatch.setattr(
            "rapidly.projects.link.actions._readable_work_item", _readable
        )

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(
            return_value=MagicMock(id=project_id, workspace_id=uuid4())
        )
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        session = MagicMock()
        with (
            patch(
                "rapidly.projects.link.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.link.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await link_actions.create(
                    session,
                    principal,
                    WorkItemRelationCreate(
                        work_item_id=source.id,
                        related_id=target.id,
                        relation_type=WorkItemRelationType.blocks,
                    ),
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member

    async def test_unknown_source_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()

        async def _readable(*_a: Any, **_k: Any) -> WorkItem:
            raise ResourceNotFound("Work item not found.")

        monkeypatch.setattr(
            "rapidly.projects.link.actions._readable_work_item", _readable
        )

        session = MagicMock()
        with pytest.raises(ResourceNotFound):
            await link_actions.create(
                session,
                principal,
                WorkItemRelationCreate(
                    work_item_id=uuid4(),
                    related_id=uuid4(),
                    relation_type=WorkItemRelationType.relates_to,
                ),
            )
