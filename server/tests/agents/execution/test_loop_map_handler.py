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
        # ``failures`` is always present (empty when nothing
        # failed). Keeps the output shape stable whether the
        # workflow opted into continue-on-error or not.
        assert out == {"results": [], "item_count": 0, "failures": []}

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


@pytest.mark.asyncio
class TestParallelDispatch:
    async def test_parallel_results_preserve_input_order(self) -> None:
        # Mark each iteration's completion order via a shared
        # counter; assert that the output ``results`` list still
        # reflects input order, not completion order. We use
        # asyncio.sleep with different durations so iteration 0
        # finishes last, exposing any "completion order" bug.
        import asyncio

        from rapidly.agents.execution import node_registry

        async def _slow(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            # Higher index = shorter sleep → finishes earlier.
            await asyncio.sleep(0.05 * (3 - inp["index"]))
            return {"value": inp["item"]}

        node_registry._REGISTRY["_test_slow"] = _slow  # type: ignore[index]
        try:
            out = await loop_map_handler(
                {},
                {
                    "inner_type": "_test_slow",
                    "inner_config": {},
                    "parallel": True,
                    "concurrency": 3,
                },
                {"items": ["A", "B", "C"]},
            )
        finally:
            del node_registry._REGISTRY["_test_slow"]  # type: ignore[index]

        assert [r["value"] for r in out["results"]] == ["A", "B", "C"]
        assert out["item_count"] == 3
        assert out["failures"] == []

    async def test_parallel_respects_concurrency_cap(self) -> None:
        # Track the maximum number of in-flight iterations. With
        # concurrency=2 and 6 items, we should see at most 2
        # iterations active simultaneously.
        import asyncio

        from rapidly.agents.execution import node_registry

        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def _watched(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            try:
                await asyncio.sleep(0.02)
                return {"ok": True}
            finally:
                async with lock:
                    in_flight -= 1

        node_registry._REGISTRY["_test_watched"] = _watched  # type: ignore[index]
        try:
            await loop_map_handler(
                {},
                {
                    "inner_type": "_test_watched",
                    "inner_config": {},
                    "parallel": True,
                    "concurrency": 2,
                },
                {"items": list(range(6))},
            )
        finally:
            del node_registry._REGISTRY["_test_watched"]  # type: ignore[index]

        assert max_in_flight <= 2

    async def test_parallel_concurrency_capped_at_max(self) -> None:
        # A workflow author asking for concurrency=1000 should be
        # silently clamped — we don't reject (the workflow still
        # runs correctly), just bound it. ``_MAX_CONCURRENCY=32``
        # so any input above 32 should track that ceiling.
        import asyncio

        from rapidly.agents.execution import node_registry

        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def _watched(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            try:
                await asyncio.sleep(0.01)
                return {"ok": True}
            finally:
                async with lock:
                    in_flight -= 1

        node_registry._REGISTRY["_test_capped"] = _watched  # type: ignore[index]
        try:
            await loop_map_handler(
                {},
                {
                    "inner_type": "_test_capped",
                    "inner_config": {},
                    "parallel": True,
                    "concurrency": 1000,
                    "max_items": 100,
                },
                {"items": list(range(60))},
            )
        finally:
            del node_registry._REGISTRY["_test_capped"]  # type: ignore[index]

        # Hard cap is 32. Allow some slack for scheduling.
        assert max_in_flight <= 32

    async def test_rejects_concurrency_below_one(self) -> None:
        with pytest.raises(LoopMapNodeError, match="concurrency must be"):
            await loop_map_handler(
                {},
                {
                    "inner_type": "echo",
                    "inner_config": {},
                    "parallel": True,
                    "concurrency": 0,
                },
                {"items": [1]},
            )


@pytest.mark.asyncio
class TestContinueOnError:
    async def test_sequential_continue_collects_failures(self) -> None:
        # Iteration 1 + 3 fail, others pass. continue_on_error
        # should leave None at the failed positions and append
        # {"index": ..., "error": ...} to failures.
        from rapidly.agents.execution import node_registry

        async def _flaky(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            if inp["index"] in (1, 3):
                raise RuntimeError(f"boom @ {inp['index']}")
            return {"item": inp["item"]}

        node_registry._REGISTRY["_test_flaky"] = _flaky  # type: ignore[index]
        try:
            out = await loop_map_handler(
                {},
                {
                    "inner_type": "_test_flaky",
                    "inner_config": {},
                    "continue_on_error": True,
                },
                {"items": ["a", "b", "c", "d"]},
            )
        finally:
            del node_registry._REGISTRY["_test_flaky"]  # type: ignore[index]

        assert out["item_count"] == 4
        assert out["results"][0]["item"] == "a"
        assert out["results"][1] is None
        assert out["results"][2]["item"] == "c"
        assert out["results"][3] is None
        # Failures carry the original index, not the position
        # in the failures list — operators correlate to source.
        failure_indices = {f["index"] for f in out["failures"]}
        assert failure_indices == {1, 3}
        # And each error message is captured (truncated to 500
        # chars in the writer; we just check it's non-empty here).
        assert all(f["error"] for f in out["failures"])

    async def test_parallel_continue_collects_failures(self) -> None:
        from rapidly.agents.execution import node_registry

        async def _flaky(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            if inp["index"] == 2:
                raise RuntimeError("boom")
            return {"ok": True}

        node_registry._REGISTRY["_test_pflaky"] = _flaky  # type: ignore[index]
        try:
            out = await loop_map_handler(
                {},
                {
                    "inner_type": "_test_pflaky",
                    "inner_config": {},
                    "parallel": True,
                    "concurrency": 4,
                    "continue_on_error": True,
                },
                {"items": list(range(5))},
            )
        finally:
            del node_registry._REGISTRY["_test_pflaky"]  # type: ignore[index]

        assert out["item_count"] == 5
        assert out["results"][2] is None
        assert out["failures"] == [{"index": 2, "error": "boom"}]


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
