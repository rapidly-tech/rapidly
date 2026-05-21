"""Project deploy-board lifecycle: list, get, create, update, delete, rotate-token.

This submodule manages the *configuration* of public project boards.
The anonymous-read endpoints (where a visitor with a token actually
fetches the project's work items) live in their own follow-up — that
surface has its own security envelope (rate limits, field filtering)
that deserves separate review.

Admin role required for all mutations.  Why admin (not member): a
public board exposes work items, comments, and votes outside the
workspace boundary.  Letting any member toggle it would let a single
compromised account exfiltrate the entire project's data.
"""

import secrets
from collections.abc import Sequence
from uuid import UUID

from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    Project,
    ProjectDeployBoard,
    ProjectMemberRole,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.deploy_board.queries import ProjectDeployBoardRepository
from rapidly.projects.deploy_board.types import (
    ProjectDeployBoardCreate,
    ProjectDeployBoardUpdate,
)
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectDeployBoard | None:
    repo = ProjectDeployBoardRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectDeployBoard.id == id)
    return await repo.get_one_or_none(stmt)


async def list_boards(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: UUID | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[ProjectDeployBoard], int]:
    repo = ProjectDeployBoardRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectDeployBoard.project_id == project_id)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectDeployBoardCreate,
) -> ProjectDeployBoard:
    """Create a deploy-board config for a project.

    Generates a fresh token server-side.  The unique constraint on
    ``project_id`` enforces one board per project; we surface that
    as a 409 before hitting the DB so the error is friendlier.
    """
    await _ensure_admin(session, auth_subject, data.project_id)

    repo = ProjectDeployBoardRepository.from_session(session)
    if await repo.get_by_project(data.project_id) is not None:
        raise ResourceAlreadyExists("This project already has a deploy board.")

    record = ProjectDeployBoard(
        project_id=data.project_id,
        token=secrets.token_urlsafe(32),
        is_public=data.is_public,
        show_comments=data.show_comments,
        show_reactions=data.show_reactions,
        show_votes=data.show_votes,
        show_intake_form=data.show_intake_form,
        view_props=data.view_props,
    )
    return await repo.create(record, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    board: ProjectDeployBoard,
    data: ProjectDeployBoardUpdate,
) -> ProjectDeployBoard:
    await _ensure_admin(session, auth_subject, board.project_id)

    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return board
    repo = ProjectDeployBoardRepository.from_session(session)
    return await repo.update(board, update_dict=update_dict)


async def rotate_token(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    board: ProjectDeployBoard,
) -> ProjectDeployBoard:
    """Replace the public token. Existing public-URL holders lose access."""
    await _ensure_admin(session, auth_subject, board.project_id)
    repo = ProjectDeployBoardRepository.from_session(session)
    return await repo.update(board, update_dict={"token": secrets.token_urlsafe(32)})


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    board: ProjectDeployBoard,
) -> None:
    await _ensure_admin(session, auth_subject, board.project_id)
    repo = ProjectDeployBoardRepository.from_session(session)
    await repo.soft_delete(board)


# ── Helpers ──


async def _ensure_admin(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project_id: UUID,
) -> Project:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
    return project
