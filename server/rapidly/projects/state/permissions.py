"""Auth dependencies for project state routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_StatesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_states_read,
        Scope.project_states_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectStatesRead = Annotated[AuthPrincipal[User | Workspace], Depends(_StatesRead)]

_StatesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_states_write},
    allowed_subjects={User, Workspace},
)
ProjectStatesWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_StatesWrite)]
