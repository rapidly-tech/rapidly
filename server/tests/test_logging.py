"""Tests for ``rapidly/logging.py``.

structlog ↔ stdlib logging bridge. Three load-bearing surfaces:

- ``_THIRD_PARTY_LOGGERS`` is the explicit allow-list of third-party
  loggers whose records propagate to the root handler. Drift drops
  visibility into a noisy framework or floods the log stream
- ``_logfire_level_remap`` translates Python's ``critical`` to
  ``fatal`` for Logfire compat — without it, criticals are silently
  re-bucketed by Logfire as ``error`` and lose alarm priority
- ``configure`` chooses between Console (dev/test) and JSON (prod)
  pipelines AND disables logfire in tests regardless of the caller's
  flag (a regression that re-enabled logfire under tests would emit
  fake events to the prod logfire project)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import structlog

from rapidly.logging import (
    _THIRD_PARTY_LOGGERS,
    ConsolePipeline,
    JSONPipeline,
    LogPipeline,
    _logfire_level_remap,
    _observability_processors,
    _shared_pre_chain,
    configure,
    generate_correlation_id,
)


class TestThirdPartyLoggers:
    def test_pinned_set(self) -> None:
        assert set(_THIRD_PARTY_LOGGERS) == {
            "uvicorn",
            "sqlalchemy",
            "dramatiq",
            "authlib",
            "logfire",
            "apscheduler",
        }

    def test_is_a_tuple(self) -> None:
        # Tuple (immutable) — the dictConfig builds the loggers
        # dict from this collection at module init; a list could
        # be mutated post-import to silently re-route logging.
        assert isinstance(_THIRD_PARTY_LOGGERS, tuple)


class TestLogfireLevelRemap:
    def test_critical_becomes_fatal(self) -> None:
        # Logfire uses ``fatal`` instead of Python's ``critical``;
        # without the remap, Python critical events end up bucketed
        # as ``error`` (or untyped) on Logfire's side and lose
        # alarm priority.
        out = _logfire_level_remap(MagicMock(), "log", {"level": "critical"})
        assert out["level"] == "fatal"

    def test_other_levels_unchanged(self) -> None:
        out = _logfire_level_remap(MagicMock(), "log", {"level": "error"})
        assert out["level"] == "error"

    def test_no_level_key_passes_through(self) -> None:
        # Defensive: ``event_dict`` without a ``level`` key (rare,
        # but possible from raw structlog calls) must not crash.
        out = _logfire_level_remap(MagicMock(), "log", {})
        assert "level" not in out


class TestObservabilityProcessors:
    def test_empty_when_logfire_disabled(self) -> None:
        # In tests, logfire is disabled — the processor chain
        # must NOT contain the LogfireProcessor (which would
        # try to ship records to the prod project).
        assert _observability_processors(enabled=False) == []

    def test_includes_remap_and_logfire_processor_when_enabled(self) -> None:
        chain = _observability_processors(enabled=True)
        assert len(chain) == 2
        assert chain[0] is _logfire_level_remap


class TestSharedPreChain:
    def test_chain_length_with_logfire(self) -> None:
        chain = _shared_pre_chain(logfire=True)
        # 7 base processors + 2 observability = 9
        assert len(chain) == 9

    def test_chain_length_without_logfire(self) -> None:
        chain = _shared_pre_chain(logfire=False)
        # 7 base processors + 0 observability = 7
        assert len(chain) == 7


class TestPipelineBase:
    def test_renderer_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            LogPipeline._renderer()


class TestConcretePipelines:
    def test_console_pipeline_returns_console_renderer(self) -> None:
        renderer = ConsolePipeline._renderer()
        assert isinstance(renderer, structlog.dev.ConsoleRenderer)

    def test_json_pipeline_returns_json_renderer(self) -> None:
        renderer = JSONPipeline._renderer()
        assert isinstance(renderer, structlog.processors.JSONRenderer)


class TestConfigureDispatch:
    def test_uses_console_pipeline_in_dev_or_test(self) -> None:
        # Dev / test envs use the Console renderer for human-readable
        # logs. JSON pipeline is for prod.
        with (
            patch("rapidly.logging.settings.is_testing", return_value=True),
            patch("rapidly.logging.settings.is_development", return_value=False),
            patch.object(ConsolePipeline, "setup") as console_setup,
            patch.object(JSONPipeline, "setup") as json_setup,
        ):
            configure()
        console_setup.assert_called_once()
        json_setup.assert_not_called()

    def test_uses_json_pipeline_in_prod(self) -> None:
        with (
            patch("rapidly.logging.settings.is_testing", return_value=False),
            patch("rapidly.logging.settings.is_development", return_value=False),
            patch.object(ConsolePipeline, "setup") as console_setup,
            patch.object(JSONPipeline, "setup") as json_setup,
        ):
            configure()
        json_setup.assert_called_once()
        console_setup.assert_not_called()

    def test_logfire_disabled_in_tests_even_when_caller_passes_true(self) -> None:
        # Load-bearing pin. ``effective_logfire = logfire and not
        # settings.is_testing()`` — the test guard short-circuits
        # any caller that mistakenly enables logfire while running
        # tests, preventing fake events from polluting the prod
        # Logfire project.
        with (
            patch("rapidly.logging.settings.is_testing", return_value=True),
            patch("rapidly.logging.settings.is_development", return_value=False),
            patch.object(ConsolePipeline, "setup") as console_setup,
        ):
            configure(logfire=True)
        # Called with logfire=False even though caller passed True.
        console_setup.assert_called_once_with(logfire=False)


class TestGenerateCorrelationId:
    def test_returns_32_char_hex(self) -> None:
        # uuid4().hex — 32 chars, all hex. A regression returning a
        # dashed UUID (36 chars) would break log-aggregator regex
        # filters.
        cid = generate_correlation_id()
        assert len(cid) == 32
        int(cid, 16)  # hex parses cleanly

    def test_distinct_across_calls(self) -> None:
        # Collision probability is 1 / 2^122 per pair — effectively
        # zero. Pinning rules out a regression to a deterministic
        # value (e.g. a static "request" string).
        ids = {generate_correlation_id() for _ in range(20)}
        assert len(ids) == 20
