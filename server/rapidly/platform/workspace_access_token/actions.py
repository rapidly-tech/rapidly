"""Workspace access token lifecycle: create, rotate, revoke, leak detection.

Manages the full OAT lifecycle including cryptographic token generation,
hash-based look-up, scope validation, usage tracking, and an email
alert flow when a leaked token is detected via secret-scanning
integrations.
"""

import uuid
from collections.abc import Sequence
from uuid import UUID

import structlog

from rapidly.config import settings
from rapidly.core.crypto import generate_token_hash_pair, get_token_hash
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams
from rapidly.core.utils import now_utc
from rapidly.enums import TokenType
from rapidly.identity.auth.models import AuthPrincipal, Workspace
from rapidly.logging import Logger
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import (
    WorkspaceAccessTokenLeakedEmail,
    WorkspaceAccessTokenLeakedProps,
)
from rapidly.models import User, WorkspaceAccessToken
from rapidly.platform.workspace.resolver import get_payload_workspace
from rapidly.platform.workspace_membership import (
    actions as workspace_membership_service,
)
from rapidly.postgres import AsyncReadSession, AsyncSession

from .ordering import WorkspaceAccessTokenSortProperty
from .queries import WorkspaceAccessTokenRepository
from .types import WorkspaceAccessTokenCreate, WorkspaceAccessTokenUpdate

_log: Logger = structlog.get_logger()

TOKEN_PREFIX = "rapidly_oat_"


# ── Reads ──


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[uuid.UUID] | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkspaceAccessTokenSortProperty]] = (
        (WorkspaceAccessTokenSortProperty.created_at, False),
    ),
) -> tuple[Sequence[WorkspaceAccessToken], int]:
    repository = WorkspaceAccessTokenRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject)
    statement = repository.apply_list_filters(
        statement, workspace_id=workspace_id, sorting=sorting
    )
    return await repository.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )


async def get(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkspaceAccessToken | None:
    repository = WorkspaceAccessTokenRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject).where(
        WorkspaceAccessToken.id == id,
        WorkspaceAccessToken.deleted_at.is_(None),
    )
    return await repository.get_one_or_none(statement)


async def get_by_token(
    session: AsyncSession, token: str, *, expired: bool = False
) -> WorkspaceAccessToken | None:
    token_hash = get_token_hash(token, secret=settings.SECRET)
    repository = WorkspaceAccessTokenRepository.from_session(session)
    return await repository.get_by_token_hash(token_hash, expired=expired)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    create_schema: WorkspaceAccessTokenCreate,
) -> tuple[WorkspaceAccessToken, str]:
    workspace = await get_payload_workspace(session, auth_subject, create_schema)
    token, token_hash = generate_token_hash_pair(
        secret=settings.SECRET, prefix=TOKEN_PREFIX
    )
    workspace_access_token = WorkspaceAccessToken(
        **create_schema.model_dump(exclude={"scopes", "expires_in", "workspace_id"}),
        workspace=workspace,
        token=token_hash,
        expires_at=now_utc() + create_schema.expires_in
        if create_schema.expires_in
        else None,
        scope=" ".join(create_schema.scopes),
    )
    repository = WorkspaceAccessTokenRepository.from_session(session)
    workspace_access_token = await repository.create(workspace_access_token, flush=True)

    return workspace_access_token, token


async def update(
    session: AsyncSession,
    workspace_access_token: WorkspaceAccessToken,
    update_schema: WorkspaceAccessTokenUpdate,
) -> WorkspaceAccessToken:
    repository = WorkspaceAccessTokenRepository.from_session(session)

    update_dict = update_schema.model_dump(exclude={"scopes"}, exclude_unset=True)
    if update_schema.scopes is not None:
        update_dict["scope"] = " ".join(update_schema.scopes)

    return await repository.update(workspace_access_token, update_dict=update_dict)


async def delete(
    session: AsyncSession, workspace_access_token: WorkspaceAccessToken
) -> None:
    repository = WorkspaceAccessTokenRepository.from_session(session)
    await repository.soft_delete(workspace_access_token)


# ── Leak detection ──


async def revoke_leaked(
    session: AsyncSession,
    token: str,
    token_type: TokenType,
    *,
    notifier: str,
    url: str | None = None,
) -> bool:
    workspace_access_token = await get_by_token(session, token)

    if workspace_access_token is None:
        return False

    repository = WorkspaceAccessTokenRepository.from_session(session)
    await repository.soft_delete(workspace_access_token)

    workspace_members = await workspace_membership_service.list_by_workspace(
        session, workspace_access_token.workspace_id
    )
    for workspace_member in workspace_members:
        email = workspace_member.user.email
        body = render_email_template(
            WorkspaceAccessTokenLeakedEmail(
                props=WorkspaceAccessTokenLeakedProps(
                    email=email,
                    workspace_access_token=workspace_access_token.comment,
                    notifier=notifier,
                    url=url or "",
                )
            )
        )
        enqueue_email(
            to_email_addr=email,
            subject="Security Notice - Your Rapidly Workspace Access Token has been leaked",
            html_content=body,
        )

    _log.info(
        "Revoke leaked workspace access token",
        id=workspace_access_token.id,
        notifier=notifier,
        url=url,
    )

    return True
