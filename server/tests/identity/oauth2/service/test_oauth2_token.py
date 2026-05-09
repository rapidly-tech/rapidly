"""Tests for OAuth2 token lifecycle service."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from rapidly.enums import TokenType
from rapidly.identity.oauth2.actions.oauth2_token import (
    oauth2_token as oauth2_token_service,
)
from rapidly.models import OAuth2Client, User, Workspace, WorkspaceMembership
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture

from ..conftest import create_oauth2_token


@pytest.fixture(autouse=True)
def render_email_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "rapidly.identity.oauth2.actions.oauth2_token.render_email_template",
        return_value="<html>mocked</html>",
    )


@pytest.fixture(autouse=True)
def enqueue_email_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "rapidly.identity.oauth2.actions.oauth2_token.enqueue_email",
        autospec=True,
    )


@pytest.mark.asyncio
class TestRevokeLeaked:
    @pytest.mark.parametrize(
        ("token", "token_type"),
        [
            ("rapidly_at_u_123", TokenType.access_token),
            ("rapidly_rt_u_123", TokenType.refresh_token),
            ("rapidly_at_o_123", TokenType.access_token),
            ("rapidly_rt_o_123", TokenType.refresh_token),
        ],
    )
    async def test_false_positive(
        self,
        token: str,
        token_type: TokenType,
        session: AsyncSession,
        enqueue_email_mock: MagicMock,
    ) -> None:
        result = await oauth2_token_service.revoke_leaked(
            session, token, token_type, notifier="github", url="https://github.com"
        )
        assert result is False

        enqueue_email_mock.assert_not_called()

    @pytest.mark.parametrize(
        ("token", "token_type"),
        [
            ("rapidly_at_u_123", TokenType.access_token),
            ("rapidly_rt_u_123", TokenType.refresh_token),
        ],
    )
    async def test_true_positive_user(
        self,
        token: str,
        token_type: TokenType,
        save_fixture: SaveFixture,
        session: AsyncSession,
        oauth2_client: OAuth2Client,
        user: User,
        enqueue_email_mock: MagicMock,
    ) -> None:
        oauth2_token = await create_oauth2_token(
            save_fixture,
            client=oauth2_client,
            access_token="rapidly_at_u_123",
            refresh_token="rapidly_rt_u_123",
            scopes=["openid"],
            user=user,
        )

        result = await oauth2_token_service.revoke_leaked(
            session, token, token_type, notifier="github", url="https://github.com"
        )
        assert result is True

        assert oauth2_token.access_token_revoked_at is not None
        assert oauth2_token.refresh_token_revoked_at is not None

        enqueue_email_mock.assert_called_once()
        assert "Security Notice" in enqueue_email_mock.call_args.kwargs["subject"]

    @pytest.mark.parametrize(
        ("token", "token_type"),
        [
            ("rapidly_at_o_123", TokenType.access_token),
            ("rapidly_rt_o_123", TokenType.refresh_token),
        ],
    )
    async def test_true_positive_workspace(
        self,
        token: str,
        token_type: TokenType,
        save_fixture: SaveFixture,
        session: AsyncSession,
        oauth2_client: OAuth2Client,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        enqueue_email_mock: MagicMock,
    ) -> None:
        oauth2_token = await create_oauth2_token(
            save_fixture,
            client=oauth2_client,
            access_token="rapidly_at_o_123",
            refresh_token="rapidly_rt_o_123",
            scopes=["openid"],
            workspace=workspace,
        )

        result = await oauth2_token_service.revoke_leaked(
            session, token, token_type, notifier="github", url="https://github.com"
        )
        assert result is True

        assert oauth2_token.access_token_revoked_at is not None
        assert oauth2_token.refresh_token_revoked_at is not None

        enqueue_email_mock.assert_called_once()
        assert "Security Notice" in enqueue_email_mock.call_args.kwargs["subject"]

    async def test_already_revoked(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        oauth2_client: OAuth2Client,
        user: User,
        enqueue_email_mock: MagicMock,
    ) -> None:
        await create_oauth2_token(
            save_fixture,
            client=oauth2_client,
            access_token="rapidly_at_u_123",
            refresh_token="rapidly_rt_u_123",
            scopes=["openid"],
            user=user,
            access_token_revoked_at=1,
            refresh_token_revoked_at=1,
        )

        result = await oauth2_token_service.revoke_leaked(
            session, "rapidly_at_u_123", TokenType.access_token, notifier="github"
        )
        assert result is True

        enqueue_email_mock.assert_not_called()
