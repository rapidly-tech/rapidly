"""Authentication dependencies for notification recipient endpoints.

Defines read and write access gates that restrict notification-recipient
operations to authenticated users with the appropriate scopes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

# ── Read access ──────────────────────────────────────────────────────

_notification_recipient_read = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.notification_recipients_read,
        Scope.notification_recipients_write,
    },
    allowed_subjects={User},
)

NotificationRecipientRead = Annotated[
    AuthPrincipal[User], Depends(_notification_recipient_read)
]

# ── Write access ─────────────────────────────────────────────────────

_notification_recipient_write = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.notification_recipients_write,
    },
    allowed_subjects={User},
)

NotificationRecipientWrite = Annotated[
    AuthPrincipal[User], Depends(_notification_recipient_write)
]
