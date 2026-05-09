"""Tests for notification recipient endpoints."""

import pytest
from httpx import AsyncClient

from rapidly.messaging.notification_recipient.types import NotificationRecipientPlatform
from rapidly.models import Workspace, WorkspaceMembership
from rapidly.models.user import User
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_notification_recipient


@pytest.mark.asyncio
class TestCreateNotificationRecipient:
    async def test_anonymous(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.post(
            "/api/notifications/recipients",
            json={
                "platform": "ios",
                "expo_push_token": "123",
            },
        )

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        response = await client.post(
            "/api/notifications/recipients",
            json={
                "platform": "ios",
                "expo_push_token": "123",
            },
        )

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_valid(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        response = await client.post(
            "/api/notifications/recipients",
            json={
                "platform": "ios",
                "expo_push_token": "123",
            },
        )

        assert response.status_code == 201

        json = response.json()
        assert json["platform"] == "ios"
        assert json["expo_push_token"] == "123"


@pytest.mark.asyncio
class TestListNotificationRecipients:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get("/api/notifications/recipients")

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        user: User,
    ) -> None:
        response = await client.get("/api/notifications/recipients")

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_metadata_filter(
        self, save_fixture: SaveFixture, client: AsyncClient, user: User
    ) -> None:
        await create_notification_recipient(
            save_fixture,
            user=user,
            expo_push_token="123",
            platform=NotificationRecipientPlatform.ios,
        )
        await create_notification_recipient(
            save_fixture,
            user=user,
            expo_push_token="456",
            platform=NotificationRecipientPlatform.ios,
        )

        response = await client.get(
            "/api/notifications/recipients",
            params={"platform": "ios"},
        )

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 2


@pytest.mark.asyncio
class TestDeleteNotificationRecipient:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.delete("/api/notifications/recipients/123")
        assert response.status_code == 401

    @pytest.mark.auth
    async def test_delete(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        user: User,
    ) -> None:
        notification_recipient = await create_notification_recipient(
            save_fixture,
            user=user,
            expo_push_token="123",
            platform=NotificationRecipientPlatform.ios,
        )

        response = await client.delete(
            f"/api/notifications/recipients/{notification_recipient.id}"
        )

        assert response.status_code == 204

        response = await client.get("/api/notifications/recipients")
        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 0
