"""Tests for workspace access token service."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.core.utils import now_utc
from rapidly.enums import TokenType
from rapidly.models import Workspace, WorkspaceAccessToken, WorkspaceMembership
from rapidly.platform.workspace_access_token import (
    actions as workspace_access_token_service,
)
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture


@pytest.fixture(autouse=True)
def render_email_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "rapidly.platform.workspace_access_token.actions.render_email_template",
        return_value="<html>mocked</html>",
    )


@pytest.fixture(autouse=True)
def enqueue_email_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "rapidly.platform.workspace_access_token.actions.enqueue_email",
        autospec=True,
    )


@pytest.mark.asyncio
class TestRevokeLeaked:
    async def test_false_positive(
        self, session: AsyncSession, enqueue_email_mock: MagicMock
    ) -> None:
        result = await workspace_access_token_service.revoke_leaked(
            session,
            "rapidly_oat_test123",
            TokenType.workspace_access_token,
            notifier="github",
            url="https://github.com",
        )
        assert result is False

        enqueue_email_mock.assert_not_called()

    async def test_true_positive(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        enqueue_email_mock: MagicMock,
    ) -> None:
        token_hash = get_token_hash("rapidly_oat_test123", secret=settings.SECRET)
        workspace_access_token = WorkspaceAccessToken(
            comment="Test",
            token=token_hash,
            workspace=workspace,
            expires_at=now_utc() + timedelta(days=1),
            scope="openid",
        )
        await save_fixture(workspace_access_token)

        result = await workspace_access_token_service.revoke_leaked(
            session,
            "rapidly_oat_test123",
            TokenType.workspace_access_token,
            notifier="github",
            url="https://github.com",
        )
        assert result is True

        updated_workspace_access_token = await session.get(
            WorkspaceAccessToken, workspace_access_token.id
        )
        assert updated_workspace_access_token is not None
        assert updated_workspace_access_token.deleted_at is not None

        enqueue_email_mock.assert_called_once()
        assert "Security Notice" in enqueue_email_mock.call_args.kwargs["subject"]
