"""Auth dependencies for work-item routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_WorkItemsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_items_read,
        Scope.work_items_write,
        Scope.projects_read,
        Scope.projects_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_WorkItemsRead)]

_WorkItemsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_items_write},
    allowed_subjects={User, Workspace},
)
WorkItemsWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_WorkItemsWrite)]
