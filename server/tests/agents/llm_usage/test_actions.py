"""Tests for the LlmUsage list + rollup actions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from rapidly.agents.llm_usage import actions
from rapidly.core.pagination import PaginationParams
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    IntegrationCredential,
    LlmUsage,
    User,
    Workspace,
    WorkspaceMembership,
)
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


async def _seed_usage(
    session: AsyncSession,
    *,
    workspace: Workspace,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    input_tokens: int = 100,
    output_tokens: int = 50,
    occurred_at: datetime | None = None,
    credential_id: uuid.UUID | None = None,
) -> LlmUsage:
    row = LlmUsage(
        workspace_id=workspace.id,
        credential_id=credential_id,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        occurred_at=occurred_at or datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


@pytest.mark.asyncio
class TestListUsage:
    async def test_returns_only_callers_workspace(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Caller's workspace has 2 rows; another workspace has 1.
        # The caller should only see their own.
        principal = await _member_principal(session, workspace)
        await _seed_usage(session, workspace=workspace)
        await _seed_usage(
            session, workspace=workspace, provider="anthropic", model="claude-3-haiku"
        )

        slug = f"o-{uuid.uuid4().hex[:6]}"
        other_ws = Workspace(name=slug, slug=slug, customer_invoice_prefix=slug.upper())
        session.add(other_ws)
        await session.flush()
        await _seed_usage(session, workspace=other_ws)

        rows, count = await actions.list_usage(
            session, principal, pagination=PaginationParams(limit=50, page=1)
        )
        assert count == 2
        assert all(r.workspace_id == workspace.id for r in rows)

    async def test_filters_by_provider(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        await _seed_usage(session, workspace=workspace, provider="openai")
        await _seed_usage(
            session, workspace=workspace, provider="anthropic", model="claude-3"
        )

        rows, count = await actions.list_usage(
            session,
            principal,
            provider="anthropic",
            pagination=PaginationParams(limit=50, page=1),
        )
        assert count == 1
        assert rows[0].provider == "anthropic"


@pytest.mark.asyncio
class TestRollup:
    async def test_groups_by_provider_and_model(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        # Two openai calls + one anthropic call.
        await _seed_usage(
            session,
            workspace=workspace,
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
        )
        await _seed_usage(
            session,
            workspace=workspace,
            provider="openai",
            model="gpt-4o",
            input_tokens=200,
            output_tokens=100,
        )
        await _seed_usage(
            session,
            workspace=workspace,
            provider="anthropic",
            model="claude-3",
            input_tokens=50,
            output_tokens=25,
        )

        result = await actions.rollup(session, principal)
        # Two groups: (openai, gpt-4o) and (anthropic, claude-3).
        assert len(result.rows) == 2
        openai_row = next(r for r in result.rows if r.provider == "openai")
        anthropic_row = next(r for r in result.rows if r.provider == "anthropic")
        assert openai_row.input_tokens == 300
        assert openai_row.output_tokens == 150
        assert openai_row.total_tokens == 450
        assert openai_row.call_count == 2
        assert anthropic_row.total_tokens == 75
        assert anthropic_row.call_count == 1

    async def test_window_excludes_older_rows(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        now = datetime.now(UTC)
        # In-window
        await _seed_usage(
            session,
            workspace=workspace,
            input_tokens=100,
            occurred_at=now - timedelta(hours=1),
        )
        # Out-of-window (default 24h)
        await _seed_usage(
            session,
            workspace=workspace,
            input_tokens=999,
            occurred_at=now - timedelta(days=2),
        )

        result = await actions.rollup(session, principal)
        assert len(result.rows) == 1
        assert result.rows[0].input_tokens == 100

    async def test_filter_by_credential_id(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)

        # Create a credential to use as a target filter.
        from rapidly.agents.integration_credential import (
            actions as cred_actions,
        )
        from rapidly.agents.integration_credential import (
            queries as cred_queries,
        )

        cred_row = IntegrationCredential(
            workspace_id=workspace.id,
            provider="openai",
            name="prod",
            secret_encrypted=cred_queries.encrypt_secret("sk-x"),
            is_default=True,
        )
        session.add(cred_row)
        await session.flush()

        # Two openai calls — one attributed to the credential,
        # one env-fallback (credential_id NULL).
        await _seed_usage(
            session, workspace=workspace, credential_id=cred_row.id, input_tokens=100
        )
        await _seed_usage(
            session, workspace=workspace, credential_id=None, input_tokens=999
        )

        # Filter by credential_id — should only see the tagged call.
        result = await actions.rollup(session, principal, credential_id=cred_row.id)
        assert len(result.rows) == 1
        assert result.rows[0].input_tokens == 100

        # Suppress lint about cred_actions being imported-not-used.
        assert cred_actions is not None

    async def test_window_capped_at_90_days(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # A pathologically large window gets clamped to 90 days.
        principal = await _member_principal(session, workspace)
        result = await actions.rollup(
            session,
            principal,
            window_start=datetime(1990, 1, 1, tzinfo=UTC),
            window_end=datetime(2030, 1, 1, tzinfo=UTC),
        )
        clamped = result.window_end - result.window_start
        assert clamped <= timedelta(days=90)

    async def test_other_workspace_not_visible(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)

        slug = f"o-{uuid.uuid4().hex[:6]}"
        other_ws = Workspace(name=slug, slug=slug, customer_invoice_prefix=slug.upper())
        session.add(other_ws)
        await session.flush()
        await _seed_usage(
            session, workspace=other_ws, input_tokens=9999, output_tokens=9999
        )

        result = await actions.rollup(session, principal)
        assert result.rows == []
