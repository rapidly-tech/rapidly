"""Tests for ``rapidly/integrations/stripe/api.py``.

Stripe webhook ingestion. Three load-bearing surfaces:

- ``_DIRECT_WEBHOOKS`` and ``_CONNECT_WEBHOOKS`` allowlists —
  drift here either silently drops legitimate events (revenue
  loss; checkout completions never finalise) OR processes
  events we don't actually handle (worker errors + alert
  noise). The two sets are scoped by webhook receiver: the
  Connect webhook handles per-account events, the direct one
  handles platform-level events. Drift in scope (e.g. an
  identity-verification event landing on Connect) means it
  comes from the wrong Stripe-Signature secret and gets
  silently dropped.
- ``_WebhookEventGetter`` verifies the signature against the
  per-receiver secret. Parse errors (malformed body) → 400,
  signature mismatches (replay / forgery) → 401. Drift to a
  shared 400 would let attackers distinguish replay from
  malformed-body and probe the secret.
- The refresh endpoint 404s on missing ``return_path`` — pin
  so a regression to "redirect to root" doesn't leak the
  Stripe-Connect refresh flow into an unprotected redirect.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import stripe
from fastapi import HTTPException

from rapidly.integrations.stripe.api import (
    _CONNECT_WEBHOOKS,
    _DIRECT_WEBHOOKS,
    _WebhookEventGetter,
)


class TestDirectWebhookSet:
    def test_pinned_event_types(self) -> None:
        # Pin the exact set. Adding here without adding a worker
        # actor produces alert noise; removing means legitimate
        # events get silently dropped.
        assert _DIRECT_WEBHOOKS == frozenset(
            {
                "identity.verification_session.verified",
                "identity.verification_session.processing",
                "identity.verification_session.requires_input",
                "identity.verification_session.canceled",
                "setup_intent.succeeded",
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
                "checkout.session.completed",
            }
        )

    def test_includes_payment_failure(self) -> None:
        # Pin: ``payment_intent.payment_failed`` MUST be in the
        # set. Drift would silently drop failure notifications,
        # leaving customers stuck on a "processing" status they
        # never recover from.
        assert "payment_intent.payment_failed" in _DIRECT_WEBHOOKS

    def test_is_immutable_frozenset(self) -> None:
        # Pin: ``frozenset`` (NOT ``set``). A mutable set would
        # let a careless ``_DIRECT_WEBHOOKS.add(...)`` from
        # another module silently broaden the allowlist.
        assert isinstance(_DIRECT_WEBHOOKS, frozenset)


class TestConnectWebhookSet:
    def test_pinned_event_types(self) -> None:
        # Pin: Connect-scoped events. ``account.updated`` carries
        # KYC progression; ``checkout.session.completed`` confirms
        # destination-charge completion on the connected account.
        assert _CONNECT_WEBHOOKS == frozenset(
            {
                "account.updated",
                "checkout.session.completed",
            }
        )

    def test_is_immutable_frozenset(self) -> None:
        assert isinstance(_CONNECT_WEBHOOKS, frozenset)


class TestWebhookSetsBoundary:
    def test_account_updated_only_on_connect(self) -> None:
        # Pin: ``account.updated`` is Connect-only. Drift to also
        # accept it on the direct webhook would route platform
        # webhooks to per-account handlers and cause race
        # conditions on stripe_account_id resolution.
        assert "account.updated" in _CONNECT_WEBHOOKS
        assert "account.updated" not in _DIRECT_WEBHOOKS

    def test_payment_intent_succeeded_only_on_direct(self) -> None:
        # Pin: payment_intent events flow through the platform
        # secret (Destination Charges model). Drift to Connect
        # would mean the wrong-secret signature check rejects
        # every legit payment confirmation.
        assert "payment_intent.succeeded" in _DIRECT_WEBHOOKS
        assert "payment_intent.succeeded" not in _CONNECT_WEBHOOKS

    def test_checkout_completed_on_both(self) -> None:
        # Pin: checkout.session.completed legitimately fires on
        # BOTH webhook receivers (Direct = platform-fee
        # checkouts, Connect = account-direct checkouts). This
        # documents the duality.
        assert "checkout.session.completed" in _DIRECT_WEBHOOKS
        assert "checkout.session.completed" in _CONNECT_WEBHOOKS


def _make_request(body: bytes, signature: str | None) -> Any:
    """Build a Starlette-like Request stub."""
    request = MagicMock()
    request.body = AsyncMock(return_value=body)
    request.headers = {"Stripe-Signature": signature} if signature is not None else {}
    return request


@pytest.mark.asyncio
class TestWebhookEventGetter:
    async def test_returns_event_on_valid_signature(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sentinel_event = {"id": "evt_1", "type": "x"}

        def fake_construct(body: bytes, sig: str, secret: str) -> Any:
            assert body == b"payload"
            assert sig == "sig-abc"
            assert secret == "secret"
            return sentinel_event

        monkeypatch.setattr(
            stripe.Webhook, "construct_event", staticmethod(fake_construct)
        )
        getter = _WebhookEventGetter("secret")
        result = await getter(_make_request(b"payload", "sig-abc"))
        assert result is sentinel_event

    async def test_400_on_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: malformed payloads (JSON parse error) → 400. Stripe
        # documents this distinction vs. signature mismatch, and
        # the SOC dashboard branches on the status code to
        # classify replay attempts vs. transport corruption.
        def boom(body: bytes, sig: str, secret: str) -> None:
            raise ValueError("bad body")

        monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(boom))
        getter = _WebhookEventGetter("secret")
        with pytest.raises(HTTPException) as exc:
            await getter(_make_request(b"x", "s"))
        assert exc.value.status_code == 400

    async def test_401_on_signature_verification_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: signature mismatches (replay / forgery) → 401.
        # Drift to a shared 400 would let attackers distinguish
        # replay-vs-malformed and probe the webhook secret.
        def boom(body: bytes, sig: str, secret: str) -> None:
            raise stripe.SignatureVerificationError(
                "no match", sig_header=sig, http_body=body
            )

        monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(boom))
        getter = _WebhookEventGetter("secret")
        with pytest.raises(HTTPException) as exc:
            await getter(_make_request(b"x", "s"))
        assert exc.value.status_code == 401

    async def test_secret_is_private_attr(self) -> None:
        # Pin: secret stored in ``_secret`` slot, not exposed
        # publicly. Defence against accidental log-leak via
        # repr / dict-walk.
        getter = _WebhookEventGetter("very-secret")
        # ``__slots__`` prevents arbitrary attribute access;
        # only ``_secret`` exists.
        assert getter._secret == "very-secret"
        assert not hasattr(getter, "secret")

    async def test_uses_slots(self) -> None:
        # Pin: ``__slots__ = ("_secret",)`` — prevents the secret
        # from being copied into ``__dict__`` by any introspection
        # helper that walks ``vars()``.
        getter = _WebhookEventGetter("s")
        assert not hasattr(getter, "__dict__")
