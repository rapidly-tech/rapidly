"""Tests for the gate handler and its engine-skip integration.

Two test classes:
    1. ``TestGateHandler`` — handler-level: operator dispatch,
       template rendering, error shape.
    2. ``TestSkipPropagation`` — engine-level: the adjacency
       helpers that walk descendants from a closed gate. The
       full walk_run integration would need a real Run + Version
       + Workflow row; the helper test pins the propagation rule
       so the engine's per-node loop has correct skip data.
"""

from __future__ import annotations

import pytest

from rapidly.agents.execution.engine import _build_adjacency, _descendants
from rapidly.agents.execution.handlers.gate import (
    GateFailedError,
    GateNodeError,
    gate_handler,
)


@pytest.mark.asyncio
class TestGateHandler:
    async def test_equality_pass(self) -> None:
        out = await gate_handler(
            {},
            {"left": "{status}", "operator": "==", "right": "open"},
            {"status": "open"},
        )
        assert out == {"passed": True, "left": "open", "right": "open"}

    async def test_equality_closes_gate(self) -> None:
        with pytest.raises(GateFailedError) as exc_info:
            await gate_handler(
                {},
                {"left": "{status}", "operator": "==", "right": "open"},
                {"status": "closed"},
            )
        assert exc_info.value.left == "closed"
        assert exc_info.value.right == "open"
        assert exc_info.value.operator == "=="

    async def test_inequality(self) -> None:
        out = await gate_handler(
            {},
            {"left": "{status}", "operator": "!=", "right": "closed"},
            {"status": "open"},
        )
        assert out["passed"] is True

    async def test_numeric_gt(self) -> None:
        out = await gate_handler(
            {},
            {"left": "{count}", "operator": ">", "right": "5"},
            {"count": 10},
        )
        assert out["passed"] is True

    async def test_numeric_lt_closes(self) -> None:
        with pytest.raises(GateFailedError):
            await gate_handler(
                {},
                {"left": "{count}", "operator": "<", "right": "5"},
                {"count": 100},
            )

    async def test_numeric_with_uncastable_value_raises_config_error(self) -> None:
        # Distinct from GateFailedError — bad config, not a
        # closed gate. The engine treats config errors as
        # workflow failures.
        with pytest.raises(GateNodeError, match="needs castable values"):
            await gate_handler(
                {},
                {"left": "{name}", "operator": ">", "right": "5"},
                {"name": "alice"},
            )

    async def test_contains_substring(self) -> None:
        out = await gate_handler(
            {},
            {
                "left": "{body}",
                "operator": "contains",
                "right": "urgent",
            },
            {"body": "this is urgent please"},
        )
        assert out["passed"] is True

    async def test_in_against_literal_list(self) -> None:
        out = await gate_handler(
            {},
            {
                "left": "{priority}",
                "operator": "in",
                "right": ["high", "urgent", "critical"],
            },
            {"priority": "high"},
        )
        assert out["passed"] is True

    async def test_not_in_closes_when_present(self) -> None:
        with pytest.raises(GateFailedError):
            await gate_handler(
                {},
                {
                    "left": "{priority}",
                    "operator": "not in",
                    "right": ["high", "urgent"],
                },
                {"priority": "high"},
            )

    async def test_unknown_operator_raises_config_error(self) -> None:
        with pytest.raises(GateNodeError, match="unknown operator"):
            await gate_handler(
                {},
                {"left": "{x}", "operator": "approximately", "right": "1"},
                {"x": "1"},
            )

    async def test_missing_operator_raises_config_error(self) -> None:
        with pytest.raises(GateNodeError, match="operator is required"):
            await gate_handler({}, {"left": "{x}", "right": "1"}, {"x": "1"})

    async def test_missing_left_raises_config_error(self) -> None:
        with pytest.raises(GateNodeError, match="left is required"):
            await gate_handler({}, {"operator": "==", "right": "1"}, {})


class TestAdjacencyAndDescendants:
    """Pin the graph-walk helpers the engine uses for skip
    propagation. The engine's per-node loop calls these once per
    run to know which subsequent nodes to mark ``skipped`` when a
    gate closes.
    """

    def test_linear_graph(self) -> None:
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
            ],
        }
        adj = _build_adjacency(graph)
        assert _descendants("a", adj) == {"b", "c"}
        assert _descendants("b", adj) == {"c"}
        assert _descendants("c", adj) == set()

    def test_diamond_graph(self) -> None:
        # a → b → d
        # a → c → d
        graph = {
            "nodes": [{"id": x} for x in ("a", "b", "c", "d")],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "a", "target": "c"},
                {"source": "b", "target": "d"},
                {"source": "c", "target": "d"},
            ],
        }
        adj = _build_adjacency(graph)
        # A closed gate at ``a`` skips every other node.
        assert _descendants("a", adj) == {"b", "c", "d"}
        # A closed gate at one branch arm only skips that arm's
        # subtree; ``d`` will still have a live edge from the
        # other arm. The engine's current scope is "skip all
        # descendants" — full edge-quorum semantics (only skip
        # ``d`` if BOTH arms close) ships in M4.3c.
        assert _descendants("b", adj) == {"d"}

    def test_isolated_node_has_no_descendants(self) -> None:
        graph = {"nodes": [{"id": "lonely"}], "edges": []}
        adj = _build_adjacency(graph)
        assert _descendants("lonely", adj) == set()

    def test_unknown_source_returns_empty(self) -> None:
        # Defensive: a malformed edge that references an unknown
        # node shouldn't crash the adjacency build.
        graph = {
            "nodes": [{"id": "a"}],
            "edges": [{"source": "ghost", "target": "a"}],
        }
        adj = _build_adjacency(graph)
        # Existing nodes still get their adjacency slot.
        assert _descendants("a", adj) == set()
        # The malformed edge is dropped (no "ghost" key).
        assert "ghost" not in adj
