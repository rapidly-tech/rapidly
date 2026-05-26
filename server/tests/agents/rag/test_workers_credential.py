"""M4.7c — indexer actor consults the IntegrationCredential store.

Verifies that ``embed_options`` carries the session + workspace_id
into ``embed_batch`` so the workspace's default credential is the
one used, not whatever ``OPENAI_API_KEY`` happens to be set to.

We don't make a real embedding call; we patch ``embed_batch`` to
capture the options dict and assert the resolver-relevant fields
are present.
"""

from __future__ import annotations

import uuid

import pytest
from pytest_mock import MockerFixture

from rapidly.agents.integration_credential import actions as cred_actions
from rapidly.agents.integration_credential.types import IntegrationCredentialCreate
from rapidly.agents.rag import workers as rag_workers
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    User,
    VectorCollection,
    Workspace,
    WorkspaceMembership,
)
from rapidly.models.file import DownloadableFile, FileScanStatus, FileServiceTypes
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
class TestIndexerCredentialPassthrough:
    async def test_passes_workspace_id_and_session_to_embedder(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        # Seed: a collection in this workspace, a file row, and a
        # default openai credential. The actor should pull the
        # credential implicitly via the embedder.
        principal = await _member_principal(session, workspace)
        await cred_actions.create(
            session,
            principal,
            IntegrationCredentialCreate(
                workspace_id=workspace.id,
                provider="openai",
                name="prod",
                secret="sk-ws-prod-key",
                is_default=True,
            ),
        )

        coll = VectorCollection(
            workspace_id=workspace.id,
            name="docs",
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
        )
        session.add(coll)
        await session.flush()

        file_row = DownloadableFile(
            workspace_id=workspace.id,
            name="readme.txt",
            path=f"workspaces/{workspace.id}/{uuid.uuid4()}",
            mime_type="text/plain",
            size=10,
            service=FileServiceTypes.downloadable,
            is_uploaded=True,
            is_enabled=True,
            scan_status=FileScanStatus.clean,
        )
        session.add(file_row)
        await session.flush()

        # Patch the S3 boundary so no MinIO round-trip happens.
        mocker.patch.object(
            rag_workers, "_download_file_bytes", return_value=b"hello world"
        )
        # Capture the options dict so we can assert workspace_id +
        # session are forwarded. Return a 4-dim vector so the
        # dimension check passes.
        captured_options: list[dict] = []

        async def _capture(
            texts: list[str], *, model_id: str, options: dict | None = None
        ) -> list[list[float]]:
            captured_options.append(options or {})
            return [[0.0, 0.25, 0.5, 0.75] for _ in texts]

        mocker.patch.object(rag_workers, "embed_batch", side_effect=_capture)

        await rag_workers.index_document(coll.id, file_row.id)

        # We get one call per batch — for one chunk, that's one
        # invocation. The options must carry session + workspace_id
        # so the embedder's resolver can look up the credential.
        assert len(captured_options) == 1
        opts = captured_options[0]
        assert opts.get("workspace_id") == workspace.id
        assert opts.get("session") is not None
        # No explicit api_key bypass — the embedder is responsible
        # for picking the right credential. The actor passing
        # api_key here would silently override the credential
        # store, which is the exact bug M4.7c fixes.
        assert "api_key" not in opts or opts["api_key"] in (None,)
