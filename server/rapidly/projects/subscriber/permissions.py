"""Auth dependencies for work-item subscriber routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_SubscribersRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_subscribers_read,
        Scope.work_item_subscribers_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemSubscribersRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_SubscribersRead)
]

# Subscribe/unsubscribe is a self-action — workspace-scoped tokens
# can't subscribe (they don't have a User to subscribe), so allow
# user subjects only on the write path.
_SubscribersWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_subscribers_write},
    allowed_subjects={User},
)
WorkItemSubscribersWrite = Annotated[AuthPrincipal[User], Depends(_SubscribersWrite)]
