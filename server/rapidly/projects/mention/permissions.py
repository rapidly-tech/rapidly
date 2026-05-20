"""Auth dependencies for work-item-mention routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_MentionsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_mentions_read,
        Scope.work_item_mentions_write,
    },
    allowed_subjects={User, Workspace},
)
MentionsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_MentionsRead)]

# Write is user-only: a mention is attributed to the calling user as
# the ``mentioned_by``. Workspace tokens have no User identity for
# attribution.
_MentionsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_mentions_write},
    allowed_subjects={User},
)
MentionsWrite = Annotated[AuthPrincipal[User], Depends(_MentionsWrite)]
