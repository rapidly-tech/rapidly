"""Ordering definitions for the webhook module.

Enumerates the sortable columns available when listing webhook endpoints.
"""

from __future__ import annotations

from enum import StrEnum


class WebhookSortProperty(StrEnum):
    """Columns that webhook lists can be sorted by."""

    created_at = "created_at"
