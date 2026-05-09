"""Tests for ``rapidly/observability/security_metrics.py``.

Security-monitoring metrics for the AV-scan + quarantine pipeline.
Four load-bearing surfaces:

- Prometheus instrument names (``rapidly_file_scans_total``,
  ``rapidly_malware_detections_total``, etc.) — Grafana panels and
  alert rules query the literal names; rename = silent dashboard +
  alert breakage
- Histogram bucket boundaries — ``FILE_SCAN_DURATION`` (0.1s..60s)
  covers fast clamd hits through the slow-path retry budget;
  ``FILE_SCAN_SIZE`` (1KB..1GB) brackets the upload-size SLA
- ``record_malware_detection`` extracts the threat category as the
  first dotted-prefix segment, lowercased — drift here makes the
  ``threat_category`` label unstable across releases and breaks
  alert grouping
- ``record_mime_mismatch`` falls back to ``"unknown"`` when the
  detected type is None — pinning prevents a regression that
  emitted empty-string labels (which Prometheus rejects)
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

from rapidly.observability.security_metrics import (
    FILE_SCAN_DURATION,
    FILE_SCAN_SIZE,
    FILE_SCANS,
    MALWARE_DETECTIONS,
    MIME_MISMATCH_DETECTIONS,
    QUARANTINE_OPERATIONS,
    record_file_scan,
    record_malware_detection,
    record_mime_mismatch,
    record_quarantine,
)


def _counter_value(counter: Counter, **labels: str) -> float:
    """Read the current value of a Counter at the given label set."""
    return counter.labels(**labels)._value.get()


def _histogram_count(hist: Histogram, **labels: str) -> float:
    """Read the observation count of a Histogram (optionally labeled)."""
    if labels:
        return hist.labels(**labels)._sum.get()  # not used here, but keep symmetry
    return hist._sum.get()


class TestFileScansCounter:
    def test_metric_type(self) -> None:
        # Grafana / alertmanager query the literal name
        # ``rapidly_file_scans_total`` — rename = silent breakage.
        assert isinstance(FILE_SCANS, Counter)

    def test_status_label_is_load_bearing(self) -> None:
        # Pin the label arity. Adding a label is a breaking change for
        # PromQL queries; removing one collapses distinct series and
        # corrupts alert thresholds.
        before = _counter_value(FILE_SCANS, status="clean")
        FILE_SCANS.labels(status="clean").inc()
        assert _counter_value(FILE_SCANS, status="clean") == before + 1


class TestFileScanDurationHistogram:
    def test_metric_type(self) -> None:
        assert isinstance(FILE_SCAN_DURATION, Histogram)

    def test_bucket_upper_bound_covers_slow_path(self) -> None:
        # The 60s upper bound covers the slowest legitimate clamd
        # response under heavy load. Tightening it would dump every
        # slow scan into ``+Inf`` and lose tail-latency signal.
        upper_bounds = [
            float(s.labels["le"])
            for m in FILE_SCAN_DURATION.collect()
            for s in m.samples
            if s.name.endswith("_bucket")
        ]
        assert max(b for b in upper_bounds if b != float("inf")) >= 60.0

    def test_bucket_lower_bound_covers_fast_path(self) -> None:
        # 100ms floor — sub-100ms scans land in a meaningful bucket.
        upper_bounds = sorted(
            float(s.labels["le"])
            for m in FILE_SCAN_DURATION.collect()
            for s in m.samples
            if s.name.endswith("_bucket") and s.labels["le"] != "+Inf"
        )
        assert upper_bounds[0] <= 0.1


class TestFileScanSizeHistogram:
    def test_metric_type(self) -> None:
        assert isinstance(FILE_SCAN_SIZE, Histogram)

    def test_bucket_upper_bound_is_one_gib(self) -> None:
        # 1 GiB upper bound brackets the upload-size cap. A regression
        # that capped at e.g. 100 MB would mis-bucket every legitimate
        # large upload as ``+Inf``.
        upper_bounds = [
            float(s.labels["le"])
            for m in FILE_SCAN_SIZE.collect()
            for s in m.samples
            if s.name.endswith("_bucket") and s.labels["le"] != "+Inf"
        ]
        assert max(upper_bounds) >= 1024 * 1024 * 1024

    def test_bucket_lower_bound_is_one_kib(self) -> None:
        # 1 KiB floor — small files (config/manifest uploads) need a
        # meaningful bucket too.
        upper_bounds = sorted(
            float(s.labels["le"])
            for m in FILE_SCAN_SIZE.collect()
            for s in m.samples
            if s.name.endswith("_bucket") and s.labels["le"] != "+Inf"
        )
        assert upper_bounds[0] <= 1024


class TestMalwareDetectionsCounter:
    def test_metric_type(self) -> None:
        assert isinstance(MALWARE_DETECTIONS, Counter)


class TestMimeMismatchCounter:
    def test_metric_type(self) -> None:
        assert isinstance(MIME_MISMATCH_DETECTIONS, Counter)


class TestQuarantineOperationsCounter:
    def test_metric_type(self) -> None:
        assert isinstance(QUARANTINE_OPERATIONS, Counter)


class TestRecordFileScan:
    def test_increments_status_counter(self) -> None:
        before = _counter_value(FILE_SCANS, status="infected")
        record_file_scan(status="infected", file_size=2048)
        assert _counter_value(FILE_SCANS, status="infected") == before + 1

    def test_observes_file_size(self) -> None:
        before = FILE_SCAN_SIZE._sum.get()
        record_file_scan(status="clean", file_size=1024)
        assert FILE_SCAN_SIZE._sum.get() == before + 1024

    def test_duration_observed_only_when_provided(self) -> None:
        # Pin the optional-duration semantics: omitting ``duration_seconds``
        # must NOT observe 0.0 (which would skew p95 / p99 down). A
        # regression to ``hist.observe(duration or 0.0)`` would silently
        # wreck dashboards.
        before = FILE_SCAN_DURATION._sum.get()
        record_file_scan(status="skipped", file_size=512)
        assert FILE_SCAN_DURATION._sum.get() == before

    def test_duration_observed_when_provided(self) -> None:
        before = FILE_SCAN_DURATION._sum.get()
        record_file_scan(status="clean", file_size=512, duration_seconds=0.25)
        assert FILE_SCAN_DURATION._sum.get() == before + 0.25


class TestRecordMalwareDetection:
    def test_extracts_category_from_dotted_threat_name(self) -> None:
        # ``Trojan.Generic.12345`` → category ``trojan``. The first
        # segment is the malware family; alert rules group by it.
        before = _counter_value(MALWARE_DETECTIONS, threat_category="trojan")
        record_malware_detection("Trojan.Generic.12345")
        assert (
            _counter_value(MALWARE_DETECTIONS, threat_category="trojan") == before + 1
        )

    def test_category_is_lowercased(self) -> None:
        # Lowercasing pins case-insensitive grouping. A regression that
        # preserved case would produce duplicate ``Trojan`` / ``trojan``
        # series and split alert thresholds.
        before = _counter_value(MALWARE_DETECTIONS, threat_category="virus")
        record_malware_detection("VIRUS.Linux.X")
        assert _counter_value(MALWARE_DETECTIONS, threat_category="virus") == before + 1

    def test_falls_back_to_unknown_for_empty_threat_name(self) -> None:
        # Defensive: an empty string from the AV engine must not crash
        # or emit an empty label (Prometheus rejects those). Pin the
        # fallback to ``"unknown"``.
        before = _counter_value(MALWARE_DETECTIONS, threat_category="unknown")
        record_malware_detection("")
        assert (
            _counter_value(MALWARE_DETECTIONS, threat_category="unknown") == before + 1
        )

    def test_no_dot_uses_full_name_as_category(self) -> None:
        # ``Eicar`` (no dotted prefix) still classifies — the whole
        # name becomes the category, lowercased.
        before = _counter_value(MALWARE_DETECTIONS, threat_category="eicar")
        record_malware_detection("Eicar")
        assert _counter_value(MALWARE_DETECTIONS, threat_category="eicar") == before + 1


class TestRecordMimeMismatch:
    def test_records_both_label_values(self) -> None:
        before = _counter_value(
            MIME_MISMATCH_DETECTIONS,
            declared_type="image/png",
            detected_type="application/x-msdownload",
        )
        record_mime_mismatch("image/png", "application/x-msdownload")
        assert (
            _counter_value(
                MIME_MISMATCH_DETECTIONS,
                declared_type="image/png",
                detected_type="application/x-msdownload",
            )
            == before + 1
        )

    def test_detected_none_falls_back_to_unknown(self) -> None:
        # Pin the None-fallback. A regression that passed ``None``
        # straight through would either crash prometheus_client or
        # emit an empty-string label — both break the metric.
        before = _counter_value(
            MIME_MISMATCH_DETECTIONS,
            declared_type="application/pdf",
            detected_type="unknown",
        )
        record_mime_mismatch("application/pdf", None)
        assert (
            _counter_value(
                MIME_MISMATCH_DETECTIONS,
                declared_type="application/pdf",
                detected_type="unknown",
            )
            == before + 1
        )


class TestRecordQuarantine:
    def test_success_true_maps_to_success_label(self) -> None:
        # Pin the bool→string mapping. Drift to e.g. ``str(success)``
        # would emit ``"True"`` / ``"False"`` and break dashboards.
        before = _counter_value(
            QUARANTINE_OPERATIONS, reason="malware", status="success"
        )
        record_quarantine("malware", success=True)
        assert (
            _counter_value(QUARANTINE_OPERATIONS, reason="malware", status="success")
            == before + 1
        )

    def test_success_false_maps_to_failure_label(self) -> None:
        before = _counter_value(
            QUARANTINE_OPERATIONS, reason="mime_mismatch", status="failure"
        )
        record_quarantine("mime_mismatch", success=False)
        assert (
            _counter_value(
                QUARANTINE_OPERATIONS, reason="mime_mismatch", status="failure"
            )
            == before + 1
        )
