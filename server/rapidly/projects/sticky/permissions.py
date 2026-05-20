"""Auth dependencies for sticky-note routes.

User-only on both sides: stickies are private notes — workspace
tokens have no User to attribute, and no other user (admin or not)
should ever see another user's stickies.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

_StickiesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.stickies_read,
        Scope.stickies_write,
    },
    allowed_subjects={User},
)
StickiesRead = Annotated[AuthPrincipal[User], Depends(_StickiesRead)]

_StickiesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.stickies_write},
    allowed_subjects={User},
)
StickiesWrite = Annotated[AuthPrincipal[User], Depends(_StickiesWrite)]
