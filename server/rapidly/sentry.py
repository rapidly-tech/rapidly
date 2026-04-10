"""Sentry error-tracking configuration for Rapidly.

Sets up the Sentry SDK with explicit integrations (no auto-discovery),
patches the Dramatiq middleware for correct scope cleanup, and provides
a helper to attach authenticated-user context to Sentry events.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import sentry_sdk
from dramatiq import get_broker
from sentry_sdk.integrations.argv import ArgvIntegration
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.integrations.dramatiq import (
    DramatiqIntegration as _BaseDramatiqIntegration,
)
from sentry_sdk.integrations.dramatiq import SentryMiddleware as _SentryMiddleware
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.modules import ModulesIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration

from rapidly.config import settings
from rapidly.identity.auth.models import AuthPrincipal, Subject, is_user_principal

if TYPE_CHECKING:
    import dramatiq

# Breadcrumb severity floor for the logging integration.
_LOG_BREADCRUMB_LEVEL = logging.INFO


# -- Dramatiq patching -------------------------------------------------------


class _SafeSentryMiddleware(_SentryMiddleware):
    """Extends the stock middleware to clean up scope on skipped messages."""

    def after_skip_message(  # type: ignore[override]
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        # Reuse the normal teardown path so hub/scope state doesn't leak.
        self.after_process_message(broker, message)  # type: ignore[arg-type]


class _RapidlyDramatiqIntegration(_BaseDramatiqIntegration):
    """Register our patched Sentry middleware on the already-initialised broker."""

    @staticmethod
    def setup_once() -> None:
        broker = get_broker()
        first_mw_type = type(broker.middleware[0])
        broker.add_middleware(_SafeSentryMiddleware(), before=first_mw_type)


# -- Initialisation -----------------------------------------------------------


_INTEGRATIONS: list[sentry_sdk.Integration] = [  # type: ignore[name-defined]
    AtexitIntegration(),
    ExcepthookIntegration(),
    DedupeIntegration(),
    ModulesIntegration(),
    ArgvIntegration(),
    LoggingIntegration(level=_LOG_BREADCRUMB_LEVEL, event_level=None),
    ThreadingIntegration(),
    StarletteIntegration(transaction_style="endpoint"),
    FastApiIntegration(transaction_style="endpoint"),
    _RapidlyDramatiqIntegration(),
]


def configure_sentry() -> None:
    """Initialise the Sentry SDK with Rapidly's integration set."""
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=None,
        profiles_sample_rate=None,
        release=os.environ.get("RELEASE_VERSION", "development"),
        server_name=os.environ.get("RENDER_INSTANCE_ID", "localhost"),
        environment=settings.ENV,
        default_integrations=False,
        auto_enabling_integrations=False,
        integrations=_INTEGRATIONS,
    )


# -- User context -------------------------------------------------------------


def set_sentry_user(auth_subject: AuthPrincipal[Subject]) -> None:
    """Tag the current Sentry scope with the authenticated user's identity."""
    if not is_user_principal(auth_subject):
        return

    user = auth_subject.subject
    sentry_sdk.set_user({"id": str(user.id)})
    sentry_sdk.set_tag("posthog_distinct_id", user.posthog_distinct_id)
