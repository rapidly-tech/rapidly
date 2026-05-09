"""Auth dependencies for billing account endpoints."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

_AccountRead = Authenticator(
    allowed_subjects={User},
    required_scopes={Scope.web_read, Scope.web_write},
)
AccountRead = Annotated[AuthPrincipal[User], Depends(_AccountRead)]

_AccountWrite = Authenticator(
    allowed_subjects={User},
    required_scopes={Scope.web_write},
)
AccountWrite = Annotated[AuthPrincipal[User], Depends(_AccountWrite)]
