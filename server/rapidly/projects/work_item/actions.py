"""Work-item lifecycle: list, get, create, update, archive, delete.

Bag-of-relationships writes (assignees + labels) are reconciled
in-place — the action computes the symmetric difference between
the existing rows and the requested set, then inserts the missing
edges and soft-deletes the obsolete ones.
"""

# Required so ``list[UUID]`` annotations on helpers below remain the
# builtin ``list`` even though ``list`` is shadowed by the route-handler
# function defined in this module.
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.config import settings
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import BadRequest, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.messaging.notifications import actions as notification_actions
from rapidly.messaging.notifications.notification import (
    NotificationType,
    WorkItemAssignedNotificationPayload,
)
from rapidly.models import (
    Project,
    ProjectLabel,
    ProjectMemberRole,
    ProjectState,
    WorkItem,
    WorkItemActivityVerb,
    WorkItemAssignee,
    WorkItemLabel,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.activity.actions import emit as emit_activity
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item.ordering import WorkItemSortProperty
from rapidly.projects.work_item.queries import WorkItemRepository
from rapidly.projects.work_item.types import WorkItemCreate, WorkItemUpdate

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItem | None:
    repo = WorkItemRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItem.id == id)
    return await repo.get_one_or_none(stmt)


async def list_items(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    state_id: Sequence[UUID] | None = None,
    parent_id: UUID | None = None,
    include_archived: bool = False,
    include_drafts: bool = False,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemSortProperty]],
) -> tuple[Sequence[WorkItem], int]:
    repo = WorkItemRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)

    if project_id is not None:
        statement = statement.where(WorkItem.project_id.in_(project_id))
    if state_id is not None:
        statement = statement.where(WorkItem.state_id.in_(state_id))
    if parent_id is not None:
        statement = statement.where(WorkItem.parent_id == parent_id)
    if not include_archived:
        statement = statement.where(WorkItem.archived_at.is_(None))
    if not include_drafts:
        statement = statement.where(WorkItem.is_draft.is_(False))

    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def get_assignee_ids(
    session: AsyncSession | AsyncReadSession, work_item_id: UUID
) -> list[UUID]:
    stmt = select(WorkItemAssignee.user_id).where(
        WorkItemAssignee.work_item_id == work_item_id,
        WorkItemAssignee.deleted_at.is_(None),
    )
    return [row[0] for row in (await session.execute(stmt)).all()]


