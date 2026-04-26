"""Tests for event type endpoints."""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient

from rapidly.core.utils import now_utc
from rapidly.identity.auth.scope import Scope
from rapidly.models import EventType, Workspace, WorkspaceMembership
from rapidly.models.event import EventSource
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_event, create_event_type

# ── List Event Types ──


@pytest.mark.asyncio
class TestListEventTypes:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get("/api/event-types/")

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get("/api/event-types/")

        assert response.status_code == 403

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_empty_list(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get("/api/event-types/")

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 0
        assert json["data"] == []

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_list_with_stats(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        event_type_1 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="test.event.1",
            label="Test Event 1",
        )
        event_type_2 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="test.event.2",
            label="Test Event 2",
        )

        base_time = now_utc()
        for i in range(5):
            await create_event(
                save_fixture,
                workspace=workspace,
                event_type=event_type_1,
                timestamp=base_time - timedelta(days=i),
            )

        for i in range(3):
            await create_event(
                save_fixture,
                workspace=workspace,
                event_type=event_type_2,
                timestamp=base_time - timedelta(days=i),
            )

        response = await client.get("/api/event-types/")

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 2

        items = json["data"]
        assert len(items) == 2

        items_by_name = {item["name"]: item for item in items}
        assert "test.event.1" in items_by_name
        assert "test.event.2" in items_by_name

        item_1 = items_by_name["test.event.1"]
        assert item_1["label"] == "Test Event 1"
        assert item_1["occurrences"] == 5
        assert "first_seen" in item_1
        assert "last_seen" in item_1

        item_2 = items_by_name["test.event.2"]
        assert item_2["label"] == "Test Event 2"
        assert item_2["occurrences"] == 3

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_filter_by_workspace(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_second: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        event_type_1 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="test.event.1",
        )
        event_type_2 = await create_event_type(
            save_fixture,
            workspace=workspace_second,
            name="test.event.2",
        )

        await create_event(save_fixture, workspace=workspace, event_type=event_type_1)
        await create_event(
            save_fixture, workspace=workspace_second, event_type=event_type_2
        )

        response = await client.get(
            "/api/event-types/", params={"workspace_id": str(workspace.id)}
        )

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["name"] == "test.event.1"

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_search_by_query(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        event_type_1 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="api.request",
            label="API Request",
        )
        event_type_2 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="user.login",
            label="User Login",
        )

        await create_event(save_fixture, workspace=workspace, event_type=event_type_1)
        await create_event(save_fixture, workspace=workspace, event_type=event_type_2)

        response = await client.get("/api/event-types/", params={"query": "API"})

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["name"] == "api.request"

        response = await client.get("/api/event-types/", params={"query": "user"})

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["name"] == "user.login"

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_sorting(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        event_type_1 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="zzz.event",
            label="ZZZ Event",
        )
        event_type_2 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="aaa.event",
            label="AAA Event",
        )

        base_time = now_utc()
        await create_event(
            save_fixture,
            workspace=workspace,
            event_type=event_type_1,
            timestamp=base_time - timedelta(hours=2),
        )
        await create_event(
            save_fixture,
            workspace=workspace,
            event_type=event_type_2,
            timestamp=base_time - timedelta(hours=1),
        )

        response = await client.get("/api/event-types/", params={"sorting": "name"})

        assert response.status_code == 200
        json = response.json()
        assert json["data"][0]["name"] == "aaa.event"
        assert json["data"][1]["name"] == "zzz.event"

        response = await client.get("/api/event-types/", params={"sorting": "-label"})

        assert response.status_code == 200
        json = response.json()
        labels = [item["label"] for item in json["data"]]
        assert labels == ["ZZZ Event", "AAA Event"]

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_pagination(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        for i in range(15):
            event_type = await create_event_type(
                save_fixture,
                workspace=workspace,
                name=f"event.{i:02d}",
            )
            await create_event(save_fixture, workspace=workspace, event_type=event_type)

        response = await client.get("/api/event-types/", params={"limit": 10})

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 15
        assert len(json["data"]) == 10

        response = await client.get(
            "/api/event-types/", params={"limit": 10, "page": 2}
        )

        assert response.status_code == 200
        json = response.json()
        assert len(json["data"]) == 5

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_filter_by_parent_id(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        from rapidly.models.event import EventSource

        event_type_1 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="root.event",
        )
        event_type_2 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="child.event",
        )

        root_event = await create_event(
            save_fixture,
            workspace=workspace,
            event_type=event_type_1,
            source=EventSource.user,
        )
        await create_event(
            save_fixture,
            workspace=workspace,
            event_type=event_type_2,
            parent_id=root_event.id,
            source=EventSource.user,
        )

        response = await client.get("/api/event-types/", params={"root_events": True})

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["name"] == "root.event"

        response = await client.get(
            "/api/event-types/", params={"parent_id": str(root_event.id)}
        )

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["name"] == "child.event"

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user", scopes={Scope.events_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.events_read}),
    )
    async def test_filter_by_source(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        event_type_1 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="user.event",
        )
        event_type_2 = await create_event_type(
            save_fixture,
            workspace=workspace,
            name="system.event",
        )

        await create_event(
            save_fixture,
            workspace=workspace,
            event_type=event_type_1,
            source=EventSource.user,
        )
        await create_event(
            save_fixture,
            workspace=workspace,
            event_type=event_type_2,
            source=EventSource.system,
        )

        response = await client.get("/api/event-types/", params={"source": "user"})

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["name"] == "user.event"

        response = await client.get("/api/event-types/", params={"source": "system"})

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["name"] == "system.event"


