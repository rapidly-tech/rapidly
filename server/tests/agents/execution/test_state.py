"""Tests for the Run + NodeRun state-machine helpers."""

from __future__ import annotations

import pytest

from rapidly.agents.execution.state import (
    can_transition_node_run,
    can_transition_run,
    is_node_run_terminal,
    is_run_terminal,
)
from rapidly.models import RunStatus
from rapidly.models.agent_node_run import NodeRunStatus


class TestRunTransitions:
    @pytest.mark.parametrize(
        ("from_", "to", "ok"),
        [
            (RunStatus.pending, RunStatus.running, True),
            (RunStatus.pending, RunStatus.cancelled, True),
            (RunStatus.running, RunStatus.succeeded, True),
            (RunStatus.running, RunStatus.failed, True),
            (RunStatus.running, RunStatus.cancelled, True),
            (RunStatus.running, RunStatus.awaiting_human, True),
            (RunStatus.awaiting_human, RunStatus.running, True),
            (RunStatus.awaiting_human, RunStatus.cancelled, True),
            # Illegal: terminal states accept nothing
            (RunStatus.succeeded, RunStatus.running, False),
            (RunStatus.failed, RunStatus.running, False),
            (RunStatus.cancelled, RunStatus.running, False),
            # Illegal: pending can't jump to succeeded directly
            (RunStatus.pending, RunStatus.succeeded, False),
            (RunStatus.pending, RunStatus.awaiting_human, False),
        ],
    )
    def test_transition(self, from_: RunStatus, to: RunStatus, ok: bool) -> None:
        assert can_transition_run(from_, to) is ok


class TestNodeRunTransitions:
    @pytest.mark.parametrize(
        ("from_", "to", "ok"),
        [
            (NodeRunStatus.pending, NodeRunStatus.running, True),
            (NodeRunStatus.pending, NodeRunStatus.skipped, True),
            (NodeRunStatus.running, NodeRunStatus.succeeded, True),
            (NodeRunStatus.running, NodeRunStatus.failed, True),
            (NodeRunStatus.running, NodeRunStatus.awaiting_human, True),
            (NodeRunStatus.awaiting_human, NodeRunStatus.running, True),
            (NodeRunStatus.succeeded, NodeRunStatus.running, False),
            (NodeRunStatus.skipped, NodeRunStatus.running, False),
        ],
    )
    def test_transition(
        self, from_: NodeRunStatus, to: NodeRunStatus, ok: bool
    ) -> None:
        assert can_transition_node_run(from_, to) is ok


class TestTerminalPredicates:
    def test_run_terminal(self) -> None:
        assert is_run_terminal(RunStatus.succeeded)
        assert is_run_terminal(RunStatus.failed)
        assert is_run_terminal(RunStatus.cancelled)
        assert not is_run_terminal(RunStatus.running)
        assert not is_run_terminal(RunStatus.pending)

    def test_node_run_terminal(self) -> None:
        assert is_node_run_terminal(NodeRunStatus.succeeded)
        assert is_node_run_terminal(NodeRunStatus.failed)
        assert is_node_run_terminal(NodeRunStatus.skipped)
        assert not is_node_run_terminal(NodeRunStatus.running)
        assert not is_node_run_terminal(NodeRunStatus.pending)
