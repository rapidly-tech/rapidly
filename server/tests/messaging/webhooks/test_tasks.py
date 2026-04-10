"""Tests for webhook background tasks."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from rapidly.config import settings
from rapidly.messaging.webhook import actions as webhook_service
from rapidly.messaging.webhook.workers import _webhook_event_send
from rapidly.models import WebhookEndpoint, WebhookEvent
from rapidly.models.webhook_endpoint import WebhookEventType
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture


@pytest.fixture
def enqueue_job_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("rapidly.messaging.webhook.workers.dispatch_task")


@pytest.mark.asyncio
class TestWebhookEventSend:
    async def test_disabled_endpoint_skips_send(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        # Disable the endpoint
        webhook_endpoint_workspace.enabled = False
        await save_fixture(webhook_endpoint_workspace)

        # Create an event for the disabled endpoint
        event = WebhookEvent(
            webhook_endpoint_id=webhook_endpoint_workspace.id,
            type=WebhookEventType.customer_created,
            payload='{"foo":"bar"}',
        )
        await save_fixture(event)

        # Send should skip without error
        await _webhook_event_send(session, webhook_event_id=event.id)

        # Event should not be marked as succeeded or failed
        await session.refresh(event)
        assert event.succeeded is None


@pytest.mark.asyncio
class TestOnEventFailed:
    async def test_disables_endpoint_after_threshold_failures(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        # Create multiple failed events
        events = []
        for i in range(settings.WEBHOOK_FAILURE_THRESHOLD):
            event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=False,
            )
            await save_fixture(event)
            events.append(event)

        # Trigger the failure handler
        await webhook_service.on_event_failed(session, events[-1].id)

        # Check that the endpoint is now disabled
        await session.refresh(webhook_endpoint_workspace)
        assert webhook_endpoint_workspace.enabled is False

    async def test_does_not_disable_endpoint_below_threshold(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        # Create fewer failed events than threshold
        events = []
        for i in range(settings.WEBHOOK_FAILURE_THRESHOLD - 1):
            event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=False,
            )
            await save_fixture(event)
            events.append(event)

        # Trigger the failure handler
        await webhook_service.on_event_failed(session, events[-1].id)

        # Check that the endpoint is still enabled
        await session.refresh(webhook_endpoint_workspace)
        assert webhook_endpoint_workspace.enabled is True

    async def test_does_not_disable_with_mixed_results(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        # Create failed events
        events = []
        for i in range(settings.WEBHOOK_FAILURE_THRESHOLD - 2):
            event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=False,
            )
            await save_fixture(event)
            events.append(event)

        # Add a successful event in the middle
        success_event = WebhookEvent(
            webhook_endpoint_id=webhook_endpoint_workspace.id,
            type=WebhookEventType.customer_created,
            payload='{"foo":"bar"}',
            succeeded=True,
        )
        await save_fixture(success_event)

        # Add more failed events
        for i in range(2):
            event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=False,
            )
            await save_fixture(event)
            events.append(event)

        # Trigger the failure handler
        await webhook_service.on_event_failed(session, events[-1].id)

        # Check that the endpoint is still enabled (success broke the streak)
        await session.refresh(webhook_endpoint_workspace)
        assert webhook_endpoint_workspace.enabled is True

    async def test_ignores_already_disabled_endpoint(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        # Disable the endpoint first
        webhook_endpoint_workspace.enabled = False
        await save_fixture(webhook_endpoint_workspace)

        # Create a failed event
        event = WebhookEvent(
            webhook_endpoint_id=webhook_endpoint_workspace.id,
            type=WebhookEventType.customer_created,
            payload='{"foo":"bar"}',
            succeeded=False,
        )
        await save_fixture(event)

        # Trigger the failure handler
        await webhook_service.on_event_failed(session, event.id)

        # Endpoint should remain disabled
        await session.refresh(webhook_endpoint_workspace)
        assert webhook_endpoint_workspace.enabled is False

    async def test_disables_endpoint_ignoring_pending_events(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        # Create threshold number of failed events
        events = []
        for i in range(settings.WEBHOOK_FAILURE_THRESHOLD):
            event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=False,
            )
            await save_fixture(event)
            events.append(event)

        # Add some pending events (succeeded=None) - these should be ignored
        for i in range(5):
            pending_event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=None,
            )
            await save_fixture(pending_event)

        # Trigger the failure handler on one of the failed events
        await webhook_service.on_event_failed(session, events[-1].id)

        # Check that the endpoint is disabled (pending events should not block this)
        await session.refresh(webhook_endpoint_workspace)
        assert webhook_endpoint_workspace.enabled is False

    async def test_marks_pending_events_as_skipped_when_disabled(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        webhook_endpoint_workspace: WebhookEndpoint,
    ) -> None:
        # Create threshold number of failed events
        events = []
        for i in range(settings.WEBHOOK_FAILURE_THRESHOLD):
            event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=False,
            )
            await save_fixture(event)
            events.append(event)

        # Add some pending events (succeeded=None)
        pending_events = []
        for i in range(3):
            pending_event = WebhookEvent(
                webhook_endpoint_id=webhook_endpoint_workspace.id,
                type=WebhookEventType.customer_created,
                payload='{"foo":"bar"}',
                succeeded=None,
                skipped=False,
            )
            await save_fixture(pending_event)
            pending_events.append(pending_event)

        # Trigger the failure handler
        await webhook_service.on_event_failed(session, events[-1].id)

        # Check that the endpoint is disabled
        await session.refresh(webhook_endpoint_workspace)
        assert webhook_endpoint_workspace.enabled is False

        # Check that pending events are now marked as skipped
        for pending_event in pending_events:
            await session.refresh(pending_event)
            assert pending_event.skipped is True
