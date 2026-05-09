"""Access control dependencies for customer routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope
from rapidly.models.workspace import Workspace

_CustomerRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.customers_read,
        Scope.customers_write,
    },
    allowed_subjects={User, Workspace},
)
CustomerRead = Annotated[AuthPrincipal[User | Workspace], Depends(_CustomerRead)]

_CustomerWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.customers_write,
    },
    allowed_subjects={User, Workspace},
)
CustomerWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_CustomerWrite)]
