"""Work-item attachment lifecycle: list, get, create, delete.

Attachments are immutable join rows: the file's content is owned by
the catalog/file infrastructure, so editing an attachment makes no
sense — to swap a file, delete the attachment and create a new one
that points at the replacement file.

The create path checks two things:
1. The caller can read the work item (auth + workspace boundary).
2. The file referenced is in the same workspace as the project.

The second check is what stops a malicious request from attaching a
private file from a foreign workspace to a work item in your own.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import BadRequest, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    File,
    Project,
    ProjectMemberRole,
    WorkItem,
    WorkItemAttachment,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.attachment.ordering import WorkItemAttachmentSortProperty
from rapidly.projects.attachment.queries import WorkItemAttachmentRepository
from rapidly.projects.attachment.types import WorkItemAttachmentCreate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item.queries import WorkItemRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemAttachment | None:
    repo = WorkItemAttachmentRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemAttachment.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_work_item(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemAttachmentSortProperty]],
) -> tuple[Sequence[WorkItemAttachment], int]:
    await _readable_work_item(session, auth_subject, work_item_id)

    repo = WorkItemAttachmentRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemAttachment.work_item_id == work_item_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: WorkItemAttachmentCreate,
) -> WorkItemAttachment:
    work_item = await _readable_work_item(session, auth_subject, data.work_item_id)
    project = await _ensure_member(session, auth_subject, work_item)

    # File must live in the same workspace as the work item's project
    # — without this check, any workspace member could attach a file
    # they uploaded in a different workspace they happen to belong to.
    await _ensure_file_in_workspace(session, data.file_id, project.workspace_id)

    repo = WorkItemAttachmentRepository.from_session(session)
    existing = await repo.get_one_or_none(
        repo.get_base_statement().where(
            WorkItemAttachment.work_item_id == data.work_item_id,
            WorkItemAttachment.file_id == data.file_id,
            WorkItemAttachment.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise ResourceAlreadyExists("This file is already attached to the work item.")

    uploader_id = (
        auth_subject.subject.id if isinstance(auth_subject.subject, User) else None
    )
    attachment = WorkItemAttachment(
        work_item_id=data.work_item_id,
        file_id=data.file_id,
        uploaded_by_id=uploader_id,
    )
    return await repo.create(attachment, flush=True)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    attachment: WorkItemAttachment,
) -> None:
    work_item = await _readable_work_item(
        session, auth_subject, attachment.work_item_id
    )
    await _ensure_member(session, auth_subject, work_item)
    repo = WorkItemAttachmentRepository.from_session(session)
    await repo.soft_delete(attachment)


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


async def _ensure_member(
    session: AsyncSession,
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
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
    return project


async def _ensure_file_in_workspace(
    session: AsyncSession, file_id: UUID, workspace_id: UUID
) -> None:
    stmt = select(File.id).where(
        File.id == file_id,
        File.workspace_id == workspace_id,
        File.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise BadRequest("File does not belong to this workspace.")
