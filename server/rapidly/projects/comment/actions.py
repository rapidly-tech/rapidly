"""Comment lifecycle: list, get, create, update, delete.

Editing and deleting a comment is **author-only** for user principals.
Project admins (and workspace-scoped tokens) may moderate by overriding
the author check.  Workspace members who are merely project guests
cannot post or mutate comments.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    Project,
    ProjectMemberRole,
    WorkItem,
    WorkItemActivityVerb,
    WorkItemComment,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.activity.actions import emit as emit_activity
from rapidly.projects.comment.ordering import WorkItemCommentSortProperty
from rapidly.projects.comment.queries import WorkItemCommentRepository
from rapidly.projects.comment.types import WorkItemCommentCreate, WorkItemCommentUpdate
from rapidly.projects.project.access import get_member_role, require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item.queries import WorkItemRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemComment | None:
    repo = WorkItemCommentRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemComment.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_work_item(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemCommentSortProperty]],
) -> tuple[Sequence[WorkItemComment], int]:
    repo = WorkItemCommentRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemComment.work_item_id == work_item_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: WorkItemCommentCreate,
) -> WorkItemComment:
    work_item = await _readable_work_item(session, auth_subject, data.work_item_id)
    project = await _project_for_work_item(session, auth_subject, work_item)
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)

    actor_id = _resolve_actor_id(auth_subject, project_owner_id=project.owner_id)

    repo = WorkItemCommentRepository.from_session(session)
    comment = WorkItemComment(
        work_item_id=work_item.id,
        actor_id=actor_id,
        body_html=data.body_html,
        body_json=data.body_json,
    )
    comment = await repo.create(comment, flush=True)
    await emit_activity(
        session,
        work_item=work_item,
        actor=auth_subject,
        verb=WorkItemActivityVerb.comment_added,
        comment_id=comment.id,
    )
    return comment


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    comment: WorkItemComment,
    data: WorkItemCommentUpdate,
) -> WorkItemComment:
    await _require_author_or_admin(session, auth_subject, comment)
    repo = WorkItemCommentRepository.from_session(session)
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return comment
    return await repo.update(comment, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    comment: WorkItemComment,
) -> None:
    await _require_author_or_admin(session, auth_subject, comment)
    repo = WorkItemCommentRepository.from_session(session)
    await repo.soft_delete(comment)


# ── Helpers ──


async def _readable_work_item(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item_id: UUID,
) -> WorkItem:
    repo = WorkItemRepository.from_session(session)
    work_item = await repo.get_one_or_none(
        repo.get_readable_statement(auth_subject).where(WorkItem.id == work_item_id)
    )
    if work_item is None:
        raise ResourceNotFound("Work item not found.")
    return work_item


async def _project_for_work_item(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item: WorkItem,
) -> Project:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == work_item.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    return project


def _resolve_actor_id(
    auth_subject: AuthPrincipal[User | Workspace], *, project_owner_id: UUID
) -> UUID:
    if is_user_principal(auth_subject):
        return auth_subject.subject.id
    # Workspace tokens post on behalf of the project's owner.
    return project_owner_id


async def _require_author_or_admin(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    comment: WorkItemComment,
) -> None:
    """Author can always edit/delete.  Otherwise, require project admin."""
    if is_workspace_principal(auth_subject):
        # Workspace tokens already pass the project-admin floor via
        # ``require_role`` semantics when scoped to the same workspace.
        await _ensure_admin_for_comment(session, auth_subject, comment)
        return

    if not is_user_principal(auth_subject):
        raise NotPermitted("Unsupported auth subject.")

    if auth_subject.subject.id == comment.actor_id:
        return

    await _ensure_admin_for_comment(session, auth_subject, comment)


async def _ensure_admin_for_comment(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    comment: WorkItemComment,
) -> None:
    work_item = await _readable_work_item(session, auth_subject, comment.work_item_id)
    project = await _project_for_work_item(session, auth_subject, work_item)
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)


__all__ = [
    "create",
    "delete",
    "get",
    "get_member_role",  # re-exported for tests that monkey-patch the gate.
    "list_for_work_item",
    "update",
]
