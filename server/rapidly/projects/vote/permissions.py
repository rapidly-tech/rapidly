"""Auth dependencies for work-item vote routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

# Anyone with workspace read can see the aggregate vote rows.
_VotesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_votes_read,
        Scope.work_item_votes_write,
    },
    allowed_subjects={User, Workspace},
)
VotesRead = Annotated[AuthPrincipal[User | Workspace], Depends(_VotesRead)]

# Casting / retracting is a self-action — workspace tokens don't get
# to vote because they have no User identity to attribute.
_VotesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_votes_write},
    allowed_subjects={User},
)
VotesWrite = Annotated[AuthPrincipal[User], Depends(_VotesWrite)]
