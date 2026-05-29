"""Tests for ``rapidly.agents.vector_collection.actions``.

Two layers:
    1. ``TestCreate / TestUpdate / TestDelete`` — mocked-repo
       unit tests that pin the request shape and side effects.
    2. ``TestTriggerIndex`` — real session + workspace + file
       integration test for the indexing dispatch path. The
       only thing mocked is ``dispatch_task`` (we don't want
       a Dramatiq round-trip in the test) and the workspace-
       membership assertion (the helper is exercised in its
       own test class).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from rapidly.agents.vector_collection import actions
from rapidly.agents.vector_collection.types import (
    VectorCollectionCreate,
    VectorCollectionUpdate,
)
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, VectorCollection, Workspace, WorkspaceMembership
from rapidly.models.file import DownloadableFile, FileScanStatus, FileServiceTypes
from rapidly.postgres import AsyncSession


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_persists_with_workspace_check(self) -> None:
        principal = _user_principal()
        workspace_id = uuid4()

        captured: list[Any] = []
        repo = MagicMock()

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with (
            patch(
                "rapidly.agents.vector_collection.actions._assert_workspace_writable",
                new=AsyncMock(),
            ),
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo,
            ),
        ):
            await actions.create(
                MagicMock(),
                principal,
                VectorCollectionCreate(
                    workspace_id=workspace_id,
                    name="docs",
                    embedding_model="openai:text-embedding-3-small",
                    dimensions=1536,
                ),
            )

        assert captured[0].workspace_id == workspace_id
        assert captured[0].name == "docs"
        assert captured[0].embedding_model == "openai:text-embedding-3-small"
        assert captured[0].dimensions == 1536


@pytest.mark.asyncio
class TestUpdate:
    async def test_empty_payload_noop(self) -> None:
        principal = _user_principal()
        collection = VectorCollection(
            id=uuid4(),
            workspace_id=uuid4(),
            name="x",
            embedding_model="test:4",
            dimensions=4,
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=collection)

        with patch(
            "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
            return_value=repo,
        ):
            result = await actions.update(
                MagicMock(), principal, collection, VectorCollectionUpdate()
            )

        assert result is collection
        repo.update.assert_not_called()

    async def test_partial_update(self) -> None:
        principal = _user_principal()
        collection = VectorCollection(
            id=uuid4(),
            workspace_id=uuid4(),
            name="x",
            embedding_model="test:4",
            dimensions=4,
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=collection)

        with patch(
            "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
            return_value=repo,
        ):
            await actions.update(
                MagicMock(),
                principal,
                collection,
                VectorCollectionUpdate(name="docs-2"),
            )

        repo.update.assert_awaited_once()
        call_kwargs = repo.update.await_args.kwargs
        assert call_kwargs["update_dict"] == {"name": "docs-2"}


@pytest.mark.asyncio
class TestTriggerIndex:
    async def test_dispatches_and_validates_file_in_workspace(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        # Real DB so we exercise the FileRepository statement; mock
        # only the dispatch boundary so no Dramatiq queue is touched.
        collection = VectorCollection(
            workspace_id=workspace.id,
            name="docs",
            embedding_model="test:4",
            dimensions=4,
        )
        session.add(collection)
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

        dispatch = mocker.patch(
            "rapidly.agents.vector_collection.actions.dispatch_task"
        )

        principal = _user_principal()
        await actions.trigger_index(session, principal, collection, file_row.id)

        dispatch.assert_called_once_with(
            "agents.rag.index_document",
            collection_id=collection.id,
            file_id=file_row.id,
        )

    async def test_rejects_file_from_other_workspace(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        # The collection sits in ``workspace``; the file sits in a
        # different workspace. Even with read on both, indexing must
        # refuse — we don't want one tenant's file to leak content
        # into another tenant's collection.
        slug = f"other-{uuid.uuid4().hex[:6]}"
        other_ws = Workspace(
            name=slug,
            slug=slug,
            customer_invoice_prefix=slug.upper(),
        )
        session.add(other_ws)
        await session.flush()

        collection = VectorCollection(
            workspace_id=workspace.id,
            name="docs",
            embedding_model="test:4",
            dimensions=4,
        )
        session.add(collection)

        wrong_file = DownloadableFile(
            workspace_id=other_ws.id,
            name="leak.txt",
            path=f"workspaces/{other_ws.id}/{uuid.uuid4()}",
            mime_type="text/plain",
            size=10,
            service=FileServiceTypes.downloadable,
            is_uploaded=True,
            is_enabled=True,
            scan_status=FileScanStatus.clean,
        )
        session.add(wrong_file)
        await session.flush()

        dispatch = mocker.patch(
            "rapidly.agents.vector_collection.actions.dispatch_task"
        )

        principal = _user_principal()
        with pytest.raises(ResourceNotFound):
            await actions.trigger_index(session, principal, collection, wrong_file.id)
        dispatch.assert_not_called()

    async def test_archived_collection_rejected(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        """M5.79: an archived collection can't accept new indexing.
        Symmetric with the workflow + dataset trigger guards
        (M5.78). Without this an automation could keep indexing
        into a corpus the operator deliberately mothballed."""
        from datetime import UTC, datetime

        from rapidly.errors import NotPermitted

        collection = VectorCollection(
            workspace_id=workspace.id,
            name="archived-docs",
            embedding_model="test:4",
            dimensions=4,
            archived_at=datetime.now(UTC),
        )
        session.add(collection)

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

        dispatch = mocker.patch(
            "rapidly.agents.vector_collection.actions.dispatch_task"
        )

        principal = _user_principal()
        with pytest.raises(NotPermitted, match="archived"):
            await actions.trigger_index(session, principal, collection, file_row.id)
        # The actor must NOT be dispatched — otherwise stale data
        # would still land in the corpus even though the API
        # returns 412.
        dispatch.assert_not_called()


@pytest.mark.asyncio
class TestAssertWorkspaceWritable:
    async def test_user_principal_with_active_membership_passes(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        user = User(email=f"u-{uuid.uuid4().hex[:6]}@example.com")
        session.add(user)
        await session.flush()
        membership = WorkspaceMembership(user_id=user.id, workspace_id=workspace.id)
        session.add(membership)
        await session.flush()

        principal = AuthPrincipal(subject=user, scopes=set(), session=None)
        # No raise = pass.
        await actions._assert_workspace_writable(session, principal, workspace.id)

    async def test_user_principal_without_membership_raises(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # User exists but has no membership in this workspace.
        user = User(email=f"u-{uuid.uuid4().hex[:6]}@example.com")
        session.add(user)
        await session.flush()

        principal = AuthPrincipal(subject=user, scopes=set(), session=None)
        with pytest.raises(ResourceNotFound):
            await actions._assert_workspace_writable(session, principal, workspace.id)

    async def test_workspace_principal_only_writes_to_self(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        other_id = uuid4()
        principal = AuthPrincipal(subject=workspace, scopes=set(), session=None)

        await actions._assert_workspace_writable(session, principal, workspace.id)

        with pytest.raises(ResourceNotFound):
            await actions._assert_workspace_writable(session, principal, other_id)


@pytest.mark.asyncio
class TestListCollections:
    """``name`` filter — substring match through the standard
    escape pattern. We can't assert SQL text through a MagicMock
    chain (per the project's documented test pattern in
    server/CLAUDE.md) so we count ``.where`` calls instead."""

    async def test_no_filters_no_where(self) -> None:
        principal = _user_principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 0

    async def test_name_adds_where(self) -> None:
        principal = _user_principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                name="docs",
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 1

    async def test_empty_name_is_noop(self) -> None:
        principal = _user_principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                name="   ",
                pagination=PaginationParams(page=1, limit=10),
            )

        # Whitespace-only is ignored — matches the workflow /
        # dataset / credentials filter contract.
        assert statement.where.call_count == 0

    async def test_project_and_name_combine_additively(self) -> None:
        principal = _user_principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                project_id=uuid4(),
                name="docs",
                pagination=PaginationParams(page=1, limit=10),
            )

        # project_id + name → 2 .where predicates.
        assert statement.where.call_count == 2

    async def test_workspace_id_adds_where(self) -> None:
        principal = _user_principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                workspace_id=uuid4(),
                pagination=PaginationParams(page=1, limit=10),
            )

        # workspace_id alone → +1 .where (narrows the readable
        # statement further).
        assert statement.where.call_count == 1

    async def test_all_filters_combine_additively(self) -> None:
        principal = _user_principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                workspace_id=uuid4(),
                project_id=uuid4(),
                name="docs",
                pagination=PaginationParams(page=1, limit=10),
            )

        # workspace_id + project_id + name → 3 .where predicates
        # (additive, no short-circuit).
        assert statement.where.call_count == 3

    async def test_is_archived_filter_modes(self) -> None:
        # Three modes: True (archived only), False (active only),
        # None / omitted (both). Mirrors the workflow + dataset
        # archive filter shape (M5.65 / M5.68). Counted via
        # .where as the MagicMock pattern documented in
        # server/CLAUDE.md.
        principal = _user_principal()

        # is_archived=True → +1 .where for IS NOT NULL.
        statement_true = MagicMock()
        statement_true.where.return_value = statement_true
        repo_true = MagicMock()
        repo_true.get_readable_statement.return_value = statement_true
        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo_true,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                is_archived=True,
                pagination=PaginationParams(page=1, limit=10),
            )
        assert statement_true.where.call_count == 1

        # is_archived=False → +1 .where for IS NULL.
        statement_false = MagicMock()
        statement_false.where.return_value = statement_false
        repo_false = MagicMock()
        repo_false.get_readable_statement.return_value = statement_false
        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo_false,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                is_archived=False,
                pagination=PaginationParams(page=1, limit=10),
            )
        assert statement_false.where.call_count == 1

        # is_archived=None → 0 .where for the archive axis.
        statement_none = MagicMock()
        statement_none.where.return_value = statement_none
        repo_none = MagicMock()
        repo_none.get_readable_statement.return_value = statement_none
        with (
            patch(
                "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
                return_value=repo_none,
            ),
            patch(
                "rapidly.agents.vector_collection.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_collections(
                MagicMock(),
                principal,
                is_archived=None,
                pagination=PaginationParams(page=1, limit=10),
            )
        assert statement_none.where.call_count == 0


@pytest.mark.asyncio
class TestArchive:
    async def test_active_collection_gets_archived_stamp(self) -> None:
        from uuid import uuid4

        principal = _user_principal()
        collection = VectorCollection(
            id=uuid4(),
            workspace_id=uuid4(),
            name="docs",
            embedding_model="openai:text-embedding-3-small",
            dimensions=1536,
            archived_at=None,
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=collection)

        with patch(
            "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
            return_value=repo,
        ):
            await actions.archive(MagicMock(), principal, collection)

        repo.update.assert_awaited_once()
        _, kwargs = repo.update.call_args
        assert "archived_at" in kwargs["update_dict"]
        assert kwargs["update_dict"]["archived_at"] is not None
        assert kwargs.get("flush") is True

    async def test_already_archived_is_noop(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        principal = _user_principal()
        existing = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
        collection = VectorCollection(
            id=uuid4(),
            workspace_id=uuid4(),
            name="docs",
            embedding_model="openai:text-embedding-3-small",
            dimensions=1536,
            archived_at=existing,
        )

        repo = MagicMock()
        repo.update = AsyncMock()

        with patch(
            "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
            return_value=repo,
        ):
            result = await actions.archive(MagicMock(), principal, collection)

        repo.update.assert_not_awaited()
        assert result.archived_at == existing


@pytest.mark.asyncio
class TestUnarchive:
    async def test_archived_collection_clears_stamp(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        principal = _user_principal()
        collection = VectorCollection(
            id=uuid4(),
            workspace_id=uuid4(),
            name="docs",
            embedding_model="openai:text-embedding-3-small",
            dimensions=1536,
            archived_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=collection)

        with patch(
            "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
            return_value=repo,
        ):
            await actions.unarchive(MagicMock(), principal, collection)

        repo.update.assert_awaited_once()
        _, kwargs = repo.update.call_args
        assert kwargs["update_dict"] == {"archived_at": None}

    async def test_already_active_is_noop(self) -> None:
        from uuid import uuid4

        principal = _user_principal()
        collection = VectorCollection(
            id=uuid4(),
            workspace_id=uuid4(),
            name="docs",
            embedding_model="openai:text-embedding-3-small",
            dimensions=1536,
            archived_at=None,
        )

        repo = MagicMock()
        repo.update = AsyncMock()

        with patch(
            "rapidly.agents.vector_collection.actions.VectorCollectionRepository.from_session",
            return_value=repo,
        ):
            await actions.unarchive(MagicMock(), principal, collection)

        repo.update.assert_not_awaited()
