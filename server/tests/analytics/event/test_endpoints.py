"""Tests for event endpoints."""

from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from rapidly.core.utils import now_utc
from rapidly.models import Workspace, WorkspaceMembership
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_event

# ── List Events ──


@pytest.mark.asyncio
class TestListEvents:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get("/api/events/")

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get("/api/events/")

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_children_sorting(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """Test that children are sorted according to sorting parameter."""
        base_time = now_utc()

        root_event1 = await create_event(
            save_fixture,
            workspace=workspace,
            name="root1",
            timestamp=base_time - timedelta(hours=10),
        )

        root_event2 = await create_event(
            save_fixture,
            workspace=workspace,
            name="root2",
            timestamp=base_time - timedelta(hours=5),
        )

        child1 = await create_event(
            save_fixture,
            workspace=workspace,
            name="child1",
            parent_id=root_event1.id,
            timestamp=base_time - timedelta(hours=3),
        )

        child2 = await create_event(
            save_fixture,
            workspace=workspace,
            name="child2",
            parent_id=root_event1.id,
            timestamp=base_time - timedelta(hours=1),
        )

        child3 = await create_event(
            save_fixture,
            workspace=workspace,
            name="child3",
            parent_id=root_event1.id,
            timestamp=base_time - timedelta(hours=2),
        )

        # Test descending sort (newest first) - no depth returns all events
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "sorting": "-timestamp",
            },
        )

        assert response.status_code == 200
        json = response.json()

        items = json["data"]
        assert len(items) == 5

        # All events should be sorted newest to oldest
        assert items[0]["id"] == str(child2.id)  # 1 hours ago
        assert items[1]["id"] == str(child3.id)  # 2 hours ago
        assert items[2]["id"] == str(child1.id)  # 3 hours ago
        assert items[3]["id"] == str(root_event2.id)  # 5 hours ago
        assert items[4]["id"] == str(root_event1.id)  # 10 hours ago
        assert items[4]["child_count"] == 3

        # Query children with descending sort (parent_id excludes the parent itself)
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "parent_id": str(root_event1.id),
                "sorting": "-timestamp",
                "depth": "1",
            },
        )

        assert response.status_code == 200
        json = response.json()
        items = json["data"]
        assert len(items) == 3  # only children, not parent
        assert items[0]["id"] == str(child2.id)  # 1 hour ago
        assert items[1]["id"] == str(child3.id)  # 2 hours ago
        assert items[2]["id"] == str(child1.id)  # 3 hours ago

        # Test ascending sort (oldest first) - no depth returns all events
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "sorting": "timestamp",
            },
        )

        assert response.status_code == 200
        json = response.json()

        items = json["data"]
        assert len(items) == 5

        # All events should be sorted oldest to newest
        assert items[0]["id"] == str(root_event1.id)  # 10 hours ago
        assert items[1]["id"] == str(root_event2.id)  # 5 hours ago
        assert items[2]["id"] == str(child1.id)  # 3 hours ago
        assert items[3]["id"] == str(child3.id)  # 2 hours ago
        assert items[4]["id"] == str(child2.id)  # 1 hours ago

        # Query children with ascending sort (parent_id excludes the parent itself)
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "parent_id": str(root_event1.id),
                "sorting": "timestamp",
                "depth": "1",
            },
        )

        assert response.status_code == 200
        json = response.json()
        items = json["data"]
        assert len(items) == 3  # only children, not parent
        assert items[0]["id"] == str(child1.id)  # 3 hours ago
        assert items[1]["id"] == str(child3.id)  # 2 hours ago
        assert items[2]["id"] == str(child2.id)  # 1 hour ago

    @pytest.mark.auth
    async def test_depth_filtering(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """Test that depth parameter correctly filters events by hierarchy level."""
        base_time = now_utc()

        root_event1 = await create_event(
            save_fixture,
            workspace=workspace,
            name="root1",
            timestamp=base_time - timedelta(hours=10),
        )

        root_event2 = await create_event(
            save_fixture,
            workspace=workspace,
            name="root2",
            timestamp=base_time - timedelta(hours=5),
        )

        child1 = await create_event(
            save_fixture,
            workspace=workspace,
            name="child1",
            parent_id=root_event1.id,
            timestamp=base_time - timedelta(hours=3),
        )

        child2 = await create_event(
            save_fixture,
            workspace=workspace,
            name="child2",
            parent_id=root_event1.id,
            timestamp=base_time - timedelta(hours=1),
        )

        child3 = await create_event(
            save_fixture,
            workspace=workspace,
            name="child3",
            parent_id=root_event1.id,
            timestamp=base_time - timedelta(hours=2),
        )

        # Test descending sort (newest first) - depth=0 returns only root events
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "sorting": "-timestamp",
                "depth": "0",
            },
        )

        assert response.status_code == 200
        json = response.json()

        items = json["data"]
        assert len(items) == 2

        # Root events should be sorted newest to oldest
        assert items[0]["id"] == str(root_event2.id)  # 5 hours ago
        assert items[1]["id"] == str(root_event1.id)  # 10 hours ago
        assert items[1]["child_count"] == 3

        # Query children with descending sort (parent_id excludes the parent itself)
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "parent_id": str(root_event1.id),
                "sorting": "-timestamp",
                "depth": "1",
            },
        )

        assert response.status_code == 200
        json = response.json()
        items = json["data"]
        assert len(items) == 3  # only children, not parent
        assert items[0]["id"] == str(child2.id)  # 1 hour ago
        assert items[1]["id"] == str(child3.id)  # 2 hours ago
        assert items[2]["id"] == str(child1.id)  # 3 hours ago

        # Test ascending sort (oldest first) - depth=0 returns only root events
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "sorting": "timestamp",
                "depth": "0",
            },
        )

        assert response.status_code == 200
        json = response.json()

        items = json["data"]
        assert len(items) == 2

        # Root events should be sorted oldest to newest
        assert items[0]["id"] == str(root_event1.id)  # 10 hours ago
        assert items[1]["id"] == str(root_event2.id)  # 5 hours ago

        # Query children with ascending sort (parent_id excludes the parent itself)
        response = await client.get(
            "/api/events/",
            params={
                "workspace_id": str(workspace.id),
                "parent_id": str(root_event1.id),
                "sorting": "timestamp",
                "depth": "1",
            },
        )

        assert response.status_code == 200
        json = response.json()
        items = json["data"]
        assert len(items) == 3  # only children, not parent
        assert items[0]["id"] == str(child1.id)  # 3 hours ago
        assert items[1]["id"] == str(child3.id)  # 2 hours ago
        assert items[2]["id"] == str(child2.id)  # 1 hour ago


