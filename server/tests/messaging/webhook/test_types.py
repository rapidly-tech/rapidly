"""Tests for ``rapidly/messaging/webhook/types.py``.

Webhook endpoint URLs must be **https-only** — webhook payloads carry
signing secrets and event data. Accepting ``http://`` would leak the
payload over the wire in plaintext on every delivery; accepting custom
schemes (``javascript:``, ``file:``, ``ftp:``) is an SSRF surface.

Also pins the legacy ``secret`` min-length (32) — the secret is now
generated server-side, but callers supplying one must still meet the
entropy floor used to verify HMAC signatures.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.messaging.webhook.types import (
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
)
from rapidly.models.webhook_endpoint import WebhookEventType, WebhookFormat

# Minimal valid body — reused across the tests.
_VALID_EVENTS: list[WebhookEventType] = [next(iter(WebhookEventType))]


class TestEndpointURLRequiresHttps:
    @pytest.mark.parametrize(
        "hostile",
        [
            "http://example.test/cb",  # plain http — MITM surface
            "ftp://example.test/cb",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/html,<script>",
        ],
    )
    def test_rejects_non_https_schemes(self, hostile: str) -> None:
        # A webhook URL that accepts ``http://`` would ship the
        # payload (including signing secrets in the header) over
        # plaintext on every delivery.
        with pytest.raises(ValidationError):
            WebhookEndpointCreate(
                url=hostile,  # type: ignore[arg-type]
                format=WebhookFormat.raw,
                events=_VALID_EVENTS,
            )

    def test_accepts_https(self) -> None:
        body = WebhookEndpointCreate(
            url="https://hooks.example.test/cb",  # type: ignore[arg-type]
            format=WebhookFormat.raw,
            events=_VALID_EVENTS,
        )
        assert str(body.url).startswith("https://")

    def test_requires_host(self) -> None:
        # host_required=True — a scheme-only URL like ``https:`` is
        # rejected. Pinning prevents a regression that let empty-host
        # URLs through and crashed the delivery worker.
        with pytest.raises(ValidationError):
            WebhookEndpointCreate(
                url="https://",  # type: ignore[arg-type]
                format=WebhookFormat.raw,
                events=_VALID_EVENTS,
            )

    def test_rejects_urls_over_2083_chars(self) -> None:
        # 2083 is the IE/Edge URL-bar limit and the practical
        # ceiling on what proxies will forward. Pinning the upper
        # bound stops a caller persisting a 10 KB URL that would
        # stall every delivery.
        too_long = "https://example.test/" + "a" * 2100
        with pytest.raises(ValidationError):
            WebhookEndpointCreate(
                url=too_long,  # type: ignore[arg-type]
                format=WebhookFormat.raw,
                events=_VALID_EVENTS,
            )


class TestEndpointSecretMinLength:
    def test_none_is_accepted(self) -> None:
        # Secret is generated server-side since the legacy path was
        # deprecated; ``None`` is the canonical modern call.
        body = WebhookEndpointCreate(
            url="https://hooks.example.test/cb",  # type: ignore[arg-type]
            format=WebhookFormat.raw,
            events=_VALID_EVENTS,
            secret=None,
        )
        assert body.secret is None

    def test_rejects_secret_under_32_chars(self) -> None:
        # Legacy override still enforces a 32-char floor — HMAC
        # verification assumes the secret has enough entropy. A
        # regression loosening this would let callers set a 4-char
        # secret and have their signatures brute-forced.
        with pytest.raises(ValidationError):
            WebhookEndpointCreate(
                url="https://hooks.example.test/cb",  # type: ignore[arg-type]
                format=WebhookFormat.raw,
                events=_VALID_EVENTS,
                secret="short",
            )

    def test_accepts_32_char_secret(self) -> None:
        secret = "a" * 32
        body = WebhookEndpointCreate(
            url="https://hooks.example.test/cb",  # type: ignore[arg-type]
            format=WebhookFormat.raw,
            events=_VALID_EVENTS,
            secret=secret,
        )
        assert body.secret == secret


class TestEndpointSecretDeprecation:
    def test_secret_field_is_marked_deprecated(self) -> None:
        # The server generates the secret now; clients supplying one
        # are on the legacy path. Pinning the deprecation marker
        # stops a future refactor from silently un-deprecating the
        # field in the OpenAPI schema.
        field = WebhookEndpointCreate.model_fields["secret"]
        assert field.deprecated


class TestWebhookEndpointUpdateSamePins:
    # The update model shares the URL/secret constraints with create.
    # Pinning them on both sides catches a regression that only
    # tightens one path (e.g., a new create-only AfterValidator).

    def test_update_rejects_non_https(self) -> None:
        with pytest.raises(ValidationError):
            WebhookEndpointUpdate(url="http://example.test/cb")  # type: ignore[arg-type]

    def test_update_rejects_short_secret(self) -> None:
        with pytest.raises(ValidationError):
            WebhookEndpointUpdate(secret="short")

    def test_update_all_fields_optional(self) -> None:
        # Partial update — empty body is valid (caller might only be
        # flipping ``enabled`` later).
        body = WebhookEndpointUpdate()
        assert body.url is None
        assert body.secret is None
        assert body.format is None
        assert body.events is None
        assert body.enabled is None
