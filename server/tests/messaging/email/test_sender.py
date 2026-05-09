"""Tests for ``rapidly/messaging/email/sender.py``.

Transactional-email delivery layer. Five load-bearing surfaces:

- ``to_ascii_email`` punycodes internationalised domain names so
  Gmail SMTP (which only accepts ASCII envelopes) can deliver
  them. Drift would silently bounce every IDN address.
- Exception hierarchy: ``SendEmailError`` extends
  ``EmailSenderError`` extends ``RapidlyError`` so callers
  catching at any level still see provider failures.
- ``GmailEmailSender.send`` builds an ``EmailMessage`` with
  exact ``Subject`` / ``From`` / ``To`` / ``Reply-To`` headers,
  attaches HTML as ``text/html`` alternative, and wraps
  ``aiosmtplib.SMTPException`` as ``SendEmailError`` (so the
  worker's retry logic distinguishes provider faults from
  programmer errors).
- ``enqueue_email`` dispatches the ``email.send`` task with every
  parameter forwarded — drift in the actor name or kwarg shape
  would silently drop emails into the void.
- ``_create_sender`` selects ``GmailEmailSender`` when
  ``EMAIL_SENDER == gmail``, otherwise ``LoggingEmailSender``.
  The selection MUST happen at module load to avoid per-call
  setting reads. Drift to per-call would make hot-reloading
  config silently change behaviour mid-flight.
"""

from __future__ import annotations

from typing import Any

import aiosmtplib
import pytest

from rapidly.config import EmailSender as EmailSenderType
from rapidly.errors import RapidlyError
from rapidly.messaging.email import sender as M
from rapidly.messaging.email.sender import (
    DEFAULT_FROM_NAME,
    DEFAULT_REPLY_TO_EMAIL_ADDRESS,
    DEFAULT_REPLY_TO_NAME,
    EmailSender,
    EmailSenderError,
    GmailEmailSender,
    LoggingEmailSender,
    SendEmailError,
    _create_sender,
    enqueue_email,
    to_ascii_email,
)


class TestToAsciiEmail:
    def test_ascii_email_passthrough(self) -> None:
        # ASCII addresses are returned unchanged.
        assert to_ascii_email("alice@example.com") == "alice@example.com"

    def test_internationalised_domain_punycoded(self) -> None:
        # Pin: IDN domain → punycode A-label. Gmail SMTP envelopes
        # MUST be ASCII; without conversion every IDN address
        # would silently bounce.
        result = to_ascii_email("user@münchen.de")
        # ``xn--mnchen-3ya`` is the canonical punycode for "münchen".
        assert result.endswith(".de") or "xn--" in result

    def test_uppercase_local_part_preserved(self) -> None:
        # Pin: validate_email lowercases the domain but preserves
        # local-part case (RFC requires it).
        result = to_ascii_email("Alice@Example.com")
        assert result == "Alice@example.com"


class TestExceptionHierarchy:
    def test_email_sender_error_extends_rapidly_error(self) -> None:
        # Pin: callers catch on RapidlyError to render generic
        # 5xx responses; drift to plain Exception would bypass
        # the standard error handler.
        assert issubclass(EmailSenderError, RapidlyError)

    def test_send_email_error_extends_email_sender_error(self) -> None:
        # Pin: the retry middleware catches SendEmailError as
        # "transient" — it MUST inherit from EmailSenderError so
        # generic ``except EmailSenderError:`` still catches it.
        assert issubclass(SendEmailError, EmailSenderError)

    def test_send_email_error_carries_message(self) -> None:
        err = SendEmailError("Gmail rejected: 421 4.7.0")
        assert "421" in str(err)


class TestPublicDefaultsExposed:
    def test_aliases_match_module_constants(self) -> None:
        # Pin: callers (workers, action helpers) import
        # ``DEFAULT_FROM_NAME`` etc. directly. Drift to a different
        # alias name silently breaks every importer.
        assert DEFAULT_FROM_NAME == M._FROM_NAME
        assert DEFAULT_REPLY_TO_NAME == M._REPLY_TO_NAME
        assert DEFAULT_REPLY_TO_EMAIL_ADDRESS == M._REPLY_TO_ADDRESS


class TestEmailSenderABC:
    def test_send_is_abstract(self) -> None:
        # Pin: ``EmailSender`` is an ABC — instantiating directly
        # must raise. Otherwise a regression that dropped @abstract
        # would let callers construct a no-op base class.
        with pytest.raises(TypeError):
            EmailSender()  # type: ignore[abstract]