# ── Ingest Events ──


@pytest.mark.asyncio
class TestIngest:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.post("/api/events/ingest", json={"events": []})

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(subject="workspace"))
    @pytest.mark.parametrize(
        "events",
        [
            [
                {
                    "name": "event1",
                    "external_customer_id": "CUSTOMER_ID",
                    "metadata": {"usage": 127.32},
                }
            ]
        ],
    )
    async def test_valid(
        self, events: list[dict[str, Any]], client: AsyncClient
    ) -> None:
        response = await client.post("/api/events/ingest", json={"events": events})

        assert response.status_code == 201
        json = response.json()
        assert json == {"inserted": len(events), "duplicates": 0}


# ── Aggregate Fields SQL Injection Validation ──

SQLI_PAYLOADS = [
    pytest.param("' OR '1'='1", id="string-breakout"),
    pytest.param("_cost.amount' --", id="comment-injection"),
    pytest.param("x}' AS NUMERIC)); DROP TABLE events --", id="drop-table"),
    pytest.param(
        'x}\' AS NUMERIC) + (SELECT count(*) FROM "user"))--',
        id="subquery-exfil",
    ),
    pytest.param(
        "x}', (SELECT to_jsonb(email) FROM users LIMIT 1), true)--",
        id="jsonb-set-exfil",
    ),
    pytest.param(
        "}||(SELECT CASE WHEN (SELECT 1)=1 THEN pg_sleep(3) END)--",
        id="sleep-injection",
    ),
]


@pytest.mark.asyncio
class TestAggregateFieldsValidation:
    """Malicious aggregate_fields values must be rejected with 422 before
    reaching any SQL execution path."""

    @pytest.mark.auth
    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    async def test_list(
        self,
        payload: str,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get(
            "/api/events/",
            params={"aggregate_fields": payload},
        )

        assert response.status_code == 422

    @pytest.mark.auth
    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    async def test_get(
        self,
        payload: str,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get(
            f"/api/events/{uuid4()}",
            params={"aggregate_fields": payload},
        )

        assert response.status_code == 422

    @pytest.mark.auth
    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    async def test_statistics_timeseries(
        self,
        payload: str,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        today = date.today()
        response = await client.get(
            "/api/events/statistics/timeseries",
            params={
                "aggregate_fields": payload,
                "start_date": str(today - timedelta(days=7)),
                "end_date": str(today),
                "interval": "day",
            },
        )

        assert response.status_code == 422