async def get_label_ids(
    session: AsyncSession | AsyncReadSession, work_item_id: UUID
) -> list[UUID]:
    stmt = select(WorkItemLabel.label_id).where(
        WorkItemLabel.work_item_id == work_item_id,
        WorkItemLabel.deleted_at.is_(None),
    )
    return [row[0] for row in (await session.execute(stmt)).all()]


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: WorkItemCreate,
) -> WorkItem:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == data.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")

    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)

    await _verify_state(session, project.id, data.state_id)
    if data.parent_id is not None:
        await _verify_parent(session, project.id, data.parent_id)
    if data.label_ids:
        await _verify_labels(session, project.id, data.label_ids)
    if data.assignee_ids:
        await _verify_assignees(session, project.workspace_id, data.assignee_ids)

    repo = WorkItemRepository.from_session(session)
    sequence_number = await repo.next_sequence_number(project.id)

    work_item = WorkItem(
        project_id=project.id,
        sequence_number=sequence_number,
        name=data.name,
        description_json=data.description_json,
        description_html=data.description_html,
        priority=data.priority,
        state_id=data.state_id,
        estimate_point_id=data.estimate_point_id,
        parent_id=data.parent_id,
        start_date=data.start_date,
        target_date=data.target_date,
        sort_order=data.sort_order if data.sort_order is not None else 65535.0,
        is_draft=data.is_draft,
    )
    work_item = await repo.create(work_item, flush=True)

    initial_assignees: set[UUID] = set(dict.fromkeys(data.assignee_ids))
    for user_id in initial_assignees:
        session.add(WorkItemAssignee(work_item_id=work_item.id, user_id=user_id))
    for label_id in dict.fromkeys(data.label_ids):
        session.add(WorkItemLabel(work_item_id=work_item.id, label_id=label_id))
    if data.assignee_ids or data.label_ids:
        await session.flush()

    await emit_activity(
        session,
        work_item=work_item,
        actor=auth_subject,
        verb=WorkItemActivityVerb.created,
    )

    await _notify_new_assignees(
        session,
        work_item=work_item,
        project=project,
        actor=auth_subject,
        new_assignee_ids=initial_assignees,
    )

    return work_item


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item: WorkItem,
    data: WorkItemUpdate,
) -> WorkItem:
    project = await _ensure_member(session, auth_subject, work_item.project_id)

    if data.state_id is not None:
        await _verify_state(session, project.id, data.state_id)
    if data.parent_id is not None:
        if data.parent_id == work_item.id:
            raise BadRequest("A work item cannot be its own parent.")
        await _verify_parent(session, project.id, data.parent_id)

    # Capture the values we want to diff before they're mutated.
    previous_state_id = work_item.state_id
    previous_priority = work_item.priority

    repo = WorkItemRepository.from_session(session)
    scalar_fields = data.model_dump(
        exclude_unset=True, exclude={"assignee_ids", "label_ids"}
    )
    if scalar_fields:
        work_item = await repo.update(work_item, update_dict=scalar_fields, flush=True)

    newly_added_assignees: set[UUID] = set()
    if data.assignee_ids is not None:
        if data.assignee_ids:
            await _verify_assignees(session, project.workspace_id, data.assignee_ids)
        newly_added_assignees = await _reconcile_assignees(
            session, work_item.id, data.assignee_ids
        )

    if data.label_ids is not None:
        if data.label_ids:
            await _verify_labels(session, project.id, data.label_ids)
        await _reconcile_labels(session, work_item.id, data.label_ids)

    # Activity log — one row per material change.  Field-level emits
    # keep the timeline readable; bulk "updated" events are less useful.
    if data.state_id is not None and data.state_id != previous_state_id:
        await emit_activity(
            session,
            work_item=work_item,
            actor=auth_subject,
            verb=WorkItemActivityVerb.state_changed,
            field="state_id",
            old_value=previous_state_id,
            new_value=data.state_id,
        )
    if data.priority is not None and data.priority != previous_priority:
        await emit_activity(
            session,
            work_item=work_item,
            actor=auth_subject,
            verb=WorkItemActivityVerb.priority_changed,
            field="priority",
            old_value=previous_priority,
            new_value=data.priority,
        )

    await _notify_new_assignees(
        session,
        work_item=work_item,
        project=project,
        actor=auth_subject,
        new_assignee_ids=newly_added_assignees,
    )

    return work_item


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item: WorkItem,
) -> None:
    await _ensure_member(session, auth_subject, work_item.project_id)
    repo = WorkItemRepository.from_session(session)
    await repo.soft_delete(work_item)


# ── Helpers ──


