"""Access control dependencies for webhook routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_WebhooksRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.webhooks_read,
        Scope.webhooks_write,
    },
    allowed_subjects={User, Workspace},
)
WebhooksRead = Annotated[AuthPrincipal[User | Workspace], Depends(_WebhooksRead)]

_WebhooksWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.webhooks_write,
    },
    allowed_subjects={User, Workspace},
)
WebhooksWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_WebhooksWrite)]
