"""Unit tests for the M4.3c conditional-edge engine helpers.

End-to-end ``walk_run`` coverage with conditional edges would
need to plumb through a real Workflow + WorkflowVersion + Run
which is more setup than the helper-level test pins (the
existing test_engine.py file covers walk_run with simpler
graphs). These tests fix the predicate semantics + input
selection logic that the engine's new code path relies on.
"""

from __future__ import annotations

from rapidly.agents.execution.engine import (
    _build_incoming_edges,
    _evaluate_edge_condition,
    _outgoing_edges_for,
    _select_input,
)


class TestEvaluateEdgeCondition:
    def test_unconditional_edge_is_open(self) -> None:
        # No condition at all (empty / None) → edge stays open.
        assert _evaluate_edge_condition("", {"x": 1}) is True
        assert _evaluate_edge_condition(None, {"x": 1}) is True  # type: ignore[arg-type]

    def test_bare_truthy_placeholder_open(self) -> None:
        # ``{passed}`` rendering to "True" → open.
        assert _evaluate_edge_condition("{passed}", {"passed": True}) is True

    def test_bare_falsy_placeholder_closed(self) -> None:
        assert _evaluate_edge_condition("{passed}", {"passed": False}) is False

    def test_equality_open(self) -> None:
        assert _evaluate_edge_condition("{status} == open", {"status": "open"}) is True

    def test_equality_closed(self) -> None:
        assert (
            _evaluate_edge_condition("{status} == open", {"status": "closed"}) is False
        )

    def test_inequality(self) -> None:
        assert (
            _evaluate_edge_condition("{status} != closed", {"status": "open"}) is True
        )

    def test_numeric_gt(self) -> None:
        assert _evaluate_edge_condition("{count} > 5", {"count": 10}) is True
        assert _evaluate_edge_condition("{count} > 5", {"count": 3}) is False

    def test_contains(self) -> None:
        assert (
            _evaluate_edge_condition(
                "{body} contains urgent", {"body": "this is urgent"}
            )
            is True
        )
        assert (
            _evaluate_edge_condition("{body} contains urgent", {"body": "all good"})
            is False
        )

    def test_missing_field_renders_placeholder_and_closes(self) -> None:
        # ``{missing}`` left as the literal "{missing}", so the
        # equality check against "open" is False → closed. Defensive
        # default — operators see "this edge never opens" instead
        # of mysterious passes.
        assert _evaluate_edge_condition("{missing} == open", {"x": 1}) is False

    def test_unrecognised_shape_closed(self) -> None:
        # No operator, no truthy keyword → fail closed.
        assert _evaluate_edge_condition("just some prose", {"x": 1}) is False


class TestBuildIncomingEdges:
    def test_per_target_edge_lists(self) -> None:
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "a", "target": "c"},
                {"source": "b", "target": "c"},
            ],
        }
        incoming = _build_incoming_edges(graph)
        assert [src for _idx, src in [(i, e["source"]) for i, e in incoming["b"]]] == [
            "a"
        ]
        c_sources = [e["source"] for _, e in incoming["c"]]
        assert sorted(c_sources) == ["a", "b"]

    def test_indices_unique_per_source(self) -> None:
        # Same source with two edges → distinct edge_index values.
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [
                {"source": "a", "target": "b", "condition": "{x} > 0"},
                {"source": "a", "target": "b", "condition": "{x} <= 0"},
            ],
        }
        incoming = _build_incoming_edges(graph)
        indices = [idx for idx, _e in incoming["b"]]
        assert indices == [0, 1]

    def test_isolated_node_has_no_incoming(self) -> None:
        graph = {"nodes": [{"id": "lonely"}], "edges": []}
        incoming = _build_incoming_edges(graph)
        assert incoming["lonely"] == []


class TestSelectInput:
    def _graph_with_two_predecessors(self) -> dict:
        return {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "c"},
                {"source": "b", "target": "c"},
            ],
        }

    def test_no_incoming_uses_run_input(self) -> None:
        incoming = _build_incoming_edges(self._graph_with_two_predecessors())
        out, skip = _select_input(
            node_id="a",  # source node, no incoming
            incoming=incoming,
            outputs={},
            skipped=set(),
            closed_edges=set(),
            run_input={"seed": 1},
        )
        assert out == {"seed": 1}
        assert skip is False

    def test_picks_first_open_incoming_source_output(self) -> None:
        incoming = _build_incoming_edges(self._graph_with_two_predecessors())
        out, skip = _select_input(
            node_id="c",
            incoming=incoming,
            outputs={"a": {"from_a": 1}, "b": {"from_b": 2}},
            skipped=set(),
            closed_edges=set(),
            run_input={},
        )
        # Order matches graph_json edge order — a is first.
        assert out == {"from_a": 1}
        assert skip is False

    def test_skipped_source_falls_through_to_next(self) -> None:
        incoming = _build_incoming_edges(self._graph_with_two_predecessors())
        out, skip = _select_input(
            node_id="c",
            incoming=incoming,
            outputs={"b": {"from_b": 2}},
            skipped={"a"},
            closed_edges=set(),
            run_input={},
        )
        # ``a`` skipped → use ``b``.
        assert out == {"from_b": 2}
        assert skip is False

    def test_all_sources_skipped_marks_node_skipped(self) -> None:
        incoming = _build_incoming_edges(self._graph_with_two_predecessors())
        out, skip = _select_input(
            node_id="c",
            incoming=incoming,
            outputs={},
            skipped={"a", "b"},
            closed_edges=set(),
            run_input={},
        )
        assert skip is True
        assert out == {}

    def test_closed_edge_falls_through(self) -> None:
        incoming = _build_incoming_edges(self._graph_with_two_predecessors())
        # Edge from ``a`` to ``c`` is closed; ``b`` still open.
        out, skip = _select_input(
            node_id="c",
            incoming=incoming,
            outputs={"a": {"from_a": 1}, "b": {"from_b": 2}},
            skipped=set(),
            closed_edges={("a", "c", 0)},
            run_input={},
        )
        assert out == {"from_b": 2}
        assert skip is False

    def test_all_edges_closed_marks_skipped(self) -> None:
        incoming = _build_incoming_edges(self._graph_with_two_predecessors())
        out, skip = _select_input(
            node_id="c",
            incoming=incoming,
            outputs={"a": {"x": 1}, "b": {"y": 2}},
            skipped=set(),
            closed_edges={("a", "c", 0), ("b", "c", 0)},
            run_input={},
        )
        assert skip is True
        assert out == {}


class TestOutgoingEdgesFor:
    def test_orders_match_graph_json(self) -> None:
        # The list order pairs with the edge_index assigned by
        # _build_incoming_edges (both walk per-source in graph_json
        # order). This pin guards against a future refactor that
        # might change ordering on one side without the other.
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"source": "a", "target": "b", "condition": "first"},
                {"source": "a", "target": "c", "condition": "second"},
                {"source": "b", "target": "c"},
            ],
        }
        out = _outgoing_edges_for(graph, "a")
        assert [e["target"] for e in out] == ["b", "c"]
        assert out[0]["condition"] == "first"
        assert out[1]["condition"] == "second"
