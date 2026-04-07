"""Lightweight utility functions used throughout the Rapidly backend.

These are intentionally dependency-free so they can be imported from
models, workers, and anywhere else without pulling in heavy packages.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

# IEC binary prefixes for human-readable file sizes.
_BINARY_PREFIXES = ("", "K", "M", "G", "T", "P", "E", "Z")


def now_utc() -> datetime:
    """Return the current moment as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def create_uuid() -> uuid.UUID:
    """Generate a random v4 UUID."""
    return uuid.uuid4()


def human_readable_size(byte_count: float, suffix: str = "B") -> str:
    """Format *byte_count* as a compact human-readable string (e.g. ``4.2 MB``)."""
    for prefix in _BINARY_PREFIXES:
        if abs(byte_count) < 1024.0:
            return f"{byte_count:3.1f} {prefix}{suffix}"
        byte_count /= 1024.0
    return f"{byte_count:.1f} Y{suffix}"
