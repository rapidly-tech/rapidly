"""Background task definitions for eventstream processing."""

from rapidly.worker import RedisMiddleware, TaskPriority, actor

from .actions import send_event


@actor(actor_name="eventstream.publish", priority=TaskPriority.HIGH)
async def eventstream_publish(event: str, channels: list[str]) -> None:
    await send_event(RedisMiddleware.get(), event, channels)
