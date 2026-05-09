"""Tests for webhook service."""

import uuid
from typing import cast
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from rapidly.errors import RequestValidationError, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.identity.auth.scope import Scope
from rapidly.messaging.webhook import actions as webhook_service
from rapidly.messaging.webhook.actions import EventDoesNotExist, EventNotSuccessful
from rapidly.messaging.webhook.types import (
    HttpsUrl,
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
)
from rapidly.models import (
    WebhookEndpoint,
    WebhookEvent,
    Workspace,
)
from rapidly.models.webhook_endpoint import WebhookEventType, WebhookFormat
from rapidly.postgres import AsyncSession
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture


@pytest.fixture
def enqueue_job_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("rapidly.messaging.webhook.actions.dispatch_task")


webhook_url = cast(HttpsUrl, "https://example.com/hook")


# ── Create Endpoint ──


@pytest.mark.asyncio
class TestCreateEndpoint:
    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_set_workspace_id(
        self, auth_subject: AuthPrincipal[Workspace], session: AsyncSession
    ) -> None:
        create_schema = WebhookEndpointCreate(
            url=webhook_url,
            format=WebhookFormat.raw,
            events=[],
            workspace_id=uuid.uuid4(),
        )

        with pytest.raises(RequestValidationError):
            await webhook_service.create_endpoint(session, auth_subject, create_schema)

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_valid(
        self,
        auth_subject: AuthPrincipal[Workspace],
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        create_schema = WebhookEndpointCreate(
            url=webhook_url,
            format=WebhookFormat.raw,
            events=[],
            workspace_id=None,
        )

        endpoint = await webhook_service.create_endpoint(
            session, auth_subject, create_schema
        )
        assert endpoint.workspace == workspace


# ── Update Endpoint ──


@pytest.mark.asyncio
class TestUpdateEndpoint:
    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_endpoint_valid(
        self, session: AsyncSession, webhook_endpoint_workspace: WebhookEndpoint
    ) -> None:
        update_schema = WebhookEndpointUpdate(
            url=cast(HttpsUrl, "https://example.com/hook-updated")
        )

        updated_endpoint = await webhook_service.update_endpoint(
            session, endpoint=webhook_endpoint_workspace, update_schema=update_schema
        )
        assert updated_endpoint.url == "https://example.com/hook-updated"


# ── Reset Endpoint Secret ──


@pytest.mark.asyncio
class TestResetEndpointSecret:
    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_endpoint_valid(
        self, session: AsyncSession, webhook_endpoint_workspace: WebhookEndpoint
    ) -> None:
        old_secret = webhook_endpoint_workspace.secret
        updated_endpoint = await webhook_service.reset_endpoint_secret(
            session, endpoint=webhook_endpoint_workspace
        )
        assert updated_endpoint.secret != old_secret


# ── Delete Endpoint ──


@pytest.mark.asyncio
class TestDeleteEndpoint:
    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_endpoint_valid(
        self, session: AsyncSession, webhook_endpoint_workspace: WebhookEndpoint
    ) -> None:
        deleted_endpoint = await webhook_service.delete_endpoint(
            session, webhook_endpoint_workspace
        )
        assert deleted_endpoint.deleted_at is not None


# ── Redeliver Event ──


@pytest.mark.asyncio
class TestRedeliverEvent:
    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace_second", scopes={Scope.webhooks_write})
    )
    async def test_workspace_endpoint_not_admin(
        self,
        auth_subject: AuthPrincipal[Workspace],
        session: AsyncSession,
        webhook_event_workspace: WebhookEvent,
    ) -> None:
        with pytest.raises(ResourceNotFound):
            await webhook_service.redeliver_event(
                session, auth_subject, webhook_event_workspace.id
            )

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.webhooks_write})
    )
    async def test_workspace_endpoint_valid(
        self,
        auth_subject: AuthPrincipal[Workspace],
        session: AsyncSession,
        webhook_event_workspace: WebhookEvent,
        enqueue_job_mock: MagicMock,
    ) -> None:
        await webhook_service.redeliver_event(
            session, auth_subject, webhook_event_workspace.id
        )
        enqueue_job_mock.assert_called_once()


# ── On Event Success ──


@pytest.mark.asyncio
class TestOnEventSuccess:
    async def test_not_existing_event(self, session: AsyncSession) -> None:
        with pytest.raises(EventDoesNotExist):
            await webhook_service.on_event_success(session, uuid.uuid4())

    async def test_not_successful_event(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        event = WebhookEvent(
            webhook_endpoint=webhook_endpoint_workspace,
            succeeded=False,
            type=WebhookEventType.customer_created,
            payload="{}",
        )
        await save_fixture(event)

        with pytest.raises(EventNotSuccessful):
            await webhook_service.on_event_success(session, event.id)
