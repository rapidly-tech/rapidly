"""Access control dependencies for payment routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope
from rapidly.models.workspace import Workspace

_PaymentRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.payments_read,
    },
    allowed_subjects={User, Workspace},
)
PaymentRead = Annotated[AuthPrincipal[User | Workspace], Depends(_PaymentRead)]
