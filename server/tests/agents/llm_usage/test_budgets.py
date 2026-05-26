"""Tests for the M4.7g credential budget endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from rapidly.agents.integration_credential import queries as cred_queries
from rapidly.agents.llm_usage import actions
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


async def _make_credential(
    session: AsyncSession,
    workspace: Workspace,
    *,
    name: str = "prod",
    provider: str = "openai",
    monthly_budget_tokens: int | None = None,
) -> IntegrationCredential:
    cred = IntegrationCredential(
        workspace_id=workspace.id,
        provider=provider,
        name=name,
        secret_encrypted=cred_queries.encrypt_secret("sk-x"),
        monthly_budget_tokens=monthly_budget_tokens,
        is_default=False,
    )
    session.add(cred)
    await session.flush()
    return cred


async def _seed_usage(
    session: AsyncSession,
    *,
    credential: IntegrationCredential,
    input_tokens: int,
    output_tokens: int = 0,
    occurred_at: datetime | None = None,
) -> None:
    session.add(
        LlmUsage(
            workspace_id=credential.workspace_id,
            credential_id=credential.id,
            provider=credential.provider,
            model="gpt-4o-mini",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            occurred_at=occurred_at or datetime.now(UTC),
        )
    )
    await session.flush()


@pytest.mark.asyncio
class TestBudgets:
    async def test_returns_zero_used_for_unbudgeted_unused(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Credential exists but has no budget and no usage.
        # Should still appear (LEFT OUTER JOIN), with mtd=0 and
        # percent_used=None.
        principal = await _member_principal(session, workspace)
        cred = await _make_credential(session, workspace, name="bare")

        result = await actions.budgets(session, principal)
        rows = [r for r in result.rows if r.credential_id == cred.id]
        assert len(rows) == 1
        assert rows[0].month_to_date_tokens == 0
        assert rows[0].monthly_budget_tokens is None
        assert rows[0].percent_used is None

    async def test_computes_percent_used(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        cred = await _make_credential(
            session, workspace, name="capped", monthly_budget_tokens=1000
        )
        await _seed_usage(session, credential=cred, input_tokens=200, output_tokens=50)

        result = await actions.budgets(session, principal)
        rows = [r for r in result.rows if r.credential_id == cred.id]
        assert len(rows) == 1
        assert rows[0].month_to_date_tokens == 250
        assert rows[0].monthly_budget_tokens == 1000
        assert rows[0].percent_used == pytest.approx(0.25)

    async def test_excludes_usage_from_prior_month(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        cred = await _make_credential(session, workspace, monthly_budget_tokens=1000)

        # In-month
        now = datetime.now(UTC)
        await _seed_usage(session, credential=cred, input_tokens=100, occurred_at=now)
        # Two months ago — must NOT contribute to MTD
        two_months_ago = datetime(now.year, now.month, 1, tzinfo=UTC) - timedelta(
            days=45
        )
        await _seed_usage(
            session, credential=cred, input_tokens=9999, occurred_at=two_months_ago
        )

        result = await actions.budgets(session, principal)
        rows = [r for r in result.rows if r.credential_id == cred.id]
        assert rows[0].month_to_date_tokens == 100

    async def test_over_budget_reports_above_one(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # A credential blowing its budget should still get a sane
        # percent_used (e.g., 1.5 for 150% of budget). Dashboards
        # render this as "over budget" without us having to flag it
        # explicitly.
        principal = await _member_principal(session, workspace)
        cred = await _make_credential(session, workspace, monthly_budget_tokens=100)
        await _seed_usage(session, credential=cred, input_tokens=150)

        result = await actions.budgets(session, principal)
        rows = [r for r in result.rows if r.credential_id == cred.id]
        assert rows[0].percent_used == pytest.approx(1.5)

    async def test_other_workspace_credentials_not_visible(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # ws_a has a credential; the test caller is a member of
        # ws_b only. The caller MUST NOT see ws_a's credential in
        # the budgets response — even if ws_a's credential has
        # zero usage and zero budget.
        slug = f"a-{uuid.uuid4().hex[:6]}"
        ws_a = Workspace(name=slug, slug=slug, customer_invoice_prefix=slug.upper())
        session.add(ws_a)
        await session.flush()
        cred_a = await _make_credential(session, ws_a)

        principal = await _member_principal(session, workspace)

        result = await actions.budgets(session, principal)
        ids = {r.credential_id for r in result.rows}
        assert cred_a.id not in ids

    async def test_soft_deleted_credentials_excluded(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Deleting a credential removes it from the budgets list
        # — operators rotating a credential don't want to see the
        # old row hanging around with stale MTD numbers.
        principal = await _member_principal(session, workspace)
        cred = await _make_credential(session, workspace, name="rotated")
        # Simulate soft delete (the credential's actions.delete
        # path does the same, but we do it inline so we don't
        # need the workspace-writable check to fire).
        cred.deleted_at = datetime.now(UTC)
        await session.flush()

        result = await actions.budgets(session, principal)
        ids = {r.credential_id for r in result.rows}
        assert cred.id not in ids
