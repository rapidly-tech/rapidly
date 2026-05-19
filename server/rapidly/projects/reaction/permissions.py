"""Auth dependencies for emoji-reaction routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_ReactionsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_reactions_read,
        Scope.work_item_reactions_write,
    },
    allowed_subjects={User, Workspace},
)
ReactionsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_ReactionsRead)]

# Write is user-only: adding/removing a reaction is a self-action.
# Workspace-scoped tokens don't have a User identity to attribute, so
# we don't allow them to react.
_ReactionsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_reactions_write},
    allowed_subjects={User},
)
ReactionsWrite = Annotated[AuthPrincipal[User], Depends(_ReactionsWrite)]
