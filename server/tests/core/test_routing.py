"""Tests for ``rapidly/core/routing.py``.

The routing module supplies the ``APIRoute`` subclasses the application
router relies on. Two of them carry real invariants:

- ``SchemaInclusionRoute`` hides non-public endpoints from the OpenAPI
  schema based on ``APITag``. A regression here leaks private-flow
  paths into the published schema on prod — an info-leak class of bug.
- ``TransactionalRoute`` auto-commits the ``AsyncSession`` the endpoint
  depends on, so endpoints can return ORM objects directly. A
  regression would silently drop writes for every route that relies on
  the default commit-on-success contract.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from rapidly.core.routing import (
    SchemaInclusionRoute,
    TransactionalRoute,
    get_api_router_class,
)
from rapidly.openapi import APITag


async def _noop() -> None:
    return None


class TestSchemaInclusionRoute:
    def test_private_route_is_hidden_outside_development(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Private-tagged endpoints must disappear from the OpenAPI
        # schema in prod/staging to avoid leaking internal flows.
        monkeypatch.setattr(
            "rapidly.core.routing.settings.is_development", lambda: False
        )
        route = SchemaInclusionRoute("/x", _noop, tags=[APITag.private])
        assert route.include_in_schema is False

    def test_private_route_is_visible_in_development(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Dev still sees it so engineers can browse the internal API.
        monkeypatch.setattr(
            "rapidly.core.routing.settings.is_development", lambda: True
        )
        route = SchemaInclusionRoute("/x", _noop, tags=[APITag.private])
        assert route.include_in_schema is True

    def test_public_route_is_always_visible(self) -> None:
        route = SchemaInclusionRoute("/x", _noop, tags=[APITag.public])
        assert route.include_in_schema is True

    def test_untagged_route_is_hidden(self) -> None:
        # Default-deny. A route missing a tag is NOT published — this
        # prevents an engineer who forgets to tag a new endpoint from
        # silently exposing it on the public schema.
        route = SchemaInclusionRoute("/x", _noop, tags=[])
        assert route.include_in_schema is False

    def test_explicitly_hidden_stays_hidden(self) -> None:
        # include_in_schema=False must NOT be flipped back on — the
        # tag-based override only runs when the default is True.
        route = SchemaInclusionRoute(
            "/x", _noop, tags=[APITag.public], include_in_schema=False
        )
        assert route.include_in_schema is False


@pytest.mark.asyncio
class TestTransactionalRoute:
    # ``TransactionalRoute.__init__`` goes through FastAPI's APIRoute
    # ctor which analyses endpoint signatures against Pydantic and
    # rejects ``AsyncSession`` as a field type. Since ``wrap_endpoint``
    # does not use ``self``, exercising it via an un-initialized
    # instance (``object.__new__``) lets the test pin the commit
    # contract without dragging in FastAPI's request-parsing machinery.

    def _wrap(self, endpoint: Any) -> Any:
        route = object.__new__(TransactionalRoute)
        return route.wrap_endpoint(endpoint)

    async def test_commits_session_after_successful_endpoint(self) -> None:
        # Contract: when an endpoint receives an AsyncSession, the
        # wrapper commits after the endpoint returns. Callers can
        # return ORM objects directly without a manual commit.
        session = MagicMock(spec=AsyncSession)
        session.commit = AsyncMock()

        async def endpoint(db: Any) -> str:
            return "ok"

        wrapped = self._wrap(endpoint)
        result = await wrapped(db=session)
        assert result == "ok"
        session.commit.assert_awaited_once()

    async def test_skips_commit_when_no_session_in_kwargs(self) -> None:
        async def endpoint() -> str:
            return "ok"

        wrapped = self._wrap(endpoint)
        result = await wrapped()
        assert result == "ok"

    async def test_skips_commit_when_kwarg_is_not_an_async_session(self) -> None:
        # The wrapper must only commit on AsyncSession instances — a
        # regression that committed on any object-valued kwarg would
        # crash on every endpoint that takes a plain Pydantic body.
        async def endpoint(body: Any) -> str:
            return "ok"

        wrapped = self._wrap(endpoint)
        result = await wrapped(body={"not": "a session"})
        assert result == "ok"

    async def test_commit_runs_after_endpoint_returns(self) -> None:
        # Ensures the endpoint's return value is computed BEFORE commit
        # runs — a regression that ran commit first would break the
        # return-ORM-object pattern the wrapper is documented to enable.
        order: list[str] = []

        session = MagicMock(spec=AsyncSession)

        async def commit_tracker() -> None:
            order.append("commit")

        session.commit = commit_tracker

        async def endpoint(db: Any) -> str:
            order.append("endpoint")
            return "ok"

        wrapped = self._wrap(endpoint)
        await wrapped(db=session)
        assert order == ["endpoint", "commit"]


class TestGetApiRouterClass:
    def test_returns_router_subclass_using_given_route_class(self) -> None:
        # ``get_api_router_class`` is how the app builder composes
        # routers per route-class policy. Pinning the route_class
        # wiring prevents a regression where a router accidentally
        # falls back to the stock ``APIRoute`` and loses
        # transactional / schema-inclusion behaviour.
        Custom = get_api_router_class(SchemaInclusionRoute)
        assert issubclass(Custom, APIRouter)
        router = Custom()

        @router.get("/x", tags=[APITag.public])
        def _handler() -> dict[str, Any]:
            return {}

        route = next(r for r in router.routes if isinstance(r, APIRoute))
        assert isinstance(route, SchemaInclusionRoute)

    def test_returned_routers_are_independent(self) -> None:
        A = get_api_router_class(SchemaInclusionRoute)
        B = get_api_router_class(TransactionalRoute)
        assert A is not B
