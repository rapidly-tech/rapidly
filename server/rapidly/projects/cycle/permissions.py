"""Auth dependencies for cycle routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_CyclesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_cycles_read,
        Scope.project_cycles_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectCyclesRead = Annotated[AuthPrincipal[User | Workspace], Depends(_CyclesRead)]

_CyclesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_cycles_write},
    allowed_subjects={User, Workspace},
)
ProjectCyclesWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_CyclesWrite)]
