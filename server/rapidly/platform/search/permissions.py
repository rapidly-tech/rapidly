"""Access control dependencies for search routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

_SearchRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.shares_read,
        Scope.shares_write,
        Scope.customers_read,
        Scope.customers_write,
    },
    allowed_subjects={User},
)
SearchRead = Annotated[AuthPrincipal[User], Depends(_SearchRead)]
