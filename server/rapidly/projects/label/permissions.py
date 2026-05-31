"""Auth dependencies for project label routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_LabelsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_labels_read,
        Scope.project_labels_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
ProjectLabelsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_LabelsRead)]

_LabelsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_labels_write},
    allowed_subjects={User, Workspace},
)
ProjectLabelsWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_LabelsWrite)]
