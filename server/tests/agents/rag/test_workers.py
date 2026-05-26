"""End-to-end test for the RAG indexing actor.

Mocks the S3 download (the actor's I/O boundary) so the test
exercises the full chunk → embed (test provider) → upsert path
against a real session, real VectorCollection, and real
VectorChunk rows.

Why the explicit ``AsyncSessionMaker`` patch:
    The auto-fixture in ``tests/fixtures/worker.py`` patches
    ``SQLAlchemyMiddleware.get_async_session`` to return the test
    session, but the production ``AsyncSessionMaker`` wraps it in
    a commit/rollback context that would close the test's outer
    transaction. The local patch replaces it with a context that
    yields the bare test session — same shape, no commit on exit.
"""

from __future__ import annotations

import uuid

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import select

from rapidly.agents.rag import workers as rag_workers
from rapidly.models import (
    VectorChunk,
    VectorCollection,
    Workspace,
)
from rapidly.models.file import DownloadableFile, FileScanStatus, FileServiceTypes
from rapidly.postgres import AsyncSession


async def _seed_collection(
    session: AsyncSession,
    *,
    workspace: Workspace,
    dimensions: int = 4,
) -> VectorCollection:
    coll = VectorCollection(
        workspace_id=workspace.id,
        project_id=None,
        name="docs",
        embedding_model=f"test:{dimensions}",
        dimensions=dimensions,
    )
    session.add(coll)
    await session.flush()
    return coll


async def _seed_text_file(
    session: AsyncSession,
    *,
    workspace: Workspace,
    mime_type: str = "text/plain",
    name: str = "readme.txt",
) -> DownloadableFile:
    f = DownloadableFile(
        workspace_id=workspace.id,
        name=name,
        path=f"workspaces/{workspace.id}/{uuid.uuid4()}",
        mime_type=mime_type,
        size=1,
        service=FileServiceTypes.downloadable,
        is_uploaded=True,
        is_enabled=True,
        scan_status=FileScanStatus.clean,
    )
    session.add(f)
    await session.flush()
    return f


def _patch_session_maker(mocker: MockerFixture, session: AsyncSession) -> None:
    """Route the actor's ``AsyncSessionMaker`` to the test session
    without the commit/rollback context that production uses.
    """

    class _Ctx:
        async def __aenter__(self) -> AsyncSession:
            return session

        async def __aexit__(self, *args: object) -> None:
            return None

    mocker.patch.object(rag_workers, "AsyncSessionMaker", return_value=_Ctx())


@pytest.mark.asyncio
class TestIndexDocument:
    async def test_chunks_and_embeds_text_file(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        coll = await _seed_collection(session, workspace=workspace)
        file_row = await _seed_text_file(session, workspace=workspace)

        # Two paragraphs separated by a blank line — the chunker
        # should group them into a single chunk (well under the cap).
        sample = b"first paragraph here.\n\nsecond paragraph here."
        mocker.patch.object(rag_workers, "_download_file_bytes", return_value=sample)
        _patch_session_maker(mocker, session)

        await rag_workers.index_document(coll.id, file_row.id)

        rows = (
            (
                await session.execute(
                    select(VectorChunk).where(VectorChunk.collection_id == coll.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].text == "first paragraph here.\n\nsecond paragraph here."
        assert rows[0].source_document_id == file_row.id
        assert rows[0].chunk_index == 0
        assert len(rows[0].embedding) == coll.dimensions

    async def test_reindex_replaces_prior_chunks(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        # Re-indexing the same file should delete the old chunks
        # — that's the idempotency contract.
        coll = await _seed_collection(session, workspace=workspace)
        file_row = await _seed_text_file(session, workspace=workspace)
        _patch_session_maker(mocker, session)

        mocker.patch.object(
            rag_workers, "_download_file_bytes", return_value=b"version one"
        )
        await rag_workers.index_document(coll.id, file_row.id)

        mocker.patch.object(
            rag_workers,
            "_download_file_bytes",
            return_value=b"version two: longer content\n\nwith two paras",
        )
        await rag_workers.index_document(coll.id, file_row.id)

        rows = (
            (
                await session.execute(
                    select(VectorChunk).where(VectorChunk.collection_id == coll.id)
                )
            )
            .scalars()
            .all()
        )
        # Only chunks from the second run should remain.
        assert len(rows) == 1
        assert rows[0].text.startswith("version two")

    async def test_empty_source_clears_chunks(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        coll = await _seed_collection(session, workspace=workspace)
        file_row = await _seed_text_file(session, workspace=workspace)
        _patch_session_maker(mocker, session)

        # First seed a chunk.
        mocker.patch.object(
            rag_workers, "_download_file_bytes", return_value=b"some content"
        )
        await rag_workers.index_document(coll.id, file_row.id)

        # Re-index against an empty source.
        mocker.patch.object(
            rag_workers, "_download_file_bytes", return_value=b"   \n  \n"
        )
        await rag_workers.index_document(coll.id, file_row.id)

        rows = (
            (
                await session.execute(
                    select(VectorChunk).where(VectorChunk.collection_id == coll.id)
                )
            )
            .scalars()
            .all()
        )
        assert rows == []

    async def test_unsupported_mime_raises(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        coll = await _seed_collection(session, workspace=workspace)
        file_row = await _seed_text_file(
            session, workspace=workspace, mime_type="application/pdf"
        )
        _patch_session_maker(mocker, session)

        mocker.patch.object(
            rag_workers, "_download_file_bytes", return_value=b"%PDF-1.4 ..."
        )

        with pytest.raises(rag_workers.IndexingError, match="application/pdf"):
            await rag_workers.index_document(coll.id, file_row.id)
