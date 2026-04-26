"""Tests for ``rapidly/messaging/webhook/ordering.py``."""

from __future__ import annotations

from rapidly.messaging.webhook.ordering import WebhookSortProperty


class TestWebhookSortProperty:
    def test_contains_only_created_at(self) -> None:
        # Minimal surface — webhook lists are typically small and
        # sorted by recency.
        assert {e.value for e in WebhookSortProperty} == {"created_at"}

    def test_is_str_enum(self) -> None:
        assert str(WebhookSortProperty.created_at) == "created_at"
