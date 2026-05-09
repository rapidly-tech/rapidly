"""Access control dependencies for member routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope
from rapidly.models.workspace import Workspace

_MemberRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.members_read,
        Scope.members_write,
    },
    allowed_subjects={User, Workspace},
)
MemberRead = Annotated[AuthPrincipal[User | Workspace], Depends(_MemberRead)]

_MemberWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.members_write,
    },
    allowed_subjects={User, Workspace},
)
MemberWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_MemberWrite)]
