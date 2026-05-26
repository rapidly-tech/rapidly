"""Tests for the node-handler registry."""

from __future__ import annotations

import pytest

from rapidly.agents.execution.node_registry import get_handler, registered_types


class TestRegistry:
    def test_echo_handler_registered(self) -> None:
        # The echo handler must be registered out of the box — it's
        # the v1 way to exercise the engine end-to-end.
        assert get_handler("echo") is not None

    def test_unknown_type_returns_none(self) -> None:
        assert get_handler("definitely-not-a-node-type") is None

    def test_registered_types_sorted(self) -> None:
        types = registered_types()
        assert types == sorted(types)
        assert "echo" in types


@pytest.mark.asyncio
class TestEchoHandler:
    async def test_returns_input_verbatim(self) -> None:
        handler = get_handler("echo")
        assert handler is not None
        out = await handler({}, {}, {"x": 1, "y": "hi"})
        assert out == {"x": 1, "y": "hi"}

    async def test_returns_a_copy_not_a_reference(self) -> None:
        handler = get_handler("echo")
        assert handler is not None
        input_data = {"x": 1}
        out = await handler({}, {}, input_data)
        # Mutating one shouldn't affect the other.
        out["x"] = 999
        assert input_data["x"] == 1
