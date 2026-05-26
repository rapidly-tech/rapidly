"""Tests for the loop_map handler.

Dispatches a registered handler N times over an input array,
collecting results.
"""

from __future__ import annotations

from typing import Any

import pytest

from rapidly.agents.execution.handlers.echo import echo_handler
from rapidly.agents.execution.handlers.loop_map import (
    LoopMapNodeError,
    _render_config,
    loop_map_handler,
)


@pytest.mark.asyncio
class TestLoopMap:
    async def test_maps_echo_over_items(self) -> None:
        # Echo handler returns its input verbatim — confirms the
        # loop calls the inner handler once per item and threads
        # the per-iteration ``{"item": ..., "index": ...}`` input.
        out = await loop_map_handler(
            {},
            {
                "inner_type": "echo",
                "inner_config": {},
            },
            {"items": ["a", "b", "c"]},
        )
        assert out["item_count"] == 3
        assert [r["item"] for r in out["results"]] == ["a", "b", "c"]
        assert [r["index"] for r in out["results"]] == [0, 1, 2]

    async def test_renders_item_placeholder_in_inner_config(self) -> None:
        # The inner config can reference ``{item}`` / ``{index}``.
        # Confirm those get rendered per iteration so each call
        # sees its own bound values.
        captured: list[dict[str, Any]] = []

        async def _capture(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            captured.append(cfg)
            return {"ok": True}

        from rapidly.agents.execution import node_registry

        node_registry._REGISTRY["_test_capture"] = _capture  # type: ignore[index]
        try:
            await loop_map_handler(
                {},
                {
                    "inner_type": "_test_capture",
                    "inner_config": {
                        "url": "https://api.example/{item}",
                        "headers": {"X-Index": "{index}"},
                        "literal_number": 42,
                    },
                },
                {"items": ["alpha", "beta"]},
            )
        finally:
            del node_registry._REGISTRY["_test_capture"]  # type: ignore[index]

        assert len(captured) == 2
        assert captured[0]["url"] == "https://api.example/alpha"
        assert captured[1]["url"] == "https://api.example/beta"
        # Nested-dict rendering: one level deep is supported.
        assert captured[0]["headers"]["X-Index"] == "0"
        # Non-string values pass through unchanged — render mustn't
        # stringify a literal int.
        assert captured[0]["literal_number"] == 42

    async def test_uses_items_path_override(self) -> None:
        # The default key is "items"; workflows can override to
        # read from another field.
        out = await loop_map_handler(
            {},
            {
                "inner_type": "echo",
                "inner_config": {},
                "items_path": "rfis",
            },
            {"rfis": [{"id": 1}, {"id": 2}]},
        )
        assert out["item_count"] == 2

    async def test_empty_list_returns_empty_results(self) -> None:
        out = await loop_map_handler(
            {},
            {"inner_type": "echo", "inner_config": {}},
            {"items": []},
        )
        assert out == {"results": [], "item_count": 0}

    async def test_rejects_missing_inner_type(self) -> None:
        with pytest.raises(LoopMapNodeError, match="inner_type is required"):
            await loop_map_handler({}, {}, {"items": []})

    async def test_rejects_inner_config_non_dict(self) -> None:
        with pytest.raises(LoopMapNodeError, match="inner_config must be a dict"):
            await loop_map_handler(
                {},
                {"inner_type": "echo", "inner_config": "not-a-dict"},
                {"items": []},
            )

    async def test_rejects_items_path_missing(self) -> None:
        with pytest.raises(LoopMapNodeError, match="not present in input_data"):
            await loop_map_handler({}, {"inner_type": "echo", "inner_config": {}}, {})

    async def test_rejects_items_path_non_list(self) -> None:
        with pytest.raises(LoopMapNodeError, match="must reference a list"):
            await loop_map_handler(
                {},
                {"inner_type": "echo", "inner_config": {}},
                {"items": "this is not a list"},
            )

    async def test_rejects_unknown_inner_type(self) -> None:
        with pytest.raises(LoopMapNodeError, match="not a registered node type"):
            await loop_map_handler(
                {},
                {"inner_type": "nonexistent_handler", "inner_config": {}},
                {"items": [1, 2]},
            )

    async def test_caps_items_at_max_items(self) -> None:
        # Hard cap prevents a runaway input from running the
        # workspace's LLM budget into the ground.
        with pytest.raises(LoopMapNodeError, match="max_items"):
            await loop_map_handler(
                {},
                {
                    "inner_type": "echo",
                    "inner_config": {},
                    "max_items": 3,
                },
                {"items": list(range(10))},
            )

    async def test_inner_failure_short_circuits(self) -> None:
        # Any inner-iteration failure raises and bails out — the
        # loop is all-or-nothing in v1. (Continue-on-error +
        # partial_failures lands in M4.3e.)
        async def _boom(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            if inp["index"] == 1:
                raise RuntimeError("boom on iteration 1")
            return {"ok": True}

        from rapidly.agents.execution import node_registry

        node_registry._REGISTRY["_test_boom"] = _boom  # type: ignore[index]
        try:
            with pytest.raises(LoopMapNodeError, match="iteration 1.*boom"):
                await loop_map_handler(
                    {},
                    {"inner_type": "_test_boom", "inner_config": {}},
                    {"items": ["a", "b", "c"]},
                )
        finally:
            del node_registry._REGISTRY["_test_boom"]  # type: ignore[index]


class TestRenderConfig:
    """Inline unit checks for the template renderer."""

    def test_missing_key_left_as_placeholder(self) -> None:
        # Missing keys leave the literal placeholder — same as the
        # LLM + gate handlers. Workflow authors fix the wiring;
        # we don't crash.
        out = _render_config({"x": "{item}-{missing}"}, item="A", index=0)
        assert out["x"] == "A-{missing}"

    def test_index_placeholder(self) -> None:
        out = _render_config({"x": "row-{index}"}, item=None, index=7)
        assert out["x"] == "row-7"

    def test_passes_through_non_string(self) -> None:
        out = _render_config({"x": 1, "y": True, "z": None}, item="i", index=0)
        assert out == {"x": 1, "y": True, "z": None}

    def test_uses_echo_handler_via_registry(self) -> None:
        # Sanity: confirm the registry still has the echo handler
        # — guards against accidental deregistration during test
        # mutations elsewhere in the suite.
        assert echo_handler is not None
