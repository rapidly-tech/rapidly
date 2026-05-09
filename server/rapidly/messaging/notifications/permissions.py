"""Access control dependencies for notifications routes.

Provides scoped authenticator dependencies that restrict notification
list and mutation endpoints to users with the required permission sets.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

# ── Read access ──────────────────────────────────────────────────────

_notifications_read = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.notifications_read,
    },
    allowed_subjects={User},
)

NotificationsRead = Annotated[AuthPrincipal[User], Depends(_notifications_read)]

# ── Write access ─────────────────────────────────────────────────────

_notifications_write = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.notifications_write,
    },
    allowed_subjects={User},
)

NotificationsWrite = Annotated[AuthPrincipal[User], Depends(_notifications_write)]
