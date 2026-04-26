"""Schemas for ClamAV scan operations."""

from enum import StrEnum


class ScanStatus(StrEnum):
    """Status of a file's malware scan."""

    pending = "pending"
    scanning = "scanning"
    clean = "clean"
    infected = "infected"
    error = "error"
    skipped = "skipped"