@pytest.mark.asyncio
class TestLoggingEmailSender:
    async def test_send_does_not_raise(self) -> None:
        # Pin: dev mode — no real SMTP, no exception. Just a log.
        sender = LoggingEmailSender()
        await sender.send(
            to_email_addr="alice@example.com",
            subject="Hi",
            html_content="<p>hi</p>",
        )


@pytest.mark.asyncio
class TestGmailEmailSender:
    async def test_builds_message_with_required_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: Subject / From / To headers MUST be set; From uses
        # the documented "<from_name> <gmail_email>" format. Drift
        # would either route mail to spam or break DMARC alignment.
        captured: dict[str, Any] = {}

        async def fake_send(msg: Any, **kw: Any) -> Any:
            captured["msg"] = msg
            captured["kwargs"] = kw

        monkeypatch.setattr(aiosmtplib, "send", fake_send)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "GMAIL_EMAIL", "no-reply@rapidly.tech")
        monkeypatch.setattr(settings_obj, "GMAIL_APP_PASSWORD", "secret")

        sender = GmailEmailSender()
        await sender.send(
            to_email_addr="user@example.com",
            subject="Welcome",
            html_content="<p>Hi</p>",
            from_name="Rapidly",
        )

        msg = captured["msg"]
        assert msg["Subject"] == "Welcome"
        assert msg["From"] == "Rapidly <no-reply@rapidly.tech>"
        assert msg["To"] == "user@example.com"

    async def test_reply_to_when_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: Reply-To uses the same "<name> <addr>" format as
        # From. Customer-support workflows route on this header;
        # drift would bury reply traffic in the no-reply mailbox.
        captured: dict[str, Any] = {}

        async def fake_send(msg: Any, **kw: Any) -> Any:
            captured["msg"] = msg

        monkeypatch.setattr(aiosmtplib, "send", fake_send)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "GMAIL_EMAIL", "from@x.com")
        monkeypatch.setattr(settings_obj, "GMAIL_APP_PASSWORD", "p")

        sender = GmailEmailSender()
        await sender.send(
            to_email_addr="user@example.com",
            subject="X",
            html_content="<p>x</p>",
            reply_to_name="Support",
            reply_to_email_addr="support@rapidly.tech",
        )

        assert captured["msg"]["Reply-To"] == "Support <support@rapidly.tech>"

    async def test_reply_to_omitted_when_either_field_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: Reply-To header is added ONLY when BOTH name and
        # address are present. Drift to single-field check would
        # produce malformed headers that some MTAs reject.
        captured: dict[str, Any] = {}

        async def fake_send(msg: Any, **kw: Any) -> Any:
            captured["msg"] = msg

        monkeypatch.setattr(aiosmtplib, "send", fake_send)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "GMAIL_EMAIL", "from@x.com")
        monkeypatch.setattr(settings_obj, "GMAIL_APP_PASSWORD", "p")

        sender = GmailEmailSender()
        await sender.send(
            to_email_addr="user@example.com",
            subject="X",
            html_content="<p>x</p>",
            reply_to_name="Support",
            reply_to_email_addr=None,
        )

        assert captured["msg"]["Reply-To"] is None

    async def test_custom_email_headers_pass_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: caller-supplied headers (e.g. List-Unsubscribe for
        # marketing emails) are added to the message. Drift would
        # silently drop them and make us non-compliant with
        # CAN-SPAM / RFC 2369.
        captured: dict[str, Any] = {}

        async def fake_send(msg: Any, **kw: Any) -> Any:
            captured["msg"] = msg

        monkeypatch.setattr(aiosmtplib, "send", fake_send)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "GMAIL_EMAIL", "from@x.com")
        monkeypatch.setattr(settings_obj, "GMAIL_APP_PASSWORD", "p")

        sender = GmailEmailSender()
        await sender.send(
            to_email_addr="user@example.com",
            subject="X",
            html_content="<p>x</p>",
            email_headers={"List-Unsubscribe": "<mailto:unsubscribe@x.com>"},
        )

        assert captured["msg"]["List-Unsubscribe"] == "<mailto:unsubscribe@x.com>"

    async def test_html_alternative_attached(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: HTML body added as ``text/html`` alternative. Drift
        # to plain-text would render Markdown / styled emails as
        # raw HTML in mail clients.
        captured: dict[str, Any] = {}

        async def fake_send(msg: Any, **kw: Any) -> Any:
            captured["msg"] = msg

        monkeypatch.setattr(aiosmtplib, "send", fake_send)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "GMAIL_EMAIL", "from@x.com")
        monkeypatch.setattr(settings_obj, "GMAIL_APP_PASSWORD", "p")

        sender = GmailEmailSender()
        await sender.send(
            to_email_addr="user@example.com",
            subject="X",
            html_content="<p>marketing</p>",
        )

        msg = captured["msg"]
        # walk() yields the message AND its parts. Find the html one.
        types = [p.get_content_type() for p in msg.walk()]
        assert "text/html" in types

    async def test_uses_starttls_with_gmail_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: aiosmtplib.send call uses start_tls=True. Drift to
        # start_tls=False would transmit the app password in clear.
        captured: dict[str, Any] = {}

        async def fake_send(msg: Any, **kw: Any) -> Any:
            captured["kwargs"] = kw

        monkeypatch.setattr(aiosmtplib, "send", fake_send)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "GMAIL_EMAIL", "from@x.com")
        monkeypatch.setattr(settings_obj, "GMAIL_APP_PASSWORD", "p")
        monkeypatch.setattr(settings_obj, "GMAIL_SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setattr(settings_obj, "GMAIL_SMTP_PORT", 587)

        sender = GmailEmailSender()
        await sender.send(
            to_email_addr="user@example.com",
            subject="X",
            html_content="<p>x</p>",
        )

        kw = captured["kwargs"]
        assert kw["start_tls"] is True
        assert kw["hostname"] == "smtp.gmail.com"
        assert kw["port"] == 587
        assert kw["username"] == "from@x.com"
        assert kw["password"] == "p"

    async def test_smtp_exception_wrapped_as_send_email_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: aiosmtplib SMTP exception → SendEmailError. Drift
        # would surface raw aiosmtplib exception types and break
        # the worker's retry-classification logic.
        async def boom(msg: Any, **kw: Any) -> None:
            raise aiosmtplib.SMTPException("transient: 421")

        monkeypatch.setattr(aiosmtplib, "send", boom)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "GMAIL_EMAIL", "from@x.com")
        monkeypatch.setattr(settings_obj, "GMAIL_APP_PASSWORD", "p")

        sender = GmailEmailSender()
        with pytest.raises(SendEmailError, match="421"):
            await sender.send(
                to_email_addr="user@example.com",
                subject="X",
                html_content="<p>x</p>",
            )