async def _ensure_member(
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
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
    return project


async def _verify_state(
    session: AsyncSession, project_id: UUID, state_id: UUID
) -> None:
    stmt = select(ProjectState.id).where(
        ProjectState.id == state_id,
        ProjectState.project_id == project_id,
        ProjectState.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise BadRequest("State does not belong to this project.")


async def _verify_parent(
    session: AsyncSession, project_id: UUID, parent_id: UUID
) -> None:
    stmt = select(WorkItem.id).where(
        WorkItem.id == parent_id,
        WorkItem.project_id == project_id,
        WorkItem.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise BadRequest("Parent work item does not belong to this project.")


async def _verify_labels(
    session: AsyncSession, project_id: UUID, label_ids: list[UUID]
) -> None:
    stmt = select(ProjectLabel.id).where(
        ProjectLabel.id.in_(label_ids),
        ProjectLabel.project_id == project_id,
        ProjectLabel.deleted_at.is_(None),
    )
    found: set[UUID] = {row[0] for row in (await session.execute(stmt)).all()}
    missing: set[UUID] = set(label_ids) - found
    if missing:
        raise BadRequest("One or more labels do not belong to this project.")


async def _verify_assignees(
    session: AsyncSession, workspace_id: UUID, user_ids: list[UUID]
) -> None:
    """Assignees must be members of the project's workspace."""
    stmt = select(WorkspaceMembership.user_id).where(
        WorkspaceMembership.user_id.in_(user_ids),
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.deleted_at.is_(None),
    )
    found: set[UUID] = {row[0] for row in (await session.execute(stmt)).all()}
    missing: set[UUID] = set(user_ids) - found
    if missing:
        raise BadRequest("One or more assignees are not workspace members.")


async def _reconcile_assignees(
    session: AsyncSession, work_item_id: UUID, target_user_ids: list[UUID]
) -> set[UUID]:
    """Reconcile assignees and return the set of newly-added user IDs.

    Why return new IDs: callers need to fire a notification per *new*
    assignee, not for assignees who were already on the work item.
    Computing the delta here keeps the caller's branching minimal.
    """
    target: set[UUID] = set(target_user_ids)
    existing_stmt = select(WorkItemAssignee).where(
        WorkItemAssignee.work_item_id == work_item_id,
        WorkItemAssignee.deleted_at.is_(None),
    )
    existing = (await session.execute(existing_stmt)).scalars().all()
    existing_by_user = {row.user_id: row for row in existing}

    newly_added = target - set(existing_by_user.keys())
    for user_id in newly_added:
        session.add(WorkItemAssignee(work_item_id=work_item_id, user_id=user_id))

    for user_id in set(existing_by_user.keys()) - target:
        existing_by_user[user_id].set_deleted_at()

    await session.flush()
    return newly_added


async def _reconcile_labels(
    session: AsyncSession, work_item_id: UUID, target_label_ids: list[UUID]
) -> None:
    target: set[UUID] = set(target_label_ids)
    existing_stmt = select(WorkItemLabel).where(
        WorkItemLabel.work_item_id == work_item_id,
        WorkItemLabel.deleted_at.is_(None),
    )
    existing = (await session.execute(existing_stmt)).scalars().all()
    existing_by_label = {row.label_id: row for row in existing}

    for label_id in target - set(existing_by_label.keys()):
        session.add(WorkItemLabel(work_item_id=work_item_id, label_id=label_id))

    for label_id in set(existing_by_label.keys()) - target:
        existing_by_label[label_id].set_deleted_at()

    await session.flush()


async def _notify_new_assignees(
    session: AsyncSession,
    *,
    work_item: WorkItem,
    project: Project,
    actor: AuthPrincipal[User | Workspace],
    new_assignee_ids: set[UUID],
) -> None:
    """Dispatch a "work item assigned" notification for each new assignee.

    Why filter out the actor's own id: assigning yourself to a work
    item shouldn't trigger a notification to yourself.  This mirrors
    Plane's behaviour and prevents noisy self-pings.
    """
    if not new_assignee_ids:
        return

    actor_id: UUID | None = None
    if isinstance(actor.subject, User):
        actor_id = actor.subject.id

    work_item_url = settings.generate_frontend_url(
        f"/preview/projects/{project.id}/work-items/{work_item.id}"
    )
    payload = WorkItemAssignedNotificationPayload(
        project_name=project.name,
        work_item_name=work_item.name,
        work_item_url=work_item_url,
    )

    for user_id in new_assignee_ids:
        if user_id == actor_id:
            continue
        await notification_actions.send_to_user(
            session,
            user_id,
            notification_actions.PartialNotification(
                type=NotificationType.work_item_assigned,
                payload=payload,
            ),
        )
