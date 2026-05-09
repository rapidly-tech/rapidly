"""Tests for metrics API endpoints."""

import pytest
from httpx import AsyncClient

from rapidly.core.time_queries import TimeInterval
from rapidly.identity.auth.scope import Scope
from rapidly.models import WorkspaceMembership
from tests.fixtures.auth import AuthSubjectFixture


@pytest.mark.asyncio
class TestGetMetrics:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get("/api/metrics/")

        assert response.status_code == 401

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.web_read}),
        AuthSubjectFixture(scopes={Scope.metrics_read}),
    )
    async def test_over_limits(
        self, client: AsyncClient, workspace_membership: WorkspaceMembership
    ) -> None:
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2023-01-01",
                "end_date": "2024-12-31",
                "interval": "day",
            },
        )

        assert response.status_code == 422

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.web_read}),
        AuthSubjectFixture(scopes={Scope.metrics_read}),
    )
    async def test_user_valid(
        self, client: AsyncClient, workspace_membership: WorkspaceMembership
    ) -> None:
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
            },
        )

        assert response.status_code == 200

        json = response.json()
        assert len(json["periods"]) == 12

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read})
    )
    async def test_workspace(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
            },
        )

        assert response.status_code == 200

        json = response.json()
        assert len(json["periods"]) == 12

    @pytest.mark.parametrize(
        "timezone",
        [
            "Europe/Paris",
            "America/New_York",
            "Asia/Yangon",
            "Asia/Kolkata",
        ],
    )
    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read})
    )
    async def test_timezones(self, timezone: str, client: AsyncClient) -> None:
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
                "timezone": timezone,
            },
        )

        assert response.status_code == 200

        json = response.json()
        assert len(json["periods"]) == 12


@pytest.mark.asyncio
class TestMetricsFiltering:
    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read})
    )
    async def test_invalid_metric_slugs(self, client: AsyncClient) -> None:
        """Test that invalid metric slugs return validation error."""
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
                "metrics": ["revenue", "invalid_metric", "another_invalid"],
            },
        )

        assert response.status_code == 422
        json = response.json()
        assert "metrics" in str(json)
        assert "invalid_metric" in str(json) or "another_invalid" in str(json)

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read})
    )
    async def test_valid_metrics(self, client: AsyncClient) -> None:
        """Test that valid metrics returns only requested metrics."""
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
                "metrics": ["file_share_revenue", "file_share_sessions"],
            },
        )

        assert response.status_code == 200
        json = response.json()
        assert len(json["periods"]) == 12

        # Requested metrics should have non-null definitions
        assert json["metrics"]["file_share_revenue"] is not None
        assert json["metrics"]["file_share_sessions"] is not None

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read})
    )
    async def test_single_metric(self, client: AsyncClient) -> None:
        """Test that a single metric works correctly."""
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
                "metrics": ["file_share_active_sessions"],
            },
        )

        assert response.status_code == 200
        json = response.json()
        assert json["metrics"]["file_share_active_sessions"] is not None

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read})
    )
    @pytest.mark.parametrize(
        "metric_slugs",
        [
            ["cashflow"],
            ["costs"],
            ["cumulative_costs"],
        ],
    )
    async def test_meta_metrics(
        self, metric_slugs: list[str], client: AsyncClient
    ) -> None:
        """Test that meta metrics (post-compute metrics) can be requested."""
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
                "metrics": metric_slugs,
            },
        )

        assert response.status_code == 200
        json = response.json()
        assert json["metrics"][metric_slugs[0]] is not None

    @pytest.mark.auth(
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read})
    )
    async def test_without_metrics_returns_all(self, client: AsyncClient) -> None:
        """Test that omitting metrics returns all metrics."""
        response = await client.get(
            "/api/metrics/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "month",
            },
        )

        assert response.status_code == 200
        json = response.json()

        # All metrics should be present when metrics is not specified
        assert json["metrics"]["file_share_revenue"] is not None
        assert json["metrics"]["file_share_sessions"] is not None
        assert json["metrics"]["costs"] is not None
        assert json["metrics"]["cashflow"] is not None


@pytest.mark.asyncio
class TestGetMetricsLimits:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get("/api/metrics/limits")

        assert response.status_code == 401

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.web_read}),
        AuthSubjectFixture(scopes={Scope.metrics_read}),
        AuthSubjectFixture(subject="workspace", scopes={Scope.metrics_read}),
    )
    async def test_valid(self, client: AsyncClient) -> None:
        response = await client.get("/api/metrics/limits")

        assert response.status_code == 200

        json = response.json()
        assert "min_date" in json
        intervals = json["intervals"]
        for interval in TimeInterval:
            assert interval.name in intervals
            assert intervals[interval.name]["max_days"] > 0
