"""Tests for ``rapidly/logfire.py``.

Logfire distributed-tracing setup. Three load-bearing surfaces:

- **Span-drop matchers** filter health-probe + worker-heartbeat
  spans before they reach Logfire's billed quota. Drift here either
  blows the quota (matchers loosened) or drops legitimate spans
  (matchers tightened wrong)
- **`_scrub_callback`** preserves the ``subject`` attribute from
  Logfire's automatic PII scrubbing — auth-subject IDs are NOT PII
  and the dashboard relies on them for crash attribution
- ``DropMatchedSampler`` short-circuits to ``ALWAYS_OFF`` when ANY
  matcher fires; default is ``ALWAYS_ON`` so unmatched spans flow
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import logfire
from opentelemetry.trace.span import TraceState

from rapidly.logfire import (
    _DROP_MATCHERS,
    DropMatchedSampler,
    _is_health_probe,
    _is_worker_heartbeat,
    _scrub_callback,
)


class TestIsHealthProbe:
    def test_matches_healthz_route(self) -> None:
        assert _is_health_probe("GET /healthz", {"http.route": "/healthz"}) is True

    def test_does_not_match_other_routes(self) -> None:
        assert _is_health_probe("GET /api/users", {"http.route": "/api/users"}) is False

    def test_does_not_match_when_attrs_is_none(self) -> None:
        # ``attrs is None`` short-circuit prevents AttributeError
        # crashes on root spans without HTTP attributes.
        assert _is_health_probe("anything", None) is False

    def test_does_not_match_when_route_attr_missing(self) -> None:
        assert _is_health_probe("GET /something", {"http.method": "GET"}) is False


class TestIsWorkerHeartbeat:
    def test_matches_recording_health_prefix(self) -> None:
        assert _is_worker_heartbeat("Recording health: redis", None) is True

    def test_matches_health_check_successful_prefix(self) -> None:
        assert _is_worker_heartbeat("Health check successful for X", None) is True

    def test_match_is_case_insensitive(self) -> None:
        # Pin case-insensitivity — Dramatiq emits lowercase, but
        # human-supplied span names might be Title Case. A regression
        # to case-sensitive matching would let title-cased heartbeats
        # leak into the billed quota.
        assert _is_worker_heartbeat("RECORDING HEALTH: db", None) is True
        assert _is_worker_heartbeat("HEALTH CHECK SUCCESSFUL", None) is True

    def test_does_not_match_unrelated_spans(self) -> None:
        assert _is_worker_heartbeat("INSERT into events", None) is False
        assert _is_worker_heartbeat("dispatch_task", None) is False


class TestDropMatchersSet:
    def test_pinned_to_two_matchers(self) -> None:
        # Adding a matcher silently broadens the suppression set —
        # silent drops mean we lose crash-attribution coverage on
        # the matching span class. Pin the count.
        assert len(_DROP_MATCHERS) == 2
        names = {m.__name__ for m in _DROP_MATCHERS}
        assert names == {"_is_health_probe", "_is_worker_heartbeat"}


class TestDropMatchedSampler:
    def _sample(self, sampler: DropMatchedSampler, name: str, attrs: Any) -> bool:
        # ``ALWAYS_ON.should_sample`` returns ``RECORD_AND_SAMPLE``;
        # ``ALWAYS_OFF`` returns ``DROP``. Compare by string repr
        # to avoid pulling in the Decision enum's exact values.
        result = sampler.should_sample(
            parent_context=None,
            trace_id=1,
            name=name,
            kind=None,
            attributes=attrs,
            links=None,
            trace_state=TraceState(),
        )
        return "RECORD" in str(result.decision).upper()

    def test_unmatched_span_is_kept(self) -> None:
        sampler = DropMatchedSampler(_DROP_MATCHERS)
        assert self._sample(sampler, "INSERT into events", None) is True

    def test_matched_health_probe_is_dropped(self) -> None:
        sampler = DropMatchedSampler(_DROP_MATCHERS)
        assert (
            self._sample(sampler, "GET /healthz", {"http.route": "/healthz"}) is False
        )

    def test_matched_heartbeat_is_dropped(self) -> None:
        sampler = DropMatchedSampler(_DROP_MATCHERS)
        assert self._sample(sampler, "Recording health: redis", None) is False

    def test_description_pinned(self) -> None:
        sampler = DropMatchedSampler(_DROP_MATCHERS)
        assert sampler.get_description() == "DropMatchedSampler"

    def test_short_circuits_when_any_matcher_fires(self) -> None:
        # Pin the OR semantics: a single positive matcher drops
        # the span even if other matchers say no. ``any(...)`` in
        # the sampler must not regress to ``all(...)``.
        always_no = MagicMock(return_value=False)
        always_yes = MagicMock(return_value=True)
        sampler = DropMatchedSampler([always_no, always_yes])
        # Sample with anything; ``always_yes`` fires → drop.
        assert self._sample(sampler, "anything", None) is False


class TestScrubCallback:
    def test_preserves_subject_attribute(self) -> None:
        # ``subject`` is the auth-subject ID; not PII and the
        # dashboard relies on it for crash attribution. A regression
        # that scrubbed it would blank out every event's subject
        # tag.
        match = MagicMock(spec=logfire.ScrubMatch)
        match.path = ("attributes", "subject")
        match.value = "user-123"
        assert _scrub_callback(match) == "user-123"

    def test_other_paths_return_none_for_default_scrub(self) -> None:
        # Returning None tells Logfire to apply its default
        # scrubbing (replace with redaction marker). Pinning
        # the None return prevents a regression that defaulted
        # to value-passthrough on other paths and leaked PII.
        match = MagicMock(spec=logfire.ScrubMatch)
        match.path = ("attributes", "email")
        match.value = "alice@example.com"
        assert _scrub_callback(match) is None

    def test_nested_path_other_than_subject_scrubbed(self) -> None:
        match = MagicMock(spec=logfire.ScrubMatch)
        match.path = ("body", "secret")
        match.value = "leaked-token"
        assert _scrub_callback(match) is None


class TestExports:
    def test_all_exports_present(self) -> None:
        from rapidly import logfire as M

        assert set(M.__all__) == {
            "configure_logfire",
            "instrument_fastapi",
            "instrument_httpx",
            "instrument_sqlalchemy",
        }
