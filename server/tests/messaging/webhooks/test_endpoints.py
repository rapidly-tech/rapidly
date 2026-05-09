"""Tests for webhook endpoints."""

import pytest
from httpx import AsyncClient

from rapidly.identity.auth.scope import Scope
from rapidly.models import User
from rapidly.models.webhook_delivery import WebhookDelivery
from rapidly.models.webhook_endpoint import WebhookEndpoint
from rapidly.models.workspace import Workspace
from rapidly.models.workspace_membership import WorkspaceMembership
from tests.fixtures.auth import AuthSubjectFixture

# ── List Webhook Endpoints ──


@pytest.mark.asyncio
class TestListWebhookEndpoints:
    async def test_unauthenticated(
        self,
        client: AsyncClient,
        workspace: Workspace,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        params = {"workspace_id": str(workspace.id)}
        response = await client.get("/api/webhooks/endpoints", params=params)
        assert response.status_code == 401

    @pytest.mark.auth
    async def test_authenticated_not_member(
        self,
        client: AsyncClient,
        workspace: Workspace,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        params = {"workspace_id": str(workspace.id)}
        response = await client.get("/api/webhooks/endpoints", params=params)

        assert response.status_code == 200
        json = response.json()
        assert len(json["data"]) == 0

    @pytest.mark.auth
    async def test_authenticated(
        self,
        client: AsyncClient,
        workspace: Workspace,
        user: User,
        workspace_membership: WorkspaceMembership,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        params = {"workspace_id": str(workspace.id)}
        response = await client.get("/api/webhooks/endpoints", params=params)

        assert response.status_code == 200
        json = response.json()
        assert len(json["data"]) == 1
        assert json["data"][0]["id"] == str(webhook_endpoint_workspace.id)


# ── Create Webhook Endpoint ──


@pytest.mark.asyncio
class TestCreateWebhookEndpoint:
    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_user_missing_scope(self, client: AsyncClient) -> None:
        params = {"url": "https://example.com/hook", "format": "raw", "events": []}
        response = await client.post("/api/webhooks/endpoints", json=params)

        assert response.status_code == 403

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.web_write}),
        AuthSubjectFixture(scopes={Scope.webhooks_write}),
    )
    async def test_user_valid(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        params = {
            "url": "https://example.com/hook",
            "format": "raw",
            "events": [],
            "workspace_id": str(workspace.id),
        }
        response = await client.post("/api/webhooks/endpoints", json=params)

        assert response.status_code == 201

    @pytest.mark.auth(AuthSubjectFixture(subject="workspace", scopes=set()))
    async def test_workspace_missing_scope(self, client: AsyncClient) -> None:
        params = {"url": "https://example.com/hook", "format": "raw", "events": []}
        response = await client.post("/api/webhooks/endpoints", json=params)

        assert response.status_code == 403

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_valid_creator_webhooks_write_scope(
        self, client: AsyncClient
    ) -> None:
        params = {"url": "https://example.com/hook", "format": "raw", "events": []}
        response = await client.post("/api/webhooks/endpoints", json=params)

        assert response.status_code == 201

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.webhooks_write}),
    )
    async def test_url_with_leading_and_trailing_spaces(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        params = {
            "url": "  https://example.com/hook  ",
            "format": "raw",
            "events": [],
            "workspace_id": str(workspace.id),
        }
        response = await client.post("/api/webhooks/endpoints", json=params)

        assert response.status_code == 201
        json = response.json()
        assert json["url"] == "https://example.com/hook"


# ── Update Webhook Endpoint ──


@pytest.mark.asyncio
class TestUpdateWebhookEndpoint:
    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_user_missing_scope(
        self,
        client: AsyncClient,
        webhook_endpoint_workspace: WebhookEndpoint,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.patch(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}", json={}
        )

        assert response.status_code == 403

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.web_write}),
        AuthSubjectFixture(scopes={Scope.webhooks_write}),
    )
    async def test_user_valid(
        self,
        client: AsyncClient,
        webhook_endpoint_workspace: WebhookEndpoint,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.patch(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}", json={}
        )

        assert response.status_code == 200

    @pytest.mark.auth(AuthSubjectFixture(subject="workspace", scopes=set()))
    async def test_workspace_missing_scope(
        self, client: AsyncClient, webhook_endpoint_workspace: WebhookEndpoint
    ) -> None:
        response = await client.patch(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}", json={}
        )

        assert response.status_code == 403

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_valid_creator_webhooks_write_scope(
        self, client: AsyncClient, webhook_endpoint_workspace: WebhookEndpoint
    ) -> None:
        response = await client.patch(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}", json={}
        )

        assert response.status_code == 200


# ── Delete Webhook Endpoint ──


@pytest.mark.asyncio
class TestDeleteWebhookEndpoint:
    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_user_missing_scope(
        self,
        client: AsyncClient,
        webhook_endpoint_workspace: WebhookEndpoint,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.delete(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}"
        )

        assert response.status_code == 403

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.web_write}),
        AuthSubjectFixture(scopes={Scope.webhooks_write}),
    )
    async def test_user_valid(
        self,
        client: AsyncClient,
        webhook_endpoint_workspace: WebhookEndpoint,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.delete(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}"
        )

        assert response.status_code == 204

    @pytest.mark.auth(AuthSubjectFixture(subject="workspace", scopes=set()))
    async def test_workspace_missing_scope(
        self, client: AsyncClient, webhook_endpoint_workspace: WebhookEndpoint
    ) -> None:
        response = await client.delete(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}"
        )

        assert response.status_code == 403

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_valid_creator_webhooks_write_scope(
        self, client: AsyncClient, webhook_endpoint_workspace: WebhookEndpoint
    ) -> None:
        response = await client.delete(
            f"/api/webhooks/endpoints/{webhook_endpoint_workspace.id}"
        )

        assert response.status_code == 204


# ── List Webhook Deliveries ──


@pytest.mark.asyncio
class TestListWebhookDeliveries:
    @pytest.mark.auth
    async def test_user_not_member(
        self,
        client: AsyncClient,
        webhook_endpoint_workspace: WebhookEndpoint,
        webhook_delivery: WebhookDelivery,
    ) -> None:
        response = await client.get("/api/webhooks/deliveries")

        assert response.status_code == 200
        json = response.json()
        assert len(json["data"]) == 0

    @pytest.mark.auth
    async def test_user(
        self,
        client: AsyncClient,
        user: User,
        webhook_endpoint_workspace: WebhookEndpoint,
        webhook_delivery: WebhookDelivery,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get("/api/webhooks/deliveries")

        assert response.status_code == 200
        json = response.json()
        assert len(json["data"]) == 1
        assert json["data"][0]["id"] == str(webhook_delivery.id)

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace(
        self,
        client: AsyncClient,
        webhook_endpoint_workspace: WebhookEndpoint,
        webhook_delivery: WebhookDelivery,
    ) -> None:
        response = await client.get("/api/webhooks/deliveries")

        assert response.status_code == 200
        json = response.json()
        assert len(json["data"]) == 1
        assert json["data"][0]["id"] == str(webhook_delivery.id)
