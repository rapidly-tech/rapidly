"""Auth dependencies for module routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_ModulesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_modules_read,
        Scope.project_modules_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectModulesRead = Annotated[AuthPrincipal[User | Workspace], Depends(_ModulesRead)]

_ModulesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_modules_write},
    allowed_subjects={User, Workspace},
)
ProjectModulesWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_ModulesWrite)]
