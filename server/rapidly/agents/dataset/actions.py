"""Dataset + DatasetCase lifecycle actions."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.agents.dataset.queries import (
    DatasetCaseRepository,
    DatasetRepository,
)
from rapidly.agents.dataset.types import (
    DatasetCaseCreate,
    DatasetCaseUpdate,
    DatasetCreate,
    DatasetUpdate,
)
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Dataset, DatasetCase, WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession

# ── Dataset CRUD ────────────────────────────────────────────


async def get_dataset(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Dataset | None:
    repo = DatasetRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(Dataset.id == id)
    return await repo.get_one_or_none(stmt)


async def get_dataset_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Dataset:
    dataset = await get_dataset(session, auth_subject, id)
    if dataset is None:
        raise ResourceNotFound("Dataset not found.")
    return dataset


async def list_datasets(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: UUID | None = None,
    name: str | None = None,
    is_archived: bool | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[Dataset], int]:
    repo = DatasetRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).order_by(
        Dataset.created_at.desc()
    )
    if workspace_id is not None:
        # Mirrors the workflow list contract (M5.41): the readable
        # statement already filters to workspaces the caller can
        # read; this narrows to one of them. Unknown IDs return
        # empty rather than 403.
        statement = statement.where(Dataset.workspace_id == workspace_id)
    if is_archived is True:
        # Tri-state archive filter, same shape as workflows (M5.65).
        statement = statement.where(Dataset.archived_at.is_not(None))
    elif is_archived is False:
        statement = statement.where(Dataset.archived_at.is_(None))
    if name is not None and name.strip():
        # Same escape pattern as the projects/labels list endpoints.
        escaped = (
            name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        statement = statement.where(Dataset.name.ilike(f"%{escaped}%", escape="\\"))
    return await paginate(session, statement, pagination=pagination)


async def create_dataset(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: DatasetCreate,
) -> Dataset:
    await _assert_workspace_writable(session, auth_subject, data.workspace_id)
    repo = DatasetRepository.from_session(session)
    record = Dataset(
        workspace_id=data.workspace_id,
        name=data.name,
        description=data.description,
    )
    return await repo.create(record, flush=True)


async def update_dataset(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    dataset: Dataset,
    data: DatasetUpdate,
) -> Dataset:
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return dataset
    repo = DatasetRepository.from_session(session)
    return await repo.update(dataset, update_dict=update_dict, flush=True)


async def delete_dataset(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    dataset: Dataset,
) -> None:
    repo = DatasetRepository.from_session(session)
    await repo.soft_delete(dataset, flush=True)


async def archive_dataset(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    dataset: Dataset,
) -> Dataset:
    """Stamp ``archived_at = now()`` if not already archived.

    Idempotent — mirrors the workflow archive action shape (M5.65).
    """
    if dataset.archived_at is not None:
        return dataset
    repo = DatasetRepository.from_session(session)
    return await repo.update(
        dataset, update_dict={"archived_at": now_utc()}, flush=True
    )


async def unarchive_dataset(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    dataset: Dataset,
) -> Dataset:
    """Clear ``archived_at``. Idempotent on already-active rows."""
    if dataset.archived_at is None:
        return dataset
    repo = DatasetRepository.from_session(session)
    return await repo.update(dataset, update_dict={"archived_at": None}, flush=True)


# ── DatasetCase CRUD ────────────────────────────────────────


async def list_cases(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    dataset: Dataset,
) -> Sequence[DatasetCase]:
    """List all cases for a dataset. Order is stable
    (order_index ASC, then created_at ASC) so the UI can render
    a consistent table across reloads.

    Pagination is deliberately omitted — a dataset with thousands
    of cases would suggest poor curation; the eval runner's
    output (M4.8b) is where pagination matters.
    """
    repo = DatasetCaseRepository.from_session(session)
    stmt = repo.for_dataset(dataset.id).order_by(
        DatasetCase.order_index.asc(), DatasetCase.created_at.asc()
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def get_case_or_raise(
    session: AsyncSession | AsyncReadSession,
    dataset: Dataset,
    case_id: UUID,
) -> DatasetCase:
    repo = DatasetCaseRepository.from_session(session)
    stmt = repo.for_dataset(dataset.id).where(DatasetCase.id == case_id)
    case = await repo.get_one_or_none(stmt)
    if case is None:
        raise ResourceNotFound("DatasetCase not found.")
    return case


async def create_case(
    session: AsyncSession,
    dataset: Dataset,
    data: DatasetCaseCreate,
) -> DatasetCase:
    repo = DatasetCaseRepository.from_session(session)
    record = DatasetCase(
        dataset_id=dataset.id,
        name=data.name,
        input_data=data.input_data,
        expected_output=data.expected_output,
        order_index=data.order_index,
    )
    return await repo.create(record, flush=True)


async def update_case(
    session: AsyncSession,
    case: DatasetCase,
    data: DatasetCaseUpdate,
) -> DatasetCase:
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return case
    repo = DatasetCaseRepository.from_session(session)
    return await repo.update(case, update_dict=update_dict, flush=True)


async def delete_case(
    session: AsyncSession,
    case: DatasetCase,
) -> None:
    # Cases don't have soft delete (no deleted_at column) — a
    # dataset is the right rollback unit if the operator wants
    # case history. Hard delete is fine because the eval runner
    # captures case_id + payload at run time, so historical
    # EvalRun rows still carry the input the case had.
    await session.delete(case)
    await session.flush()


# ── Helpers ─────────────────────────────────────────────────


async def _assert_workspace_writable(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace_id: UUID,
) -> None:
    """Confirm the caller can create resources in ``workspace_id``."""
    if is_user_principal(auth_subject):
        stmt = (
            select(WorkspaceMembership.user_id)
            .where(
                WorkspaceMembership.user_id == auth_subject.subject.id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.deleted_at.is_(None),
            )
            .limit(1)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            raise ResourceNotFound("Workspace not found.")
        return
    if is_workspace_principal(auth_subject):
        if auth_subject.subject.id != workspace_id:
            raise ResourceNotFound("Workspace not found.")
        return
    raise ResourceNotFound("Workspace not found.")
