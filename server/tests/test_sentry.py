"""Tests for ``rapidly/sentry.py``.

Sentry error-tracking configuration. Two load-bearing pins:

- ``configure_sentry`` initialises with **explicit integrations**
  (``default_integrations=False``, ``auto_enabling_integrations=False``).
  This is intentional — letting Sentry auto-discover integrations
  has historically pulled in noisy ones (e.g. boto3 patching) that
  blew up the event quota
- ``set_sentry_user`` only tags the scope when the principal is a
  USER. Workspace / Customer / Member / Anonymous principals must
  NOT call ``sentry_sdk.set_user`` — otherwise non-user identifiers
  would leak into Sentry's user dashboard
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from rapidly.identity.auth.models import (
    Anonymous,
    AuthPrincipal,
)
from rapidly.sentry import (
    _INTEGRATIONS,
    _LOG_BREADCRUMB_LEVEL,
    _SafeSentryMiddleware,
    configure_sentry,
    set_sentry_user,
)


def _user_principal() -> Any:
    # ``User`` is a SQLAlchemy model — touching its attributes
    # without ``_sa_instance_state`` raises. ``SimpleNamespace`` +
    # patching ``is_user_principal`` avoids the SA machinery.
    user = SimpleNamespace(id=uuid4(), posthog_distinct_id="ph_user_123")
    return AuthPrincipal(user, set(), None)


def _workspace_principal() -> Any:
    ws = SimpleNamespace(id=uuid4())
    return AuthPrincipal(ws, set(), None)


def _anonymous_principal() -> AuthPrincipal:  # type: ignore[type-arg]
    return AuthPrincipal(Anonymous(), set(), None)


class TestLogBreadcrumbLevel:
    def test_pinned_to_info(self) -> None:
        # Below INFO is too noisy for Sentry breadcrumbs (DEBUG
        # logs flood the trail); above INFO drops useful context.
        # Pin INFO as the documented floor.
        assert _LOG_BREADCRUMB_LEVEL == logging.INFO


class TestIntegrationSet:
    def test_explicit_set_pinned(self) -> None:
        # The list is the canonical Sentry integration contract;
        # silent additions can blow Sentry quota, silent removals
        # drop crash-attribution coverage. Pin the names.
        names = sorted(type(i).__name__ for i in _INTEGRATIONS)
        assert names == sorted(
            [
                "AtexitIntegration",
                "ExcepthookIntegration",
                "DedupeIntegration",
                "ModulesIntegration",
                "ArgvIntegration",
                "LoggingIntegration",
                "ThreadingIntegration",
                "StarletteIntegration",
                "FastApiIntegration",
                "_RapidlyDramatiqIntegration",
            ]
        )


class TestConfigureSentry:
    def test_inits_with_explicit_integrations_only(self) -> None:
        # Load-bearing pin. ``default_integrations=False`` and
        # ``auto_enabling_integrations=False`` together prevent the
        # SDK from auto-discovering noisy integrations (boto3,
        # asyncpg) that would blow the event quota.
        captured: dict[str, Any] = {}

        def fake_init(**kwargs: Any) -> None:
            captured.update(kwargs)

        with patch("rapidly.sentry.sentry_sdk.init", side_effect=fake_init):
            configure_sentry()

        assert captured["default_integrations"] is False
        assert captured["auto_enabling_integrations"] is False
        assert captured["integrations"] is _INTEGRATIONS

    def test_environment_from_settings(self) -> None:
        from rapidly.config import settings

        captured: dict[str, Any] = {}
        with patch(
            "rapidly.sentry.sentry_sdk.init",
            side_effect=lambda **kwargs: captured.update(kwargs),
        ):
            configure_sentry()
        assert captured["environment"] == settings.ENV


class TestSetSentryUser:
    def test_user_principal_tags_scope(self) -> None:
        # User principal — ``set_user({"id": ...})`` is called and
        # the posthog_distinct_id tag is set so Sentry events
        # cross-link to PostHog sessions. ``is_user_principal`` is
        # patched True since SimpleNamespace doesn't pass the
        # ``isinstance(..., User)`` check.
        principal = _user_principal()
        with (
            patch("rapidly.sentry.is_user_principal", return_value=True),
            patch("rapidly.sentry.sentry_sdk.set_user") as set_user,
            patch("rapidly.sentry.sentry_sdk.set_tag") as set_tag,
        ):
            set_sentry_user(principal)
        set_user.assert_called_once_with({"id": str(principal.subject.id)})
        set_tag.assert_called_once_with(
            "posthog_distinct_id", principal.subject.posthog_distinct_id
        )

    def test_non_user_principal_does_not_tag(self) -> None:
        # Load-bearing pin. ``set_sentry_user`` is a no-op when
        # ``is_user_principal`` is False — leaking non-user ids
        # into Sentry's user dashboard would mis-attribute crashes
        # to non-human identities.
        principal = _workspace_principal()
        with (
            patch("rapidly.sentry.is_user_principal", return_value=False),
            patch("rapidly.sentry.sentry_sdk.set_user") as set_user,
            patch("rapidly.sentry.sentry_sdk.set_tag") as set_tag,
        ):
            set_sentry_user(principal)
        set_user.assert_not_called()
        set_tag.assert_not_called()

    def test_anonymous_principal_does_not_tag(self) -> None:
        # Anonymous is a real (slot-only) class so isinstance check
        # works without patching.
        principal = _anonymous_principal()
        with patch("rapidly.sentry.sentry_sdk.set_user") as set_user:
            set_sentry_user(principal)
        set_user.assert_not_called()


class TestSafeSentryMiddleware:
    def test_after_skip_routes_through_after_process(self) -> None:
        # The patched middleware's whole point: when Dramatiq
        # SKIPS a message (debounced, retry-exhausted, etc) the
        # Sentry hub/scope state must be torn down through the
        # SAME path as the normal post-process. A regression
        # leaving scope state dangling causes the next message's
        # error report to attribute to the WRONG message.
        mw = _SafeSentryMiddleware()
        broker = MagicMock()
        message = MagicMock()
        with patch.object(mw, "after_process_message") as after_process:
            mw.after_skip_message(broker, message)
        after_process.assert_called_once_with(broker, message)
