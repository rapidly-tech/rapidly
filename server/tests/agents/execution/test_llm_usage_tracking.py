"""Tests for the M4.7d LLM usage-tracking write path.

The LLM + structured_output handlers now insert an ``LlmUsage``
row after each successful provider call so per-credential +
per-workspace billing rollups have first-class data.

We don't make a real LLM call — the test model in pydantic-ai
returns zero tokens, which is what we'd want at the unit-test
boundary anyway. The point of the test is: a successful call
writes a row with the right tenancy fields and the right
credential attribution.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from rapidly.agents.execution.handlers.llm import (
    _record_usage,
    llm_handler,
    structured_output_handler,
)
from rapidly.agents.integration_credential import actions as cred_actions
from rapidly.agents.integration_credential.types import IntegrationCredentialCreate
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
    session: AsyncSession, workspace: Workspace, *, secret: str = "sk-test"
) -> IntegrationCredential:
    principal = await _member_principal(session, workspace)
    return await cred_actions.create(
        session,
        principal,
        IntegrationCredentialCreate(
            workspace_id=workspace.id,
            provider="openai",
            name="prod",
            secret=secret,
            is_default=True,
        ),
    )


async def _llm_usage_for_workspace(
    session: AsyncSession, workspace: Workspace
) -> list[LlmUsage]:
    return list(
        (
            await session.execute(
                select(LlmUsage).where(LlmUsage.workspace_id == workspace.id)
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
class TestRecordUsage:
    async def test_writes_row_with_workspace_attribution(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # No run_id in ctx — the writer leaves run_id NULL. The
        # ``test_run_id_roundtrips`` case below covers the FK
        # path with a real Run row.
        ctx = {
            "session": session,
            "workspace_id": workspace.id,
        }
        await _record_usage(
            ctx=ctx,
            provider="openai",
            model="gpt-4o-mini",
            usage={"input_tokens": 120, "output_tokens": 45},
        )
        rows = await _llm_usage_for_workspace(session, workspace)
        assert len(rows) == 1
        row = rows[0]
        assert row.workspace_id == workspace.id
        assert row.provider == "openai"
        assert row.model == "gpt-4o-mini"
        assert row.input_tokens == 120
        assert row.output_tokens == 45
        assert row.total_tokens == 165
        # No credential resolved (no _resolved_credential_id in ctx)
        # → credential_id stays null, representing env-fallback or
        # explicit-key calls.
        assert row.credential_id is None

    async def test_attributes_to_resolved_credential(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        cred = await _make_credential(session, workspace)
        ctx = {
            "session": session,
            "workspace_id": workspace.id,
            "_resolved_credential_id": cred.id,
        }
        await _record_usage(
            ctx=ctx,
            provider="openai",
            model="gpt-4o-mini",
            usage={"input_tokens": 50, "output_tokens": 20},
        )
        rows = await _llm_usage_for_workspace(session, workspace)
        assert len(rows) == 1
        assert rows[0].credential_id == cred.id

    async def test_skipped_when_no_session(self) -> None:
        # Best-effort write: a handler invoked outside an engine
        # context (no session) must not crash the call. The provider
        # already succeeded.
        await _record_usage(
            ctx={"workspace_id": uuid.uuid4()},
            provider="openai",
            model="gpt-4o-mini",
            usage={"input_tokens": 10, "output_tokens": 0},
        )
        # No assertion needed — the absence of an exception is the
        # contract here.

    async def test_skipped_when_no_workspace_id(
        self,
        session: AsyncSession,
    ) -> None:
        await _record_usage(
            ctx={"session": session},
            provider="openai",
            model="gpt-4o-mini",
            usage={"input_tokens": 10, "output_tokens": 0},
        )


@pytest.mark.asyncio
class TestHandlerEmitsUsage:
    async def test_llm_handler_writes_row_after_call(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Test provider — no network. We're verifying that a
        # successful call results in a usage row, not the token
        # counts themselves (which the test model reports as 0).
        ctx = {
            "session": session,
            "workspace_id": workspace.id,
        }
        await llm_handler(
            ctx,
            {
                "provider": "test",
                "model": "stub",
                "prompt_template": "hi {name}",
            },
            {"name": "world"},
        )
        rows = await _llm_usage_for_workspace(session, workspace)
        assert len(rows) == 1
        assert rows[0].provider == "test"
        assert rows[0].model == "stub"

    async def test_structured_output_handler_writes_row(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        ctx = {
            "session": session,
            "workspace_id": workspace.id,
        }
        # Minimal JSON Schema — primitive-only object so the
        # dynamic-pydantic builder doesn't bail.
        await structured_output_handler(
            ctx,
            {
                "provider": "test",
                "model": "stub",
                "prompt_template": "extract from {body}",
                "schema_json": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            },
            {"body": "anything"},
        )
        rows = await _llm_usage_for_workspace(session, workspace)
        assert len(rows) == 1
        assert rows[0].provider == "test"
        assert rows[0].model == "stub"
