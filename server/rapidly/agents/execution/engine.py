"""DAG walker — the heart of the agent runtime.

For v1 the engine implements **sequential topological execution**:

- Validate the graph (no cycles, no orphans) before walking.
- Use Kahn's algorithm to produce a deterministic topological
  order.
- For each node in order:
    * check the Run's status; bail if it's been cancelled
    * create a NodeRun row in ``running``
    * dispatch to the per-type handler from ``node_registry``
    * write back ``succeeded`` (with output_data) or ``failed``
      (with error_message)
    * cache the output for downstream nodes
- After the last node: write the Run as ``succeeded`` (or ``failed``
  if any node failed).

v2 splits will add parallel branches (asyncio.gather across
independent paths), loop / branch / sub-workflow node semantics,
and human-in-the-loop pausing. The shape here lets the v1 echo
node prove the spine works.

The engine does NOT own the Dramatiq actor lifecycle — the actor
(``workers.execute_run``) is the only caller and handles the
session + retry semantics. The engine itself is a pure(ish)
coroutine that takes a session + run_id and walks.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from rapidly.agents.execution.handlers.gate import GateFailedError
from rapidly.agents.execution.node_registry import get_handler
from rapidly.agents.execution.state import (
    can_transition_node_run,
    can_transition_run,
    is_run_terminal,
)
from rapidly.core.utils import now_utc
from rapidly.models import (
    NodeRun,
    NodeRunStatus,
    Run,
    RunStatus,
    Workflow,
    WorkflowVersion,
)

_log = structlog.get_logger(__name__)


class GraphValidationError(Exception):
    """Raised when a graph_json can't be walked safely."""


