"""Tests for ``rapidly.projects.page.actions``.

Invariants pinned:
- ``create`` requires ``member`` role on the parent project.
- ``create`` rejects a parent page that belongs to a different project.
- ``create`` rejects a duplicate slug within the same project.
- ``update`` of a locked page requires ``admin`` role.
- ``update`` rejects self-parenting.
- A page's owner can update / delete it; a non-owner / non-admin cannot.
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
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    ProjectMemberRole,
    ProjectPage,
    ProjectPageAccess,
    User,
)
from rapidly.projects.page import actions as page_actions
from rapidly.projects.page.types import ProjectPageCreate, ProjectPageUpdate


def _user_principal(user_id: UUID | None = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=user_id or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _page(
    project_id: UUID | None = None,
    owner_id: UUID | None = None,
    is_locked: bool = False,
) -> ProjectPage:
    return ProjectPage(
        id=uuid4(),
        project_id=project_id or uuid4(),
        owner_id=owner_id,
        name="Home",
        slug="home",
        access=ProjectPageAccess.public,
        is_locked=is_locked,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_duplicate_slug_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()
        project = MagicMock(id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.page.actions._ensure_member", _ensure)

        repo = MagicMock()
        repo.get_by_slug = AsyncMock(return_value=_page(project_id=project.id))

        with patch(
            "rapidly.projects.page.actions.ProjectPageRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await page_actions.create(
                    session,
                    principal,
                    ProjectPageCreate(project_id=project.id, name="Home", slug="home"),
                )

    async def test_role_gate_member_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.page.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await page_actions.create(
                session,
                principal,
                ProjectPageCreate(project_id=uuid4(), name="Home", slug="home"),
            )

    async def test_parent_in_other_project_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()
        # ``_verify_parent`` runs a select; return no rows so it raises.
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        project = MagicMock(id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.page.actions._ensure_member", _ensure)

        with pytest.raises(BadRequest):
            await page_actions.create(
                session,
                principal,
                ProjectPageCreate(
                    project_id=project.id,
                    name="Sub",
                    slug="sub",
                    parent_id=uuid4(),
                ),
            )


@pytest.mark.asyncio
class TestUpdate:
    async def test_locked_page_requires_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a locked page can only be edited by an admin.  Drift
        # would let any project member bypass the lock.
        principal = _user_principal()
        page = _page(is_locked=True, owner_id=principal.subject.id)
        session = MagicMock()
        project = MagicMock(id=page.project_id)

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.page.actions._ensure_member", _ensure)

        with patch(
            "rapidly.projects.page.actions.require_role",
            side_effect=NotPermitted(),
        ) as gate:
            with pytest.raises(NotPermitted):
                await page_actions.update(
                    session,
                    principal,
                    page,
                    ProjectPageUpdate(name="Renamed"),
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.admin

    async def test_self_parent_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        page = _page(owner_id=principal.subject.id)
        session = MagicMock()
        project = MagicMock(id=page.project_id)

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        async def _admin_or_author(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr("rapidly.projects.page.actions._ensure_member", _ensure)
        monkeypatch.setattr(
            "rapidly.projects.page.actions._require_author_or_admin",
            _admin_or_author,
        )

        with pytest.raises(BadRequest):
            await page_actions.update(
                session,
                principal,
                page,
                ProjectPageUpdate(parent_id=page.id),
            )

    async def test_non_owner_non_admin_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: editing someone else's page without admin role is denied.
        principal = _user_principal()
        page = _page(owner_id=uuid4())  # different owner
        session = MagicMock()
        project = MagicMock(id=page.project_id)

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.page.actions._ensure_member", _ensure)

        with patch(
            "rapidly.projects.page.actions.require_role",
            side_effect=NotPermitted(),
        ):
            with pytest.raises(NotPermitted):
                await page_actions.update(
                    session,
                    principal,
                    page,
                    ProjectPageUpdate(name="Renamed"),
                )

    async def test_owner_can_update(self, monkeypatch: pytest.MonkeyPatch) -> None:
        owner_id = uuid4()
        principal = _user_principal(owner_id)
        page = _page(owner_id=owner_id)
        session = MagicMock()
        project = MagicMock(id=page.project_id)

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        async def _snapshot(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr("rapidly.projects.page.actions._ensure_member", _ensure)
        # Versioning hook writes a snapshot row when content changes — stub
        # it so this test stays focused on the update path itself.
        monkeypatch.setattr(
            "rapidly.projects.page.actions._snapshot_page", _snapshot
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=page)
        repo.get_by_slug = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.page.actions.ProjectPageRepository.from_session",
            return_value=repo,
        ):
            updated = await page_actions.update(
                session,
                principal,
                page,
                ProjectPageUpdate(name="Renamed"),
            )
        assert updated is page
        repo.update.assert_awaited_once()
