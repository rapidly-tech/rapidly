"""Tests for event type action logic."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from rapidly.analytics.event_type import actions as event_type_actions
from rapidly.analytics.event_type.ordering import EventTypesSortProperty
from rapidly.analytics.event_type.types import EventTypeWithStats
from rapidly.core.pagination import PaginationParams
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.integrations.tinybird.actions import TinybirdEventTypeStats
from rapidly.models import Workspace
from rapidly.models.event import EventSource
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_event, create_event_type


@pytest.mark.asyncio
class TestListWithStatsDualRead:
    @pytest.mark.auth(AuthSubjectFixture(subject="workspace"))
    async def test_uses_db_when_tinybird_read_disabled_globally(
        self,
        mocker: MockerFixture,
        session: AsyncMock,
        auth_subject: AuthPrincipal[Workspace],
        workspace: Workspace,
        save_fixture: SaveFixture,
    ) -> None:
        mocker.patch(
            "rapidly.analytics.event_type.actions.settings.TINYBIRD_EVENTS_READ", False
        )

        event_type = await create_event_type(
            save_fixture, workspace=workspace, name="test.event"
        )
        await create_event(save_fixture, workspace=workspace, event_type=event_type)

        tinybird_mock = mocker.patch(
            "rapidly.analytics.event_type.actions._list_with_stats_from_tinybird",
            new_callable=AsyncMock,
        )

        results, count = await event_type_actions.list_with_stats(
            session,
            auth_subject,
            pagination=PaginationParams(page=1, limit=10),
            sorting=[(EventTypesSortProperty.last_seen, True)],
        )

        tinybird_mock.assert_not_called()
        assert count == 1

    @pytest.mark.auth(AuthSubjectFixture(subject="workspace"))
    async def test_uses_db_when_org_tinybird_read_disabled(
        self,
        mocker: MockerFixture,
        session: AsyncMock,
        auth_subject: AuthPrincipal[Workspace],
        workspace: Workspace,
        save_fixture: SaveFixture,
    ) -> None:
        mocker.patch(
            "rapidly.analytics.event_type.actions.settings.TINYBIRD_EVENTS_READ", True
        )
        workspace.feature_settings = {
            "tinybird_read": False,
            "tinybird_compare": False,
        }
        await save_fixture(workspace)

        event_type = await create_event_type(
            save_fixture, workspace=workspace, name="test.event"
        )
        await create_event(save_fixture, workspace=workspace, event_type=event_type)

        tinybird_mock = mocker.patch(
            "rapidly.analytics.event_type.actions._list_with_stats_from_tinybird",
            new_callable=AsyncMock,
        )

        results, count = await event_type_actions.list_with_stats(
            session,
            auth_subject,
            pagination=PaginationParams(page=1, limit=10),
            sorting=[(EventTypesSortProperty.last_seen, True)],
        )

        tinybird_mock.assert_not_called()
        assert count == 1

    @pytest.mark.auth(AuthSubjectFixture(subject="workspace"))
    async def test_returns_tinybird_when_enabled(
        self,
        mocker: MockerFixture,
        session: AsyncMock,
        auth_subject: AuthPrincipal[Workspace],
        workspace: Workspace,
        save_fixture: SaveFixture,
    ) -> None:
        mocker.patch(
            "rapidly.analytics.event_type.actions.settings.TINYBIRD_EVENTS_READ", True
        )
        workspace.feature_settings = {
            "tinybird_read": True,
            "tinybird_compare": False,
        }
        await save_fixture(workspace)

        event_type = await create_event_type(
            save_fixture, workspace=workspace, name="test.event"
        )
        await create_event(save_fixture, workspace=workspace, event_type=event_type)

        now = datetime.now(UTC)
        tinybird_results = [
            EventTypeWithStats(
                id=event_type.id,
                created_at=event_type.created_at,
                modified_at=event_type.modified_at,
                name="test.event",
                label="test.event",
                label_property_selector=None,
                workspace_id=workspace.id,
                source=EventSource.system,
                occurrences=99,
                first_seen=now,
                last_seen=now,
            )
        ]

        mocker.patch(
            "rapidly.analytics.event_type.actions._list_with_stats_from_tinybird",
            new_callable=AsyncMock,
            return_value=(tinybird_results, 1),
        )

        results, count = await event_type_actions.list_with_stats(
            session,
            auth_subject,
            pagination=PaginationParams(page=1, limit=10),
            sorting=[(EventTypesSortProperty.last_seen, True)],
        )

        assert count == 1
        assert results[0].occurrences == 99

    @pytest.mark.auth(AuthSubjectFixture(subject="workspace"))
    async def test_shadow_mode_runs_both_and_logs(
        self,
        mocker: MockerFixture,
        session: AsyncMock,
        auth_subject: AuthPrincipal[Workspace],
        workspace: Workspace,
        save_fixture: SaveFixture,
    ) -> None:
        mocker.patch(
            "rapidly.analytics.event_type.actions.settings.TINYBIRD_EVENTS_READ", True
        )
        workspace.feature_settings = {
            "tinybird_read": True,
            "tinybird_compare": True,
        }
        await save_fixture(workspace)

        event_type = await create_event_type(
            save_fixture, workspace=workspace, name="test.event"
        )
        await create_event(save_fixture, workspace=workspace, event_type=event_type)

        now = datetime.now(UTC)
        tinybird_stats = [
            TinybirdEventTypeStats(
                name="test.event",
                source=EventSource.system,
                occurrences=10,
                first_seen=now,
                last_seen=now,
            )
        ]

        logfire_mock = mocker.patch("rapidly.analytics.event_type.actions.logfire")

        mocker.patch(
            "rapidly.integrations.tinybird.actions.TinybirdEventTypesQuery.get_event_type_stats",
            new_callable=AsyncMock,
            return_value=tinybird_stats,
        )

        results, count = await event_type_actions.list_with_stats(
            session,
            auth_subject,
            pagination=PaginationParams(page=1, limit=10),
            sorting=[(EventTypesSortProperty.last_seen, True)],
        )

        assert count == 1
        logfire_mock.span.assert_called_once()
        call_kwargs = logfire_mock.span.call_args.kwargs
        assert call_kwargs["workspace_id"] == str(workspace.id)
        assert "has_diff" in call_kwargs
