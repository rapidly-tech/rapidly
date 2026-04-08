"""Ordering definitions for the file module.

Enumerates the sortable columns available when listing uploaded files.
"""

from __future__ import annotations

from enum import StrEnum


class FileSortProperty(StrEnum):
    """Columns that file lists can be sorted by."""

    created_at = "created_at"
    file_name = "name"
