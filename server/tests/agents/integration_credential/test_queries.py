"""Tests for the IntegrationCredential queries module —
encryption roundtrip + ``resolve_for_workspace`` lookup.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import InvalidToken

from rapidly.agents.integration_credential import queries
from rapidly.models import IntegrationCredential, Workspace
from rapidly.postgres import AsyncSession


class TestEncryptionRoundtrip:
    def test_encrypt_then_decrypt_yields_original(self) -> None:
        ciphertext = queries.encrypt_secret("sk-abcdef123456")
        assert ciphertext != "sk-abcdef123456"
        assert queries.decrypt_secret(ciphertext) == "sk-abcdef123456"

    def test_two_encrypts_of_same_plaintext_differ(self) -> None:
        # Fernet includes a timestamp + IV, so two encryptions of
        # the same plaintext should produce different ciphertexts.
        # If they ever match, the Fernet primitive has been
        # mis-used (e.g., deterministic mode), which would weaken
        # at-rest security.
        a = queries.encrypt_secret("sk-same")
        b = queries.encrypt_secret("sk-same")
        assert a != b

    def test_decrypt_rejects_tampered_ciphertext(self) -> None:
        ct = queries.encrypt_secret("sk-abc")
        # Flip a byte in the middle.
        tampered = ct[:20] + "X" + ct[21:]
        with pytest.raises(InvalidToken):
            queries.decrypt_secret(tampered)


@pytest.mark.asyncio
class TestResolveForWorkspace:
    async def test_returns_none_when_no_default(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # No credentials in this workspace at all.
        result = await queries.resolve_for_workspace(
            session, workspace_id=workspace.id, provider="openai"
        )
        assert result is None

    async def test_returns_decrypted_default(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        cred = IntegrationCredential(
            workspace_id=workspace.id,
            provider="openai",
            name="production",
            secret_encrypted=queries.encrypt_secret("sk-prod-key"),
            base_url=None,
            is_default=True,
        )
        session.add(cred)
        await session.flush()

        result = await queries.resolve_for_workspace(
            session, workspace_id=workspace.id, provider="openai"
        )
        assert result == ("sk-prod-key", None)

    async def test_ignores_default_from_other_provider(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # A default exists, but for the wrong provider. The
        # lookup must NOT cross provider boundaries — that would
        # send an OpenAI key to an Anthropic API call.
        wrong = IntegrationCredential(
            workspace_id=workspace.id,
            provider="anthropic",
            name="claude-default",
            secret_encrypted=queries.encrypt_secret("sk-ant-key"),
            is_default=True,
        )
        session.add(wrong)
        await session.flush()

        result = await queries.resolve_for_workspace(
            session, workspace_id=workspace.id, provider="openai"
        )
        assert result is None

    async def test_explicit_id_overrides_default(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        default_cred = IntegrationCredential(
            workspace_id=workspace.id,
            provider="openai",
            name="prod",
            secret_encrypted=queries.encrypt_secret("sk-prod"),
            is_default=True,
        )
        staging_cred = IntegrationCredential(
            workspace_id=workspace.id,
            provider="openai",
            name="staging",
            secret_encrypted=queries.encrypt_secret("sk-staging"),
            base_url="https://staging.example.com",
            is_default=False,
        )
        session.add_all([default_cred, staging_cred])
        await session.flush()

        result = await queries.resolve_for_workspace(
            session,
            workspace_id=workspace.id,
            provider="openai",
            credential_id=staging_cred.id,
        )
        assert result == ("sk-staging", "https://staging.example.com")

    async def test_ignores_credential_from_other_workspace(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        import uuid as uuid_mod

        slug = f"other-{uuid_mod.uuid4().hex[:6]}"
        other_ws = Workspace(
            name=slug,
            slug=slug,
            customer_invoice_prefix=slug.upper(),
        )
        session.add(other_ws)
        await session.flush()

        # Credential exists, but in a different workspace. Even
        # if the caller passes a valid credential_id, the
        # workspace_id filter must reject it.
        cred = IntegrationCredential(
            workspace_id=other_ws.id,
            provider="openai",
            name="cross-tenant",
            secret_encrypted=queries.encrypt_secret("sk-other"),
            is_default=True,
        )
        session.add(cred)
        await session.flush()

        result = await queries.resolve_for_workspace(
            session,
            workspace_id=workspace.id,
            provider="openai",
            credential_id=cred.id,
        )
        assert result is None
