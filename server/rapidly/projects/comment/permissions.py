"""Auth dependencies for work-item comment routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_CommentsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_comments_read,
        Scope.work_item_comments_write,
        Scope.work_items_read,
        Scope.work_items_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemCommentsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_CommentsRead)
]

_CommentsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_comments_write},
    allowed_subjects={User, Workspace},
)
WorkItemCommentsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_CommentsWrite)
]
