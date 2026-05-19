"""Auth dependencies for project saved-view routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_ViewsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_views_read,
        Scope.project_views_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectViewsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_ViewsRead)]

_ViewsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_views_write},
    allowed_subjects={User, Workspace},
)
ProjectViewsWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_ViewsWrite)]
