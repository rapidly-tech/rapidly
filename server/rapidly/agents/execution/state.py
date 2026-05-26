"""Run + NodeRun state-machine helpers.

The engine walks a graph and writes status transitions through
these helpers so the rules live in one place, not scattered across
the actor body. Calling code does not raise on illegal transitions;
it asks ``can_transition_run`` first.

Why not encode the state machine as a class: most of what we want
out of a state machine is a single is-legal-transition predicate.
A class with a dispatch table buys ceremony, not clarity.
"""

from __future__ import annotations

from rapidly.models import RunStatus
from rapidly.models.agent_node_run import (
    TERMINAL_NODE_RUN_STATUSES,
    NodeRunStatus,
)
from rapidly.models.agent_run import TERMINAL_RUN_STATUSES

# Legal Run state transitions. The engine enforces these; the API
# layer's cancel uses TERMINAL_RUN_STATUSES directly for its own
# guard.
_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.pending: frozenset({RunStatus.running, RunStatus.cancelled}),
    RunStatus.running: frozenset(
        {
            RunStatus.succeeded,
            RunStatus.failed,
            RunStatus.cancelled,
            RunStatus.awaiting_human,
        }
    ),
    RunStatus.awaiting_human: frozenset({RunStatus.running, RunStatus.cancelled}),
    # Terminal states accept no further transitions.
    RunStatus.succeeded: frozenset(),
    RunStatus.failed: frozenset(),
    RunStatus.cancelled: frozenset(),
}

# Legal NodeRun state transitions. Same shape.
_NODE_RUN_TRANSITIONS: dict[NodeRunStatus, frozenset[NodeRunStatus]] = {
    NodeRunStatus.pending: frozenset({NodeRunStatus.running, NodeRunStatus.skipped}),
    NodeRunStatus.running: frozenset(
        {
            NodeRunStatus.succeeded,
            NodeRunStatus.failed,
            NodeRunStatus.awaiting_human,
        }
    ),
    NodeRunStatus.awaiting_human: frozenset({NodeRunStatus.running}),
    NodeRunStatus.succeeded: frozenset(),
    NodeRunStatus.failed: frozenset(),
    NodeRunStatus.skipped: frozenset(),
}


def can_transition_run(from_: RunStatus, to: RunStatus) -> bool:
    """Return True iff Run can move from ``from_`` to ``to``."""
    return to in _RUN_TRANSITIONS.get(from_, frozenset())


def can_transition_node_run(from_: NodeRunStatus, to: NodeRunStatus) -> bool:
    """Return True iff NodeRun can move from ``from_`` to ``to``."""
    return to in _NODE_RUN_TRANSITIONS.get(from_, frozenset())


def is_run_terminal(status: RunStatus) -> bool:
    return status in TERMINAL_RUN_STATUSES


def is_node_run_terminal(status: NodeRunStatus) -> bool:
    return status in TERMINAL_NODE_RUN_STATUSES
