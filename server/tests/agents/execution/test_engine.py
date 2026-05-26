"""Tests for the DAG walker.

Topological order is pure-function — tested directly. The
``walk_run`` loop integrates with a real session + DB; covered in
follow-up integration tests when the DB fixture lands.
"""

from __future__ import annotations

import pytest

from rapidly.agents.execution.engine import (
    GraphValidationError,
    topological_order,
)


class TestTopologicalOrder:
    def test_single_node(self) -> None:
        g = {"nodes": [{"id": "a", "type": "echo"}], "edges": []}
        order = topological_order(g)
        assert [n["id"] for n in order] == ["a"]

    def test_linear_chain(self) -> None:
        # a → b → c
        g = {
            "nodes": [
                {"id": "a", "type": "echo"},
                {"id": "b", "type": "echo"},
                {"id": "c", "type": "echo"},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
            ],
        }
        order = topological_order(g)
        assert [n["id"] for n in order] == ["a", "b", "c"]

    def test_diamond(self) -> None:
        # a → b → d
        #  \→ c ↗
        g = {
            "nodes": [
                {"id": "a", "type": "echo"},
                {"id": "b", "type": "echo"},
                {"id": "c", "type": "echo"},
                {"id": "d", "type": "echo"},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "a", "target": "c"},
                {"source": "b", "target": "d"},
                {"source": "c", "target": "d"},
            ],
        }
        order = topological_order(g)
        # ``a`` must come first, ``d`` must come last; b and c can
        # be in either order but we tie-break by id so the test is
        # deterministic.
        ids = [n["id"] for n in order]
        assert ids[0] == "a"
        assert ids[-1] == "d"
        assert set(ids[1:3]) == {"b", "c"}
        assert ids[1] == "b"  # alphabetical tie-break

    def test_rejects_cycle(self) -> None:
        # a → b → a
        g = {
            "nodes": [
                {"id": "a", "type": "echo"},
                {"id": "b", "type": "echo"},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"},
            ],
        }
        with pytest.raises(GraphValidationError, match="cycle"):
            topological_order(g)

    def test_rejects_edge_referencing_unknown_node(self) -> None:
        g = {
            "nodes": [{"id": "a", "type": "echo"}],
            "edges": [{"source": "a", "target": "ghost"}],
        }
        with pytest.raises(GraphValidationError, match="unknown node"):
            topological_order(g)

    def test_disconnected_components_both_walked(self) -> None:
        # Two disjoint single-node graphs — both should appear.
        g = {
            "nodes": [
                {"id": "a", "type": "echo"},
                {"id": "b", "type": "echo"},
            ],
            "edges": [],
        }
        ids = [n["id"] for n in topological_order(g)]
        assert sorted(ids) == ["a", "b"]
