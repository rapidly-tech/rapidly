"""Tests for ``rapidly.agents.integration_credential.actions``."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from rapidly.agents.integration_credential import actions, queries
from rapidly.agents.integration_credential.types import (
    IntegrationCredentialCreate,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import IntegrationCredential, User, Workspace, WorkspaceMembership
from rapidly.postgres import AsyncSession


async def _member_principal(
    session: AsyncSession, workspace: Workspace
) -> AuthPrincipal[User]:
    user = User(email=f"u-{uuid.uuid4().hex[:6]}@example.com")
    session.add(user)
    await session.flush()
    session.add(WorkspaceMembership(user_id=user.id, workspace_id=workspace.id))
    await session.flush()
    return AuthPrincipal(subject=user, scopes=set(), session=None)


@pytest.mark.asyncio
class TestCreate:
    async def test_persists_with_encrypted_secret(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        record = await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="production",
                secret="sk-prod-12345",
            ),
        )

        # Stored ciphertext != plaintext.
        assert record.secret_encrypted != "sk-prod-12345"
        # And it roundtrips through the queries decrypt path.
        assert queries.decrypt_secret(record.secret_encrypted) == "sk-prod-12345"

    async def test_setting_default_demotes_prior_default(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        first = await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="prod-v1",
                secret="sk-1",
                is_default=True,
            ),
        )
        second = await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="prod-v2",
                secret="sk-2",
                is_default=True,
            ),
        )
        await session.refresh(first)
        await session.refresh(second)
        assert first.is_default is False
        assert second.is_default is True

    async def test_user_without_membership_rejected(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # User exists, but no membership in the workspace.
        user = User(email=f"u-{uuid.uuid4().hex[:6]}@example.com")
        session.add(user)
        await session.flush()
        principal = AuthPrincipal(subject=user, scopes=set(), session=None)

        from rapidly.errors import ResourceNotFound

        with pytest.raises(ResourceNotFound):
            await actions.create(
                session,
                principal,
                IntegrationCredentialCreate(
                    workspace_id=workspace.id,
                    provider="openai",
                    name="prod",
                    secret="sk-prod",
                ),
            )


@pytest.mark.asyncio
class TestSetDefault:
    async def test_promotes_and_demotes(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        first = await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="prod-v1",
                secret="sk-1",
                is_default=True,
            ),
        )
        second = await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="prod-v2",
                secret="sk-2",
                is_default=False,
            ),
        )

        await actions.set_default(session, principal, second)
        await session.refresh(first)
        await session.refresh(second)
        assert first.is_default is False
        assert second.is_default is True

    async def test_already_default_is_noop(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        record = await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="prod",
                secret="sk-prod",
                is_default=True,
            ),
        )
        result = await actions.set_default(session, principal, record)
        assert result is record


@pytest.mark.asyncio
class TestDelete:
    async def test_soft_deletes(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        record = await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="prod",
                secret="sk-prod",
            ),
        )
        await actions.delete(session, principal, record)
        await session.refresh(record)
        assert record.deleted_at is not None

        # Resolver should now miss the deleted credential.
        # (Even if we set it as default before deletion, the
        # ``deleted_at IS NULL`` filter blocks it.)
        rows = (
            (
                await session.execute(
                    select(IntegrationCredential).where(
                        IntegrationCredential.workspace_id == workspace.id,
                        IntegrationCredential.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert rows == []


@pytest.mark.asyncio
class TestListCredentials:
    """``name`` filter — substring match through the same escape
    pattern used by workflows + datasets (M5.25). Hits real DB
    so the ilike escape semantics are exercised end-to-end."""

    async def test_name_filter_substring_match(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        from rapidly.core.pagination import PaginationParams

        principal = await _member_principal(session, workspace)
        await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="openai-prod",
                secret="sk-prod",
            ),
        )
        await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="openai_staging",
                secret="sk-staging",
            ),
        )
        await actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="anthropic",
                name="anthropic-prod",
                secret="sk-ant",
            ),
        )

        # Case-insensitive substring catches both openai-* rows.
        _, count = await actions.list_credentials(
            session,
            principal,
            name="OPENAI",
            pagination=PaginationParams(limit=50, page=1),
        )
        assert count == 2

        # Literal ``_`` in the input must be treated as a literal
        # char, not a SQL single-char wildcard — so the underscore
        # row should match alone.
        rows, count = await actions.list_credentials(
            session,
            principal,
            name="openai_",
            pagination=PaginationParams(limit=50, page=1),
        )
        assert count == 1
        assert rows[0].name == "openai_staging"

        # Whitespace-only is treated as "no filter".
        _, count = await actions.list_credentials(
            session,
            principal,
            name="   ",
            pagination=PaginationParams(limit=50, page=1),
        )
        assert count == 3

        # provider + name combine additively.
        _, count = await actions.list_credentials(
            session,
            principal,
            provider="openai",
            name="prod",
            pagination=PaginationParams(limit=50, page=1),
        )
        assert count == 1
