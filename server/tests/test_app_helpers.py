"""Tests for the helpers in ``rapidly/app.py``.

The full ``create_app`` / ``lifespan`` factory needs a real broker +
DB and is exercised by integration tests. This file pins the
testable helpers:

- ``_generate_operation_id`` — produces ``{tag}:{name}`` for every
  route's OpenAPI ``operationId``. The TS client generator + SDK
  stubs key off this format; a regression to ``{name}`` only would
  generate ambiguous method names across modules.
- Lifecycle hook registry (``on_startup`` / ``on_shutdown``) —
  decorators that append to module-level lists and return the
  function unchanged so they can be stacked.
- API-prefix constants — the legacy `/v1` → `/api` rewrite is
  handled by ``RouteNormalizationMiddleware`` which reads these
  literals.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.app import (
    _CURRENT_API_PREFIX,
    _LEGACY_API_PREFIX,
    State,
    _generate_operation_id,
    _shutdown_hooks,
    _startup_hooks,
    on_shutdown,
    on_startup,
)


class TestGenerateOperationId:
    def test_uses_first_tag_and_name(self) -> None:
        # ``{tag}:{name}`` — the documented format. SDK codegen
        # relies on this.
        route = MagicMock()
        route.tags = ["customers"]
        route.name = "create_customer"
        assert _generate_operation_id(route) == "customers:create_customer"

    def test_falls_back_to_default_when_no_tags(self) -> None:
        # An untagged route still needs a deterministic id; the
        # fallback prefix is ``default``.
        route = MagicMock()
        route.tags = []
        route.name = "ping"
        assert _generate_operation_id(route) == "default:ping"

    def test_falls_back_to_unknown_when_name_missing(self) -> None:
        route = MagicMock()
        route.tags = ["health"]
        route.name = None
        assert _generate_operation_id(route) == "health:unknown"

    def test_uses_first_tag_when_multiple(self) -> None:
        # Pinning the "first tag" rule prevents a regression that
        # joined all tags or picked alphabetically — the SDK
        # ergonomics depend on the FIRST tag matching the module
        # name.
        route = MagicMock()
        route.tags = ["customers", "private"]
        route.name = "list"
        assert _generate_operation_id(route) == "customers:list"


class TestApiPrefixConstants:
    def test_legacy_prefix_is_regex_anchored(self) -> None:
        # ``RouteNormalizationMiddleware`` consumes this as a
        # regex; the ``^`` anchor prevents matching ``/v1`` mid-
        # path (e.g. ``/api/v1foo`` should NOT trigger).
        assert _LEGACY_API_PREFIX == r"^/v1"

    def test_current_prefix_is_api(self) -> None:
        assert _CURRENT_API_PREFIX == "/api"


class TestLifecycleHookRegistry:
    def test_on_startup_appends_and_returns_callable(self) -> None:
        async def my_hook() -> None:
            pass

        before = len(_startup_hooks)
        result = on_startup(my_hook)
        try:
            # Decorator must return the same callable (so it can
            # be stacked and remain importable under the same name).
            assert result is my_hook
            assert _startup_hooks[-1] is my_hook
            assert len(_startup_hooks) == before + 1
        finally:
            _startup_hooks.pop()

    def test_on_shutdown_appends_and_returns_callable(self) -> None:
        async def my_hook() -> None:
            pass

        before = len(_shutdown_hooks)
        result = on_shutdown(my_hook)
        try:
            assert result is my_hook
            assert _shutdown_hooks[-1] is my_hook
            assert len(_shutdown_hooks) == before + 1
        finally:
            _shutdown_hooks.pop()


class TestStateTypedDict:
    def test_state_has_documented_keys(self) -> None:
        # The ``State`` TypedDict pins the lifespan-state schema
        # that's mounted on ``request.state``. Adding/removing a
        # key without updating downstream consumers leaves them
        # with a missing attribute at request time.
        keys = State.__annotations__.keys()
        assert set(keys) == {
            "async_engine",
            "async_sessionmaker",
            "async_read_engine",
            "async_read_sessionmaker",
            "sync_engine",
            "sync_sessionmaker",
            "redis",
        }


class TestExports:
    def test_all_documented(self) -> None:
        from rapidly import app as A

        assert set(A.__all__) == {"create_app", "on_shutdown", "on_startup"}
