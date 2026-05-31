"""Auth dependencies for project routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_ProjectsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_ProjectsRead)]

_ProjectsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.projects_write},
    allowed_subjects={User, Workspace},
)
ProjectsWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_ProjectsWrite)]
