"""Dramatiq queue names and priority levels for the background worker."""

from enum import IntEnum, StrEnum


class TaskPriority(IntEnum):
    """Numeric priorities — lower values are processed first."""

    HIGH = 0
    MEDIUM = 50
    LOW = 100


class TaskQueue(StrEnum):
    """Named queues consumed by the Dramatiq worker processes."""

    HIGH_PRIORITY = "high_priority"
    MEDIUM_PRIORITY = "medium_priority"
    LOW_PRIORITY = "low_priority"
    WEBHOOKS = "webhooks"

    @classmethod
    def for_priority(cls, priority: TaskPriority) -> "TaskQueue":
        """Return the queue that matches a given priority level."""
        return _PRIORITY_TO_QUEUE[priority]


_PRIORITY_TO_QUEUE: dict[TaskPriority, TaskQueue] = {
    TaskPriority.HIGH: TaskQueue.HIGH_PRIORITY,
    TaskPriority.MEDIUM: TaskQueue.MEDIUM_PRIORITY,
    TaskPriority.LOW: TaskQueue.LOW_PRIORITY,
}

__all__ = [
    "TaskPriority",
    "TaskQueue",
]
