"""Webhook test fixtures — endpoints, events, and deliveries."""

import pytest_asyncio

from rapidly.models import (
    User,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
    Workspace,
)
from rapidly.models.webhook_endpoint import WebhookEventType, WebhookFormat
from tests.fixtures.database import SaveFixture

# ── User-scoped fixtures ──


@pytest_asyncio.fixture
async def webhook_endpoint_user(
    save_fixture: SaveFixture, user: User
) -> WebhookEndpoint:
    endpoint = WebhookEndpoint(
        url="https://example.com/foo",
        format=WebhookFormat.raw,
        user_id=user.id,
        secret="foobar",
    )
    await save_fixture(endpoint)
    return endpoint


@pytest_asyncio.fixture
async def webhook_event_user(
    save_fixture: SaveFixture,
    webhook_endpoint_user: WebhookEndpoint,
) -> WebhookEvent:
    event = WebhookEvent(
        webhook_endpoint_id=webhook_endpoint_user.id,
        last_http_code=200,
        succeeded=True,
        type=WebhookEventType.customer_created,
        payload='{"foo":"bar"}',
    )
    await save_fixture(event)
    return event


# ── Workspace-scoped fixtures ──


@pytest_asyncio.fixture
async def webhook_endpoint_workspace(
    save_fixture: SaveFixture, workspace: Workspace
) -> WebhookEndpoint:
    endpoint = WebhookEndpoint(
        url="https://example.com/foo",
        format=WebhookFormat.raw,
        workspace_id=workspace.id,
        secret="foobar",
    )
    await save_fixture(endpoint)
    return endpoint


@pytest_asyncio.fixture
async def webhook_event_workspace(
    save_fixture: SaveFixture,
    webhook_endpoint_workspace: WebhookEndpoint,
) -> WebhookEvent:
    event = WebhookEvent(
        webhook_endpoint_id=webhook_endpoint_workspace.id,
        last_http_code=200,
        succeeded=True,
        type=WebhookEventType.customer_created,
        payload='{"foo":"bar"}',
    )
    await save_fixture(event)
    return event


@pytest_asyncio.fixture
async def webhook_delivery(
    save_fixture: SaveFixture,
    webhook_endpoint_workspace: WebhookEndpoint,
    webhook_event_workspace: WebhookEvent,
) -> WebhookDelivery:
    delivery = WebhookDelivery(
        webhook_endpoint_id=webhook_endpoint_workspace.id,
        webhook_event_id=webhook_event_workspace.id,
        http_code=200,
        succeeded=True,
    )
    await save_fixture(delivery)
    return delivery
