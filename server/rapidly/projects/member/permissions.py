"""Auth dependencies for project-member routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_MembersRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_members_read,
        Scope.project_members_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectMembersRead = Annotated[AuthPrincipal[User | Workspace], Depends(_MembersRead)]

_MembersWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_members_write},
    allowed_subjects={User, Workspace},
)
ProjectMembersWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_MembersWrite)]
