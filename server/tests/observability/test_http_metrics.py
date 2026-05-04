"""Tests for ``rapidly/observability/http_metrics.py``.

HTTP request metrics for SLI/SLO monitoring. Three load-bearing
surfaces:

- ``METRICS_DENY_LIST`` excludes high-frequency probe endpoints
  (``/healthz``, ``/readyz``, well-known JWKS / OIDC) from the
  metric stream — including them blows the cardinality budget on
  the Prometheus backend
- Prometheus instrument names (``rapidly_http_request_total`` /
  ``rapidly_http_request_duration_seconds``) — Grafana dashboards
  query these literals; rename = silent dashboard breakage
- Histogram bucket boundaries — the documented
  ``0.01s..30s`` range covers sub-ms health checks through 30s
  SSR pages; tightening the upper bound would lose tail-latency
  signal
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

from rapidly.observability.http_metrics import (
    _DURATION_BUCKETS,
    _DURATION_LABELS,
    _REQUEST_LABELS,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUEST_TOTAL,
    METRICS_DENY_LIST,
    METRICS_EXCLUDED_APPS,
    exclude_app_from_metrics,
)


class TestMetricsDenyList:
    def test_excludes_high_frequency_probe_paths(self) -> None:
        # Probes hit these paths every few seconds; metrics for them
        # would dominate the cardinality budget without operational
        # value. Pinning the exact set protects ops budget.
        assert METRICS_DENY_LIST == {
            "/healthz",
            "/readyz",
            "/.well-known/openid-configuration",
            "/.well-known/jwks.json",
        }


class TestExcludeAppFromMetrics:
    def test_adds_app_to_excluded_set(self) -> None:
        # Sub-apps (e.g. the admin HTMX app) opt out via this
        # helper. Pin the registration semantics so a refactor
        # to a registry pattern doesn't drop the call.
        sentinel = object()
        try:
            exclude_app_from_metrics(sentinel)  # type: ignore[arg-type]
            assert sentinel in METRICS_EXCLUDED_APPS
        finally:
            METRICS_EXCLUDED_APPS.discard(sentinel)  # type: ignore[arg-type]

    def test_idempotent_when_called_twice(self) -> None:
        sentinel = object()
        try:
            exclude_app_from_metrics(sentinel)  # type: ignore[arg-type]
            exclude_app_from_metrics(sentinel)  # type: ignore[arg-type]
            assert sentinel in METRICS_EXCLUDED_APPS
            # ``set`` semantics — only one entry.
            count = sum(1 for x in METRICS_EXCLUDED_APPS if x is sentinel)
            assert count == 1
        finally:
            METRICS_EXCLUDED_APPS.discard(sentinel)  # type: ignore[arg-type]


class TestRequestCounter:
    def test_metric_name_and_type(self) -> None:
        # Grafana dashboards query the literal name. A rename
        # silently breaks every panel.
        assert isinstance(HTTP_REQUEST_TOTAL, Counter)
        # The Counter's name in the registry has ``_total`` appended
        # automatically by prometheus_client; the documented public
        # name is ``rapidly_http_request_total``.
        names = [m.name for m in HTTP_REQUEST_TOTAL.collect()]
        assert "rapidly_http_request" in names

    def test_request_labels(self) -> None:
        assert _REQUEST_LABELS == ["endpoint", "method", "status_code"]


class TestDurationHistogram:
    def test_metric_type_and_labels(self) -> None:
        assert isinstance(HTTP_REQUEST_DURATION_SECONDS, Histogram)
        assert _DURATION_LABELS == ["endpoint", "method"]

    def test_bucket_boundaries(self) -> None:
        # Pin the exact bucket set. Drift here changes histogram
        # interpretation in dashboards (p95 / p99 calculations
        # shift). The 30s upper bound covers the slowest legit
        # SSR page; shrinking it would lose tail-latency signal.
        assert _DURATION_BUCKETS == (
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
            30.0,
        )

    def test_bucket_starts_below_10ms(self) -> None:
        # Cheap-ops floor — sub-10ms requests need a meaningful
        # bucket to land in. A regression to e.g. 0.05 as the
        # lower bound would group every fast request together
        # and lose granular timing.
        assert _DURATION_BUCKETS[0] <= 0.01

    def test_buckets_strictly_increasing(self) -> None:
        # Histogram buckets must be ascending — Prometheus rejects
        # non-monotonic ranges silently and the resulting metric
        # would be useless.
        for prev, curr in zip(_DURATION_BUCKETS, _DURATION_BUCKETS[1:], strict=False):
            assert prev < curr