def topological_order(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Return graph['nodes'] in topological order. Raises
    ``GraphValidationError`` on cycle / orphan."""
    nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in graph["nodes"]}
    incoming: dict[str, set[str]] = {nid: set() for nid in nodes_by_id}
    outgoing: dict[str, set[str]] = {nid: set() for nid in nodes_by_id}
    for edge in graph["edges"]:
        src, dst = edge["source"], edge["target"]
        if src not in nodes_by_id or dst not in nodes_by_id:
            raise GraphValidationError(f"edge {edge!r} references unknown node")
        outgoing[src].add(dst)
        incoming[dst].add(src)

    # Kahn's algorithm. Process nodes with no remaining incoming
    # edges; tie-break by id for determinism so the same graph
    # produces the same node-execution order across runs.
    no_incoming = sorted((nid for nid, preds in incoming.items() if not preds))
    order: list[dict[str, Any]] = []
    while no_incoming:
        nid = no_incoming.pop(0)
        order.append(nodes_by_id[nid])
        for downstream in sorted(outgoing[nid]):
            incoming[downstream].discard(nid)
            if not incoming[downstream]:
                # Insertion sorted so tie-breaks stay deterministic.
                _insort(no_incoming, downstream)

    if len(order) != len(nodes_by_id):
        unreached = sorted(set(nodes_by_id) - {n["id"] for n in order})
        raise GraphValidationError(f"graph has a cycle; unreached nodes: {unreached!r}")

    return order


def _insort(xs: list[str], v: str) -> None:
    # Tiny binary insort. ``bisect`` would work too; this keeps the
    # walk module self-contained.
    lo, hi = 0, len(xs)
    while lo < hi:
        mid = (lo + hi) // 2
        if xs[mid] < v:
            lo = mid + 1
        else:
            hi = mid
    xs.insert(lo, v)


async def walk_run(session: Any, run_id: UUID) -> None:
    """Execute the run identified by ``run_id``.

    The session is passed in so the actor can wrap retry semantics
    around it. The engine doesn't open or close sessions on its
    own.
    """
    run = await _load_run(session, run_id)
    if run is None:
        _log.warning("agents.execute_run.missing", run_id=str(run_id))
        return
    if is_run_terminal(run.status):
        _log.info(
            "agents.execute_run.terminal_skip",
            run_id=str(run_id),
            status=run.status,
        )
        return

    version = await _load_version(session, run.workflow_version_id)
    if version is None:
        await _fail_run(session, run, "WorkflowVersion not found")
        return

    workspace_id = await _load_workspace_id(session, version.workflow_id)
    if workspace_id is None:
        # The version references a workflow that no longer
        # exists. Should be unreachable in steady state — the
        # workflow_id FK forbids it — but a partial delete
        # would land here, and we'd rather fail the run cleanly
        # than have the handlers crash on a None ctx field.
        await _fail_run(session, run, "Workflow not found for version")
        return

    try:
        order = topological_order(version.graph_json)
    except GraphValidationError as exc:
        await _fail_run(session, run, str(exc))
        return

    # Transition pending → running.
    if not can_transition_run(run.status, RunStatus.running):
        _log.info(
            "agents.execute_run.illegal_transition",
            run_id=str(run_id),
            from_=run.status,
        )
        return
    run.status = RunStatus.running
    run.started_at = now_utc()
    await session.flush()

    outputs: dict[str, dict[str, Any]] = {}
    # workspace_id is the tenancy boundary every handler needs.
    # Threading it here means individual handlers don't re-query
    # the chain (run → version → workflow → workspace) and the
    # M4.7b credential resolver can look up keys by workspace.
    ctx: dict[str, Any] = {
        "run_id": run.id,
        "session": session,
        "workspace_id": workspace_id,
    }

    # Adjacency map for gate-skip propagation. Built once from
    # the edge list so the descendant walk doesn't re-scan
    # every loop iteration.
    adjacency = _build_adjacency(version.graph_json)
    incoming = _build_incoming_edges(version.graph_json)
    skipped: set[str] = set()
    # Edges deactivated by their per-edge ``condition`` — keyed
    # by (source_id, target_id, edge_index). The engine consults
    # this when picking each node's input so a closed conditional
    # edge can't propagate data to its target.
    closed_edges: set[tuple[str, str, int]] = set()
    # Track the most recently produced output so the run's final
    # ``output_data`` reflects the last successful node (the
    # workflow's "result"). Multi-output aggregation is v2.
    last_output: dict[str, Any] = dict(run.input_data)

    for node in order:
        # Cancellation check between nodes. The cancel endpoint
        # writes the status; we re-read here. M4.x will add a redis
        # pubsub signal for instant pickup.
        latest = await _load_run(session, run_id)
        if latest is None or latest.status == RunStatus.cancelled:
            return

        # Resolve this node's input from its incoming edges.
        # Nodes with no incoming edges get the run's input_data
        # (workflow entry-points). Nodes whose every incoming
        # edge originates from a skipped source OR is closed by
        # a condition get marked skipped — cascades naturally.
        node_input, is_skipped = _select_input(
            node_id=node["id"],
            incoming=incoming,
            outputs=outputs,
            skipped=skipped,
            closed_edges=closed_edges,
            run_input=dict(run.input_data),
        )

        if is_skipped or node["id"] in skipped:
            # Mark + emit a NodeRun row so the API surface can
            # render "this node was skipped" rather than silently
            # omitting it.
            skipped.add(node["id"])
            skipped_run = NodeRun(
                run_id=run.id,
                node_id=node["id"],
                node_type=node["type"],
                status=NodeRunStatus.skipped,
                started_at=now_utc(),
                completed_at=now_utc(),
                input_data=node_input,
            )
            session.add(skipped_run)
            await session.flush()
            continue

        node_run = NodeRun(
            run_id=run.id,
            node_id=node["id"],
            node_type=node["type"],
            status=NodeRunStatus.running,
            started_at=now_utc(),
            input_data=node_input,
        )
        session.add(node_run)
        await session.flush()

        handler = get_handler(node["type"])
        if handler is None:
            await _fail_node_run(
                session, node_run, f"no handler for node_type {node['type']!r}"
            )
            await _fail_run(session, run, f"unknown node type {node['type']!r}")
            return

        # node_run_id is per-iteration ctx — handlers that emit
        # ancillary records (LlmUsage, future cost-tracking
        # tables) tag them with this id so a run's per-step
        # cost split is queryable. Reset _resolved_credential_id
        # too so a credential-store hit from a *previous* node
        # doesn't bleed into the next one's usage attribution.
        ctx["node_run_id"] = node_run.id
        ctx.pop("_resolved_credential_id", None)

        try:
            output = await handler(ctx, dict(node.get("config", {})), dict(node_input))
        except GateFailedError as gate_exc:
            # Deliberate flow-control exit — not a failure. Mark
            # this gate node succeeded with the failed condition
            # in its output_data, then mark every descendant as
            # skipped so the subsequent iteration short-circuits
            # them.
            node_run.status = NodeRunStatus.succeeded
            node_run.completed_at = now_utc()
            node_run.output_data = {
                "passed": False,
                "left": gate_exc.left,
                "right": gate_exc.right,
                "operator": gate_exc.operator,
            }
            await session.flush()
            outputs[node["id"]] = node_run.output_data
            # Downstream propagation. ``_descendants`` walks every
            # reachable node via the adjacency map.
            skipped |= _descendants(node["id"], adjacency)
            continue
        except Exception as exc:
            await _fail_node_run(session, node_run, str(exc)[:1000])
            await _fail_run(session, run, str(exc)[:1000])
            _log.exception("agents.execute_run.node_failed", node_id=node["id"])
            return

        if not can_transition_node_run(node_run.status, NodeRunStatus.succeeded):
            await _fail_node_run(session, node_run, "illegal node_run transition")
            await _fail_run(session, run, "engine state-machine violation")
            return
        node_run.status = NodeRunStatus.succeeded
        node_run.completed_at = now_utc()
        node_run.output_data = output
        await session.flush()
        outputs[node["id"]] = output
        last_output = output

        # Evaluate outgoing edges' per-edge conditions against
        # the node's output. Conditional edges that fail close;
        # their targets can't pull input through that edge.
        # Unconditional edges (no ``condition`` field) stay open.
        for edge_index, edge in enumerate(
            _outgoing_edges_for(version.graph_json, node["id"])
        ):
            cond = edge.get("condition")
            if cond is None:
                continue
            if not _evaluate_edge_condition(cond, output):
                closed_edges.add((node["id"], edge["target"], edge_index))

    # All nodes succeeded — write the Run as succeeded with the
    # last node's output as the run's output_data. Multi-output
    # aggregation is a v2 concern.
    if not can_transition_run(run.status, RunStatus.succeeded):
        return
    run.status = RunStatus.succeeded
    run.completed_at = now_utc()
    run.output_data = last_output
    await session.flush()


def _build_incoming_edges(
    graph: dict[str, Any],
) -> dict[str, list[tuple[int, dict[str, Any]]]]:
    """Map ``target_id`` → list of ``(edge_index, edge_dict)``.

    The edge_index pairs with the source's outgoing-edge order so
    the engine can key ``closed_edges`` uniquely even when two
    edges share the same (source, target) pair (rare but legal:
    a workflow with both a "true" branch and a "false" branch
    pointing back to the same merge node).
    """
    out: dict[str, list[tuple[int, dict[str, Any]]]] = {
        n["id"]: [] for n in graph.get("nodes", [])
    }
    # Re-number edges per source so the same edge_index keys
    # both outgoing-side closed_edges entries + incoming-side
    # lookups.
    per_source_counter: dict[str, int] = {}
    for edge in graph.get("edges", []):
        src = edge.get("source")
        dst = edge.get("target")
        if dst not in out or src is None:
            continue
        idx = per_source_counter.get(src, 0)
        per_source_counter[src] = idx + 1
        out[dst].append((idx, edge))
    return out


def _outgoing_edges_for(graph: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
    """All edges originating at ``source_id``, in graph_json order.

    The list-index in the returned list pairs with the
    edge_index assigned by ``_build_incoming_edges`` (both walk
    edges in graph_json order, incrementing per source).
    """
    return [e for e in graph.get("edges", []) if e.get("source") == source_id]


def _select_input(
    *,
    node_id: str,
    incoming: dict[str, list[tuple[int, dict[str, Any]]]],
    outputs: dict[str, dict[str, Any]],
    skipped: set[str],
    closed_edges: set[tuple[str, str, int]],
    run_input: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Pick a node's input from its incoming edges.

    Returns ``(input, is_skipped)``. The bool is True when every
    incoming edge has been closed or comes from a skipped source
    — the engine then emits a ``skipped`` NodeRun and moves on.

    Workflow entry-points (no incoming edges) get ``run_input``.
    Nodes with multiple open incoming edges currently take the
    first one's source output. Multi-input merge (concat /
    structured join) is v2 — workflow authors today can wire an
    explicit merge node if they need it.
    """
    edges = incoming.get(node_id, [])
    if not edges:
        return run_input, False

    for edge_index, edge in edges:
        src = edge.get("source")
        if src in skipped:
            continue
        if (src, node_id, edge_index) in closed_edges:
            continue
        if src not in outputs:
            # Source hasn't run yet — possible if it failed
            # earlier (we'd have already aborted) or if the
            # topological walk ran out of order (engine bug).
            # Either way, this edge can't supply input.
            continue
        return dict(outputs[src]), False
    return {}, True


def _evaluate_edge_condition(condition: str, source_output: dict[str, Any]) -> bool:
    """Evaluate an edge ``condition`` against the source's output.

    The condition uses the same templating + operator surface as
    the ``gate`` handler (M4.3b): a string of the form
    ``"{field} <op> <value>"`` where ``field`` is a key from
    the source's output and ``op`` is one of ``==``, ``!=``,
    ``<``, ``<=``, ``>``, ``>=``, ``contains``. Anything else
    is treated as a Python truthiness of the rendered string —
    rarely useful, but lets a workflow author write
    ``"{passed}"`` for a bare bool check.

    Failure modes default to closed (the safer side): any
    parsing or rendering error → return False so the edge
    closes rather than spuriously opening through a malformed
    config.
    """
    if not condition or not isinstance(condition, str):
        return True

    # Render placeholders against source_output (same SafeDict
    # pattern the gate + loop_map renderers use).
    class _SafeDict(dict):  # type: ignore[type-arg]
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    try:
        rendered = condition.format_map(_SafeDict(source_output))
    except (KeyError, ValueError):
        return False

    # Quick truthiness shortcut for the bare ``{passed}`` style.
    stripped = rendered.strip()
    if stripped.lower() in ("true", "1", "yes"):
        return True
    if stripped.lower() in ("false", "0", "no", ""):
        return False

    # Operator dispatch — same surface as the gate handler.
    for op_token in (" == ", " != ", " >= ", " <= ", " > ", " < ", " contains "):
        if op_token in rendered:
            left, right = rendered.split(op_token, 1)
            left, right = left.strip(), right.strip()
            op = op_token.strip()
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "contains":
                return right in left
            # Numeric ops — coerce; fall back to closed on cast
            # failure.
            try:
                lv, rv = float(left), float(right)
            except ValueError:
                return False
            if op == ">":
                return lv > rv
            if op == ">=":
                return lv >= rv
            if op == "<":
                return lv < rv
            if op == "<=":
                return lv <= rv
    # Unrecognised condition shape — fail closed.
    return False


def _build_adjacency(graph: dict[str, Any]) -> dict[str, set[str]]:
    """Build an outgoing-edge adjacency map for the graph.

    Used by the gate-skip propagation. Kept separate from the
    topological-order walk so the walk's data shape stays pure
    (it only cares about incoming counts).
    """
    out: dict[str, set[str]] = {n["id"]: set() for n in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        src = edge.get("source")
        dst = edge.get("target")
        if src in out and dst is not None:
            out[src].add(dst)
    return out


def _descendants(start: str, adjacency: dict[str, set[str]]) -> set[str]:
    """BFS over outgoing edges, returning every node reachable from
    ``start`` (excluding ``start`` itself).
    """
    seen: set[str] = set()
    frontier = list(adjacency.get(start, ()))
    while frontier:
        node = frontier.pop()
        if node in seen:
            continue
        seen.add(node)
        frontier.extend(adjacency.get(node, ()))
    return seen


async def _load_run(session: Any, run_id: UUID) -> Run | None:
    stmt = select(Run).where(Run.id == run_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_version(session: Any, version_id: UUID) -> WorkflowVersion | None:
    stmt = select(WorkflowVersion).where(WorkflowVersion.id == version_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_workspace_id(session: Any, workflow_id: UUID) -> UUID | None:
    """Look up the workspace_id for a workflow without loading the row."""
    stmt = select(Workflow.workspace_id).where(Workflow.id == workflow_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _fail_run(session: Any, run: Run, message: str) -> None:
    if not can_transition_run(run.status, RunStatus.failed):
        return
    run.status = RunStatus.failed
    run.completed_at = now_utc()
    run.error_message = message[:1000]
    await session.flush()


async def _fail_node_run(session: Any, node_run: NodeRun, message: str) -> None:
    if not can_transition_node_run(node_run.status, NodeRunStatus.failed):
        return
    node_run.status = NodeRunStatus.failed
    node_run.completed_at = now_utc()
    node_run.error_message = message[:1000]
    await session.flush()
