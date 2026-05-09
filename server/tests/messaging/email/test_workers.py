"""Tests for ``rapidly/messaging/email/workers.py``.

Email-send worker with Redis-backed dedup. Three load-bearing
surfaces:

- ``_EMAIL_DEDUP_TTL_SECONDS = 3600`` — 1-hour dedup window.
  Drift down lets duplicate sends slip through (e.g., double
  signup emails on a retry storm); drift up suppresses
  legitimate re-sends within the same day.
- ``_email_dedup_key`` digests ``to:subject:html_content`` with
  SHA-256, takes the first 16 hex chars, and prefixes
  ``email:dedup:``. Drift in the digest input would cause keys
  to NOT collide for actual duplicates; drift in the prefix
  would silently scatter dedup state across multiple Redis
  namespaces.
- ``email.send`` actor: dedup key checked → if exists, log and
  return without sending; otherwise call sender, then mark the
  key with the TTL. The dedup-key set MUST happen AFTER a
  successful send so failures get retried (and not cached as
  "already sent").
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import AsyncMock

import pytest

from rapidly.messaging.email import workers as M
from rapidly.messaging.email.workers import (
    _EMAIL_DEDUP_TTL_SECONDS,
    _email_dedup_key,
    email_send,
)


class TestDedupTtl:
    def test_pinned_to_one_hour(self) -> None:
        # 1 h dedup window — drift down lets duplicates slip
        # through (retry-storm during incident); drift up
        # suppresses legitimate same-day re-sends.
        assert _EMAIL_DEDUP_TTL_SECONDS == 3600


class TestDedupKey:
    def test_format_includes_email_dedup_prefix(self) -> None:
        # Pin the namespace prefix. Drift would silently scatter
        # dedup state across Redis namespaces and break
        # deduplication entirely.
        key = _email_dedup_key("a@b.com", "Subject", "<p>body</p>")
        assert key.startswith("email:dedup:")

    def test_digest_uses_sha256_first_16_chars(self) -> None:
        # Pin the digest algorithm + truncation. SHA-256 → 64 hex
        # chars; the first 16 give us 64 bits of collision
        # resistance per (to, subject, body) triple — enough for
        # a 1-hour window. Drift to MD5 or full digest would
        # change every key on upgrade and silently disable dedup.
        key = _email_dedup_key("a@b.com", "S", "<p/>")
        digest = hashlib.sha256(b"a@b.com:S:<p/>").hexdigest()[:16]
        assert key == f"email:dedup:{digest}"

    def test_same_inputs_yield_same_key(self) -> None:
        # Pin determinism — different worker processes computing
        # the same key for the same email is the entire mechanism.
        a = _email_dedup_key("x@y.com", "Hi", "body")
        b = _email_dedup_key("x@y.com", "Hi", "body")
        assert a == b

    def test_different_recipient_yields_different_key(self) -> None:
        a = _email_dedup_key("a@b.com", "S", "body")
        b = _email_dedup_key("c@d.com", "S", "body")
        assert a != b

    def test_different_subject_yields_different_key(self) -> None:
        a = _email_dedup_key("a@b.com", "Hi", "body")
        b = _email_dedup_key("a@b.com", "Bye", "body")
        assert a != b

    def test_different_body_yields_different_key(self) -> None:
        # Pin: body is part of the key. Otherwise a "Welcome" email
        # sent to a user followed by a personalised "Welcome,
        # Alice!" email would dedup to the first.
        a = _email_dedup_key("a@b.com", "S", "<p>body 1</p>")
        b = _email_dedup_key("a@b.com", "S", "<p>body 2</p>")
        assert a != b


@pytest.mark.asyncio
class TestEmailSendActor:
    async def _setup_redis_and_sender(
        self, monkeypatch: pytest.MonkeyPatch, *, already_sent: bool
    ) -> tuple[Any, Any]:
        # Build mock redis (with predetermined ``exists``) and
        # mock email_sender.
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=already_sent)
        redis.set = AsyncMock()
        monkeypatch.setattr(
            "rapidly.messaging.email.workers.RedisMiddleware.get",
            staticmethod(lambda: redis),
        )
        sender = AsyncMock()
        monkeypatch.setattr(M, "email_sender", sender)
        return redis, sender

    async def test_skips_when_dedup_key_exists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: when dedup key already exists, the send is skipped
        # (NOT just logged-and-sent-anyway). Drift would let an
        # actor retry storm produce duplicate sends.
        redis, sender = await self._setup_redis_and_sender(
            monkeypatch, already_sent=True
        )
        await email_send.__wrapped__(  # type: ignore[attr-defined]
            to_email_addr="a@b.com",
            subject="S",
            html_content="<p/>",
            from_name="X",
            email_headers=None,
            reply_to_name=None,
            reply_to_email_addr=None,
        )
        sender.send.assert_not_awaited()
        # And the dedup key is NOT re-set (would extend TTL of an
        # already-deduped send).
        redis.set.assert_not_awaited()

    async def test_sends_then_marks_dedup_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: successful send sets the dedup key with the
        # documented TTL. Drift in TTL would change the dedup
        # window silently.
        redis, sender = await self._setup_redis_and_sender(
            monkeypatch, already_sent=False
        )
        await email_send.__wrapped__(  # type: ignore[attr-defined]
            to_email_addr="a@b.com",
            subject="S",
            html_content="<p/>",
            from_name="X",
            email_headers=None,
            reply_to_name=None,
            reply_to_email_addr=None,
        )
        sender.send.assert_awaited_once()
        # ``set`` invoked AFTER send — sequencing matters so a
        # failed send doesn't mark "already sent".
        redis.set.assert_awaited_once()
        kwargs = redis.set.call_args
        # ex= keyword pin
        assert kwargs.kwargs["ex"] == _EMAIL_DEDUP_TTL_SECONDS

    async def test_failed_send_does_not_mark_dedup_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (load-bearing): a send-failure must NOT mark the
        # dedup key. Otherwise the worker's retry would skip
        # forever and the user never receives the email.
        redis, sender = await self._setup_redis_and_sender(
            monkeypatch, already_sent=False
        )
        sender.send = AsyncMock(side_effect=RuntimeError("smtp down"))

        with pytest.raises(RuntimeError, match="smtp down"):
            await email_send.__wrapped__(  # type: ignore[attr-defined]
                to_email_addr="a@b.com",
                subject="S",
                html_content="<p/>",
                from_name="X",
                email_headers=None,
                reply_to_name=None,
                reply_to_email_addr=None,
            )

        redis.set.assert_not_awaited()

    async def test_forwards_all_send_kwargs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: every kwarg the actor receives is forwarded to
        # email_sender.send by name. Drift would silently drop
        # caller-customised values (e.g., reply_to gets lost).
        redis, sender = await self._setup_redis_and_sender(
            monkeypatch, already_sent=False
        )

        attachments = [{"remote_url": "https://x/y", "filename": "a.pdf"}]
        await email_send.__wrapped__(  # type: ignore[attr-defined]
            to_email_addr="a@b.com",
            subject="S",
            html_content="<p/>",
            from_name="From",
            email_headers={"List-Unsubscribe": "<mailto:u@x.com>"},
            reply_to_name="Reply",
            reply_to_email_addr="r@x.com",
            attachments=attachments,
        )
        sender.send.assert_awaited_once_with(
            to_email_addr="a@b.com",
            subject="S",
            html_content="<p/>",
            from_name="From",
            email_headers={"List-Unsubscribe": "<mailto:u@x.com>"},
            reply_to_name="Reply",
            reply_to_email_addr="r@x.com",
            attachments=attachments,
        )
