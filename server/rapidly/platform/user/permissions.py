"""Access control dependencies for user routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

_UserWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.user_write,
    },
    allowed_subjects={User},
)
UserWrite = Annotated[AuthPrincipal[User], Depends(_UserWrite)]

_UserScopesRead = Authenticator(
    allowed_subjects={User},
)
UserScopesRead = Annotated[AuthPrincipal[User], Depends(_UserScopesRead)]
