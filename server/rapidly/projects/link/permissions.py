"""Auth dependencies for work-item relation routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_RelationsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_relations_read,
        Scope.work_item_relations_write,
        Scope.work_items_read,
        Scope.work_items_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemRelationsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_RelationsRead)
]

_RelationsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_relations_write},
    allowed_subjects={User, Workspace},
)
WorkItemRelationsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_RelationsWrite)
]
