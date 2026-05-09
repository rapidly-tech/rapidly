"""Tests for ``rapidly/worker/_queues.py``.

Queue names + priority levels for the Dramatiq worker. Three
load-bearing pins:

- ``TaskPriority`` is an IntEnum where lower values = higher priority
  (Dramatiq's documented contract). The spacing (0 / 50 / 100) leaves
  room for future insertions without renumbering consumers
- ``TaskQueue`` names are the Redis list keys consumed by worker
  processes — a rename desyncs publishers from consumers and stalls
  every enqueued job on the old queue
- ``for_priority`` maps every priority → a queue (no gaps); adding
  a new ``TaskPriority`` member without updating the map would
  KeyError the enqueue path
"""

from __future__ import annotations

import pytest

from rapidly.worker._queues import TaskPriority, TaskQueue


class TestTaskPriority:
    def test_values_are_ordered_low_to_high_number(self) -> None:
        # Dramatiq: lower value = higher priority.
        assert TaskPriority.HIGH.value == 0
        assert TaskPriority.MEDIUM.value == 50
        assert TaskPriority.LOW.value == 100

    def test_spacing_leaves_insertion_room(self) -> None:
        # Future ``CRITICAL`` or ``BACKGROUND`` priorities can slot
        # in between HIGH/MEDIUM/LOW without renumbering consumers —
        # a regression to a dense {0, 1, 2} scheme would break that.
        members = [p.value for p in TaskPriority]
        gaps = [members[i + 1] - members[i] for i in range(len(members) - 1)]
        assert all(gap >= 10 for gap in gaps)

    def test_high_is_lower_than_low_numerically(self) -> None:
        # IntEnum comparison: HIGH < LOW (because numerically
        # smaller = higher priority).
        assert TaskPriority.HIGH < TaskPriority.LOW


class TestTaskQueueNames:
    def test_wire_values_match_redis_keys(self) -> None:
        # The wire values are the Redis LIST keys worker processes
        # pop from. A rename here desyncs publishers from
        # consumers and strands every enqueued job.
        assert TaskQueue.HIGH_PRIORITY.value == "high_priority"
        assert TaskQueue.MEDIUM_PRIORITY.value == "medium_priority"
        assert TaskQueue.LOW_PRIORITY.value == "low_priority"
        assert TaskQueue.WEBHOOKS.value == "webhooks"

    def test_enum_has_four_queues(self) -> None:
        # Adding a queue silently means publishers might target it
        # without a worker subscribing to it; pin the count.
        assert len(list(TaskQueue)) == 4


class TestForPriority:
    @pytest.mark.parametrize(
        ("priority", "expected_queue"),
        [
            (TaskPriority.HIGH, TaskQueue.HIGH_PRIORITY),
            (TaskPriority.MEDIUM, TaskQueue.MEDIUM_PRIORITY),
            (TaskPriority.LOW, TaskQueue.LOW_PRIORITY),
        ],
    )
    def test_maps_priority_to_queue(
        self, priority: TaskPriority, expected_queue: TaskQueue
    ) -> None:
        assert TaskQueue.for_priority(priority) is expected_queue

    def test_every_priority_has_a_queue(self) -> None:
        # Load-bearing completeness pin: adding a TaskPriority
        # without updating ``_PRIORITY_TO_QUEUE`` would KeyError
        # every enqueue call for the new priority.
        for priority in TaskPriority:
            # Must not raise.
            TaskQueue.for_priority(priority)


class TestExports:
    def test_all_declared(self) -> None:
        from rapidly.worker import _queues as Q

        assert set(Q.__all__) == {"TaskPriority", "TaskQueue"}
