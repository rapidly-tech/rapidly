"""Tests for external event ingestion service."""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from rapidly.analytics.external_event import actions as external_event_service
from rapidly.models import ExternalEvent
from rapidly.models.external_event import ExternalEventSource
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture


@pytest.fixture
def enqueue_job_mock(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch("rapidly.analytics.external_event.actions.dispatch_task")


@pytest.mark.asyncio
class TestEnqueue:
    async def test_basic(
        self, session: AsyncSession, enqueue_job_mock: AsyncMock
    ) -> None:
        event = await external_event_service.enqueue(
            session, ExternalEventSource.stripe, "task_name", "EXTERNAL_EVENT_ID", {}
        )

        assert event.source == ExternalEventSource.stripe
        assert event.task_name == "task_name"
        assert event.external_id == "EXTERNAL_EVENT_ID"

        enqueue_job_mock.assert_called_once_with("task_name", event.id)

    async def test_already_existing(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        enqueue_job_mock: AsyncMock,
    ) -> None:
        existing_event = ExternalEvent(
            source=ExternalEventSource.stripe,
            task_name="task_name",
            external_id="EXTERNAL_EVENT_ID",
            data={},
        )
        await save_fixture(existing_event)

        event = await external_event_service.enqueue(
            session, ExternalEventSource.stripe, "task_name", "EXTERNAL_EVENT_ID", {}
        )

        assert event == existing_event

        enqueue_job_mock.assert_not_called()
