"""Tests for webhook dispatch and payload formatting."""

from typing import cast
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from dramatiq import Retry
from pytest_mock import MockerFixture
from standardwebhooks.webhooks import Webhook as StandardWebhook

from rapidly.core.db.postgres import AsyncSession
from rapidly.messaging.webhook.queries import WebhookDeliveryRepository
from rapidly.messaging.webhook.workers import _webhook_event_send, webhook_event_send
from rapidly.models.webhook_endpoint import (
    WebhookEndpoint,
    WebhookEventType,
    WebhookFormat,
)
from rapidly.models.webhook_event import WebhookEvent
from rapidly.models.workspace import Workspace
from tests.fixtures.database import SaveFixture


@pytest.fixture(autouse=True)
def _force_production_env(mocker: MockerFixture) -> None:
    """Force production env so webhooks are actually sent via HTTP in tests."""
    from rapidly.config import Environment

    mocker.patch(
        "rapidly.messaging.webhook.workers.settings.ENV",
        Environment.production,
    )


@pytest.fixture
def enqueue_job_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("rapidly.messaging.webhook.actions.dispatch_task")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(200, json={"status": "ok"}), '{"status":"ok"}'),
        (httpx.Response(200), None),
        pytest.param(
            httpx.Response(200, text="a" * 8192),
            "a" * 2048,
            id="long response that is truncated",
        ),
    ],
)
async def test_webhook_delivery_success(
    response: httpx.Response,
    expected: str,
    session: AsyncSession,
    save_fixture: SaveFixture,
    respx_mock: respx.MockRouter,
    workspace: Workspace,
) -> None:
    respx_mock.post("https://example.com/hook").mock(return_value=response)

    endpoint = WebhookEndpoint(
        url="https://example.com/hook",
        format=WebhookFormat.raw,
        workspace_id=workspace.id,
        secret="mysecret",
    )
    await save_fixture(endpoint)

    event = WebhookEvent(
        webhook_endpoint_id=endpoint.id,
        type=WebhookEventType.customer_created,
        payload='{"foo":"bar"}',
    )
    await save_fixture(event)

    await webhook_event_send(webhook_event_id=event.id)

    delivery_repository = WebhookDeliveryRepository.from_session(session)
    deliveries = await delivery_repository.get_all_by_event(event.id)
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.succeeded is True
    assert delivery.response == expected


@pytest.mark.asyncio
async def test_webhook_delivery_500(
    session: AsyncSession,
    save_fixture: SaveFixture,
    respx_mock: respx.MockRouter,
    workspace: Workspace,
) -> None:
    respx_mock.post("https://example.com/hook").mock(
        return_value=httpx.Response(500, text="Internal Error")
    )

    endpoint = WebhookEndpoint(
        url="https://example.com/hook",
        format=WebhookFormat.raw,
        workspace_id=workspace.id,
        secret="mysecret",
    )
    await save_fixture(endpoint)

    event = WebhookEvent(
        webhook_endpoint_id=endpoint.id,
        type=WebhookEventType.customer_created,
        payload='{"foo":"bar"}',
    )
    await save_fixture(event)

    # First attempt: should retry
    with pytest.raises(Retry):
        await _webhook_event_send(session=session, webhook_event_id=event.id)

    # Last attempt: mock can_retry to return False so it records permanent failure
    with patch("rapidly.messaging.webhook.workers.can_retry", return_value=False):
        await _webhook_event_send(session=session, webhook_event_id=event.id)

    delivery_repository = WebhookDeliveryRepository.from_session(session)
    deliveries = await delivery_repository.get_all_by_event(event.id)

    assert len(deliveries) == 2
    for delivery in deliveries:
        assert delivery.succeeded is False


@pytest.mark.asyncio
async def test_webhook_delivery_http_error(
    session: AsyncSession,
    save_fixture: SaveFixture,
    respx_mock: respx.MockRouter,
    workspace: Workspace,
) -> None:
    respx_mock.post("https://example.com/hook").mock(
        side_effect=httpx.HTTPError("ERROR")
    )

    endpoint = WebhookEndpoint(
        url="https://example.com/hook",
        format=WebhookFormat.raw,
        workspace_id=workspace.id,
        secret="mysecret",
    )
    await save_fixture(endpoint)

    event = WebhookEvent(
        webhook_endpoint_id=endpoint.id,
        type=WebhookEventType.customer_created,
        payload='{"foo":"bar"}',
    )
    await save_fixture(event)

    # First attempt: should retry
    with pytest.raises(Retry):
        await _webhook_event_send(session=session, webhook_event_id=event.id)

    # Last attempt: mock can_retry to return False so it records permanent failure
    with patch("rapidly.messaging.webhook.workers.can_retry", return_value=False):
        await _webhook_event_send(session=session, webhook_event_id=event.id)

    delivery_repository = WebhookDeliveryRepository.from_session(session)
    deliveries = await delivery_repository.get_all_by_event(event.id)
    assert len(deliveries) == 2
    for delivery in deliveries:
        assert delivery.succeeded is False


@pytest.mark.asyncio
async def test_webhook_standard_webhooks_compatible(
    session: AsyncSession,
    save_fixture: SaveFixture,
    respx_mock: respx.MockRouter,
    workspace: Workspace,
) -> None:
    secret = "mysecret"
    route_mock = respx_mock.post("https://example.com/hook").mock(
        return_value=httpx.Response(200)
    )

    endpoint = WebhookEndpoint(
        url="https://example.com/hook",
        format=WebhookFormat.raw,
        workspace_id=workspace.id,
        secret=secret,
    )
    await save_fixture(endpoint)

    event = WebhookEvent(
        webhook_endpoint_id=endpoint.id,
        type=WebhookEventType.customer_created,
        payload='{"foo":"bar"}',
    )
    await save_fixture(event)

    await _webhook_event_send(session=session, webhook_event_id=event.id)

    # Check that the generated signature is correct
    request = route_mock.calls.last.request
    w = StandardWebhook(secret.encode("utf-8"))
    assert w.verify(request.content, cast(dict[str, str], request.headers)) is not None
