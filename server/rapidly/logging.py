"""Rapidly logging -- wires *structlog* into Python's stdlib logging.

Architecture
------------
The ``LogPipeline`` base class (parameterised by renderer type) encapsulates
both the structlog processor chain and the stdlib ``logging.config`` dict.
Concrete pipelines (``ConsolePipeline``, ``JSONPipeline``) select their
renderer.  ``configure()`` picks the right pipeline based on the active
environment.
"""

from __future__ import annotations

import logging.config
import uuid
from typing import Any

import structlog
from logfire.integrations.structlog import LogfireProcessor

from rapidly.config import settings

Logger = structlog.stdlib.BoundLogger

# ---------------------------------------------------------------------------
# Third-party loggers propagated to the root handler
# ---------------------------------------------------------------------------

_THIRD_PARTY_LOGGERS: tuple[str, ...] = (
    "uvicorn",
    "sqlalchemy",
    "dramatiq",
    "authlib",
    "logfire",
    "apscheduler",
)

# ---------------------------------------------------------------------------
# Processor building blocks
# ---------------------------------------------------------------------------

_timestamper = structlog.processors.TimeStamper(fmt="iso")


def _logfire_level_remap(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Translate Python's ``critical`` level to ``fatal`` for Logfire compat."""
    if event_dict.get("level") == "critical":
        event_dict["level"] = "fatal"
    return event_dict


def _observability_processors(enabled: bool) -> list[Any]:
    """Return the Logfire processor chain when *enabled*, empty list otherwise."""
    if not enabled:
        return []
    return [_logfire_level_remap, LogfireProcessor()]


def _shared_pre_chain(*, logfire: bool) -> list[Any]:
    """Processor chain shared between structlog and stdlib foreign pre-chain."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _timestamper,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.StackInfoRenderer(),
        *_observability_processors(logfire),
    ]


# ---------------------------------------------------------------------------
# Pipeline base
# ---------------------------------------------------------------------------


class LogPipeline[RendererType]:
    """Configures both structlog and stdlib logging in a single ``setup()`` call."""

    @classmethod
    def _renderer(cls) -> RendererType:
        raise NotImplementedError

    @classmethod
    def setup(cls, *, logfire: bool = False) -> None:
        level = settings.LOG_LEVEL
        renderer = cls._renderer()
        pre_chain = _shared_pre_chain(logfire=logfire)

        # -- stdlib logging config -----------------------------------------
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "rapidly": {
                        "()": structlog.stdlib.ProcessorFormatter,
                        "processors": [
                            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                            renderer,
                        ],
                        "foreign_pre_chain": [
                            *pre_chain[:3],  # contextvars, level, name
                            structlog.stdlib.ExtraAdder(),
                            *pre_chain[
                                3:
                            ],  # positional, timestamp, unicode, stack, logfire
                        ],
                    },
                },
                "handlers": {
                    "default": {
                        "level": level,
                        "class": "logging.StreamHandler",
                        "formatter": "rapidly",
                    },
                },
                "loggers": {
                    "": {
                        "handlers": ["default"],
                        "level": level,
                        "propagate": False,
                    },
                    **{
                        name: {"handlers": [], "propagate": True}
                        for name in _THIRD_PARTY_LOGGERS
                    },
                },
            }
        )

        # -- structlog config ----------------------------------------------
        structlog.configure_once(
            processors=[
                *pre_chain,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


# ---------------------------------------------------------------------------
# Concrete pipelines
# ---------------------------------------------------------------------------


class ConsolePipeline(LogPipeline[structlog.dev.ConsoleRenderer]):
    @classmethod
    def _renderer(cls) -> structlog.dev.ConsoleRenderer:
        return structlog.dev.ConsoleRenderer(colors=True)


class JSONPipeline(LogPipeline[structlog.processors.JSONRenderer]):
    @classmethod
    def _renderer(cls) -> structlog.processors.JSONRenderer:
        return structlog.processors.JSONRenderer()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def configure(*, logfire: bool = False) -> None:
    """Select and activate the logging pipeline for the current environment."""
    pipeline_map: dict[bool, type[LogPipeline[Any]]] = {
        True: ConsolePipeline,
        False: JSONPipeline,
    }
    use_console = settings.is_testing() or settings.is_development()
    pipeline = pipeline_map[use_console]
    # Disable logfire in tests regardless of the flag
    effective_logfire = logfire and not settings.is_testing()
    pipeline.setup(logfire=effective_logfire)


def generate_correlation_id() -> str:
    """Return a new UUID4 string suitable for request correlation."""
    return uuid.uuid4().hex
