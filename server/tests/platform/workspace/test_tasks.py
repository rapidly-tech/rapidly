"""Tests for workspace background tasks."""

import uuid
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from rapidly.core.db.postgres import AsyncSession
from rapidly.models import User, Workspace
from rapidly.models.workspace import WorkspaceStatus
from rapidly.platform.workspace.workers import (
    WorkspaceDoesNotExist,
    workspace_created,
    workspace_reviewed,
    workspace_under_review,
)
from tests.fixtures.database import SaveFixture


@pytest.fixture(autouse=True)
def enqueue_email_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "rapidly.platform.workspace.workers.enqueue_email", autospec=True
    )


@pytest.mark.asyncio
class TestWorkspaceCreated:
    async def test_not_existing_workspace(self, session: AsyncSession) -> None:
        # then
        session.expunge_all()

        with pytest.raises(WorkspaceDoesNotExist):
            await workspace_created(uuid.uuid4())

    async def test_existing_workspace(
        self, workspace: Workspace, session: AsyncSession
    ) -> None:
        # then
        session.expunge_all()

        await workspace_created(workspace.id)


@pytest.mark.asyncio
class TestWorkspaceUnderReview:
    async def test_not_existing_workspace(self, session: AsyncSession) -> None:
        # then
        session.expunge_all()

        with pytest.raises(WorkspaceDoesNotExist):
            await workspace_under_review(uuid.uuid4())

    async def test_existing_workspace(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
    ) -> None:
        # Update workspace to have under review status
        workspace.status = WorkspaceStatus.INITIAL_REVIEW
        await save_fixture(workspace)

        # then
        session.expunge_all()

        await workspace_under_review(workspace.id)


@pytest.mark.asyncio
class TestWorkspaceReviewed:
    async def test_not_existing_workspace(self, session: AsyncSession) -> None:
        # then
        session.expunge_all()

        with pytest.raises(WorkspaceDoesNotExist):
            await workspace_reviewed(uuid.uuid4())

    async def test_existing_workspace(
        self,
        mocker: MockerFixture,
        enqueue_email_mock: MagicMock,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
    ) -> None:
        # Update workspace to have active status
        workspace.status = WorkspaceStatus.ACTIVE
        await save_fixture(workspace)

        get_admin_user_mock = mocker.patch(
            "rapidly.platform.workspace.workers.WorkspaceRepository.get_admin_user",
            return_value=user,
        )

        # then
        session.expunge_all()

        await workspace_reviewed(workspace.id, initial_review=True)

        enqueue_email_mock.assert_called_once()
        get_admin_user_mock.assert_called_once()
