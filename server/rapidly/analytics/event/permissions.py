"""Access control dependencies for event routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope
from rapidly.models.workspace import Workspace

_EventRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.events_read,
        Scope.events_write,
    },
    allowed_subjects={User, Workspace},
)
EventRead = Annotated[AuthPrincipal[User | Workspace], Depends(_EventRead)]

_EventWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.events_write,
    },
    allowed_subjects={User, Workspace},
)
EventWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_EventWrite)]
