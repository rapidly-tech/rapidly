"""Auth dependencies for work-item-type routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_TypesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_types_read,
        Scope.work_item_types_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemTypesRead = Annotated[AuthPrincipal[User | Workspace], Depends(_TypesRead)]

_TypesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_types_write},
    allowed_subjects={User, Workspace},
)
WorkItemTypesWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_TypesWrite)]
