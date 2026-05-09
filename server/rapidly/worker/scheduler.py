"""APScheduler-based cron scheduler for recurring background tasks."""

import logfire
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.base import STATE_STOPPED
from apscheduler.schedulers.blocking import BlockingScheduler

from rapidly.logfire import configure_logfire
from rapidly.logging import configure as configure_logging
from rapidly.sentry import configure_sentry

from ._broker import scheduler_middleware

configure_sentry()
configure_logfire("worker")
configure_logging(logfire=True)


class LogfireBlockingScheduler(BlockingScheduler):
    def _main_loop(self) -> None:
        wait_seconds = 1
        while self.state != STATE_STOPPED:
            with logfire.span("Scheduler wakeup"):
                self._event.wait(wait_seconds)
                self._event.clear()
                wait_seconds = self._process_jobs()


def start() -> None:
    scheduler = LogfireBlockingScheduler()

    scheduler.add_jobstore(MemoryJobStore(), "memory")

    for func, cron_trigger in scheduler_middleware.cron_triggers:
        scheduler.add_job(func, cron_trigger, jobstore="memory")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()


__all__ = ["start"]


if __name__ == "__main__":
    start()
