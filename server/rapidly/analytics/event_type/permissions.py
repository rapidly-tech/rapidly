"""Access control dependencies for event type routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope
from rapidly.models.workspace import Workspace

_EventTypeRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.events_read,
        Scope.events_write,
    },
    allowed_subjects={User, Workspace},
)
EventTypeRead = Annotated[AuthPrincipal[User | Workspace], Depends(_EventTypeRead)]

_EventTypeWrite = Authenticator(
    required_scopes={
        Scope.web_write,
    },
    allowed_subjects={User, Workspace},
)
EventTypeWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_EventTypeWrite)]
