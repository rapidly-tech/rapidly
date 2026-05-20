"""Work-item-mention lifecycle.

Create / delete are gated by:
- Caller must be able to read the comment (workspace boundary).
- Caller must be the comment's author OR a project admin. Why: a
  random project member shouldn't be able to retroactively tag a
  teammate into a conversation they didn't start. Letting only the
  author (or an admin) write mentions matches who'd legitimately
  edit the comment body itself.
- Mentioned user must be a workspace member — keeps cross-workspace
  pings out of the system.

Notification fan-out is intentionally not wired here; the next PR
in the stack adds a NotificationType.work_item_mentioned event +
React Email template, then calls notifications.send_to_user from
the create path.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import (
    BadRequest,
    NotPermitted,
    ResourceAlreadyExists,
    ResourceNotFound,
)
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    Project,
    ProjectMemberRole,
    WorkItem,
    WorkItemComment,
    WorkItemMention,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.mention.ordering import WorkItemMentionSortProperty
from rapidly.projects.mention.queries import WorkItemMentionRepository
from rapidly.projects.mention.types import WorkItemMentionCreate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemMention | None:
    repo = WorkItemMentionRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemMention.id == id)
    return await repo.get_one_or_none(stmt)


async def list_mentions(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID | None = None,
    comment_id: UUID | None = None,
    mentioned_user_id: UUID | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemMentionSortProperty]],
) -> tuple[Sequence[WorkItemMention], int]:
    repo = WorkItemMentionRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if work_item_id is not None:
        statement = statement.where(WorkItemComment.work_item_id == work_item_id)
    if comment_id is not None:
        statement = statement.where(WorkItemMention.comment_id == comment_id)
    if mentioned_user_id is not None:
        statement = statement.where(
            WorkItemMention.mentioned_user_id == mentioned_user_id
        )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: WorkItemMentionCreate,
) -> WorkItemMention:
    comment, work_item, project = await _resolve_comment(
        session, auth_subject, data.comment_id
    )
    await _ensure_author_or_admin(session, auth_subject, comment, project)
    await _ensure_user_in_workspace(
        session, project.workspace_id, data.mentioned_user_id
    )

    repo = WorkItemMentionRepository.from_session(session)
    existing = await repo.get_for_comment_and_user(
        data.comment_id, data.mentioned_user_id
    )
    if existing is not None:
        raise ResourceAlreadyExists("This user is already mentioned in the comment.")

    mention = WorkItemMention(
        comment_id=data.comment_id,
        mentioned_user_id=data.mentioned_user_id,
        mentioned_by_id=auth_subject.subject.id,
    )
    return await repo.create(mention, flush=True)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    mention: WorkItemMention,
) -> None:
    comment, _, project = await _resolve_comment(
        session, auth_subject, mention.comment_id
    )
    await _ensure_author_or_admin(session, auth_subject, comment, project)
    repo = WorkItemMentionRepository.from_session(session)
    await repo.soft_delete(mention)


# ── Helpers ──


async def _resolve_comment(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    comment_id: UUID,
) -> tuple[WorkItemComment, WorkItem, Project]:
    """Pull the comment + its work item + its project through the
    workspace boundary in a single round-trip."""
    user_id = auth_subject.subject.id
    stmt = (
        select(WorkItemComment, WorkItem, Project)
        .join(WorkItem, WorkItem.id == WorkItemComment.work_item_id)
        .join(Project, Project.id == WorkItem.project_id)
        .where(
            WorkItemComment.id == comment_id,
            WorkItemComment.deleted_at.is_(None),
            Project.workspace_id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            ),
        )
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise ResourceNotFound("Comment not found.")
    return row[0], row[1], row[2]


async def _ensure_author_or_admin(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    comment: WorkItemComment,
    project: Project,
) -> None:
    # WorkItemComment names its author column ``actor_id``.
    if comment.actor_id == auth_subject.subject.id:
        return

    # Refetch the project through the project-repo readable filter so
    # ``require_role`` has the right scope, then enforce admin.
    project_repo = ProjectRepository.from_session(session)
    readable_project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project.id
        )
    )
    if readable_project is None:
        # Lost workspace access between the comment resolve and now —
        # rare but treat as not-found to avoid an oracle.
        raise NotPermitted()
    await require_role(
        session, auth_subject, readable_project, minimum=ProjectMemberRole.admin
    )


async def _ensure_user_in_workspace(
    session: AsyncSession, workspace_id: UUID, user_id: UUID
) -> None:
    stmt = select(WorkspaceMembership.user_id).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).first() is None:
        raise BadRequest("Mentioned user is not in this workspace.")
