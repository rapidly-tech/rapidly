"""Auth dependencies for analytic-view routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_AnalyticViewsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.analytic_views_read,
        Scope.analytic_views_write,
    },
    allowed_subjects={User, Workspace},
)
AnalyticViewsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_AnalyticViewsRead)
]

_AnalyticViewsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.analytic_views_write},
    allowed_subjects={User, Workspace},
)
AnalyticViewsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_AnalyticViewsWrite)
]
