"""Auth dependencies for project page routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_PagesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_pages_read,
        Scope.project_pages_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectPagesRead = Annotated[AuthPrincipal[User | Workspace], Depends(_PagesRead)]

_PagesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_pages_write},
    allowed_subjects={User, Workspace},
)
ProjectPagesWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_PagesWrite)]
