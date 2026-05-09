"""Authentication dependencies for custom field endpoints."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope
from rapidly.models.workspace import Workspace

_CustomFieldRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.custom_fields_read,
        Scope.custom_fields_write,
    },
    allowed_subjects={User, Workspace},
)
CustomFieldRead = Annotated[AuthPrincipal[User | Workspace], Depends(_CustomFieldRead)]

_CustomFieldWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.custom_fields_write,
    },
    allowed_subjects={User, Workspace},
)
CustomFieldWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_CustomFieldWrite)
]
