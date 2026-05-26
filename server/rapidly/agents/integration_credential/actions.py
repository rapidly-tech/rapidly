"""IntegrationCredential lifecycle: list, get, create, delete, set-default.

No PATCH endpoint: rotating a credential means rotating the
secret, and a partial update that touches the secret would force
the API to accept plaintext on a non-create path. Operators
rotate by ``DELETE`` + ``POST``.

Encrypts the incoming plaintext secret at create-time. The
plaintext never crosses the action → API boundary back to the
caller; the response schema strips it.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.agents.integration_credential.queries import (
    IntegrationCredentialRepository,
    encrypt_secret,
)
from rapidly.agents.integration_credential.types import IntegrationCredentialCreate
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import IntegrationCredential, WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> IntegrationCredential | None:
    repo = IntegrationCredentialRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(
        IntegrationCredential.id == id
    )
    return await repo.get_one_or_none(stmt)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> IntegrationCredential:
    record = await get(session, auth_subject, id)
    if record is None:
        raise ResourceNotFound("IntegrationCredential not found.")
    return record


async def list_credentials(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    provider: str | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[IntegrationCredential], int]:
    repo = IntegrationCredentialRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if provider is not None:
        statement = statement.where(IntegrationCredential.provider == provider)
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: IntegrationCredentialCreate,
) -> IntegrationCredential:
    await _assert_workspace_writable(session, auth_subject, data.workspace_id)

    # If the caller is setting this as default, clear any prior
    # default for the same (workspace, provider). The partial
    # unique index would otherwise reject the insert and leak a
    # 500 to the API. Doing it explicitly here makes the flip
    # atomic from the caller's perspective.
    if data.is_default:
        await _clear_other_defaults(
            session, workspace_id=data.workspace_id, provider=data.provider
        )

    repo = IntegrationCredentialRepository.from_session(session)
    record = IntegrationCredential(
        workspace_id=data.workspace_id,
        provider=data.provider,
        name=data.name,
        secret_encrypted=encrypt_secret(data.secret),
        base_url=data.base_url,
        is_default=data.is_default,
        monthly_budget_tokens=data.monthly_budget_tokens,
    )
    return await repo.create(record, flush=True)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    record: IntegrationCredential,
) -> None:
    repo = IntegrationCredentialRepository.from_session(session)
    await repo.soft_delete(record, flush=True)


async def set_default(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    record: IntegrationCredential,
) -> IntegrationCredential:
    """Promote ``record`` to default for its (workspace, provider)
    pair. Demotes any prior default in the same atomic flush.
    """
    if record.is_default:
        return record
    await _clear_other_defaults(
        session, workspace_id=record.workspace_id, provider=record.provider
    )
    repo = IntegrationCredentialRepository.from_session(session)
    return await repo.update(record, update_dict={"is_default": True})


async def _clear_other_defaults(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    provider: str,
) -> None:
    """Demote any existing default for ``(workspace_id, provider)``."""
    stmt = select(IntegrationCredential).where(
        IntegrationCredential.workspace_id == workspace_id,
        IntegrationCredential.provider == provider,
        IntegrationCredential.is_default.is_(True),
        IntegrationCredential.deleted_at.is_(None),
    )
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        row.is_default = False
    if rows:
        await session.flush()


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
