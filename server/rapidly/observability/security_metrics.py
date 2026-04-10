"""Prometheus metrics for security monitoring.

Tracks security-related events:
- File scan results (clean, infected, mime_mismatch, error)
- Malware detections with threat names
- Download quota violations
- Quarantine operations

These metrics can be used to:
- Alert on malware detection spikes
- Monitor quota enforcement
- Track security infrastructure health
"""

from prometheus_client import Counter, Histogram

# ── Counters ──

# File scanning metrics
FILE_SCANS = Counter(
    "rapidly_file_scans_total",
    "Total number of file scans",
    ["status"],  # clean, infected, mime_mismatch, error, skipped
)

FILE_SCAN_DURATION = Histogram(
    "rapidly_file_scan_duration_seconds",
    "File scan duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

FILE_SCAN_SIZE = Histogram(
    "rapidly_file_scan_size_bytes",
    "Size of scanned files in bytes",
    buckets=(
        1024,  # 1 KB
        10 * 1024,  # 10 KB
        100 * 1024,  # 100 KB
        1024 * 1024,  # 1 MB
        10 * 1024 * 1024,  # 10 MB
        100 * 1024 * 1024,  # 100 MB
        1024 * 1024 * 1024,  # 1 GB
    ),
)

# Malware detection metrics
MALWARE_DETECTIONS = Counter(
    "rapidly_malware_detections_total",
    "Total number of malware detections",
    ["threat_category"],  # trojan, virus, worm, etc.
)

MIME_MISMATCH_DETECTIONS = Counter(
    "rapidly_mime_mismatch_detections_total",
    "Total number of MIME type mismatch detections",
    ["declared_type", "detected_type"],
)

# Quarantine metrics
QUARANTINE_OPERATIONS = Counter(
    "rapidly_quarantine_operations_total",
    "Total number of quarantine operations",
    ["reason", "status"],  # reason: malware/mime_mismatch, status: success/failure
)

# ── Tracking Helpers ──


def record_file_scan(
    status: str,
    file_size: int,
    duration_seconds: float | None = None,
) -> None:
    """Record a file scan result.

    Args:
        status: Scan status (clean, infected, mime_mismatch, error, skipped)
        file_size: Size of the scanned file in bytes
        duration_seconds: Time taken for scan (optional)
    """
    FILE_SCANS.labels(status=status).inc()
    FILE_SCAN_SIZE.observe(file_size)

    if duration_seconds is not None:
        FILE_SCAN_DURATION.observe(duration_seconds)


def record_malware_detection(threat_name: str) -> None:
    """Record a malware detection.

    Args:
        threat_name: Name of the detected threat (e.g., "Trojan.Generic")
    """
    # Extract threat category from name (first part before dot)
    category = "unknown"
    if threat_name:
        parts = threat_name.split(".")
        if parts:
            category = parts[0].lower()

    MALWARE_DETECTIONS.labels(threat_category=category).inc()


def record_mime_mismatch(declared_type: str, detected_type: str | None) -> None:
    """Record a MIME type mismatch detection.

    Args:
        declared_type: The MIME type declared by the uploader
        detected_type: The actual MIME type detected from content
    """
    MIME_MISMATCH_DETECTIONS.labels(
        declared_type=declared_type,
        detected_type=detected_type or "unknown",
    ).inc()


def record_quarantine(reason: str, success: bool) -> None:
    """Record a quarantine operation.

    Args:
        reason: Why the file was quarantined (malware, mime_mismatch)
        success: Whether the quarantine operation succeeded
    """
    QUARANTINE_OPERATIONS.labels(
        reason=reason,
        status="success" if success else "failure",
    ).inc()