# ── Update Event Type ──


@pytest.mark.asyncio
class TestUpdateEventType:
    async def test_anonymous(self, client: AsyncClient, event_type: EventType) -> None:
        response = await client.patch(
            f"/api/event-types/{event_type.id}",
            json={"label": "Updated Label"},
        )

        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_member(self, client: AsyncClient, event_type: EventType) -> None:
        response = await client.patch(
            f"/api/event-types/{event_type.id}",
            json={"label": "Updated Label"},
        )

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_not_existing(self, client: AsyncClient) -> None:
        response = await client.patch(
            f"/api/event-types/{uuid.uuid4()}",
            json={"label": "Updated Label"},
        )

        assert response.status_code == 404

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_valid(
        self,
        client: AsyncClient,
        event_type: EventType,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        response = await client.patch(
            f"/api/event-types/{event_type.id}",
            json={"label": "Updated Label", "label_property_selector": "subject"},
        )

        assert response.status_code == 200
        json = response.json()
        assert json["id"] == str(event_type.id)
        assert json["label"] == "Updated Label"
        assert json["label_property_selector"] == "subject"
        assert json["name"] == event_type.name
        assert json["workspace_id"] == str(workspace.id)

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_label_not_owned_by_org(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_second: Workspace,
        save_fixture: SaveFixture,
    ) -> None:
        other_org_event_type = EventType(
            name="test.event",
            label="Original Label",
            workspace_id=workspace_second.id,
        )
        await save_fixture(other_org_event_type)

        response = await client.patch(
            f"/api/event-types/{other_org_event_type.id}",
            json={"label": "Hacked Label"},
        )

        assert response.status_code == 404

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_empty_label(
        self,
        client: AsyncClient,
        event_type: EventType,
    ) -> None:
        response = await client.patch(
            f"/api/event-types/{event_type.id}",
            json={"label": ""},
        )

        assert response.status_code == 422

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_whitespace_label(
        self,
        client: AsyncClient,
        event_type: EventType,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.patch(
            f"/api/event-types/{event_type.id}",
            json={"label": "   "},
        )

        assert response.status_code == 422

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_label_with_special_characters(
        self,
        client: AsyncClient,
        event_type: EventType,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.patch(
            f"/api/event-types/{event_type.id}",
            json={"label": "Test Label 🎉 with émojis & symbols!"},
        )

        assert response.status_code == 200
        json = response.json()
        assert json["label"] == "Test Label 🎉 with émojis & symbols!"
