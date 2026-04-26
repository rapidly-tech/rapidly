"""Entry point for the Dramatiq worker process.

Importing this module triggers side-effects that configure logging,
telemetry, and the Dramatiq broker. The ``broker`` binding is the only
symbol that Dramatiq's CLI needs to discover actors.
"""

from rapidly.logfire import configure_logfire
from rapidly.logging import configure as configure_logging
from rapidly.posthog import configure_posthog
from rapidly.sentry import configure_sentry
from rapidly.worker import broker

# Telemetry and logging setup — order matters: Sentry wraps everything,
# Logfire needs to be initialised before structured logging is configured.
configure_sentry()
configure_logfire("worker")
configure_logging(logfire=True)
configure_posthog()

# Importing ``workers`` registers all @actor-decorated functions with the
# broker so Dramatiq's worker threads can discover them.
from rapidly import workers as _register_actors  # noqa: E402, F401

__all__ = ["broker"]
