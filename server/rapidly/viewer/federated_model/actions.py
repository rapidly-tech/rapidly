"""Federated-model lifecycle: list, get, create, delete.

The IfcOpenShell parse worker that flips ``status='uploaded'`` →
``'parsing'`` → ``'ready'`` ships in M3.1b along with the system-
deps (apt-installed ifcopenshell-tools) it needs. This module exists
so the frontend upload UI can be built against a real route surface.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import FederatedModel, ModelStatus
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.viewer.federated_model.queries import FederatedModelRepository
from rapidly.viewer.federated_model.types import FederatedModelCreate
from rapidly.worker import dispatch_task


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> FederatedModel | None:
    repo = FederatedModelRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(FederatedModel.id == id)
    return await repo.get_one_or_none(stmt)


async def list_models(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: UUID | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[FederatedModel], int]:
    repo = FederatedModelRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(FederatedModel.project_id == project_id)
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: FederatedModelCreate,
) -> FederatedModel:
    """Create the row in ``status='uploaded'`` and dispatch the
    parse worker.

    The frontend has already done the multipart upload via
    ``catalog/file``'s presigned-PUT flow and passes the resulting
    ``source_file_id`` here. The actor that flips
    ``uploaded -> parsing -> ready`` lives in ``workers.parse_ifc``.
    """
    repo = FederatedModelRepository.from_session(session)
    record = FederatedModel(
        project_id=data.project_id,
        name=data.name,
        source_file_id=data.source_file_id,
        status=ModelStatus.uploaded,
    )
    created = await repo.create(record, flush=True)
    # Dispatch only after the flush so the worker can SELECT the
    # row by id. The actor itself re-loads the row in its own
    # session — we just need the id to be persisted.
    dispatch_task("viewer.parse_ifc", model_id=created.id)
    return created


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    model: FederatedModel,
) -> None:
    repo = FederatedModelRepository.from_session(session)
    await repo.soft_delete(model)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> FederatedModel:
    model = await get(session, auth_subject, id)
    if model is None:
        raise ResourceNotFound("Federated model not found.")
    return model