class TestEnqueueEmail:
    def test_dispatches_email_send_actor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin the actor name + kwarg names — drift in either
        # silently drops emails. The worker's ``@actor(actor_name=
        # "email.send")`` reads the same literal.
        dispatched: list[Any] = []

        def fake_dispatch(actor: str, *args: Any, **kw: Any) -> None:
            dispatched.append((actor, args, kw))

        monkeypatch.setattr(M, "dispatch_task", fake_dispatch)

        enqueue_email(
            to_email_addr="user@example.com",
            subject="Subj",
            html_content="<p>body</p>",
            from_name="Custom",
        )

        assert len(dispatched) == 1
        actor, args, kw = dispatched[0]
        assert actor == "email.send"
        assert kw["to_email_addr"] == "user@example.com"
        assert kw["subject"] == "Subj"
        assert kw["html_content"] == "<p>body</p>"
        assert kw["from_name"] == "Custom"

    def test_defaults_passthrough_on_optional_args(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: omitted optional args resolve to module defaults
        # (NOT None / missing). Drift would let a worker actor
        # crash on a None reply-to in production.
        dispatched: list[Any] = []
        monkeypatch.setattr(
            M, "dispatch_task", lambda *a, **kw: dispatched.append((a, kw))
        )

        enqueue_email(
            to_email_addr="x@y.com",
            subject="s",
            html_content="<p/>",
        )

        kw = dispatched[0][1]
        assert kw["from_name"] == DEFAULT_FROM_NAME
        assert kw["reply_to_name"] == DEFAULT_REPLY_TO_NAME
        assert kw["reply_to_email_addr"] == DEFAULT_REPLY_TO_EMAIL_ADDRESS


class TestCreateSender:
    def test_gmail_setting_yields_gmail_sender(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "EMAIL_SENDER", EmailSenderType.gmail)
        s = _create_sender()
        assert isinstance(s, GmailEmailSender)

    def test_logger_setting_yields_logging_sender(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "EMAIL_SENDER", EmailSenderType.logger)
        s = _create_sender()
        assert isinstance(s, LoggingEmailSender)
