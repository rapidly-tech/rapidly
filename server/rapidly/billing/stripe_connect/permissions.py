"""Access control dependencies for stripe connect routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_StripeConnectRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
    },
    allowed_subjects={User, Workspace},
)
StripeConnectRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_StripeConnectRead)
]
