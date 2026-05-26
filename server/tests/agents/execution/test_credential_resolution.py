"""Tests for the M4.7b credential-resolution path.

Three layers:
    1. engine — workspace_id threads into ctx via the run →
       version → workflow chain
    2. embedder — ``_resolve_credential`` reads from the credential
       store when session+workspace_id are in opts, falls back to env
    3. llm — ``_resolve_credential`` reads from the credential
       store when session+workspace_id are in ctx
"""

from __future__ import annotations

import uuid

import pytest

from rapidly.agents.execution.handlers.llm import (
    _resolve_credential as llm_resolve_credential,
)
from rapidly.agents.integration_credential import actions as cred_actions
from rapidly.agents.integration_credential import queries as cred_queries
from rapidly.agents.integration_credential.types import IntegrationCredentialCreate
from rapidly.agents.rag.embedder import (
    _resolve_credential as embedder_resolve_credential,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, Workspace, WorkspaceMembership
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


async def _seed_default(
    session: AsyncSession,
    workspace: Workspace,
    provider: str,
    secret: str,
    base_url: str | None = None,
) -> None:
    principal = await _member_principal(session, workspace)
    await cred_actions.create(
        session,
        principal,
        IntegrationCredentialCreate(
            workspace_id=workspace.id,
            provider=provider,
            name=f"default-{provider}",
            secret=secret,
            base_url=base_url,
            is_default=True,
        ),
    )


@pytest.mark.asyncio
class TestEmbedderResolution:
    async def test_explicit_api_key_wins_over_credential(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Credential exists but should NOT be consulted when the
        # caller passes an explicit key.
        await _seed_default(session, workspace, "openai", "sk-from-store")
        key, base_url = await embedder_resolve_credential(
            provider="openai",
            opts={
                "api_key": "sk-explicit",
                "session": session,
                "workspace_id": workspace.id,
            },
        )
        assert key == "sk-explicit"
        assert base_url is None

    async def test_falls_back_to_credential_store(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        await _seed_default(
            session, workspace, "openai", "sk-store-default", base_url="https://eu"
        )
        key, base_url = await embedder_resolve_credential(
            provider="openai",
            opts={"session": session, "workspace_id": workspace.id},
        )
        assert key == "sk-store-default"
        assert base_url == "https://eu"

    async def test_env_fallback_when_store_misses(
        self,
        session: AsyncSession,
        workspace: Workspace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        # Workspace has no default → fall through to env.
        key, base_url = await embedder_resolve_credential(
            provider="openai",
            opts={"session": session, "workspace_id": workspace.id},
        )
        assert key == "sk-env"
        assert base_url is None

    async def test_env_used_without_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No session/workspace_id supplied (indexer-worker path
        # until M4.7c). Goes straight to env.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-only")
        key, base_url = await embedder_resolve_credential(provider="openai", opts={})
        assert key == "sk-env-only"
        assert base_url is None


@pytest.mark.asyncio
class TestLlmResolution:
    async def test_explicit_node_config_key_wins(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        await _seed_default(session, workspace, "openai", "sk-store")
        key, base_url = await llm_resolve_credential(
            "openai",
            {"api_key": "sk-from-node"},
            {"session": session, "workspace_id": workspace.id},
        )
        assert key == "sk-from-node"
        assert base_url is None

    async def test_reads_credential_store_by_default(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        await _seed_default(
            session,
            workspace,
            "anthropic",
            "sk-ant-default",
        )
        key, base_url = await llm_resolve_credential(
            "anthropic",
            {},
            {"session": session, "workspace_id": workspace.id},
        )
        assert key == "sk-ant-default"
        # Anthropic credentials don't surface base_url through the
        # handler — only OpenAI/Ollama use the override slot.
        assert base_url is None

    async def test_explicit_credential_id_pins_lookup(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Two credentials for openai; default is "primary", but the
        # workflow names credential_id="secondary".
        principal = await _member_principal(session, workspace)
        primary = await cred_actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="primary",
                secret="sk-primary",
                is_default=True,
            ),
        )
        secondary = await cred_actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="secondary",
                secret="sk-secondary",
                is_default=False,
            ),
        )

        key, _ = await llm_resolve_credential(
            "openai",
            {"credential_id": str(secondary.id)},
            {"session": session, "workspace_id": workspace.id},
        )
        assert key == "sk-secondary"

        # And the default still wins without the pin.
        key_default, _ = await llm_resolve_credential(
            "openai", {}, {"session": session, "workspace_id": workspace.id}
        )
        assert key_default == "sk-primary"
        # Suppress lint about ``primary`` being unused.
        assert primary.id != secondary.id

    async def test_env_fallback_when_no_credential_or_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
        key, base_url = await llm_resolve_credential("anthropic", {}, {})
        assert key == "sk-ant-env"
        assert base_url is None

    async def test_unknown_provider_returns_none(self) -> None:
        # An unsupported provider with no node-config key + no
        # session and no env var → both slots stay None. The
        # ``_build_model`` will raise ``unknown provider`` after
        # this; the resolver itself doesn't.
        key, base_url = await llm_resolve_credential("cohere", {}, {})
        assert key is None
        assert base_url is None


@pytest.mark.asyncio
class TestEngineCtxThreading:
    """Confirms the engine puts workspace_id into ctx.

    The engine walks ``run → version → workflow → workspace`` to
    populate ctx; this test exercises the helper directly so we
    don't need a full pending run to validate the lookup.
    """

    async def test_load_workspace_id_resolves_chain(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        from rapidly.agents.execution.engine import _load_workspace_id
        from rapidly.models import Workflow

        workflow = Workflow(
            workspace_id=workspace.id,
            name="rfi-triage",
            description=None,
        )
        session.add(workflow)
        await session.flush()

        resolved = await _load_workspace_id(session, workflow.id)
        assert resolved == workspace.id

    async def test_load_workspace_id_returns_none_for_missing(
        self,
        session: AsyncSession,
    ) -> None:
        from rapidly.agents.execution.engine import _load_workspace_id

        resolved = await _load_workspace_id(session, uuid.uuid4())
        assert resolved is None


@pytest.mark.asyncio
class TestEmbedderCredentialDoesNotLeak:
    """End-to-end resolver check: the credential ciphertext never
    appears in the returned plaintext key, and the resolver doesn't
    leak across workspaces.
    """

    async def test_cross_workspace_isolation(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # ws_a has a default; ws_b has none. A lookup on ws_b
        # must NOT pick up ws_a's credential.
        ws_a = workspace
        slug = f"b-{uuid.uuid4().hex[:6]}"
        ws_b = Workspace(name=slug, slug=slug, customer_invoice_prefix=slug.upper())
        session.add(ws_b)
        await session.flush()

        await _seed_default(session, ws_a, "openai", "sk-a-key")

        # Hit ws_b — no credential, no env → expect None.
        key, _ = await embedder_resolve_credential(
            provider="openai",
            opts={"session": session, "workspace_id": ws_b.id},
        )
        # Default is None when env is unset OR equals the env value
        # (whichever is set in the test runner). The key thing is
        # it MUST NOT be ws_a's secret.
        assert key != "sk-a-key"

    async def test_ciphertext_never_returned(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Sanity check: even though the row stores ciphertext, the
        # resolver returns plaintext. Confirms the decrypt path is
        # active (a regression that returned ciphertext would
        # silently break LLM calls).
        await _seed_default(session, workspace, "openai", "sk-plain-target")
        key, _ = await embedder_resolve_credential(
            provider="openai",
            opts={"session": session, "workspace_id": workspace.id},
        )
        assert key == "sk-plain-target"

        # And the encrypt helper returns something else.
        ciphertext = cred_queries.encrypt_secret("sk-plain-target")
        assert ciphertext != "sk-plain-target"
