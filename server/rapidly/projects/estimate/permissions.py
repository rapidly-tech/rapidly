"""Auth dependencies for project estimate routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_EstimatesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_estimates_read,
        Scope.project_estimates_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectEstimatesRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_EstimatesRead)
]

_EstimatesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_estimates_write},
    allowed_subjects={User, Workspace},
)
ProjectEstimatesWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_EstimatesWrite)
]
