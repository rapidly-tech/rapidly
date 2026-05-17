"""Tests for ``rapidly.projects.project.actions``.

Focus on the surfaces that would break the security or invariant
contract if they drifted:

- Slug and identifier are unique per workspace (case-sensitive for
  identifier, case-sensitive for slug post-validation).  Conflict
  → ``ResourceAlreadyExists`` (HTTP 409).
- ``create`` auto-attaches the creating user as a project admin.
- ``archive``/``unarchive``/``delete`` require ``admin`` role.
- ``update`` requires ``member`` role.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import Project, ProjectMemberRole, User, Workspace
from rapidly.projects.project import actions as project_actions
from rapidly.projects.project.types import (
    ProjectCreate,
    ProjectUpdate,
)


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _workspace_principal(workspace_id: UUID) -> AuthPrincipal[Workspace]:
    workspace = Workspace(id=workspace_id, name="acme", slug="acme")
    return AuthPrincipal(subject=workspace, scopes=set(), session=None)


def _project(workspace_id: UUID | None = None) -> Project:
    return Project(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),
        owner_id=uuid4(),
        name="P",
        identifier="P",
        slug="p",
    )


def _create_payload(**overrides: Any) -> ProjectCreate:
    base: dict[str, Any] = {
        "workspace_id": uuid4(),
        "name": "Atlas",
        "identifier": "ATL",
        "slug": "atlas",
    }
    base.update(overrides)
    return ProjectCreate(**base)


@pytest.mark.asyncio
class TestCreate:
    async def test_rejects_duplicate_identifier(self) -> None:
        # Pin: ``(workspace_id, identifier)`` uniqueness is enforced
        # *before* the DB so we return 409 instead of letting the
        # constraint violation bubble up as 500.
        principal = _user_principal()
        payload = _create_payload()
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        existing = _project(payload.workspace_id)
        repo = MagicMock()
        repo.get_by_identifier = AsyncMock(return_value=existing)
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock()

        workspace_repo = MagicMock()
        workspace_repo.get_accessible_by_id = AsyncMock(
            return_value=Workspace(id=payload.workspace_id, name="w", slug="w")
        )

        with (
            patch(
                "rapidly.projects.project.actions.ProjectRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.project.actions.WorkspaceRepository.from_session",
                return_value=workspace_repo,
            ),
        ):
            with pytest.raises(ResourceAlreadyExists):
                await project_actions.create(
                    session, principal, payload.workspace_id, payload
                )

    async def test_rejects_duplicate_slug(self) -> None:
        principal = _user_principal()
        payload = _create_payload()
        session = MagicMock()

        existing = _project(payload.workspace_id)
        repo = MagicMock()
        repo.get_by_identifier = AsyncMock(return_value=None)
        repo.get_by_slug = AsyncMock(return_value=existing)

        workspace_repo = MagicMock()
        workspace_repo.get_accessible_by_id = AsyncMock(
            return_value=Workspace(id=payload.workspace_id, name="w", slug="w")
        )

        with (
            patch(
                "rapidly.projects.project.actions.ProjectRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.project.actions.WorkspaceRepository.from_session",
                return_value=workspace_repo,
            ),
        ):
            with pytest.raises(ResourceAlreadyExists):
                await project_actions.create(
                    session, principal, payload.workspace_id, payload
                )

    async def test_user_principal_without_workspace_access_rejected(self) -> None:
        # Pin: a user creating a project must be a member of the
        # target workspace.  Drift = cross-workspace project
        # creation via API.
        principal = _user_principal()
        payload = _create_payload()
        session = MagicMock()

        workspace_repo = MagicMock()
        workspace_repo.get_accessible_by_id = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.project.actions.WorkspaceRepository.from_session",
            return_value=workspace_repo,
        ):
            with pytest.raises(ResourceNotFound):
                await project_actions.create(
                    session, principal, payload.workspace_id, payload
                )

    async def test_workspace_token_mismatch_rejected(self) -> None:
        # Pin: a workspace token can ONLY create projects in its own
        # workspace.  Drift = tenant-isolation break.
        token_workspace_id = uuid4()
        other_workspace_id = uuid4()
        principal = _workspace_principal(token_workspace_id)
        payload = _create_payload(workspace_id=other_workspace_id)
        session = MagicMock()

        workspace_repo = MagicMock()

        with patch(
            "rapidly.projects.project.actions.WorkspaceRepository.from_session",
            return_value=workspace_repo,
        ):
            with pytest.raises(NotPermitted):
                await project_actions.create(
                    session, principal, other_workspace_id, payload
                )


class TestProjectCreateValidator:
    """Pin slug/identifier validation rules — they show up in URLs."""

    def test_identifier_uppercased(self) -> None:
        payload = ProjectCreate(
            workspace_id=uuid4(), name="A", identifier="abc12", slug="atlas"
        )
        assert payload.identifier == "ABC12"

    def test_identifier_rejects_non_alnum(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProjectCreate(
                workspace_id=uuid4(), name="A", identifier="A-B", slug="atlas"
            )

    def test_slug_rejects_uppercase_after_lower(self) -> None:
        # Pin: slug is lower-cased and only `a-z0-9-` allowed.
        # ``"My Slug"`` becomes ``"my slug"`` then fails space check.
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProjectCreate(
                workspace_id=uuid4(), name="A", identifier="ABC", slug="bad slug"
            )

    def test_slug_accepts_hyphens(self) -> None:
        payload = ProjectCreate(
            workspace_id=uuid4(), name="A", identifier="ABC", slug="my-project"
        )
        assert payload.slug == "my-project"


@pytest.mark.asyncio
class TestUpdateRoleGate:
    async def test_update_requires_member(self) -> None:
        # Pin: a workspace member without a project membership
        # cannot edit a project they can see.  Drift = privilege
        # escalation through visibility.
        principal = _user_principal()
        project = _project()
        session = MagicMock()

        with patch(
            "rapidly.projects.project.actions.require_role",
            side_effect=NotPermitted(),
        ) as gate:
            with pytest.raises(NotPermitted):
                await project_actions.update(
                    session, principal, project, ProjectUpdate(name="x")
                )
            gate.assert_awaited_once_with(
                session, principal, project, minimum=ProjectMemberRole.member
            )

    async def test_archive_requires_admin(self) -> None:
        # Pin: archive is destructive enough to require admin.
        principal = _user_principal()
        project = _project()
        session = MagicMock()

        with patch(
            "rapidly.projects.project.actions.require_role",
            side_effect=NotPermitted(),
        ) as gate:
            with pytest.raises(NotPermitted):
                await project_actions.archive(session, principal, project)
            gate.assert_awaited_once_with(
                session, principal, project, minimum=ProjectMemberRole.admin
            )

    async def test_delete_requires_admin(self) -> None:
        principal = _user_principal()
        project = _project()
        session = MagicMock()

        with patch(
            "rapidly.projects.project.actions.require_role",
            side_effect=NotPermitted(),
        ) as gate:
            with pytest.raises(NotPermitted):
                await project_actions.delete(session, principal, project)
            gate.assert_awaited_once_with(
                session, principal, project, minimum=ProjectMemberRole.admin
            )


@pytest.mark.asyncio
class TestListNameFilter:
    async def test_no_name_no_extra_where(self) -> None:
        # Baseline: only the implicit archived filter runs when name is
        # absent.  Establishes the .where count for the diffs below.
        principal = _user_principal()
        session = MagicMock()
        statement = MagicMock()
        statement.where = MagicMock(return_value=statement)
        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=statement)
        repo.apply_sorting = MagicMock(return_value=statement)
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.project.actions.ProjectRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.project.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await project_actions.list(
                session, principal, pagination=pagination, sorting=()
            )
        assert statement.where.call_count == 1

    async def test_name_filter_adds_where(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        statement = MagicMock()
        statement.where = MagicMock(return_value=statement)
        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=statement)
        repo.apply_sorting = MagicMock(return_value=statement)
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.project.actions.ProjectRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.project.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await project_actions.list(
                session,
                principal,
                name="rapidly",
                pagination=pagination,
                sorting=(),
            )
        assert statement.where.call_count == 2

    async def test_blank_name_skipped(self) -> None:
        # ``"   "`` must not bypass into a "match everything" ilike.
        principal = _user_principal()
        session = MagicMock()
        statement = MagicMock()
        statement.where = MagicMock(return_value=statement)
        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=statement)
        repo.apply_sorting = MagicMock(return_value=statement)
        pagination = MagicMock()
        with (
            patch(
                "rapidly.projects.project.actions.ProjectRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.project.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await project_actions.list(
                session,
                principal,
                name="   ",
                pagination=pagination,
                sorting=(),
            )
        assert statement.where.call_count == 1
