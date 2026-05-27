"""Tests for the M4.7h credential budget-alert state machine.

The check helper ``check_and_arm_budget_alert`` is called by the
LLM handler after each LlmUsage write. These tests pin the
arming logic against representative MTD vs threshold conditions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from rapidly.agents.integration_credential import queries as cred_queries
from rapidly.agents.llm_usage import actions as llm_actions
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
    monthly_budget_tokens: int | None,
    budget_alert_threshold_percent: int | None,
) -> IntegrationCredential:
    cred = IntegrationCredential(
        workspace_id=workspace.id,
        provider="openai",
        name="prod",
        secret_encrypted=cred_queries.encrypt_secret("sk-x"),
        monthly_budget_tokens=monthly_budget_tokens,
        budget_alert_threshold_percent=budget_alert_threshold_percent,
        is_default=False,
    )
    session.add(cred)
    await session.flush()
    return cred


async def _add_usage(
    session: AsyncSession,
    credential: IntegrationCredential,
    *,
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
class TestCheckAndArmBudgetAlert:
    async def test_arms_when_crossing_threshold(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        cred = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=80,
        )
        # Usage at 850 tokens — 85%, past the 80% threshold.
        await _add_usage(session, cred, input_tokens=850)

        await cred_queries.check_and_arm_budget_alert(session, credential_id=cred.id)
        await session.refresh(cred)
        assert cred.budget_alert_triggered_at is not None

    async def test_does_not_arm_below_threshold(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        cred = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=80,
        )
        await _add_usage(session, cred, input_tokens=500)  # 50% — under

        await cred_queries.check_and_arm_budget_alert(session, credential_id=cred.id)
        await session.refresh(cred)
        assert cred.budget_alert_triggered_at is None

    async def test_idempotent_within_a_month(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Once armed this month, subsequent checks don't move
        # ``triggered_at``. The operator's already been notified.
        cred = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=80,
        )
        await _add_usage(session, cred, input_tokens=850)
        await cred_queries.check_and_arm_budget_alert(session, credential_id=cred.id)
        await session.refresh(cred)
        first_armed_at = cred.budget_alert_triggered_at
        assert first_armed_at is not None

        # Add more usage and check again
        await _add_usage(session, cred, input_tokens=100)
        await cred_queries.check_and_arm_budget_alert(session, credential_id=cred.id)
        await session.refresh(cred)
        # Same timestamp — not re-armed
        assert cred.budget_alert_triggered_at == first_armed_at

    async def test_noop_when_no_threshold_configured(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Budget set, but no threshold → no alert.
        cred = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=None,
        )
        await _add_usage(session, cred, input_tokens=999)
        await cred_queries.check_and_arm_budget_alert(session, credential_id=cred.id)
        await session.refresh(cred)
        assert cred.budget_alert_triggered_at is None

    async def test_noop_when_no_budget(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Threshold set, but no budget → percent is undefined,
        # don't arm.
        cred = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=None,
            budget_alert_threshold_percent=80,
        )
        await _add_usage(session, cred, input_tokens=10**9)
        await cred_queries.check_and_arm_budget_alert(session, credential_id=cred.id)
        await session.refresh(cred)
        assert cred.budget_alert_triggered_at is None

    async def test_excludes_prior_month_usage(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Usage from two months ago shouldn't count toward MTD,
        # so a current-month under-threshold credential stays
        # un-armed.
        cred = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=80,
        )
        # Lots of usage 2 months ago — not in MTD.
        old = datetime.now(UTC) - timedelta(days=60)
        await _add_usage(session, cred, input_tokens=9999, occurred_at=old)
        # Tiny usage this month.
        await _add_usage(session, cred, input_tokens=10)

        await cred_queries.check_and_arm_budget_alert(session, credential_id=cred.id)
        await session.refresh(cred)
        assert cred.budget_alert_triggered_at is None


@pytest.mark.asyncio
class TestAlertsEndpoint:
    async def test_returns_armed_credentials_for_workspace(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        # Three credentials: one armed, one with config but not
        # armed, one with no alerting config at all.
        armed = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=80,
        )
        armed.budget_alert_triggered_at = datetime.now(UTC)
        await _add_usage(session, armed, input_tokens=850)

        not_armed = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=80,
        )
        await _add_usage(session, not_armed, input_tokens=200)

        no_config = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=None,
            budget_alert_threshold_percent=None,
        )
        await _add_usage(session, no_config, input_tokens=500)

        await session.flush()

        result = await llm_actions.alerts(session, principal)
        ids = {row.credential_id for row in result.rows}
        assert armed.id in ids
        assert not_armed.id not in ids
        assert no_config.id not in ids

    async def test_excludes_alerts_from_prior_month(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # An alert triggered in a prior month shouldn't surface
        # in the current month's response — MTD has reset and the
        # operator's prior notification is stale.
        principal = await _member_principal(session, workspace)
        cred = await _make_credential(
            session,
            workspace,
            monthly_budget_tokens=1000,
            budget_alert_threshold_percent=80,
        )
        cred.budget_alert_triggered_at = datetime.now(UTC) - timedelta(days=60)
        await _add_usage(session, cred, input_tokens=100)
        await session.flush()

        result = await llm_actions.alerts(session, principal)
        ids = {row.credential_id for row in result.rows}
        assert cred.id not in ids
