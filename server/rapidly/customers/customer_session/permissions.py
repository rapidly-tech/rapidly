"""Access control dependencies for customer session routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope
from rapidly.models.workspace import Workspace

_CustomerSessionWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.customer_sessions_write,
    },
    allowed_subjects={User, Workspace},
)
CustomerSessionWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_CustomerSessionWrite)
]
