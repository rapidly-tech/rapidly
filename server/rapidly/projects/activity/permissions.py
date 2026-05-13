"""Auth dependencies for work-item activity routes (read-only)."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_ActivitiesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_activities_read,
        Scope.work_items_read,
        Scope.work_items_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemActivitiesRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_ActivitiesRead)
]
