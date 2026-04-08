"""Access control dependencies for file routes."""

from typing import Annotated

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_FileRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.files_write,
        Scope.files_read,
    },
    allowed_subjects={User, Workspace},
)
FileRead = Annotated[AuthPrincipal[User | Workspace], Depends(_FileRead)]

_FileWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.files_write,
    },
    allowed_subjects={User, Workspace},
)
FileWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_FileWrite)]
